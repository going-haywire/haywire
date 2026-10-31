# Load Image

`haybale-image:node:LoadImageNode` · kind: node

Reads an image file from a volume

## Ports

| id | direction | type | description |
|---|---|---|---|
| `path` | inlet | `haywire-core:type:FILE_PATH` | A file inside a named volume such as the project folder or `models`. |
| `image` | outlet | `haybale-image:type:IMAGE` | A picture of any channel layout. Pixels are kept as made and converted on demand. |

## Notes

Reads an image file from a volume into an `Image`.

Gray files stay gray, files with transparency become RGBA and everything else
is RGB. The camera's rotation (EXIF orientation) is applied to the pixels on
load, because OpenCV's reader ignores it.
16-bit and float files are read at full precision; see Image Info's `Depth`.

The node reports an error naming the file when it is missing or is not an
image, and when `Path` leads to a volume that is not defined on this machine.

```
For Each File → Load Image → Image Info
```
