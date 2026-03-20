# haywire/ui/themes/workbench.py
"""
WorkbenchTheme — CSS variable definitions for the app shell.

Fields are plain Color string class attributes (NOT setting() descriptors).
WorkbenchTheme.__init_subclass__ auto-wraps them into minimal objects so that
_fields is populated uniformly and to_css_vars() works without extra boilerplate.
"""

from __future__ import annotations
from typing import ClassVar


class _FieldProxy:
    """Minimal descriptor-like object wrapping a plain Color default value."""
    __slots__ = ('_default', '_attr_name')

    def __init__(self, default: str, attr_name: str = ''):
        self._default = default
        self._attr_name = attr_name


class WorkbenchTheme:
    """
    Base class for workbench (app-shell) themes.

    Subclasses define CSS variable values as plain class attributes:

        class HaywireDarkTheme(WorkbenchTheme):
            bg_page    = '#12121e'
            bg_surface = '#1e1e2e'
            ...

    _CSS_TOKEN_MAP maps field names to CSS custom property names.
    to_css_vars() returns the {--hw-token: value} dict for injection into :root.

    Subclasses decorated with @workbench_theme get a class_identity attribute
    and can be registered with ThemeRegistry.
    """

    _fields: ClassVar[dict[str, _FieldProxy]] = {}
    _namespace: ClassVar[str] = ''

    # Maps field_name -> CSS variable name.
    # These names match the --hw-* vars used throughout app_shell.py and other CSS.
    _CSS_TOKEN_MAP: ClassVar[dict[str, str]] = {
        # Backgrounds
        'bg_page':           '--hw-bg-page',
        'bg_surface':        '--hw-bg-surface',
        'bg_sidebar':        '--hw-bg-sidebar',
        'bg_elevated':       '--hw-bg-elevated',
        'bg_overlay':        '--hw-bg-overlay',
        'bg_input':          '--hw-bg-input',
        # Borders
        'border':            '--hw-border',
        'border_strong':     '--hw-border-strong',
        # Text
        'text_body':         '--hw-text-body',
        'text_muted':        '--hw-text-muted',
        'text_dim':          '--hw-text-dim',
        'text_expansion':    '--hw-text-expansion',
        'text_on_accent':    '--hw-text-on-accent',
        # Accent
        'accent':            '--hw-accent',
        'accent_hover':      '--hw-accent-hover',
        'accent_active':     '--hw-accent-active',
        # Status
        'danger':            '--hw-danger',
        'warning':           '--hw-warning',
        'success':           '--hw-success',
        'info':              '--hw-info',
        # Node chrome
        'node_bg':           '--hw-node-bg',
        'node_border':       '--hw-node-border',
        'node_header_bg':    '--hw-node-header-bg',
        'node_header_text':  '--hw-node-header-text',
        'node_selected':     '--hw-node-selected',
        'node_shadow':       '--hw-node-shadow',
        # Edges
        'edge_default':      '--hw-edge-default',
        'edge_selected':     '--hw-edge-selected',
        # Canvas
        'canvas_bg':         '--hw-canvas-bg',
        'canvas_grid':       '--hw-canvas-grid',
        # TopBar
        'topbar_bg':         '--hw-topbar-bg',
        'topbar_text':       '--hw-topbar-text',
        # Sidebar
        'sidebar_bg':        '--hw-sidebar-bg',
        'sidebar_icon':      '--hw-sidebar-icon',
        'sidebar_icon_active': '--hw-sidebar-icon-active',
        # Panel
        'panel_bg':          '--hw-panel-bg',
        'panel_text':        '--hw-panel-text',
        # StatusBar
        'statusbar_bg':      '--hw-statusbar-bg',
        'statusbar_text':    '--hw-statusbar-text',
        # Console
        'console_bg':        '--hw-console-bg',
        'console_text':      '--hw-console-text',
        # Compact fields
        'compact_gap':       '--hw-compact-gap',
        'compact_field_h':   '--hw-compact-field-h',
        'compact_row_min_h': '--hw-compact-row-min-h',
    }

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Fresh dict per class
        cls._fields = {}
        for name, val in cls.__dict__.items():
            if name.startswith('_'):
                continue
            if isinstance(val, str) and not callable(val):
                proxy = _FieldProxy(default=val, attr_name=name)
                cls._fields[name] = proxy

    def to_css_vars(self) -> dict[str, str]:
        """
        Build {css_variable: value} dict for all known CSS tokens.

        Walks _CSS_TOKEN_MAP and reads the corresponding _fields entry.
        Fields not in the map are silently ignored.
        """
        result = {}
        for field_name, css_var in self._CSS_TOKEN_MAP.items():
            proxy = self._fields.get(field_name)
            if proxy is not None:
                result[css_var] = proxy._default
        return result

