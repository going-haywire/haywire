import logging
import os
import time
import threading

from typing import Dict, Iterator, Set, Tuple, List, Optional

from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from watchdog.events import FileSystemEventHandler

from ..registry.base import HotReloadRegistry, FileChangeEvent, FileEventType
from .identity import LibraryIdentity

logger = logging.getLogger(__name__)

#: Directory names never walked when seeding _known_files. These hold no source
#: a registry could claim, and a library with a local virtualenv makes the
#: unfiltered walk cost real time on the enable path.
_UNWALKED_DIRS = frozenset({"__pycache__", ".venv", "venv", "node_modules", ".git", ".mypy_cache"})


def _walk_files(folder_path: str) -> Iterator[str]:
    """Yield every file under ``folder_path``, skipping :data:`_UNWALKED_DIRS`."""
    for dirpath, dirnames, filenames in os.walk(folder_path):
        # In place, so os.walk never descends into the pruned directories.
        dirnames[:] = [d for d in dirnames if d not in _UNWALKED_DIRS]
        for filename in filenames:
            yield os.path.join(dirpath, filename)


class LibraryFileHandler(FileSystemEventHandler):
    """Routes file system events to registries, by folder-to-registry mapping.

    Every non-directory event is routed to the registries whose folder path is
    a prefix of the file's, whatever the file's kind; a registry rejects what
    it does not care about itself (see ``BaseRegistry.event_dispatcher``). Each
    folder mapping carries its own library identity, so one handler serves
    several libraries.
    """

    def __init__(self):
        # folder_path -> (library_identity, registry, debounce_delay)
        self.folder_mappings: Dict[str, Tuple[LibraryIdentity, HotReloadRegistry, float]] = {}
        # library_root_path -> (library_identity, [registries], debounce_delay)
        # Fallback for files under the library root that don't match any
        # folder_mapping. Each registry decides via its own dependency graph
        # whether the changed file is relevant.
        self.root_fallbacks: Dict[str, Tuple[LibraryIdentity, List[HotReloadRegistry], float]] = {}
        # (file_path, registry_id) -> FileChangeEvent
        self.pending_events: Dict[Tuple[str, int], FileChangeEvent] = {}
        # (file_path, registry_id) -> timer
        self.debounce_timers: Dict[Tuple[str, int], threading.Timer] = {}
        # file_path -> expiry timestamp: suppresses DELETED for a file just
        # promoted by an atomic write (tmp → py), for which the OS may deliver
        # a spurious DELETE after the move event.
        self._atomic_write_suppress: Dict[str, float] = {}
        # Files known to exist on disk — seeded when a folder mapping is added
        # and maintained as CREATE/DELETE events flow through. Downgrades a
        # spurious CREATE (from an atomic write) to MODIFIED.
        self._known_files: Set[str] = set()
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
            # Seed from disk, so an atomic-write CREATE for a pre-existing file
            # is downgraded to MODIFIED.
            self._known_files.update(_walk_files(folder_path))

    def remove_folder_mapping(self, folder_path: str):
        """Unregister a folder path"""
        with self._lock:
            if folder_path in self.folder_mappings:
                del self.folder_mappings[folder_path]

    def add_root_fallback(
        self,
        root_path: str,
        library_identity: LibraryIdentity,
        registries: List[HotReloadRegistry],
        debounce_delay: float = 0.5,
    ):
        """Register a library root as a fallback for files not covered by any folder_mapping.

        A file under the root but under no folder mapping is dispatched to
        every given registry as a dependency event; each registry decides from
        its own dependency graph whether the file is relevant.
        """
        with self._lock:
            self.root_fallbacks[root_path] = (library_identity, list(registries), debounce_delay)

    def remove_root_fallback(self, root_path: str):
        """Unregister a library-root fallback"""
        with self._lock:
            if root_path in self.root_fallbacks:
                del self.root_fallbacks[root_path]

    def _get_matching_registries(
        self, file_path: str
    ) -> List[Tuple[LibraryIdentity, HotReloadRegistry, float, bool]]:
        """Find all registries that should receive events for this file.

        Returns:
            ``(library_identity, registry, debounce_delay, is_dependency)``
            tuples. ``is_dependency`` is True for root-fallback matches, which
            the registry treats as a dependency change. A folder mapping
            shadows the fallbacks: when any matches, no fallback is consulted.
        """
        matches: List[Tuple[LibraryIdentity, HotReloadRegistry, float, bool]] = []
        for folder_path, mapping in self.folder_mappings.items():
            if file_path.startswith(folder_path):
                library_identity, registry, debounce_delay = mapping
                matches.append((library_identity, registry, debounce_delay, False))

        if matches:
            return matches

        for root_path, fallback in self.root_fallbacks.items():
            if file_path.startswith(root_path):
                library_identity, registries, debounce_delay = fallback
                for registry in registries:
                    matches.append((library_identity, registry, debounce_delay, True))
        return matches

    def on_modified(self, event):
        if event.is_directory:
            return
        with self._lock:
            self._known_files.add(event.src_path)
        self._handle_file_change(event.src_path, FileEventType.MODIFIED)

    def on_created(self, event):
        if event.is_directory:
            return
        with self._lock:
            already_known = event.src_path in self._known_files
            self._known_files.add(event.src_path)
        if already_known:
            # The file already existed, so this CREATE is an overwrite.
            logger.debug(f"FileWatcher: downgrading CREATE to MODIFIED for known file: {event.src_path}")
            self._handle_file_change(event.src_path, FileEventType.MODIFIED)
        else:
            self._handle_file_change(event.src_path, FileEventType.CREATED)

    def on_deleted(self, event):
        if event.is_directory:
            return
        with self._lock:
            expiry = self._atomic_write_suppress.get(event.src_path, 0)
            if time.time() < expiry:
                logger.info(
                    f"FileWatcher: suppressing spurious DELETE for atomic-written file: {event.src_path}"
                )
                return
        with self._lock:
            self._known_files.discard(event.src_path)
        self._handle_file_change(event.src_path, FileEventType.DELETED)

    def on_moved(self, event):
        """Handle file moves within the watched directory.

        A true rename (foo.py → bar.py) is dispatched as DELETED on the source
        plus CREATED on the destination. An atomic write (foo.py.tmp → foo.py)
        is dispatched as MODIFIED on the destination, and suppresses a spurious
        DELETE for it for the next two seconds.

        The two are told apart by whether the move lands on a file already in
        ``_known_files``: a rename gives a file a new name, so the destination
        did not exist; an atomic write promotes a scratch file over a target
        that did. The source being tracked is not enough to tell them apart —
        a temp file written inside the watched folder is tracked by its own
        CREATE.
        """
        if event.is_directory:
            return

        logger.info(f"File moved: {event.src_path} → {event.dest_path}")

        with self._lock:
            src_was_tracked = event.src_path in self._known_files
            dest_existed = event.dest_path in self._known_files

        if src_was_tracked and not dest_existed:
            # True rename: a file we knew about moved to a new name.
            with self._lock:
                self._known_files.discard(event.src_path)
                self._known_files.add(event.dest_path)
            self._handle_file_change(event.src_path, FileEventType.DELETED)
            self._handle_file_change(event.dest_path, FileEventType.CREATED)
        else:
            # Atomic write. The suppression window covers the spurious DELETE
            # the OS may deliver for dest_path after this move (macOS/kqueue).
            # The source path is dropped: it is gone from disk, and a stale
            # entry would be reused by the next save.
            with self._lock:
                self._known_files.discard(event.src_path)
                self._known_files.add(event.dest_path)
                self._atomic_write_suppress[event.dest_path] = time.time() + 2.0
            self._handle_file_change(event.dest_path, FileEventType.MODIFIED)

    def _handle_file_change(self, file_path: str, event_type: FileEventType):
        """Handle file change with per-registry debouncing.

        Each matching registry gets its own debounced event stream, carrying
        that folder's library identity; only the latest event per file and
        registry survives the debounce window.
        """
        matching_registries = self._get_matching_registries(file_path)

        if not matching_registries:
            return  # File not in any watched folder

        with self._lock:
            for library_identity, registry, debounce_delay, is_dependency in matching_registries:
                registry_id = id(registry)
                event_key = (file_path, registry_id)

                if event_key in self.debounce_timers:
                    self.debounce_timers[event_key].cancel()

                event = FileChangeEvent(
                    file_path=file_path,
                    event_type=event_type,
                    library_identity=library_identity,
                    timestamp=time.time(),
                    dependency_event=is_dependency,
                )

                self.pending_events[event_key] = event

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
            self._known_files.clear()
            self.root_fallbacks.clear()


