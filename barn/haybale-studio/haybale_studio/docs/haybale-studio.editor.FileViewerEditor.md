# File Viewer

`haybale-studio:editor:FileViewerEditor` · kind: editor

Displays the contents of a file selected in the Files browser.

## Details

- **default_slot**: `edit`
- **opens**: `OpenBehavior.ON_PAYLOAD`
- **order**: `100`

## Notes

Renders file contents in the middle area.

Responds to FILE_SELECTED events. Supports syntax-highlighted code
(via ui.code), rendered markdown, and plain text. Binary files and
files over 512 KB show an informational message.
