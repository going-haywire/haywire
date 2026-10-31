# Image Info

`haybale-image:node:ImageInfoNode` · kind: node

Reports the width, height, channel layout and bit depth of an image

## Ports

| id | direction | type | description |
|---|---|---|---|
| `image` | inlet | `haybale-image:type:IMAGE` | A picture of any channel layout. Pixels are kept as made and converted on demand. |
| `width` | outlet | `haywire-core:type:INT` | Whole number |
| `height` | outlet | `haywire-core:type:INT` | Whole number |
| `layout` | outlet | `haywire-core:type:STRING` | Text data |
| `depth` | outlet | `haywire-core:type:INT` | Whole number |

## Notes

Reports the width, height, channel layout and bit depth of an `Image`.

- `Width`, `Height`: size in pixels.
- `Layout`: `gray`, `rgb` or `rgba`.
- `Depth`: bits per channel of the file the image was read from (8, 16 or 32).