class FileWatcher:
    """Manages a single file observer that can watch multiple libraries.

    One Observer per root path, watching recursively; folder-to-registry
    routing (including library identity) is the handler's job, so one watcher
    serves every library under that root.
    """

    def __init__(self, watch_path: str):
        """Initialize file watcher for a root path.

        Args:
            watch_path: Root path to watch recursively — a library root, or a
                parent folder containing several libraries.
        """
        self.watch_path = watch_path
        self.observer: Optional[BaseObserver] = None
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
        """Register a folder to be routed to a specific registry.

        Args:
            debounce_delay: Seconds of quiet before a file's change is
                dispatched.
        """
        self.handler.add_folder_mapping(folder_path, library_identity, registry, debounce_delay)

        rel_path = folder_path[len(self.watch_path) :] or "/"
        logger.info(
            f"Library '{library_identity.label}': Registered folder '{rel_path}' for hot reload events."
        )

    def remove_watch(self, folder_path: str, library_identity: LibraryIdentity):
        """Unregister a folder from routing.

        Args:
            library_identity: Used for logging only.
        """
        self.handler.remove_folder_mapping(folder_path)

        rel_path = folder_path[len(self.watch_path) :] or "/"
        logger.info(
            f"Library '{library_identity.label}': Unregistered folder '{rel_path}' from hot reload events."
        )

    def add_root_fallback(
        self,
        root_path: str,
        library_identity: LibraryIdentity,
        registries: List[HotReloadRegistry],
        debounce_delay: float = 0.5,
    ):
        """Register a library-root fallback for files outside every watched folder.

        Such a file still triggers a dependency reload when a registry's
        dependency graph knows it.
        """
        self.handler.add_root_fallback(root_path, library_identity, registries, debounce_delay)
        logger.info(
            f"Library '{library_identity.label}': Registered root fallback "
            f"with {len(registries)} registries for hot reload dependency events."
        )

    def remove_root_fallback(self, root_path: str, library_identity: LibraryIdentity):
        """Unregister a library-root fallback"""
        self.handler.remove_root_fallback(root_path)
        logger.info(
            f"Library '{library_identity.label}': Unregistered root fallback from hot reload events."
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
