# Image Info

`haybale-image:node:ImageInfoNode` · kind: node

Reports the width, height, channel layout and bit depth of an image

## Ports

| id | direction | type | description |
|---|---|---|---|
| `image` | inlet | `haybale-image:type:IMAGE` | Image to describe |
| `width` | outlet | `haywire-core:type:INT` | Width in pixels |
| `height` | outlet | `haywire-core:type:INT` | Height in pixels |
| `layout` | outlet | `haywire-core:type:STRING` | Channels: gray, rgb or rgba |
| `depth` | outlet | `haywire-core:type:INT` | Bits per channel of the source file, such as 8 or 16 |

## Notes

Reports the width, height, channel layout and bit depth of an `Image`.

- `Width`, `Height`: size in pixels.
- `Layout`: `gray`, `rgb` or `rgba`.
- `Depth`: bits per channel of the file the image was read from (8, 16 or 32).
