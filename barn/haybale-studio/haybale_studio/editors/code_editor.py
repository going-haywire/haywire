"""
CodeEditor — text/code editor for source-like files.

Smoke test for the close-consent + dirty-flag work: edits a text file in a
CodeMirror-backed editor with syntax highlighting derived from the file's
extension. Markdown files additionally get a Preview tab. Sets
``wrapper.set_dirty(True)`` on every keystroke and back to False after a
successful save, so the tab bar shows a leading "•" while there are
unsaved changes. Overrides ``handle_close_request`` to prompt the user
when closing a dirty tab.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.context_signals import ThemeMoved
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_signals import ContextSignal
    from nicegui.element import Element


# Map file extension → CodeMirror language string. None means "no language
# extension" (plain text). Extensions not present here are not opened by the
# code editor — they fall through to FileViewerEditor.
CmLanguage = Literal[
    "Markdown",
    "Python",
    "JSON",
    "TOML",
    "YAML",
    "JavaScript",
    "TypeScript",
    "CSS",
    "HTML",
    "XML",
    "Shell",
]
CmTheme = Literal["vscodeLight", "vscodeDark"]

_LANGUAGE_BY_EXT: dict[str, Optional[CmLanguage]] = {
    ".md": "Markdown",
    ".py": "Python",
    ".json": "JSON",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".css": "CSS",
    ".html": "HTML",
    ".xml": "XML",
    ".sh": "Shell",
    ".txt": None,
}

EDITABLE_EXTS = frozenset(_LANGUAGE_BY_EXT.keys())


@editor(
    label="Code Editor",
    icon="code",
    default_slot="main",
    opens="on_payload",
    description=(
        "Text/code editor with syntax highlighting (Markdown, Python, JSON, TOML,"
        " YAML, JS/TS, CSS/HTML/XML, Shell, plain text). Markdown files have a"
        " Preview tab. Save and Save As supported."
    ),
)
class CodeEditor(BaseEditor):
    """Tiny text/code editor with optional Markdown preview."""

    def __init__(self):
        self._content: str = ""
        self._original: str = ""
        self._mode: str = "edit"  # "edit" | "preview" (preview only for .md)
        self._editor: Optional[ui.codemirror] = None
        self._preview: Optional[ui.markdown] = None
        self._tab_panels = None  # ui.tab_panels (only present when .md)
        self._mode_button: Optional[ui.button] = None
        self._save_button: Optional[ui.button] = None
        self._path_label: Optional[ui.label] = None
        self._save_as_dialog: Optional[ui.dialog] = None
        self._save_as_input: Optional[ui.input] = None
        self._save_as_warning: Optional[ui.label] = None

    # ------------------------------------------------------------------
    # identity / payload
    # ------------------------------------------------------------------

    def _resolve_path(self) -> Optional[Path]:
        if self.wrapper is None or self.wrapper.payload is None:
            return None
        return Path(self.wrapper.payload)

    def _language_for(self, path: Optional[Path]) -> Optional[CmLanguage]:
        if path is None:
            return None
        return _LANGUAGE_BY_EXT.get(path.suffix.lower())

    def _is_markdown(self, path: Optional[Path]) -> bool:
        return path is not None and path.suffix.lower() == ".md"

    def get_tab_label(self, context: "SessionContext") -> str:
        path = self._resolve_path()
        return path.name if path is not None else self.class_identity.label

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------

    def poll(self, context: "SessionContext", signal: "ContextSignal") -> bool:
        """Redraw on workbench-theme change so CodeMirror picks up the new theme."""
        return isinstance(signal, ThemeMoved)

    @staticmethod
    def _codemirror_theme(context: "SessionContext") -> CmTheme:
        """Pick a CodeMirror theme that matches the active workbench theme."""
        theme_key = context.active_workbench_theme_key.value or "core:theme:workbench:haywire-dark"
        return "vscodeLight" if "light" in theme_key else "vscodeDark"

    def draw(self, context: "SessionContext", container: "Element") -> None:
        path = self._resolve_path()
        self._content = self._read_file(path) if path is not None else ""
        self._original = self._content
        is_md = self._is_markdown(path)
        # On hot-reload of the editor class the mode might be "preview" but
        # the new file is not markdown — reset to edit.
        if not is_md:
            self._mode = "edit"

        with container:
            with ui.column().classes("w-full h-full gap-0"):
                with (
                    ui.row()
                    .classes("w-full items-center px-3 gap-2 flex-shrink-0 border-b")
                    .style("min-height: 32px; background: var(--hw-bg-surface);")
                ):
                    ui.icon("description", size="14px").classes("hw-text-dim")
                    label_text = str(path) if path is not None else "Untitled"
                    self._path_label = ui.label(label_text).classes(
                        "text-xs hw-text-muted truncate font-mono flex-1"
                    )

                    # Preview button only for markdown
                    if is_md:
                        self._mode_button = (
                            ui.button(
                                "Preview",
                                icon="visibility",
                                on_click=self._toggle_mode,
                            )
                            .props("flat dense size=sm")
                            .tooltip("Toggle edit/preview")
                        )
                    else:
                        self._mode_button = None

                    self._save_button = (
                        ui.button(
                            "Save",
                            icon="save",
                            on_click=self._save,
                        )
                        .props("flat dense size=sm")
                        .tooltip("Save (overwrites the open file)")
                    )
                    (
                        ui.button(
                            "Save As",
                            icon="save_as",
                            on_click=self._open_save_as_dialog,
                        )
                        .props("flat dense size=sm")
                        .tooltip("Save under a different name")
                    )

                # body — markdown gets edit/preview tabs; everything else is
                # just the editor.
                if is_md:
                    self._render_body_with_preview(context)
                else:
                    self._render_editor_only(context)

            self._save_as_dialog = self._build_save_as_dialog(context)

        self._update_save_state()

    def _render_editor_only(self, context: "SessionContext") -> None:
        path = self._resolve_path()
        with (
            ui.element("div")
            .classes("hw-cm-isolate")
            .style("flex: 1; min-height: 0; width: 100%; display: flex;")
        ):
            self._editor = self._make_codemirror(context, language=self._language_for(path))
        self._preview = None
        self._tab_panels = None

    def _render_body_with_preview(self, context: "SessionContext") -> None:
        # Headless ui.tab_panels (no ui.tabs sibling) lets us switch
        # edit/preview by setting tab_panels.value while the codemirror stays
        # in the DOM with a stable layout. Same pattern slot.py uses to keep
        # editor panels alive.
        self._tab_panels = (
            ui.tab_panels(value="edit", animated=False)
            .props("keep-alive")
            .style("flex: 1; min-height: 0; width: 100%; background: transparent;")
        )
        with self._tab_panels:
            with ui.tab_panel("edit").style(
                "padding: 0; height: 100%; display: flex; flex-direction: column; overflow: hidden;"
            ):
                # .hw-cm-isolate prevents .hw-panel CSS from cascading into
                # CodeMirror's token spans (see app_shell.py).
                with (
                    ui.element("div")
                    .classes("hw-cm-isolate")
                    .style("flex: 1; min-height: 0; width: 100%; display: flex;")
                ):
                    self._editor = self._make_codemirror(context, language="Markdown")

            with ui.tab_panel("preview").style("padding: 1rem; height: 100%; overflow: auto;"):
                self._preview = ui.markdown(self._content).classes("w-full text-sm")

    def _make_codemirror(self, context: "SessionContext", language: Optional[CmLanguage]) -> ui.codemirror:
        return ui.codemirror(
            value=self._content,
            language=language,
            theme=self._codemirror_theme(context),
            line_wrapping=True,
            on_change=lambda e: self._on_text_changed(e.value),
        ).style("flex: 1; min-height: 0; width: 100%; height: 100%;")

    def _on_text_changed(self, new_value) -> None:
        if not isinstance(new_value, str):
            return
        self._content = new_value
        self._update_save_state()

    def _toggle_mode(self) -> None:
        # Only meaningful when the preview tab exists (.md files).
        if self._tab_panels is None:
            return
        self._mode = "preview" if self._mode == "edit" else "edit"
        if self._mode == "preview" and self._preview is not None:
            self._preview.set_content(self._content)
        self._tab_panels.set_value(self._mode)
        if self._mode_button is not None:
            if self._mode == "preview":
                self._mode_button.text = "Edit"
                self._mode_button.props(remove="icon=visibility")
                self._mode_button.props("icon=edit")
            else:
                self._mode_button.text = "Preview"
                self._mode_button.props(remove="icon=edit")
                self._mode_button.props("icon=visibility")

    def _update_save_state(self) -> None:
        is_dirty = self._content != self._original
        if self.wrapper is not None:
            self.wrapper.set_dirty(is_dirty)
            slot = getattr(self.wrapper, "_slot", None)
            if slot is not None and hasattr(slot, "_refresh_bar"):
                try:
                    slot._refresh_bar()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # save / save-as
    # ------------------------------------------------------------------

    def _save(self) -> None:
        path = self._resolve_path()
        if path is None:
            self._open_save_as_dialog()
            return
        try:
            path.write_text(self._content, encoding="utf-8")
        except OSError as exc:
            ui.notify(f"Save failed: {exc}", type="negative")
            return
        self._original = self._content
        self._update_save_state()
        ui.notify(f"Saved {path.name}", type="positive")

    def _open_save_as_dialog(self) -> None:
        if self._save_as_dialog is None or self._save_as_input is None:
            return
        path = self._resolve_path()
        default = path.name if path is not None else "untitled.txt"
        self._save_as_input.value = default
        if self._save_as_warning is not None:
            self._save_as_warning.set_visibility(False)
        self._save_as_dialog.open()

    def _build_save_as_dialog(self, context: "SessionContext"):
        with ui.dialog() as dialog, ui.card().style("min-width: 420px;"):
            with ui.column().classes("w-full gap-2"):
                ui.label("Save As").classes("text-base font-semibold")
                self._save_as_input = (
                    ui.input(label="File path")
                    .classes("w-full")
                    .props("outlined dense")
                    .on("update:model-value", lambda _: self._clear_save_as_warning())
                )
                self._save_as_warning = ui.label("").classes("text-xs hw-text-danger -mt-1")
                self._save_as_warning.set_visibility(False)
                with ui.row().classes("w-full justify-end gap-2 mt-1"):
                    ui.button("Cancel", on_click=dialog.close).props("flat dense")
                    ui.button(
                        "Save",
                        on_click=lambda: self._do_save_as(context, dialog),
                    ).props("color=positive dense")
        return dialog

    def _clear_save_as_warning(self) -> None:
        if self._save_as_warning is not None:
            self._save_as_warning.set_visibility(False)

    def _do_save_as(self, context: "SessionContext", dialog) -> None:
        if self._save_as_input is None:
            return
        path_str = (self._save_as_input.value or "").strip()
        if not path_str:
            self._show_save_as_warning("Please enter a file path.")
            return

        target = Path(path_str).expanduser()
        if not target.is_absolute():
            base = self._default_base_dir(context)
            target = (base / target).resolve()

        old = self._resolve_path()
        # Default the suffix from the current file's extension when no
        # suffix is provided; fall back to .txt for new files.
        if target.suffix == "":
            target = target.with_suffix(old.suffix if old is not None else ".txt")

        if target.exists() and target != old:
            self._show_save_as_warning(f'"{target.name}" already exists.')
            return

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self._content, encoding="utf-8")
        except OSError as exc:
            self._show_save_as_warning(f"Save failed: {exc}")
            return

        self._original = self._content
        new_payload = str(target)
        if self.wrapper is not None and (old is None or str(old) != new_payload):
            self.wrapper.repayload(new_payload, new_label=target.name)
        if self._path_label is not None:
            self._path_label.text = new_payload
        self._update_save_state()
        ui.notify(f"Saved {target.name}", type="positive")
        dialog.close()

    def _show_save_as_warning(self, msg: str) -> None:
        if self._save_as_warning is not None:
            self._save_as_warning.text = msg
            self._save_as_warning.set_visibility(True)

    @staticmethod
    def _default_base_dir(context: "SessionContext") -> Path:
        app = getattr(context, "app", None)
        root = getattr(app, "workspace_root", None) if app is not None else None
        return Path(root) if root else Path.home()

    # ------------------------------------------------------------------
    # close consent
    # ------------------------------------------------------------------

    async def handle_close_request(self) -> bool:
        """Prompt the user when closing a dirty tab."""
        if self.wrapper is None or not self.wrapper.state.is_dirty:
            return True

        result: dict = {}

        with ui.dialog() as dialog, hui.dialog_card("w-[420px]"):
            ui.label("Save changes before closing?").classes("text-base font-semibold")
            ui.label("You have unsaved changes in this file.").classes("text-sm hw-text-muted")

            def _resolve(action: str) -> None:
                result["action"] = action
                dialog.close()

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Cancel", on_click=lambda: _resolve("cancel")).props("flat dense")
                ui.button("Discard", on_click=lambda: _resolve("discard")).props("flat dense").style(
                    "color: var(--hw-danger);"
                )
                ui.button("Save & Close", on_click=lambda: _resolve("save")).props("flat dense").style(
                    "color: var(--hw-positive);"
                )

        await dialog
        action = result.get("action", "cancel")

        if action == "cancel":
            return False
        if action == "save":
            path = self._resolve_path()
            if path is None:
                self._open_save_as_dialog()
                return False
            try:
                path.write_text(self._content, encoding="utf-8")
            except OSError as exc:
                ui.notify(f"Save failed: {exc}", type="negative")
                return False
            self._original = self._content
        return True

    # ------------------------------------------------------------------
    # housekeeping
    # ------------------------------------------------------------------

    @staticmethod
    def _read_file(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    def cleanup(self) -> None:
        self._editor = None
        self._preview = None
        self._tab_panels = None
        self._mode_button = None
        self._save_button = None
        self._path_label = None
        self._save_as_dialog = None
        self._save_as_input = None
        self._save_as_warning = None
