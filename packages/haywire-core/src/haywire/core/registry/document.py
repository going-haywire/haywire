"""Components backed by files rather than Python modules.

``DocumentRegistry`` registers every file of one suffix under a claimed
folder, parsing each into an element that satisfies ``RegisteredClass``. File
events map onto the same lifecycle a class registry emits, so a consumer
subscribed to component changes cannot tell the two apart.
"""

from typing import ClassVar, Dict, Optional, cast
from abc import abstractmethod
import hashlib
import logging
from pathlib import Path

from ..errors import HaywireException
from ..library.identity import LibraryIdentity
from .component import ComponentRegistry
from .events import FileChangeEvent, FileEventType, T
from .lifecycle_event import LifeCycleEvent, LifeCycleEventType

logger = logging.getLogger(__name__)


class DocumentRegistry(ComponentRegistry[T]):
    """A registry whose elements are parsed documents.

    A subclass sets :attr:`SUFFIX` and implements :meth:`_parse` and
    :meth:`_document_key`. Content is hashed on every load, so a save that
    does not change the bytes notifies nobody.

    Elements are instances, not classes. ``ComponentRegistry`` types its map
    as ``type[T]`` because a class registry stores classes; consumers read
    only ``class_identity`` and ``class_library`` off the result, which a
    document element provides too. :meth:`_store` carries that one cast.
    """

    #: File suffix this registry claims, including the dot.
    SUFFIX: ClassVar[str] = ""

    def __init__(self):
        super().__init__()

        # registry_key -> sha256 of the text last parsed successfully
        self._hashes: Dict[str, str] = {}
        # registry_key -> the file it came from
        self._key_to_path: Dict[str, Path] = {}

    @abstractmethod
    def _parse(self, path: Path, text: str, library_identity: LibraryIdentity) -> T:
        """Return the element ``text`` describes.

        Raises:
            Exception: Any failure is reported as ``CLASS_RELOAD_FAILED``
                against this document's key, leaving the previous element
                registered.
        """
        pass

    @abstractmethod
    def _document_key(self, path: Path, library_identity: LibraryIdentity) -> str:
        """Return the registry key ``path`` registers under."""
        pass

    def _store(self, registry_key: str, element: T) -> None:
        """Put an element in the map under the class-registry's ``type[T]`` typing."""
        self._classes[registry_key] = cast("type[T]", element)

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _claims(self, file_path: str) -> bool:
        """Whether this registry handles ``file_path``.

        The watcher routes every file under a claimed folder, so deciding
        which suffix matters is the registry's own business — the same split
        ``BaseRegistry`` makes for ``.py``.
        """
        return bool(self.SUFFIX) and file_path.endswith(self.SUFFIX)

    # ============================================================================
    # Folder registration
    # ============================================================================

    def add_folder(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """Register every ``SUFFIX`` file directly inside ``folder_path``."""
        if folder_path in self._folder_to_library:
            logger.warning(
                f"Library '{library_identity.label}': Folder '{folder_path}' is already "
                f"registered in registry '{self.__class__.__name__}'. Skipping."
            )
            return

        self._folder_to_library[folder_path] = library_identity

        for path in sorted(Path(folder_path).glob(f"*{self.SUFFIX}")):
            self.register_file(str(path), library_identity, notify=False)

        self._notify_batch_event_subscribers()

    def remove_folder(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """Unregister everything ``folder_path`` contributed."""
        self._folder_to_library.pop(folder_path, None)

        root = Path(folder_path)
        for key, path in list(self._key_to_path.items()):
            if root in path.parents:
                self._forget(key)
                self._queue_lifecycle_event(
                    self._lifecycle(key, LifeCycleEventType.CLASS_REMOVED, library_identity)
                )

        self._notify_batch_event_subscribers()

    def register_file(
        self,
        file_path: str,
        library_identity: LibraryIdentity,
        notify: bool = True,
    ) -> str | None:
        """Parse and register one document, returning its key.

        Synchronous, so a caller that has just written a file sees the
        component immediately rather than waiting for the watcher.

        Args:
            notify: Whether to flush the lifecycle queue to batch subscribers.
                Pass ``False`` when registering many files in one pass.

        Returns:
            The registry key, or ``None`` if the document was refused.
        """
        path = Path(file_path)
        key = self._document_key(path, library_identity)
        try:
            text = path.read_text(encoding="utf-8")
            element = self._parse(path, text, library_identity)
        except Exception as e:
            self._report_failure(key, e, library_identity, notify=notify)
            return None

        existed = self.has(key)
        if existed:
            # A duplicate stem within one library is an authoring error, not a
            # reload: the second file would shadow the first with no way to
            # tell them apart.
            if self._key_to_path.get(key) != path:
                raise ValueError(
                    f"Library '{library_identity.label}': two documents claim the key '{key}' "
                    f"('{self._key_to_path.get(key)}' and '{path}')."
                )

        self._store(key, element)
        self._hashes[key] = self._hash(text)
        self._key_to_path[key] = path

        self._queue_lifecycle_event(
            self._lifecycle(
                key,
                LifeCycleEventType.CLASS_RELOADED if existed else LifeCycleEventType.CLASS_ADDED,
                library_identity,
            )
        )
        if notify:
            self._notify_batch_event_subscribers()
        return key

    # ============================================================================
    # Hot-Reload
    # ============================================================================

    def event_dispatcher(self, event: FileChangeEvent):
        """Route one file change onto the component lifecycle."""
        if not self._claims(event.file_path):
            return None

        path = Path(event.file_path)
        library_identity = event.library_identity
        key = self._document_key(path, library_identity)

        logger.info(
            f"Library '{library_identity.label}': Registry '{self.__class__.__name__}': "
            f"DETECTED Hot Reloading event: file-'{event.event_type.value}' "
            f"on file: {path.name}. INITIATING ..."
        )

        if event.event_type == FileEventType.DELETED:
            if self.has(key):
                self._forget(key)
                self._queue_lifecycle_event(
                    self._lifecycle(key, LifeCycleEventType.CLASS_REMOVED, library_identity)
                )
                self._notify_batch_event_subscribers()
            return None

        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            self._report_failure(key, e, library_identity)
            return None

        if self.has(key) and self._hashes.get(key) == self._hash(text):
            # An atomic save rewrites the file whether or not anything changed.
            return None

        self.register_file(str(path), library_identity)
        return None

    # ============================================================================
    # Internals
    # ============================================================================

    def _forget(self, registry_key: str) -> None:
        self._classes.pop(registry_key, None)
        self._hashes.pop(registry_key, None)
        self._key_to_path.pop(registry_key, None)

    def _lifecycle(
        self,
        registry_key: str,
        event_type: LifeCycleEventType,
        library_identity: LibraryIdentity,
        error: Optional[HaywireException] = None,
    ) -> LifeCycleEvent:
        return LifeCycleEvent(
            registry_key=registry_key,
            event_type=event_type,
            affected_class=self.get(registry_key),
            library_identity=library_identity,
            error=error,
        )

    def _report_failure(
        self,
        registry_key: str,
        exception: Exception,
        library_identity: LibraryIdentity,
        notify: bool = True,
    ) -> None:
        """Queue a reload failure, keeping any previously parsed document registered."""
        error = HaywireException.from_exception(
            exception=exception,
            operation="Document registry load",
            message=(f"Failed loading document '{registry_key}' in library '{library_identity.label}'"),
        ).enrich(registry_key=registry_key, library_identity=library_identity)
        error.log(self.logger)

        self._queue_lifecycle_event(
            self._lifecycle(registry_key, LifeCycleEventType.CLASS_RELOAD_FAILED, library_identity, error)
        )
        if notify:
            self._notify_batch_event_subscribers()
