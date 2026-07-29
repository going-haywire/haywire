# KnobWidget

`example:widget:KnobWidget` · kind: widget

knob widget

## Details


## Notes

Rotary knob widget for numeric ports.

Config options (via ``KnobWidget.config(properties={...})``):

- ``min`` (int | float): Minimum value.
- ``max`` (int | float): Maximum value.
- ``step`` (int | float): Step increment.
- ``color`` (str): Quasar color name for the knob arc (e.g. ``'primary'``, ``'green'``).
- ``size`` (str): CSS size of the knob element (e.g. ``'60px'``).

Example::

    KnobWidget.config(properties={'min': 0, 'max': 360, 'step': 1, 'color': 'teal'})
