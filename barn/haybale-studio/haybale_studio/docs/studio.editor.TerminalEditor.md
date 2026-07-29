# Log

`studio:editor:TerminalEditor` · kind: editor

Application output. Captures Python logging and print() output.

## Details

- **default_slot**: `info`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `100`

## Notes

Renders a scrollable log panel capturing both Python logging and stdout.

`registry_id` must stay pinned to the old "TerminalEditor" class name: it
defaults to the class name and `registry_key` derives from it, and slot
layout is persisted by that wire string in `.haywire/workspace_state.json`.
Dropping the pin would silently orphan every existing user's bottom-slot
layout.
