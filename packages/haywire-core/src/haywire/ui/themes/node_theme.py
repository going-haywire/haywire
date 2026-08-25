# haywire/ui/themes/node_theme.py
"""
NodeTheme — the node-scoped subset of the workbench token vocabulary.

A NodeTheme is not a second theme system: it declares the SAME tokens a
WorkbenchTheme does (``node_bg``, ``node_border_color``, …), and emits them
through the same ``to_css_vars()``. What differs is only *where* the result is
injected, and therefore what it overrides:

    :root            WorkbenchTheme        every token
    :root            global NodeTheme      node tokens, overriding the above
    .graph-canvas    graph's NodeTheme     only if it differs from global
    .ui-node-slot    node's NodeTheme      only if it differs from the graph

Nothing reads a theme in Python. A skin emits ``background: var(--hw-node-bg)``
once and the browser re-resolves it whenever a tier's declarations change —
which is why a per-node look costs a style-write and never a card redraw.
"""

from __future__ import annotations
from typing import ClassVar

from .workbench import _FieldProxy, BaseTheme


class NodeTheme(BaseTheme):
    """
    Base class for node rendering themes.

    Subclasses decorated with @theme can be registered with ThemeRegistry.

    Declare only node-scoped tokens (``NODE_TIER_TOKENS``). Anything else is
    silently dropped by ``to_css_vars()``, which walks the shared token map —
    including the Tier 2 tokens (``node_selected`` / ``node_active`` /
    ``node_shadow``), which are real tokens but are consumed on an ANCESTOR of
    the element a node theme writes to, so a node tier cannot reach them.
    """

    _fields: ClassVar[dict[str, _FieldProxy]] = {}
    _namespace: ClassVar[str] = ""
