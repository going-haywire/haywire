"""HaystackSettingsPanel — exposes HaystackSettings in the properties editor.

Pinned to AppFocus (always available) because haystack settings are
workspace-global, not tied to a particular graph or node. Uses the
codebase's canonical render_schema() pattern — every field on
HaystackSettings auto-renders, wired to the registry-backed setter so
changes persist via save_to_toml_debounced.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout, panel, render_schema

from haybale_haystack.settings.haystack_settings import HaystackSettings
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haybale_studio.focuses import ExecutionFocus

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    action=PropertiesEditorActions,
    focus=ExecutionFocus,
    label="Haystack",
    icon=hui.icon.save,
    order=80,
)
class HaystackSettingsPanel(BasePanel):
    """Renders all HaystackSettings fields auto-wired to the registry."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return True

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(HaystackSettings, registry)
