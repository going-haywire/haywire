from .properties.setting.app import ThemeSettingsPanel
from .properties.setting.app import NodeSkinDefaultPanel
from .properties.setting.app import EditorSettingsPanel
from .properties.setting.app import ActivitySettingsPanel
from .properties.setting.canvas import CanvasSettingsPanel
from .properties.setting.canvas import NodeSkinSettingsPanel
from .properties.setting.canvas import EdgeUISettingsPanel
from .properties.setting.canvas import EditorZoomPanSettingsPanel
from .properties.setting.canvas import MinimapSettingsPanel
from .properties.setting.debug import DebugOverlaySettingsPanel
from .properties.setting.debug import DebugSettingsPanel
from .properties.setting.execution import ExecutionSettingsPanel
from .file_browser.menu.file import OpenInCodeEditorMenuPanel
from .file_browser.menu.file import OpenInFileViewerMenuPanel

# Backwards-compat aliases for external consumers using old names
OpenInCodeEditorPanel = OpenInCodeEditorMenuPanel
OpenInFileViewerPanel = OpenInFileViewerMenuPanel

__all__ = [
    "ActivitySettingsPanel",
    "CanvasSettingsPanel",
    "DebugOverlaySettingsPanel",
    "DebugSettingsPanel",
    "EdgeUISettingsPanel",
    "EditorSettingsPanel",
    "EditorZoomPanSettingsPanel",
    "ExecutionSettingsPanel",
    "MinimapSettingsPanel",
    "NodeSkinDefaultPanel",
    "NodeSkinSettingsPanel",
    "OpenInCodeEditorMenuPanel",
    "OpenInCodeEditorPanel",
    "OpenInFileViewerMenuPanel",
    "OpenInFileViewerPanel",
    "ThemeSettingsPanel",
]
