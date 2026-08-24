# packages/haywire-core/src/haywire/ui/surface/surface.py
"""Surface: a place Panels appear — a properties tab, a context menu, a
region within one, a flyout. See docs/adr/0029-surface-model.md.

Each Surface subclass declares:
  - id: ClassVar[str]                  — stable key (used for hot-reload
                                          supersede and registry lookup; see
                                          docs/adr/0009-surface-id-stable-key.md).
  - order: ClassVar[int]               — sort key for host listings.
  - presentation: ClassVar[Presentation | None] — chrome (label + icon) for
                                          hosts that draw a tab per surface;
                                          None for menu/toolbar surfaces.
  - provides: ClassVar[type | None]    — a runtime_checkable Protocol naming
                                          verbs the surface's host must
                                          implement; None means no contract.
  - poll(cls, ctx) -> bool             — classmethod, concrete, defaults to
                                          True. Overridden when a surface is
                                          only sometimes reachable.

The framework auto-builds an id -> class map at class-definition time via
__init_subclass__. Collisions raise ValueError immediately; a
same-module/same-qualname redeclaration (hot-reload) supersedes the prior
registration instead.

A Surface is never instantiated — subclasses are used as classes throughout,
purely as a namespace/metadata carrier queried by id.

There is no `parent` field and no surface-to-surface tree. Nesting is
declared by panels via `hosts=` and realised at render by `render_surface` —
both later-stage concerns, not part of this package.
"""

from __future__ import annotations

from abc import ABC
from typing import Any, ClassVar

from haywire.ui.surface.presentation import Presentation

# id -> Surface subclass map. Populated by Surface.__init_subclass__.
_SURFACE_BY_ID: dict[str, type["Surface"]] = {}


class Surface(ABC):
    """A place Panels appear. Never instantiated; queried by id."""

    id: ClassVar[str]
    order: ClassVar[int] = 100
    presentation: ClassVar[Presentation | None] = None
    provides: ClassVar[type | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        provides = cls.__dict__.get("provides")
        if provides is not None and not getattr(provides, "_is_runtime_protocol", False):
            raise TypeError(
                f"{cls.__module__}.{cls.__name__}.provides={provides!r} must be a "
                "typing.Protocol decorated with @runtime_checkable — host "
                "validation uses isinstance(), which raises TypeError against a "
                "plain Protocol."
            )

        # Skip subclasses that don't declare id (intermediate ABCs).
        if "id" not in cls.__dict__:
            return
        surface_id = cls.__dict__["id"]
        if surface_id in _SURFACE_BY_ID:
            existing = _SURFACE_BY_ID[surface_id]
            same_origin = existing.__module__ == cls.__module__ and existing.__qualname__ == cls.__qualname__
            if not same_origin:
                raise ValueError(
                    f"Surface id collision: {cls.__module__}.{cls.__name__} and "
                    f"{existing.__module__}.{existing.__name__} both declare id={surface_id!r}"
                )
            # Same module + qualname: this is a hot-reload re-declaring its own
            # class. The new class object supersedes the old in _SURFACE_BY_ID.
        _SURFACE_BY_ID[surface_id] = cls

    @classmethod
    def poll(cls, ctx: Any) -> bool:
        """Return whether this surface applies given current state.

        Concrete with a default of True (unlike Focus.available, which was
        an abstractmethod that read as None/false when merely called on the
        class rather than an instance). Override when a surface is only
        sometimes reachable.
        """
        return True
