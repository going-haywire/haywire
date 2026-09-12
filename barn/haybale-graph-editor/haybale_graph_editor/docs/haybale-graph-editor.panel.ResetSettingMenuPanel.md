# Reset to default

`haybale-graph-editor:panel:ResetSettingMenuPanel` · kind: panel

## Details

- **surface**: `pin`
- **order**: `15`

## Notes

Put the backing setting back to its declared default, from the pin.

The Properties row has offered this all along; the pin had not, which was
a real gap once a promoted pin can carry its own editable widget: a value
typed into the widget on the card could only be undone somewhere else.

Greyed rather than hidden on a clean or unpromoted pin — the convention
every panel on this surface follows, and load-bearing here for the same
reason ``DetachSettingMenuPanel`` documents: this surface needs at least
one leaf or the popup is deleted entirely.
