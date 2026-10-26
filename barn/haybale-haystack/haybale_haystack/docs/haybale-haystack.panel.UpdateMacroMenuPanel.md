# Update Macro

`haybale-haystack:panel:UpdateMacroMenuPanel` · kind: panel

Send a modified instance's changes back to the macro it came from.

## Details

- **surface**: `selection-macro`
- **order**: `30`

## Notes

Send a modified instance's changes back to the macro it came from.

Only visible on a Group that was detached from a macro. The card becomes a
placement of that macro again, and the macro opens in its own tab with the
instance's contents, unsaved. Saving it updates every placement.

Greyed out when the macro is not installed, cannot be edited in place, or
has unsaved edits in its tab.
