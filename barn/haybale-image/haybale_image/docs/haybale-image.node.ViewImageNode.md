# View Image

`haybale-image:node:ViewImageNode` · kind: node

Shows an image on the node, as a live stream or as a still picture

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `image` | inlet | `haybale-image:type:IMAGE` | A picture of any channel layout. Pixels are kept as made and converted on demand. |
| `next` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `image_out` | outlet | `haybale-image:type:IMAGE` | A picture of any channel layout. Pixels are kept as made and converted on demand. |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `mode` | viewer | `'still'` | stream for images that change often (a camera); still for large, rarely changing ones |
| `enlarge` | viewer | `3.0` | How many times wider the view gets when a still image is clicked |
| `zoom` | viewer | `1.0` | How many times the enlarged view's width the image shows; 1 fits it |

## Notes

Shows `Image` on the node and passes it on to `Image Out`.

- `Mode`: `stream` for images that change many times a second, such as a camera;
  `still` for large images that change rarely, such as a loaded file. A still
  image keeps its transparency.

Click a still image to enlarge the view: it gets `Enlarge view` times wider and
takes the image's shape, and the image shows `Zoom image` times the view's width
(1 fits it). Drag inside it to move around the image; click again to go back.

The view appears once `Image` is connected.

```text
Load Image → View Image (Mode = still)
```
