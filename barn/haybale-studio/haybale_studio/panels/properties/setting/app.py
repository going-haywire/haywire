# haybale_studio/panels/properties/setting/app.py
"""
Application settings panels, on the ``AppSettings`` surface.

ThemeSettingsPanel    — active workbench theme
NodeSkinDefaultPanel  — default node skin settings
EditorSettingsPanel   — undo, auto-save, interaction, clipboard, node creation
ActivitySettingsPanel — Farmhand activity tracker: history size, audit log path
SecurityPanel         — read-only posture report plus the studio port
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema

from haybale_studio.settings.theme_settings import WorkbenchThemeSettings, NodeThemeSettings
from haywire.core.skin.settings import NodeDefaultSkinSettings
from haywire.ui.prefs.editor import EditorSettings
from haywire.core.farmhand.settings import ActivitySettings

from haywire.barn.builtin.surfaces import AppSettings

from haywire.core.access import AccessTier
from haywire_studio.network.settings import NetworkSettings
from haywire_studio.network.tls_operations import status as tls_status
from haywire_studio.security.posture import Severity, assess_document

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire_studio.security.posture import Posture


@panel(
    surface=AppSettings,
    label="Workbench",
    icon=hui.icon.theme,
    order=10,
    default_open=True,
)
class ThemeSettingsPanel(BasePanel):
    """Active workbench and node themes."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(WorkbenchThemeSettings, registry)
        render_schema(NodeThemeSettings, registry)


@panel(
    surface=AppSettings,
    label="Default Skins",
    icon=hui.icon.skin,
    order=20,
    default_open=False,
)
class NodeSkinDefaultPanel(BasePanel):
    """Node Default Skins."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(NodeDefaultSkinSettings, registry)


@panel(
    surface=AppSettings,
    label="Editor",
    icon=hui.icon.edit,
    order=30,
    default_open=False,
)
class EditorSettingsPanel(BasePanel):
    """Undo, auto-save, interaction, clipboard and node-creation behaviour."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(EditorSettings, registry)


@panel(
    surface=AppSettings,
    label="Activity",
    icon="smart_toy",  # matches ActivityEditor/OpenActivityPanel's icon
    order=35,
    default_open=False,
)
class ActivitySettingsPanel(BasePanel):
    """Farmhand activity tracker: in-memory history size, audit log path.

    See ``haywire.core.farmhand.settings.ActivitySettings`` and
    ``docs/superpowers/plans/2026-08-18-farmhand-activity-expansion.md``.
    """

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ActivitySettings, registry)


_MARKERS = {
    Severity.CRITICAL: ("CRITICAL", "text-red-400"),
    Severity.WARNING: ("WARNING", "text-amber-400"),
    Severity.NOTE: ("note", "text-slate-400"),
}


@panel(
    surface=AppSettings,
    label="Security",
    icon=hui.icon.severity,
    order=40,
    default_open=False,
    access=AccessTier.ADMIN,
)
class SecurityPanel(BasePanel):
    """What this studio's defences currently are — read-only (ADR 0028).

    **Deliberately not editable.** Exposure, the peer allowlist, TLS and the
    Farmhand switches all left the settings system precisely because a panel
    that writes them writes the *workspace* settings tier, a per-project file
    that travels into git and onto other machines. They are changed with
    ``haywire network``, ``haywire auth``, ``haywire ssl`` and
    ``haywire farmhand``, with the studio stopped, because every one of them is
    read once at startup.

    The port stays here: it is a local convenience, not a security control.
    """

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        document = getattr(ctx.app, "security_document", None)
        if document is None:
            hui.label("Security state is unavailable — the studio was started without one.")
            return

        posture = assess_document(document, tls_status(document=document))
        self._draw_axes(posture)
        self._draw_findings(posture)

        registry = ctx.app.library_service.get_settings_registry()
        render_schema(NetworkSettings, registry)

    def _draw_axes(self, posture: "Posture") -> None:
        network = (
            f"exposed at {posture.reachable_at or 'this machine'} ({posture.allowed_ranges})"
            if posture.reachable_by_others
            else "loopback only"
        )
        auth = f"{posture.principals} principal(s)" if posture.auth_enabled else "off"
        tls = "on — HTTPS" if posture.tls_on else "off — plain HTTP"
        farmhand = (
            "off"
            if not posture.farmhand_enabled
            else ("/mcp, loopback only" if posture.farmhand_loopback else "/mcp, ANY host")
        )
        for label, value in (
            ("Network", network),
            ("Auth", auth),
            ("TLS", tls),
            ("Farmhand", farmhand),
        ):
            with ui.row():
                hui.label(label).classes("w-24 opacity-70")
                hui.label(value)

    def _draw_findings(self, posture: "Posture") -> None:
        if not posture.findings:
            hui.label("Nothing to fix.").classes("mt-2 opacity-70")
            return
        for finding in posture.findings:
            marker, colour = _MARKERS[finding.severity]
            with ui.column().classes("mt-2 gap-0"):
                hui.label(f"[{marker}] {finding.headline}").classes(colour)
                for line in finding.detail:
                    hui.label(line).classes("text-xs opacity-70")
                if finding.fix:
                    # Copyable, because the fix is a command to paste into a
                    # terminal — with the studio stopped, which is the one moment
                    # this panel is no longer on screen to read it from.
                    hui.code_snippet(finding.fix).classes("text-xs")
