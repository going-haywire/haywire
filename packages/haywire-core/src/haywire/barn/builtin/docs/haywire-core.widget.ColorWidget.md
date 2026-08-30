# ColorWidget

`haywire-core:widget:ColorWidget` · kind: widget

Color picker widget

## Details


## Notes

Color picker widget for COLOR ports.

Config options (via ``ColorWidget.config(properties={...})``):

- ``alpha`` (bool): When ``True`` the picker edits and emits an 8-digit
  ``#rrggbbaa`` value instead of the 6-digit ``#rrggbb`` default. This is
  the opacity control — there is no separate opacity setting, because
  ``COLOR`` is a string type whose contract has always been "hex or rgba"
  (see ``ColorStr``), so the alpha rides inside the value itself.

Quasar's QColor drives this through ``format-model``; ``hexa`` is the
alpha-carrying counterpart of ``hex``. The default stays ``hex`` so every
existing COLOR port is untouched.

Example::

    ColorWidget.config(properties={'alpha': True})
