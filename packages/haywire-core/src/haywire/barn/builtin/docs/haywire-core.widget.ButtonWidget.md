# ButtonWidget

`haywire-core:widget:ButtonWidget` · kind: widget

button widget

## Details


## Notes

Push button for boolean ports: a click sets the port to ``True``.

The button shows as pending while the port is ``True``; whatever consumes
the press sets it back to ``False``. A click the port refuses changes nothing.

Config options (via ``ButtonWidget.config(properties={...})``):

- ``text`` (str): Button label (default: ``"Run"``).
- ``icon`` (str): Material icon name shown before the label (default: none).

Example::

    ButtonWidget.config(properties={'text': 'Run', 'icon': 'play_arrow'})
