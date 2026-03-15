# haywire/core/settings/types.py
"""
Type aliases for descriptor annotations — purely for IDE hinting.
At runtime these are just str.
"""

Color = str   # hex or rgba string, implies color-picker widget
Icon  = str   # material icon name, implies icon-picker widget
