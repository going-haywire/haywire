# View Image

`haybale-image:node:ViewImageNode` · kind: node

Shows an image on the node, as a live stream or as a still picture

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `image` | inlet | `haybale-image:type:IMAGE` | A picture of any channel layout. Pixels are kept as made and converted on demand. |
| `mode` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `image_out` | outlet | `haybale-image:type:IMAGE` | A picture of any channel layout. Pixels are kept as made and converted on demand. |

## Notes

Shows `Image` on the node and passes it on to `Image Out`.

- `Mode`: `stream` for images that change many times a second, such as a camera;
  `still` for large images that change rarely, such as a loaded file. A still
  image keeps its transparency; click it to see it at its natural size (1:1),
  and click again to fit it.

The view appears once `Image` is connected.

```text
Load Image → View Image (Mode = still)
```
