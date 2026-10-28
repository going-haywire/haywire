# History

`haybale-graph-editor:editor:HistoryEditor` · kind: editor

The undo history of the active graph's file: every step, who recorded it, and where.

## Details

- **default_slot**: `context`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `70`

## Notes

Lists the undo history of the file the active graph belongs to, newest step on top.

The list covers the whole file: a step inside a Group or macro interior shows
the interior's path. Each step names who recorded it — a session (principal and
a short session id) or a Farmhand call. Steps past the undo marker are dimmed:
Redo would apply them again. The marker names who last moved it. Steps still
waiting in the grouping window are tagged `pending`; a closing fence shows as
a divider. Click a row to see its details; click a group to see its steps.

The list is read-only: it does not undo or redo.
