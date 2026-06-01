# packages/haywire-core/src/haywire/ui/panel/panel.py
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

    Subclasses are decorated with `@panel(...)` and inherit from `BasePanel`::

        @panel(
            actions=NodeContextActions,  # -> decorator
            focus=NodeFocus,
            label="Delete Node",
        )
        class DeleteNodePanel(BasePanel):
            actions: NodeContextActions  # -> annotation

            def draw(self, ctx, layout):
                self.actions.delete_node(...)

    Panels with `actions` enter it in both the decorator and the annotation;
    panels with no `actions` omit it.
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
