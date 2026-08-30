# Agent activity

`haybale-studio:panel:OpenActivityPanel` · kind: panel

## Details

- **surface**: `account`
- **order**: `20`

## Notes

Opens the ActivityEditor.

The entry point lives here rather than on the TopBar's agent chip: the chip
is core's (``haywire.ui.app.shell``) and the editor is this library's, so a
chip click could only reach it by resolving a registry key hardcoded in
core — a dependency pointing the wrong way. A panel against
``AccountMenu`` inverts it: the library that owns the editor is also the
one that names it, and core stays unaware the editor exists.

VIEW access matches the editor's own: what the agents in this studio are
doing is useful to every collaborator.
