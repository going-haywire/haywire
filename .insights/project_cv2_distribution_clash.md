---
name: cv2 distributions clash — opencv-python, -contrib-python and -headless share one cv2/ package
description: The three opencv wheels install into the same cv2/ directory; the last install wins, silently. Dev .venv carries 4.x and contrib 5.x together.
type: project
---

`opencv-python`, `opencv-contrib-python` and `opencv-contrib-python-headless` all install into one `cv2/` package. Whichever was installed last owns the files; pip/uv see three healthy distributions and say nothing.

The dev `.venv` carries `opencv-python` 4.x (required by upstream `visiongraph`) beside `opencv-contrib-python` 5.x. Contrib wins only by install order, so a reinstall of visiongraph (`uv pip install -e ../haybale-visiongraph/...`, or `uv sync`) pulls 4.x over it and `cv2` silently becomes 4.x.

haybale-image declares `opencv-contrib-python>=5.0.0.93` (visiongraph's floor) and never the other two.

Check: `uv run python -c "import cv2; print(cv2.__version__, hasattr(cv2, 'ximgproc'))"` must print 5.x and `True`. Repair: `uv pip uninstall opencv-python opencv-contrib-python && uv pip install opencv-contrib-python==5.0.0.93`.
