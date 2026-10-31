# ImageViewerWidget

`haybale-image:widget:ImageViewerWidget` · kind: widget

Shows an image, as a live stream or as a still picture

## Details

- **min_width**: `160`

## Notes

Shows the port's image.

Properties (`ImageViewerWidget.config(properties={...})`):

- `mode`: `stream` (default) sends every image as JPEG, for images that change
  many times a second; `still` sends the image as PNG only when the view asks for
  it, for large images that change rarely. Click a still image to see it at its
  natural size (1:1) and scroll it; click again to fit it.
- `quality`: JPEG quality in `stream` mode, 0 to 100 (default `80`).
- `frame_width`: CSS width of a border around the view (default `0`, none).
- `frame_color`: CSS color of that border (default `var(--hw-border)`).

`stream` shows nothing until the view is open, and RGBA images lose their
transparency. `still` keeps transparency and shows 8 bits per channel.

```python
self.add(IMAGE.as_inlet(
    "image",
    widget=ImageViewerWidget.config(properties={"mode": "still"}),
))
```
