# packages/haywire-core/src/haywire/ui/panel/panel.py
"""BasePanel — base class for panels.

BasePanel defines the panel contract:
  - poll(cls, ctx) -> bool: classmethod; default True. Host evaluates
    before instantiating the panel.
  - draw(self, ctx, layout) -> None: instance method; abstract. Host
    calls only when poll returned True.

Panels with an `actions:` annotation access the host via `self.actions`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from haywire.core.library.identity import LibraryIdentity

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.ui.panel.layout import PanelLayout
    from haywire.ui.panel.identity import PanelIdentity


class BasePanel(ABC):
    """Base class for panels.

    Subclasses are decorated with `@panel(...)` and inherit from `BasePanel`:

        .. code-block:: python
        @panel(
            actions=NodeContextActions,  # -> decorator  < ━┓
            focus=NodeFocus,                                ┃
            label="Delete Node"                             ┃
        )                                                   ┃
        class DeleteNodePanel(BasePanel):                   ┃
            actions: NodeContextActions  # -> annotation < ━┛

            def draw(self, ctx, layout):
                self.actions.delete_node(...)

    Panels with `actions` need to enter both the decorator and the annotation

    Panels with no `actions` just don't don't write them.
    """

    # Set by @panel decorator.
    class_identity: ClassVar["PanelIdentity"]
    class_library: ClassVar[LibraryIdentity]

    # Host instance injected at mount time when the panel declares an
    # ``actions:`` annotation whose Protocol the host satisfies. Display
    # panels (no annotation) leave it as None.
    actions: Any = None

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        """Return whether the panel should currently be visible."""
        return True

    @abstractmethod
    def draw(
        self,
        ctx: "SessionContext",
        layout: "PanelLayout",
    ) -> None:
        """Render the panel's content. Called only when poll returned True."""
