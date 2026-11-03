# Load Image

`haybale-image:node:LoadImageNode` · kind: node

Reads an image file from a volume

## Ports

| id | direction | type | description |
|---|---|---|---|
| `path` | inlet | `haywire-core:type:FILE_PATH` | Image file to read |
| `progress.main` | config | `haywire-core:type:PROGRESS` |  |
| `image` | outlet | `haybale-image:type:IMAGE` | The decoded image |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `main` | progress | `PROGRESS(active=False, fraction=None, label='')` |  |

## Notes

Reads an image file from a volume into an `Image`.

Gray files stay gray, files with transparency become RGBA and everything else
is RGB. The camera's rotation (EXIF orientation) is applied to the pixels on
load, because OpenCV's reader ignores it.
16-bit and float files are read at full precision; see Image Info's `Depth`.

The Loading bar shows while the file is read and decoded.

The node reports an error naming the file when it is missing or is not an
image, and when `Path` leads to a volume that is not defined on this machine.

```
For Each File → Load Image → Image Info
```
