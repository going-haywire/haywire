# SelectWidget

`builtin:widget:SelectWidget` · kind: widget

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

Example::

    SelectWidget.config(properties={'options': ['Low', 'Medium', 'High']})
    SelectWidget.config(properties={'options': {0: 'Off', 1: 'On'}, 'clearable': True})
    SelectWidget.config(properties={'options': lambda: list_available_skins()})
