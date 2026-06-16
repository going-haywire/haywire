from .file_browser.menu.file import OpenInHaystackMenuPanel
from .properties.introspect.graph_run_settings_panel import GraphRunSettingsPanel

# Backwards-compat alias
OpenInHaystackPanel = OpenInHaystackMenuPanel

__all__ = [
    "GraphRunSettingsPanel",
    "OpenInHaystackMenuPanel",
    "OpenInHaystackPanel",
]
