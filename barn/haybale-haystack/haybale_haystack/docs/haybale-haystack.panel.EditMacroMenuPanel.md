# Edit Macro

`haybale-haystack:panel:EditMacroMenuPanel` · kind: panel

## Details

- **surface**: `selection`
- **order**: `37`

## Notes

Open the document behind a macro placement, in its own editor tab.

Only visible on a placement. Descending into one is refused — its interior
is runtime state rebuilt from the template, so there is nothing there to
edit in place — and this row is what the gesture resolves to instead.
