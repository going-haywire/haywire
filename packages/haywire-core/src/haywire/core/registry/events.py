"""File-change vocabulary and the structural bounds every registry shares.

Separate from ``base`` so a registry module may depend on this vocabulary
without importing the module-reload machinery.
"""

from typing import Protocol, TypeVar
from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dc_field
from enum import Enum

from ..library.identity import LibraryIdentity
from .identity import BaseIdentity


class FileEventType(Enum):
    """Enum for file change event types"""

    CREATED = "creation"
    MODIFIED = "modification"
    DELETED = "deletion"
    DETECTED = "detection"


@dataclass
class FileChangeEvent:
    """Represents a file change event"""

    file_path: str
    event_type: FileEventType  # 'created', 'modified', 'deleted', 'detected'
    library_identity: LibraryIdentity
    timestamp: float
    reloaded_modules: set[str] = dc_field(default_factory=set)
    """Track modules already reloaded in this event chain"""
    dependency_event: bool = False  # Whether this event is due to dependency reload
    """indicates if this event is a result of a dependency change (detected by a different registry)"""


class HotReloadRegistry(ABC):
    """Abstract base class for registries that support hot-reloading"""

    @abstractmethod
    def event_dispatcher(self, event: FileChangeEvent):
        """Handle creation of a module"""
        pass


class RegisteredClass(Protocol):
    """Structural bound for registry element types.

    The registry contract: every managed class carries both a
    ``class_identity`` (its registry metadata) and a ``class_library`` (the
    owning library, used for hot-reload) — set by its component decorator.

    Both are typed as read-only properties so concrete element classes may
    declare them as ``ClassVar`` of narrower subtypes (``NodeIdentity``,
    ``AdapterIdentity``, ...). A writable Protocol member (plain annotation
    or ``ClassVar``) would be invariant and reject them.
    """

    @property
    def class_identity(self) -> BaseIdentity: ...

    @property
    def class_library(self) -> LibraryIdentity: ...


T = TypeVar("T", bound=RegisteredClass)
