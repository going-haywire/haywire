"""ShareEditor — the project's publishing status, and the way into the flow.

Status-only by design. Listing barn libraries as *navigation* — click one, see
its details — would mean opening haybale-marketplace's editors, which would
make this library depend on the marketplace and duplicate its library browser
besides. Everything shown here is publishing-relevant and none of it is
available from that browser.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.core.signals import LibraryCatalogChanged
from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName

if TYPE_CHECKING:
    from nicegui.element import Element

    from haywire.core.session.context import SessionContext


@editor(
    label="Share",
    icon=hui.icon.promote,
    default_slot=SlotName.ACTION,
    description="Publish this project: dependencies, version, docs, commit, tag, push.",
)
class ShareEditor(BaseEditor):
    """Project publishing status plus the button that opens the Share flow."""

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self._body: Optional[ui.column] = None
        self._context: Optional["SessionContext"] = None

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._context = context
        with container:
            with ui.column().classes("w-full h-full gap-0"):
                with hui.slot_header("Share", icon=hui.icon.promote):
                    hui.icon_action(hui.icon.refresh, tooltip="Refresh", on_click=self._redraw)
                with ui.scroll_area().classes("flex-1 w-full"):
                    self._body = ui.column().classes("w-full gap-2 p-2")
        self._render_body()

    def _redraw(self) -> None:
        if self._body is None:
            return
        self._body.clear()
        self._render_body()

    def _workspace_root(self) -> Path | None:
        context = self._context
        root = getattr(context.app, "workspace_root", None) if context else None
        return Path(root) if root else None

    def _render_body(self) -> None:
        if self._body is None:
            return
        root = self._workspace_root()
        with self._body:
            if root is None:
                hui.hint("No project open.")
                hui.hint(
                    "Share publishes a haywire project directory — the workspace root "
                    "holding barn/ and marketstall.toml."
                )
                return

            from haybale_share._flow._state import ShareFlow

            status = ShareFlow.project_status(root)
            libraries = status.libraries

            hui.heading(root.name)
            hui.hint(str(root)).classes("font-mono")

            version = status.version
            if status.disagree:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("warning", size="14px").style("color: var(--hw-warning);")
                    hui.hint("Library versions disagree — the flow will ask for a target.")
            elif version:
                hui.hint(f"Version {version} — every library in lockstep")

            if not libraries:
                hui.hint("No library under barn/ — nothing to publish yet.")
                return

            hui.section_label(f"{len(libraries)} librar{'y' if len(libraries) == 1 else 'ies'}")
            with hui.indented().classes("w-full"):
                for name in libraries:
                    hui.hint(name).classes("font-mono")

            with hui.action_row().classes("pt-2"):
                ui.button("Share…", on_click=self._open_flow).props("flat dense").style(
                    "color: var(--hw-positive);"
                )

    def _open_flow(self) -> None:
        root = self._workspace_root()
        if root is None:
            ui.notify("No project open.", type="warning")
            return
        from haybale_share._flow.chrome import show_share_flow

        # Redraw on close: a completed publish changes the version this editor
        # displays, and a bumped registry may have changed the library list.
        show_share_flow(root, on_done=self._on_flow_done)

    def _on_flow_done(self) -> None:
        """Redraw this editor, then tell every other catalog view to redraw too."""
        self._redraw()
        context = self._context
        session = context.session if context is not None else None
        if session is not None:
            session.publish(LibraryCatalogChanged())
