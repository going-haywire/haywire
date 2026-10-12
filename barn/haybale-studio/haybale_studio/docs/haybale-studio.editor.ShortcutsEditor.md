# Shortcuts

`haybale-studio:editor:ShortcutsEditor` · kind: editor

Keyboard shortcuts of every editor, grouped by editor.

## Details

- **default_slot**: `context`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `60`

## Notes

Lists the keyboard shortcuts of every editor, one collapsible group per editor.

The group of the editor that receives key presses opens and carries an
`active` tag; the other groups close. Clicking into an editor without
shortcuts, this one included, leaves the open group as it is. A command
that loses a key to another command of the same editor is marked with the
command that holds the key.
