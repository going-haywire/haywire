import logging
import time
import threading

logger = logging.getLogger(__name__)
from typing import Dict, Set, Tuple, List, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ..registry.base import HotReloadRegistry, FileChangeEvent, FileEventType
from .identity import LibraryIdentity


class LibraryFileHandler(FileSystemEventHandler):
    """
    Handles file system events with multiple folder-to-registry mappings.

    Library-agnostic handler that routes file events to appropriate registries
    based on folder path matching. Each folder mapping includes its own
    library identity, allowing one handler to serve multiple libraries.
    """

    def __init__(self):
        # folder_path -> (library_identity, registry, debounce_delay)
        self.folder_mappings: Dict[str, Tuple[LibraryIdentity, HotReloadRegistry, float]] = {}
        # (file_path, registry_id) -> FileChangeEvent
        self.pending_events: Dict[Tuple[str, int], FileChangeEvent] = {}
        # (file_path, registry_id) -> timer
        self.debounce_timers: Dict[Tuple[str, int], threading.Timer] = {}
        # file_path -> expiry timestamp: suppress DELETED events for files recently
        # promoted via atomic write (tmp → py), since the OS may deliver a spurious
        # DELETE for the destination file after the move event.
        self._atomic_write_suppress: Dict[str, float] = {}
        self._lock = threading.Lock()

    def add_folder_mapping(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        registry: HotReloadRegistry,
        debounce_delay: float = 0.5,
    ):
        """Register a folder path to be routed to a specific registry"""
        with self._lock:
            self.folder_mappings[folder_path] = (library_identity, registry, debounce_delay)

    def remove_folder_mapping(self, folder_path: str):
        """Unregister a folder path"""
        with self._lock:
            if folder_path in self.folder_mappings:
                del self.folder_mappings[folder_path]

    def _get_matching_registries(
        self, file_path: str
    ) -> List[Tuple[LibraryIdentity, HotReloadRegistry, float]]:
        """
        Find all registries that should receive events for this file.

        Returns:
            List of (library_identity, registry, debounce_delay) tuples
            for matching folders
        """
        matches = []
        for folder_path, mapping in self.folder_mappings.items():
            if file_path.startswith(folder_path):
                library_identity, registry, debounce_delay = mapping
                matches.append((library_identity, registry, debounce_delay))
        return matches

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".py"):
            self._handle_file_change(event.src_path, FileEventType.MODIFIED)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".py"):
            self._handle_file_change(event.src_path, FileEventType.CREATED)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith(".py"):
            with self._lock:
                expiry = self._atomic_write_suppress.get(event.src_path, 0)
                if time.time() < expiry:
                    logger.info(
                        f"FileWatcher: suppressing spurious DELETE for atomic-written file: {event.src_path}"
                    )
                    return
            self._handle_file_change(event.src_path, FileEventType.DELETED)

    def on_moved(self, event):
        """
        Handle file moves within the watched directory.

        A true rename (foo.py → bar.py) is treated as DELETED + CREATED.
        An atomic write (foo.py.tmp → foo.py) is treated as MODIFIED — the
        source was a temp file, not a tracked Python module. This also
        cancels any pending DELETED event for the destination file that may
        have been queued when the editor truncated/replaced the original.

        Args:
            event: FileMovedEvent with src_path and dest_path
        """
        if not event.is_directory:
            src_is_py = event.src_path.endswith(".py")
            dest_is_py = event.dest_path.endswith(".py")

            if src_is_py or dest_is_py:
                logger.info(f"File moved: {event.src_path} → {event.dest_path}")

            if src_is_py and dest_is_py:
                # True rename: foo.py → bar.py
                self._handle_file_change(event.src_path, FileEventType.DELETED)
                self._handle_file_change(event.dest_path, FileEventType.CREATED)
            elif dest_is_py and not src_is_py:
                # Atomic write: tmp file promoted to .py — treat as modification.
                # Suppress any spurious DELETE that the OS may deliver for dest_path
                # after this move event (observed on macOS/kqueue).
                with self._lock:
                    self._atomic_write_suppress[event.dest_path] = time.time() + 2.0
                self._handle_file_change(event.dest_path, FileEventType.MODIFIED)

    def _handle_file_change(self, file_path: str, event_type: FileEventType):
        """
        Handle file change with per-registry debouncing.

        Routes events to all matching registries based on folder mappings.
        Each registry gets its own debounced event stream with the
        appropriate library_identity.
        """
        matching_registries = self._get_matching_registries(file_path)

        if not matching_registries:
            return  # File not in any watched folder

        with self._lock:
            for library_identity, registry, debounce_delay in matching_registries:
                registry_id = id(registry)
                event_key = (file_path, registry_id)

                # Cancel existing timer for this file+registry combination
                if event_key in self.debounce_timers:
                    self.debounce_timers[event_key].cancel()

                # Create new event with the folder's library_identity
                event = FileChangeEvent(
                    file_path=file_path,
                    event_type=event_type,
                    library_identity=library_identity,
                    timestamp=time.time(),
                )

                # Store latest event for this registry
                self.pending_events[event_key] = event

                # Set up debounce timer
                timer = threading.Timer(
                    debounce_delay, self._process_debounced_event, args=[event_key, registry]
                )
                self.debounce_timers[event_key] = timer
                timer.start()

    def _process_debounced_event(self, event_key: Tuple[str, int], registry: HotReloadRegistry):
        """Process the event after debounce delay"""
        with self._lock:
            if event_key not in self.pending_events:
                return

            event = self.pending_events[event_key]
            del self.pending_events[event_key]

            if event_key in self.debounce_timers:
                del self.debounce_timers[event_key]

        registry.event_dispatcher(event)

    def cleanup(self):
        """Clean up pending timers"""
        with self._lock:
            for timer in self.debounce_timers.values():
                timer.cancel()
            self.debounce_timers.clear()
            self.pending_events.clear()
            self._atomic_write_suppress.clear()


