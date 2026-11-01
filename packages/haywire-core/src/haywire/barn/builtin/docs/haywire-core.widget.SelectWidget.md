# SelectWidget

`haywire-core:widget:SelectWidget` · kind: widget

select widget

## Details


## Notes

Dropdown select widget for int and string ports.

Config options (via ``SelectWidget.config(properties={...})``):

- ``options`` (list, ``{value: label}`` dict, or zero-arg callable returning
  either): List of selectable values (required). A callable is invoked fresh
  at every ``build()`` — options can reflect state that changed since the
  setting/port was declared (e.g. available theme skins).
- ``clearable`` (bool): If ``True``, shows a clear button to reset the selection.
- ``multiple`` (bool): If ``True``, allows selecting multiple values.
- ``new_value_mode`` (``"add-unique"``, ``"add"`` or ``"toggle"``): Lets the
  user filter the options by typing and keep typed text that is not an
  option (committed with Enter). A value that is not an option, typed or
  loaded, is shown as an extra option of this widget only; the declared
  options never change.

Example::

    SelectWidget.config(properties={'options': ['Low', 'Medium', 'High']})
    SelectWidget.config(properties={'options': {0: 'Off', 1: 'On'}, 'clearable': True})
    SelectWidget.config(properties={'options': lambda: list_available_skins()})
    # Suggestions, plus any typed value:
    SelectWidget.config(properties={'options': ['auto', 'cpu'], 'new_value_mode': 'add-unique'})
