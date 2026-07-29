# Choices

`builtin:type:CHOICES` · kind: type

A string constrained to a set of options (options live per-use in widget_config)

## Details

- **flow_type**: `data`
- **default**: `{'value': ''}`
- **widget_key**: `builtin:widget:SelectWidget`
- **color**: `#ffd54f`

## Notes

String selected from a per-setting/per-port option list.

The TYPE carries only 'renders as a select'; the options are supplied by
each setting/port via widget_config={"options": [...] | {value: label} |
callable}.
