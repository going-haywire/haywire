# MenuWidget

`haywire-core:widget:MenuWidget` · kind: widget

menu widget

## Details


## Notes

Dropdown select widget for int and string ports.

Config options (via ``MenuWidget.config(properties={...})``):

- ``options`` (list, ``{value: label}`` dict, or callable returning either):
  List of selectable values (required). A callable is invoked at ``build()``
  and again each time the dropdown opens, so the list follows state that
  changes while the widget is shown (e.g. senders found on the network). A
  callable with a positional parameter receives the ``Settings`` bag that
  owns the field (``None`` when there is none), so the list can depend on a
  sibling setting. The current value stays listed across a refresh.
- ``refresh`` (``True`` or callable): Shows a refresh button beside the
  dropdown. Clicking it runs the query off the UI thread, so it may block
  (e.g. look for senders on the network), and shows its result as the
  options. A callable is called like a callable ``options``; ``True``
  calls ``options`` again. With ``refresh`` the button is the only update:
  opening the dropdown does not re-read ``options``, which is read once at
  ``build()`` and should be fast (e.g. what the last refresh found).
- ``clearable`` (bool): If ``True``, shows a clear button to reset the selection.
- ``multiple`` (bool): If ``True``, allows selecting multiple values.
- ``new_value_mode`` (``"add-unique"``, ``"add"`` or ``"toggle"``): Lets the
  user filter the options by typing and keep typed text that is not an
  option (committed with Enter). A value that is not an option, typed or
  loaded, is shown as an extra option of this widget only; the declared
  options never change.

Example::

    MenuWidget.config(properties={'options': ['Low', 'Medium', 'High']})
    MenuWidget.config(properties={'options': {0: 'Off', 1: 'On'}, 'clearable': True})
    MenuWidget.config(properties={'options': lambda: list_available_skins()})
    # Depends on a sibling setting of the same bag:
    MenuWidget.config(properties={'options': lambda bag: list_sources(bag.backend)})
    # A slow query, run when the user clicks refresh:
    MenuWidget.config(properties={'options': known_sources, 'refresh': find_sources})
    # Suggestions, plus any typed value:
    MenuWidget.config(properties={'options': ['auto', 'cpu'], 'new_value_mode': 'add-unique'})
