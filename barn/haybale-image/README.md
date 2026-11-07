# Image

<!-- marketstall:share-url:start -->
*Subscribe URL not yet published — run `haywire share --save`.*
<!-- marketstall:share-url:end -->

Image types, IO and viewers shared by vision and ML libraries

## Nodes
### Image
- **Image Info** — Reports the width, height, channel layout and bit depth of an image
- **Load Image** — Reads an image file from a volume
- **Save Image** — Writes an image to a file in a volume, in the format its extension names
- **View Image** — Shows an image on the node, as a live stream or as a still picture

## Types
- **Depth** — A depth map, one value per pixel in millimetres.
- **Gray image** — A one-channel picture.
- **Image** — A picture of any channel layout. Pixels are kept as made and converted on demand.
- **RGB image** — A three-channel picture.
- **RGBA image** — A picture with three colour channels and transparency.

## Adapters
- **ImageToGrayAdapter** — Convert an image to gray
- **ImageToRgbAdapter** — Convert an image to RGB
- **ImageToRgbaAdapter** — Convert an image to RGBA

## Widgets
- **ImageViewerWidget** — Shows an image, as a live stream or as a still picture

## Settings
- **Image** — Defaults for saving images

## Panels
- **Image** — Defaults for saving images.