class FileWatcher:
    """
    Manages a single file observer that can watch multiple libraries.

    Library-agnostic watcher that creates one Observer for a root path,
    with folder-to-registry routing (including library identity) handled
    by the handler. This design allows the FileWatcher to be shared across
    multiple libraries, reducing the number of observer threads.
    """

    def __init__(self, watch_path: str):
        """
        Initialize file watcher for a root path.

        Args:
            watch_path: Root path to watch recursively (e.g., library root
                       or parent folder containing multiple libraries)
        """
        self.watch_path = watch_path
        self.observer: Optional[Observer] = None
        self.handler: LibraryFileHandler = LibraryFileHandler()
        self._lock = threading.Lock()
        self._is_started = False

    def add_watch(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        registry: HotReloadRegistry,
        debounce_delay: float = 0.5,
    ):
        """
        Register a folder to be routed to a specific registry.

        Args:
            folder_path: Path to folder whose files should route to this registry
            library_identity: Identity of the library this folder belongs to
            registry: Registry that will receive file change events
            debounce_delay: Delay in seconds before processing file changes
        """
        self.handler.add_folder_mapping(folder_path, library_identity, registry, debounce_delay)

        rel_path = folder_path[len(self.watch_path) :] or "/"
        logger.info(
            f"Library '{library_identity.label}': Registered folder '{rel_path}' for hot reload events."
        )

    def remove_watch(self, folder_path: str, library_identity: LibraryIdentity):
        """
        Unregister a folder from routing.

        Args:
            folder_path: Path to folder to stop routing
            library_identity: Identity of the library (for logging)
        """
        self.handler.remove_folder_mapping(folder_path)

        rel_path = folder_path[len(self.watch_path) :] or "/"
        logger.info(
            f"Library '{library_identity.label}': Unregistered folder '{rel_path}' from hot reload events."
        )

    def start(self):
        """Start the observer if not already started"""
        with self._lock:
            if not self._is_started:
                self.observer = Observer()
                self.observer.schedule(self.handler, self.watch_path, recursive=True)
                self.observer.start()
                self._is_started = True
                logger.info(f"FileWatcher: Started watching {self.watch_path}")

    def stop(self):
        """Stop the observer and clean up"""
        with self._lock:
            if self._is_started and self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None
                self._is_started = False
                self.handler.cleanup()
                logger.info(f"FileWatcher: Stopped watching {self.watch_path}")

    def is_watching(self, folder_path: str) -> bool:
        """Check if a folder is currently registered for routing"""
        return folder_path in self.handler.folder_mappings

    def get_watched_folders(self) -> Set[str]:
        """Get all currently registered folder paths"""
        return set(self.handler.folder_mappings.keys())

    def is_started(self) -> bool:
        """Check if the observer is currently running"""
        return self._is_started
