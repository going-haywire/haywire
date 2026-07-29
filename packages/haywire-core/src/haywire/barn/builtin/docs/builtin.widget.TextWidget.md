# TextWidget

`builtin:widget:TextWidget` · kind: widget

Fast text input widget

## Details


## Notes

Text input widget for string ports.

An inline single-line input plus an expand-to-modal button: the button pops
out a full-size ``autogrow`` textarea (``text_modal``) for editing long or
multi-line values, writing the confirmed text back through the port cell so
the inline input re-syncs automatically.

Config options (via ``TextWidget.config(properties={...})``):

- ``label`` (str): Input label shown above the field.
- ``placeholder`` (str): Placeholder text shown when the field is empty.
- ``password`` (bool): If ``True``, input is masked as a password field.

Example::

    TextWidget.config(properties={'label': 'Name', 'placeholder': 'Enter name...'})
