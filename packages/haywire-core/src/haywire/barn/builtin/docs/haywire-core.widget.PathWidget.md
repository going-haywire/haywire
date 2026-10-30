# PathWidget

`haywire-core:widget:PathWidget` · kind: widget

Pick a file or folder inside a volume

## Details

- **min_width**: `200`

## Notes

Pick a file or folder inside a volume such as the project folder or `models`.

Choose the volume, then type the path inside it or browse to it. The line
below shows where the path points on this machine, cropped in the middle to
fit (hover for the full path), or what is wrong: a volume that is not
defined here, a volume whose folder is missing (an unplugged drive, say), or
a path that leaves its volume (`..` is not allowed). Volumes are added in
the Volumes editor.

Options (in `properties`):

- `mode`: `"file"` (default) picks an existing file, `"folder"` a folder,
  `"save"` a folder plus a file name typed in the browser.
- `extensions`: file endings such as `".png"` that the browser shows in
  `file` and `save` mode; empty shows every file.

```python
PathWidget.config(properties={"mode": "folder"})
PathWidget.config(properties={"mode": "file", "extensions": [".png", ".jpg"]})
```
