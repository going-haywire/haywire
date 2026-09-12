# Set to none

`haybale-graph-editor:panel:ClearSettingMenuPanel` · kind: panel

## Details

- **surface**: `pin`
- **order**: `16`

## Notes

Clear the backing setting to ABSENCE — ``OPTIONAL[T]`` fields only.

Distinct from Reset wherever the declared default is itself a value: Reset
goes back to that value, this goes to "pass nothing". On a field whose
default is already absence the two land in the same place, and both are
still listed, because Reset greys when the field is clean and this one
does not — which is exactly the state a user reaches by editing the pin's
own widget.
