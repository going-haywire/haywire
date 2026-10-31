# Save Image

`haybale-image:node:SaveImageNode` · kind: node

Writes an image to a file in a volume, in the format its extension names

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `image` | inlet | `haybale-image:type:IMAGE` | A picture of any channel layout. Pixels are kept as made and converted on demand. |
| `path` | inlet | `haywire-core:type:FILE_PATH` | A file inside a named volume such as the project folder or `models`. |
| `if_exists` | config | `haywire-core:type:STRING` | Text data |
| `depth` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `saved` | outlet | `haywire-core:type:FILE_PATH` | A file inside a named volume such as the project folder or `models`. |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `compression` | png | `None` | Compression of saved PNG files, from 0 (fastest) to 9 (smallest); never loses detail |
| `quality` | jpeg | `None` | Quality of saved JPEG files, from 0 (smallest) to 100 (best) |
| `quality` | webp | `None` | Quality of saved WebP files, from 0 (smallest) to 100 (best) |
| `lossless` | webp | `None` | Save WebP files without losing detail; WebP quality is then ignored |
| `compression` | tiff | `None` | Compression of saved TIFF files; none of them loses detail |
| `quality` | avif | `None` | Quality of saved AVIF files, from 0 (smallest) to 100 (best) |

## Notes

Writes `Image` to the file at `Path`, in the format its extension names.

Known extensions: `.png`, `.jpg`/`.jpeg`, `.webp`, `.tif`/`.tiff`, `.bmp`, `.gif`,
`.tga`, `.avif`. The file appears complete or not at all; a half-written file is
never left behind.

- `If Exists`: what to do when the file is already there. `overwrite` replaces
  it, `skip` keeps it and writes nothing, `unique-suffix` saves beside it as
  `name_1.png`, `name_2.png`, and so on.
- `Depth`: `source` keeps the image's own bit depth; `8`, `16` and `32` (float)
  ask for that depth. A format that cannot store it gets the deepest it can
  (JPEG is always 8-bit, PNG at most 16-bit). 16-bit and float saves drop the
  image's ICC profile and EXIF block.

`Saved` is the file that now holds the image: the suffixed name for
`unique-suffix`, and the existing file for `skip`.

The quality and compression settings default to the library's *Image* settings;
change them here for this node only. Only the settings of the format `Path` names
are shown.

The folder must already exist; add Create Folder before Save Image to make it.
An empty image, an unknown extension and a volume that is not defined on this
machine are reported as errors.

```text
For Each File → Load Image → … → Save Image (Path = Output Path)
```
