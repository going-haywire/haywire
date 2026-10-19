"""The font choices a skin offers for its text, and the CSS font stack of each.

Leaf module: no imports, so a node's settings can offer the choices on the
headless path. The annotation and widget-node skins share it.
"""

#: Font choices, each a family a skin maps to a CSS font stack.
FONTS = ("sans", "serif", "mono", "handwriting")

#: CSS font stack of each choice in ``FONTS``.
FONT_STACKS = {
    "sans": "inherit",
    "serif": "Georgia, 'Times New Roman', serif",
    "mono": "ui-monospace, Menlo, Consolas, monospace",
    "handwriting": "'Segoe Print', 'Bradley Hand', 'Comic Sans MS', cursive",
}
