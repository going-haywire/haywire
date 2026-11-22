# haybale-image — component index (v0.6.0)

## node
- `haybale-image:node:ImageEventNode` — Image Event — Triggered for each image a connected image emitter delivers  _tags: image, frame, event, callback, receive, stream, camera_
- `haybale-image:node:ImageInfoNode` — Image Info — Reports the width, height, channel layout and bit depth of an image  _tags: image, info, size, width, height, layout, depth, channels_
- `haybale-image:node:LoadImageNode` — Load Image — Reads an image file from a volume  _tags: image, load, open, read, file, png, jpg, tiff, import_
- `haybale-image:node:SaveImageNode` — Save Image — Writes an image to a file in a volume, in the format its extension names  _tags: image, save, write, export, file, png, jpg, tiff, webp_
- `haybale-image:node:ViewImageNode` — View Image — Shows an image on the node, as a live stream or as a still picture  _tags: image, view, show, preview, display, viewer, stream_

## type
- `haybale-image:type:DEPTH_BUFFER` — Depth Buffer — A depth buffer, one value per pixel in millimetres.
- `haybale-image:type:GRAY_IMAGE` — Gray Image — A one-channel picture.
- `haybale-image:type:IMAGE` — Image — A picture of any channel layout. Pixels are kept as made and converted on demand.
- `haybale-image:type:IMAGE_CALLBACK` — Image Callback — Subscription for emitters that deliver single images
- `haybale-image:type:RGBA_IMAGE` — RGBA Image — A picture with three colour channels and transparency.
- `haybale-image:type:RGB_IMAGE` — RGB Image — A three-channel picture.

## adapter
- `haybale-image:adapter:ImageToGrayAdapter` — ImageToGrayAdapter — Convert an image to gray
- `haybale-image:adapter:ImageToRgbAdapter` — ImageToRgbAdapter — Convert an image to RGB
- `haybale-image:adapter:ImageToRgbaAdapter` — ImageToRgbaAdapter — Convert an image to RGBA

## widget
- `haybale-image:widget:ImageViewerWidget` — ImageViewerWidget — Shows an image, as a live stream or as a still picture

## setting
- `haybale-image:setting:ImageSettings` — Image — Defaults for saving images

## panel
- `haybale-image:panel:ImageSettingsPanel` — Image — Defaults for saving images.
