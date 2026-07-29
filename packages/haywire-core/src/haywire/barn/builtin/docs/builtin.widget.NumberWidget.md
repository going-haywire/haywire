# NumberWidget

`builtin:widget:NumberWidget` · kind: widget

Fast number input widget

## Details


## Notes

Blender-style number input widget for float and int ports.

Drag horizontally to change the value, click to type, or use
the arrow buttons that appear on hover.

Config options (via ``NumberWidget.config(properties={...})``):

- ``min`` (int | float): Minimum allowed value.
- ``max`` (int | float): Maximum allowed value.
- ``step`` (int | float): Step increment for drag / arrows.
- ``precision`` (int): Decimal places to display (-1 = auto from step).
- ``prefix`` (str): Text shown before the value (e.g. ``'$'``).
- ``suffix`` (str): Text shown after the value (e.g. ``'kg'``).
- ``sensitivity`` (float): Drag sensitivity multiplier (default 1.0).

Example::

    NumberWidget.config(properties={'min': 0, 'max': 200, 'step': 0.5})
