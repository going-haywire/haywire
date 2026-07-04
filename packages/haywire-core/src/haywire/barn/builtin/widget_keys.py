"""Registry keys of the builtin widgets — the one place the strings live.

Leaf module by design: no imports, so engine-side type declarations
(@type(widget_key=...)) can reference widget keys without importing widget
classes (which are NiceGUI-backed). Each constant MUST match the key derived
by @widget for the class of the same name; test_widget_keys.py enforces it.
"""

NUMBER_WIDGET = "builtin:widget:NumberWidget"
TEXT_WIDGET = "builtin:widget:TextWidget"
SWITCH_WIDGET = "builtin:widget:SwitchWidget"
SELECT_WIDGET = "builtin:widget:SelectWidget"
COLOR_WIDGET = "builtin:widget:ColorWidget"
VEC_WIDGET = "builtin:widget:VecWidget"
SIMPLE_LABEL_WIDGET = "builtin:widget:SimpleLabelWidget"
