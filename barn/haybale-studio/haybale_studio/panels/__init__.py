from haybale_studio.panels.properties.setting.app import ThemeSettingsPanel
from haybale_studio.panels.properties.setting.app import NodeSkinDefaultPanel
from haybale_studio.panels.properties.setting.app import EditingSettingsPanel
from haybale_studio.panels.properties.setting.app import ActivitySettingsPanel
from haybale_studio.panels.properties.setting.canvas import CanvasSettingsPanel
from haybale_studio.panels.properties.setting.canvas import EditorZoomPanSettingsPanel
from haybale_studio.panels.properties.setting.canvas import MinimapSettingsPanel
from haybale_studio.panels.properties.setting.canvas import EdgeDefaultSettingsPanel
from haybale_studio.panels.properties.setting.canvas import ArrangeSettingsPanel
from haybale_studio.panels.properties.setting.debug import DebugOverlaySettingsPanel
from haybale_studio.panels.properties.setting.debug import DebugSettingsPanel
from haybale_studio.panels.properties.setting.execution import ExecutionSettingsPanel
from haybale_studio.panels.file_browser.menu.file import OpenInCodeEditorMenuPanel
from haybale_studio.panels.file_browser.menu.file import OpenInFileViewerMenuPanel

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
