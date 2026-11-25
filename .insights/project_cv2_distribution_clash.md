---
name: cv2 distributions clash — opencv-python, -contrib-python and -headless share one cv2/ package
description: The three opencv wheels install into the same cv2/ directory; the last install wins, silently. visiongraph 1.2.0 pulled in opencv-python beside contrib; 1.3.0 depends on contrib and removes the clash.
type: project
---

`opencv-python`, `opencv-contrib-python` and `opencv-contrib-python-headless` all install into one `cv2/` package. Whichever was installed last owns the files; pip/uv see the distributions as healthy and say nothing.

haybale-image declares `opencv-contrib-python>=4.13.0.90` and never the other two. The floor is AVIF: 4.10 and 4.11 are built without libavif, and 4.12.0.88 has it but cannot encode grayscale AVIF; 4.13.0.90 is the first wheel that passes `tests/image`. It was once `>=5.0.0.93` with no reason recorded; it was never visiongraph's floor.

The clash came from upstream `visiongraph` up to 1.2.0, which depends on plain `opencv-python`: installed next to haybale-image, it put 4.x over contrib, or contrib over it, depending on install order (`uv pip install -e ../haybale-visiongraph/...`, or `uv sync`). visiongraph 1.3.0 depends on `opencv-contrib-python~=4.12` itself, which removes the clash at its source. Any other package that requires plain `opencv-python` or `-headless` brings it back.

Check: `tests/image/test_library.py::test_no_plain_opencv_beside_contrib` fails when a plain distribution sits beside contrib, and `uv run python -c "import cv2; print(cv2.__version__, hasattr(cv2, 'ximgproc'))"` must print `True`. Repair: `uv pip uninstall opencv-python opencv-python-headless opencv-contrib-python && uv pip install opencv-contrib-python` (the version the lock names: `uv sync` then restores it), then find which package asked for the plain wheel.
