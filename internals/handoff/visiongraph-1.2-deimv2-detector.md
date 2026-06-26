# Handoff — Re-add DEIMv2 detector once visiongraph ≥1.2.0 is reachable

**Status:** deferred by decision. The estimator nodes shipped against the
**installed visiongraph 1.1.0.1**; the DEIMv2 detector models were intentionally
left out because DEIMv2 does not exist in 1.1.0.1.

**Type:** small follow-up to the haybale-visiongraph estimator nodes (one node's
`MODELS` dict + a dependency bump). Not started.

## The situation

- `barn/haybale-visiongraph/pyproject.toml` depends on `visiongraph[all]`
  (unpinned). The resolved/installed version in `.venv` is **1.1.0.1** (latest on
  PyPI as of this writing — PyPI tops out at 1.1.0.1).
- A **newer, unpublished visiongraph 1.2.0** lives in a local checkout at
  `/Volumes/Ddrive/03_personal/visiongraph` (GitLab remote
  `git@gitlab.zhdk.ch:iaspace/07_libraries/visiongraph.git`). It adds
  `visiongraph/estimator/spatial/DEIMv2Detector.py` (`DEIMv2Detector` +
  `DEIMv2Config`). 1.2.0 is **not on PyPI**.
- Because 1.2.0 isn't installed, the two DEIMv2 entries I had drafted failed to
  resolve, so they were removed from `ObjectDetectorNode.MODELS`
  (`barn/haybale-visiongraph/haybale_visiongraph/nodes/object_detector_node.py`).
  Everything else (YOLOv8-N/S/M, SSDLite, segmentation, pose) is correct for the
  installed version.

## What to do when visiongraph ≥1.2.0 is reachable

1. **Make 1.2.0 available**, by whichever path was chosen by then:
   - editable local install: `uv pip install -e '/Volumes/Ddrive/03_personal/visiongraph[all]'`; or
   - pin to a GitLab tag/commit in `barn/haybale-visiongraph/pyproject.toml`
     (`visiongraph[all] @ git+ssh://git@gitlab.zhdk.ch/iaspace/07_libraries/visiongraph.git@<tag>`); or
   - once published: bump the dep to `visiongraph[all]>=1.2.0`.

2. **Re-add the DEIMv2 models** to `ObjectDetectorNode.MODELS`. The node uses
   lazily-resolved `ModelSpec(module, cls_name, config_cls_name, variant)` strings
   (no import until first frame), so just add:

   ```python
   "DEIMv2-Pico (COCO)": ModelSpec(
       "visiongraph.estimator.spatial.DEIMv2Detector",
       "DEIMv2Detector", "DEIMv2Config", "DEIMv2_HgNetv2_Pico_COCO",
   ),
   "DEIMv2-N (COCO)": ModelSpec(
       "visiongraph.estimator.spatial.DEIMv2Detector",
       "DEIMv2Detector", "DEIMv2Config", "DEIMv2_HgNetv2_N_COCO",
   ),
   ```

   Confirm the variant member names against the resolved 1.2.0 (they were
   `DEIMv2_HgNetv2_Pico_COCO` / `DEIMv2_HgNetv2_N_COCO` in the source tree; the
   enum also has `…_Atto_…`, `…_Femto_…` if you want more).

3. **Validate** the specs resolve against the *installed* package (this is the
   exact check that caught the gap — run it again):

   ```python
   import importlib
   from haybale_visiongraph.nodes.object_detector_node import ObjectDetectorNode
   for label, spec in ObjectDetectorNode.MODELS.items():
       mod = importlib.import_module(spec.module)
       getattr(getattr(mod, spec.config_cls_name), spec.variant)   # raises if wrong
   ```

4. Run `/haywire-dep-check` (the visiongraph version source may have changed) and
   `uv run ruff check . && uv run mypy <pkg> && uv run pytest -m "not integration"`.

## Related: optional-backend deps in dev

Separately observed during the build (not blocking, just context): several models
need optional backends that `visiongraph[all]` declares but the current dev `.venv`
only partially has — `openvino` (SSDLite, MaskRCNN, MoveNet) and `mediapipe`
(MediaPipe Pose, via `mediapipe-numpy2`). On a full `uv pip install -e .` of the
library these arrive. If the **Pose Estimator** node shows "Load error: No module
named 'mediapipe'/'openvino'" for every model, that's the cause — install
`visiongraph[all]` completely, don't change the node. The lazy-load design surfaces
this as a status-label message rather than a crash, by design.

## Provenance

The estimator-node design and rationale are in
`barn/haybale-visiongraph/notes.md` (Q1–Q15). This handoff covers only the DEIMv2 /
version gap deferred at implementation time.

## Suggested skills

- **`haywire-dep-check`** — after changing how visiongraph is sourced/pinned.
- **`verify`** — full lint/type/test pass before claiming done.
