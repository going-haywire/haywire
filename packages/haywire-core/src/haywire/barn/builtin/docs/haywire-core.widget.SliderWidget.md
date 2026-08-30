# SliderWidget

`haywire-core:widget:SliderWidget` · kind: widget

slider widget

## Details


## Notes

Horizontal slider widget for numeric ports.

Config options (via ``SliderWidget.config(properties={...})``):

- ``min`` (int | float): Minimum value (default: ``0``).
- ``max`` (int | float): Maximum value (default: ``100``).
- ``step`` (int | float): Step increment (default: ``1``).

Example::

    SliderWidget.config(properties={'min': -1.0, 'max': 1.0, 'step': 0.01})
