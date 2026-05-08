# packages/haywire-core/src/haywire/ui/panel/panel.py
"""BasePanel — the new contract base class.

Phase 1 contract:
  - poll(cls, ctx) -> bool: classmethod; default True. Host evaluates
    before instantiating the panel.
  - draw(self, ctx, layout, actions) -> None: instance method; abstract.
    Host calls only when poll returned True.

Phase 2 promotes poll to an instance method, adds @reads, and wraps
both methods in Subscriptions. Panels written for Phase 1 migrate
mechanically to Phase 2 (drop @classmethod, change cls -> self).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.panel.layout import PanelLayout
    from haywire.ui.panel.identity import PanelIdentity


class BasePanel(ABC):
    """Base class for new-contract panels.

    Subclasses are decorated with `@panel(...)` and inherit from `BasePanel`:

        @panel(action=MyEditorActions, focus=MyFocus, label="My Panel")
        class MyPanel(BasePanel):
            @classmethod
            def poll(cls, ctx: SessionContext) -> bool:
                # Library-defined SessionState read; the field set lives in
                # the library's SessionState subclass, not on SessionContext.
                return ctx.data[MyLibState].active_item.value is not None

            def draw(self, ctx, layout, actions):
                ...
    """

    # Set by @panel decorator.
    class_identity: ClassVar["PanelIdentity"]

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        """Return whether the panel should currently be visible.

        Default: True (always visible). Override when visibility depends
        on session state.

        Phase 1: classmethod (host calls before instantiation).
        Phase 2: instance method (wrapped in Subscription).
        """
        return True

    @abstractmethod
    def draw(
        self,
        ctx: "SessionContext",
        layout: "PanelLayout",
        actions: Any,
    ) -> None:
        """Render the panel's content.

        Called only when poll returned True. The panel renders into
        `layout`'s container. `actions` is the host's actions object,
        typed against the panel's declared `action=` Protocol.
        """
