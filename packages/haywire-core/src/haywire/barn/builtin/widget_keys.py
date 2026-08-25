"""Registry keys of the builtin widgets — the one place the strings live.

Leaf module by design: no imports, so engine-side type declarations
(@type(widget_key=...)) can reference widget keys without importing widget
classes (which are NiceGUI-backed). Each constant MUST match the key derived
by @widget for the class of the same name; test_widget_keys.py enforces it.
"""

NUMBER_WIDGET = "haywire-core:widget:NumberWidget"
TEXT_WIDGET = "haywire-core:widget:TextWidget"
SWITCH_WIDGET = "haywire-core:widget:SwitchWidget"
SELECT_WIDGET = "haywire-core:widget:SelectWidget"
COLOR_WIDGET = "haywire-core:widget:ColorWidget"
FILL_WIDGET = "haywire-core:widget:FillWidget"
VEC_WIDGET = "haywire-core:widget:VecWidget"
SIMPLE_LABEL_WIDGET = "haywire-core:widget:SimpleLabelWidget"
