# Paste

`haybale-graph-editor:panel:PastePanel` · kind: panel

## Details

- **surface**: `graph-toolbar`
- **order**: `10`

## Notes

Paste at the click position, as an icon shortcut.

Declares no ``poll``: the OS clipboard is not readable synchronously at
poll time, so the shortcut is always shown and the handler reports
"Nothing to paste". There is deliberately no ``ctx.app.clipboard``
predicate to gate on.
