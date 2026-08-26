# haywire/ui/themes/workbench.py
"""
BaseTheme — CSS variable definitions for the app shell, the canvas, and node cards.

Fields are plain Color string class attributes (NOT field() descriptors).
BaseTheme.__init_subclass__ auto-wraps them into minimal objects so that
_fields is populated uniformly and to_css_vars() works without extra
boilerplate.
"""

from __future__ import annotations
from typing import ClassVar

from haywire.core.library.identity import LibraryIdentity
from haywire.ui.themes.identity import ThemeClassIdentity


class _FieldProxy:
    """Minimal descriptor-like object wrapping a plain Color default value."""

    __slots__ = ("_default", "_attr_name")

    def __init__(self, default: str, attr_name: str = ""):
        self._default = default
        self._attr_name = attr_name


class BaseTheme:
    """
    Base class for every theme — workbench and node alike.

    One class, one token vocabulary (``_CSS_TOKEN_MAP``, in full). What
    distinguishes a "workbench theme" from a "node theme" is
    ``class_identity.theme_type`` (set by the ``@theme(theme_type=...)``
    decorator, see decorator.py), which decides WHERE the theme's
    declarations get injected (``:root`` vs ``.graph-canvas`` vs
    ``.ui-node-slot``) — not the class you subclass.

    Subclass and override only the tokens you want to change:

        @theme(theme_type='workbench', label='Haywire Dark')
        class HaywireDarkTheme(BaseTheme):
            bg_page    = '#12121e'
            bg_surface = '#1e1e2e'
            ...

        @theme(theme_type='node', label='Default Node Theme')
        class DefaultNodeTheme(BaseTheme):
            node_bg = '#1e1e2e'
            ...

    Field values are plain class-attribute strings (not ``field()``
    descriptors); ``__init_subclass__`` below wraps them into ``_fields``
    uniformly. A field not in ``_CSS_TOKEN_MAP`` is silently dropped by
    ``to_css_vars()``.
    """

    class_identity: ClassVar[ThemeClassIdentity]
    class_library: ClassVar[LibraryIdentity]

    _fields: ClassVar[dict[str, _FieldProxy]] = {}
    _namespace: ClassVar[str] = ""

    # Maps field_name -> CSS variable name.
    # These names match the --hw-* vars used throughout app_shell.py and other CSS.
    #
    # A field NOT in this map is silently dropped by to_css_vars() — it walks
    # the map, not _fields. That is the cost of the map being explicit, and the
    # reason a mistyped token in a theme subclass produces no var and no error.
    _CSS_TOKEN_MAP: ClassVar[dict[str, str]] = {
        # Backgrounds
        "bg_page": "--hw-bg-page",
        "bg_surface": "--hw-bg-surface",
        "bg_sidebar": "--hw-bg-sidebar",
        "bg_elevated": "--hw-bg-elevated",
        "bg_overlay": "--hw-bg-overlay",
        "bg_input": "--hw-bg-input",
        "bg_hover": "--hw-bg-hover",
        "bg_active": "--hw-bg-active",
        # Borders
        "border": "--hw-border",
        "border_strong": "--hw-border-strong",
        # Text
        "text_body": "--hw-text-body",
        "text_muted": "--hw-text-muted",
        "text_dim": "--hw-text-dim",
        "text_expansion": "--hw-text-expansion",
        "text_on_accent": "--hw-text-on-accent",
        # Accent
        "accent": "--hw-accent",
        "accent_hover": "--hw-accent-hover",
        "accent_active": "--hw-accent-active",
        # Status
        "danger": "--hw-danger",
        "warning": "--hw-warning",
        "warning_dim": "--hw-warning-dim",
        "success": "--hw-success",
        "info": "--hw-info",
        "positive": "--hw-positive",
        # Node chrome — card surface. A node- or graph-authored theme may
        # override any token in this whole map, this group included. Lengths
        # carry their unit IN the value ("3px", not 3): var() is textual
        # substitution, so `border: 3 solid red` is invalid CSS and fails
        # silently. Same shape as muted_opacity / compact_field_h.
        "node_bg": "--hw-node-bg",
        "node_border_color": "--hw-node-border-color",
        "node_border_width": "--hw-node-border-width",
        "node_border_radius": "--hw-node-border-radius",
        "node_header_bg": "--hw-node-header-bg",
        "node_header_text_color": "--hw-node-header-text-color",
        "node_text_color": "--hw-node-text-color",
        # Node chrome — canvas affordances expressing editor state.
        #
        # Consumed by canvas.vue on [data-node-id]. The graph and global tiers
        # (.graph-canvas / :root) sit ABOVE [data-node-id] and reach these
        # normally. The node tier (.ui-node-slot) sits BELOW it — custom
        # properties inherit downward only, so a value set there is accepted
        # and written like any other token but is structurally inert for these
        # three: a node-tier theme cannot restyle its own selection ring, no
        # matter what it sets here. See theme-canon.
        "node_selected": "--hw-node-selected",
        "node_active": "--hw-node-active",
        "node_shadow": "--hw-node-shadow",
        # Edges
        "edge_default": "--hw-edge-default",
        "edge_selected": "--hw-edge-selected",
        "edge_active": "--hw-edge-active",
        # Canvas
        "canvas_bg": "--hw-canvas-bg",
        "canvas_grid": "--hw-canvas-grid",
        "ghost_pin": "--hw-ghost-pin",
        "danger_bg": "--hw-danger-bg",
        # TopBar
        "topbar_bg": "--hw-topbar-bg",
        "topbar_text": "--hw-topbar-text",
        # Sidebar
        "sidebar_bg": "--hw-sidebar-bg",
        "sidebar_icon": "--hw-sidebar-icon",
        "sidebar_icon_active": "--hw-sidebar-icon-active",
        # Panel
        "panel_bg": "--hw-panel-bg",
        "panel_text": "--hw-panel-text",
        "panel_header_0_bg": "--hw-panel-header-0-bg",
        "panel_header_1_bg": "--hw-panel-header-1-bg",
        # StatusBar
        "statusbar_bg": "--hw-statusbar-bg",
        "statusbar_text": "--hw-statusbar-text",
        # Console
        "console_bg": "--hw-console-bg",
        "console_text": "--hw-console-text",
        # Popups / drag
        "popup_shadow": "--hw-popup-shadow",
        "drag_over": "--hw-drag-over",
        "drag_ghost": "--hw-drag-ghost",
        # Menu rows (hui.menu_row / hui.submenu_row — one row look for every
        # menu). Each is optional: the .hw-menu-row CSS block falls back to the
        # semantic token beside it (text -> --hw-text-body, icon -> --hw-text-dim,
        # hover -> --hw-bg-hover), so a theme sets these only to give menus a
        # look of their own.
        "menu_row_text": "--hw-menu-row-text",
        "menu_row_icon": "--hw-menu-row-icon",
        "menu_row_icon_size": "--hw-menu-row-icon-size",
        "menu_row_hover_bg": "--hw-menu-row-hover-bg",
        "menu_row_font_size": "--hw-menu-row-font-size",
        "menu_row_font_weight": "--hw-menu-row-font-weight",
        "menu_row_text_transform": "--hw-menu-row-text-transform",
        # Compact fields
        "compact_gap": "--hw-compact-gap",
        "compact_field_h": "--hw-compact-field-h",
        "compact_row_min_h": "--hw-compact-row-min-h",
    }

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Fresh dict per class
        cls._fields = {}
        for name, val in cls.__dict__.items():
            if name.startswith("_"):
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
