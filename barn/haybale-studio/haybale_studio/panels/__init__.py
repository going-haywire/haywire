from __future__ import annotations

from haybale_studio.panels.file_browser.menu.file import OpenInCodeEditorMenuPanel, OpenInFileViewerMenuPanel
from haybale_studio.panels.properties.setting.app import (
    ActivitySettingsPanel,
    EditingSettingsPanel,
    NodeSkinDefaultPanel,
    ThemeSettingsPanel,
)
from haybale_studio.panels.properties.setting.canvas import (
    ArrangeSettingsPanel,
    CanvasSettingsPanel,
    EdgeDefaultSettingsPanel,
    EditorZoomPanSettingsPanel,
    MinimapSettingsPanel,
)
from haybale_studio.panels.properties.setting.debug import DebugOverlaySettingsPanel, DebugSettingsPanel
from haybale_studio.panels.properties.setting.execution import ExecutionSettingsPanel

# Backwards-compat aliases for external consumers using old names
OpenInCodeEditorPanel = OpenInCodeEditorMenuPanel
OpenInFileViewerPanel = OpenInFileViewerMenuPanel

__all__ = [
    "ActivitySettingsPanel",
    "ArrangeSettingsPanel",
    "CanvasSettingsPanel",
    "DebugOverlaySettingsPanel",
    "DebugSettingsPanel",
    "EditingSettingsPanel",
    "EditorZoomPanSettingsPanel",
    "ExecutionSettingsPanel",
    "MinimapSettingsPanel",
    "EdgeDefaultSettingsPanel",
    "NodeSkinDefaultPanel",
    "OpenInCodeEditorMenuPanel",
    "OpenInCodeEditorPanel",
    "OpenInFileViewerMenuPanel",
    "OpenInFileViewerPanel",
    "ThemeSettingsPanel",
]
