# Handoff: haybale-visiongraph adopts haybale-image's viewer widget

For the haybale-visiongraph session. Start once the haywire release carrying
`feat/view-image-mode-config` is out (the maintainer session will tell you).

## Why

`haybale_visiongraph.widgets` (`NumpyViewerWidget`, `StreamingViewer`/`StreamingBackend`,
`numpy_viewer.js`, ~550 lines) is a copy of what `haybale_image.widgets.image_viewer_widget.ImageViewerWidget`
grew from. Measured 2026-11-15: the stream pipeline and JS are identical; haybale-image's is the superset
(still mode, enlarge/pan/zoom, login-gated routes). The "visiongraph is snappier" report was View Image
defaulting to `still` mode, not the widget.

## Do

1. In `nodes/numpy_frame_display_node.py` replace
   `NumpyViewerWidget.config(properties={"quality": 85, "frame_queue_size": 1, "block_on_full": False})`
   with `ImageViewerWidget.config(properties={"mode": "stream", "quality": 85})`
   (`from haybale_image.widgets.image_viewer_widget import ImageViewerWidget`).
   `frame_queue_size`/`block_on_full` are not exposed there; the old values were its defaults.
2. Delete `widgets/numpy_viewer_widget.py`, `widgets/components/streaming_viewer.py`,
   `widgets/components/numpy_viewer.js`, and the `NumpyViewerWidget` export in `widgets/__init__.py`.
   `grep -rn NumpyViewerWidget` first: only `FrameDisplayNode` used it on 2026-11-15.
3. Raise the haybale-image floor in visiongraph's declarations to the released version (it already
   imports `haybale_image.value`).
4. Side effect to mention in the PR: visiongraph streams now sit behind the studio login gate.
5. Live check: a Syphon or camera stream into Frame Info Display, 30 fps, no jitter.
