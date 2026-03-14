# haywire/ui/themes/node_theme.py
"""
NodeTheme — per-node rendering color tokens.

Follows the same pattern as WorkbenchTheme: plain Color string class attributes
auto-wrapped into _FieldProxy objects by __init_subclass__.
"""

from __future__ import annotations
from typing import ClassVar

from .workbench import _FieldProxy


class NodeTheme:
    """
    Base class for node rendering themes.

    Subclasses decorated with @node_theme can be registered with ThemeRegistry.
    """

    _fields: ClassVar[dict[str, _FieldProxy]] = {}
    _namespace: ClassVar[str] = ''

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls._fields = {}
        for name, val in cls.__dict__.items():
            if name.startswith('_'):
                continue
            if isinstance(val, str) and not callable(val):
                proxy = _FieldProxy(default=val, attr_name=name)
                cls._fields[name] = proxy

    def get_color(self, token: str) -> str:
        """Return the color value for a named token (or '' if missing)."""
        proxy = self._fields.get(token)
        return proxy._default if proxy is not None else ''

