# Visiongraph on Image Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace visiongraph's `RGB_FRAME`, `GRAY_FRAME` and `DEPTH_FRAME` with `IMAGE_RGB`, `IMAGE_GRAY` and `DEPTH`.

**Architecture:** Cameras wrap their buffers without copying (`ImageValue.from_array(..., order=BGR)`), and the event node stamps timestamp and frame number as fields. Consumers ask for BGR `uint8`, which returns the camera buffer itself, read-only.

**Tech Stack:** Python 3.12, numpy, OpenCV, visiongraph, DepthAI.

**Spec:** [2026-11-06-carrier-metadata-design.md](2026-11-06-carrier-metadata-design.md)

## Global Constraints

- Requires Plan A released; set `haybale-image` and `haywire-core` floors to that version. For local work, the editable installs are enough.
- Repo: `../haybale-visiongraph`, package at `barn/haybale-visiongraph/haybale_visiongraph`. All paths below are relative to that package.
- Field keys: `camera_timestamp` (FLOAT), `camera_frame_number` (INT).
- Inlets `frame` and outlets `rgb`, `depth`, `ir` keep their ids, so edges survive.
- `linked_libraries` takes module names: add `haybale_image`. Declare `haybale-image` in `pyproject.toml` too.
- Never commit without the user's explicit consent. The user pushes.

## Review Focus

1. An estimator that writes into its input: `array()` is read-only, so this now raises instead of corrupting the frame. Test in Task 2.
2. A gray or RGBA image wired into an estimator: the `IMAGE_RGB` inlet converts it, as `GRAY_FRAME` did. Test in Task 2.
3. A frame reaching a viewer with no pixels: the viewer shows nothing and does not raise. Test in Task 3.
4. A graph saved with the old type keys and not migrated: it opens with visible errors and no crash. Test in Task 4.
5. A frame with no stamped fields, as from Load Image, reaching the Display node: it shows frame 0 and raises nothing. Test in Task 3.

---

### Task 1: Event node produces image values

**Files:**
- Modify: `nodes/numpy_frame_event_node.py:170-177`, `:221-243`
- Modify: `haybale.toml`, `../pyproject.toml`
- Test: `../../../tests/test_frame_values.py`

**Interfaces:**
- Consumes: `ImageValue.from_array`, `ChannelOrder.BGR`, `DepthValue.from_array`, `CarrierValue.stamped` from Plan A.
- Produces: `hb_wrap_streams(payload: dict) -> dict[str, CarrierValue]` on the event node, with `rgb` as BGR, `ir` as gray, `depth` as `DepthValue`, each stamped.

- [ ] **Step 1: Write the failing tests**

```python
def test_rgb_wraps_without_copying_and_is_bgr(event_node):
    buf = np.zeros((2, 2, 3), np.uint8); buf[..., 0] = 200  # blue
    out = event_node.hb_wrap_streams({"rgb": buf, "timestamp": 1.5, "frame_number": 7})["rgb"]
    assert np.shares_memory(out.array(np.uint8, ChannelOrder.BGR), buf)
    assert out.array(np.uint8, ChannelOrder.RGB)[0, 0, 2] == 200

def test_fields_are_stamped_on_every_stream(event_node):
    payload = {"rgb": np.zeros((2, 2, 3), np.uint8), "depth": np.zeros((2, 2), np.uint16),
               "ir": np.zeros((2, 2), np.uint8), "timestamp": 1.5, "frame_number": 7}
    for value in event_node.hb_wrap_streams(payload).values():
        assert value.fields["camera_timestamp"].value == 1.5
        assert value.fields["camera_frame_number"].value == 7

def test_a_missing_stream_is_left_out(event_node):
    assert set(event_node.hb_wrap_streams({"rgb": np.zeros((2, 2, 3), np.uint8)})) == {"rgb"}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_frame_values.py -q`, from the visiongraph repo.
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Implement**

Outlets become `IMAGE_RGB`, `DEPTH`, `IMAGE_GRAY`. The existing `timestamp` and `frame_number` outlets stay. Payload producers `web_cam_node.py:385` and `oak_d_camera_node.py:689-693` are unchanged.

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/test_frame_values.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-visiongraph tests/test_frame_values.py
git commit -m "feat: camera event node outputs image values with stamped fields"
```

### Task 2: Estimators and Annotate

**Files:**
- Modify: `nodes/base_estimator_node.py:197-203`, `:435-453`
- Modify: `nodes/annotate_node.py:158-181`, `:185-235`
- Modify: `../../../tests/test_estimator_models.py:183-188`
- Test: `../../../tests/test_frame_values.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_estimator_gets_bgr_uint8_and_the_empty_image_is_refused(...):
    # fake estimator records its input: dtype uint8, BGR order; empty image -> "No valid frame", no call

def test_estimator_writing_into_its_input_raises_not_corrupts(...):
    # fake process() writes to the array -> ValueError surfaces, source buffer unchanged

def test_gray_reaches_an_estimator_through_the_adapter(...):
    # IMAGE_GRAY outlet -> frame inlet, edge functional, process() sees H×W×3

def test_annotate_keeps_fields_and_does_not_touch_the_input(...):
    # stamped input; output differs, input pixels unchanged, output carries camera_timestamp
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_frame_values.py tests/test_estimator_models.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

Inlets become `IMAGE_RGB`. Validity is `frame is not None and not frame.is_empty`. `estimator.process(frame.array(np.uint8, ChannelOrder.BGR))`. If a real visiongraph estimator writes into its input, copy at that one call and note it; do not copy for all of them. Annotate: `frame.array(np.uint8, BGR).copy()`, then `frame.derive(ImageValue.from_array(image, order=BGR, source_depth=frame.source_depth)).with_fields(frame.fields)`, since drawing keeps the frame's facts true.

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-visiongraph tests
git commit -m "feat: estimators and Annotate read IMAGE_RGB"
```

### Task 3: Display node and viewer, and removal

**Files:**
- Modify: `nodes/numpy_frame_display_node.py:12`, `:44-77`, `:96-131`
- Modify: `widgets/numpy_viewer_widget.py:79-80`
- Delete: `types/frame_type.py`, `adapters/frame_adapters.py`
- Modify: `types/__init__.py:1,14-17`
- Test: `../../../tests/test_frame_values.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_display_reads_stamped_facts(...):
    # stamped 7 and 1.5, 4×2 RGB -> info contains "#7", "4x2x3"; frame_number outlet 7

def test_display_without_fields_shows_zero_and_does_not_raise(...):

def test_viewer_encodes_bgr_from_an_image_value(...):
def test_viewer_ignores_an_empty_image(...):

def test_the_frame_types_are_gone():
    with pytest.raises(ImportError):
        from haybale_visiongraph.types.frame_type import RGB_FRAME
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_frame_values.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

Remove the display node's raw-ndarray branch: the inlet is now `IMAGE_RGB`. `frame_pass` is `IMAGE_RGB`. The viewer calls `frame.array(np.uint8, ChannelOrder.BGR)`. Grep for `RGB_FRAME`, `BaseFrame` and `frame.data` across the package and `QUICKREF.md`, and fix what remains.

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/ -q && uv run haywire docs barn/haybale-visiongraph`
Expected: PASS, docs generated.

- [ ] **Step 5: Commit**

```bash
git add -A barn/haybale-visiongraph tests
git commit -m "feat!: remove RGB_FRAME, GRAY_FRAME and DEPTH_FRAME"
```

### Task 4: Graphs

**Files:**
- Modify: `graphs/webcam.haywire` (visiongraph repo); `graphs/webcam.haywire`, `graphs/oakNwebCam.haywire` (haywire-repo)
- Modify if it fails: `tests/core/test_graph/fixtures/prehydration/webcam.haywire` (haywire-repo)
- Test: `../../../tests/test_frame_values.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize("path", GRAPHS)
def test_a_migrated_graph_loads_with_working_frame_edges(path, library_system):
    # load_from_dict; no ErrorNode; every edge touching a frame pin is_functional()

def test_an_unmigrated_graph_opens_without_a_crash(library_system):
    # document with registry_key "haybale-visiongraph:type:RGB_FRAME": load returns True, the edge reports an error
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_frame_values.py -q -k graph`
Expected: FAIL on the first test.

- [ ] **Step 3: Migrate with a one-off script in `.scratch/` (not committed)**

In each port dict with an old type: replace `registry_key`, `registry_id`, `class_name`, `module`, `label`, `color` from the new type's `class_identity`; set `default` to the new type's default; update the `recipe`. There is no migration hook (ADR 0033), and the library is pre-1.0, so old graphs are not otherwise supported.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/ -q`, then in haywire-repo `uv run pytest tests/core/test_graph/test_prehydration.py -q`
Expected: PASS.

- [ ] **Step 5: Live check, mark done, commit**

With a webcam, use the `haywire-live-studio` skill: the preview shows correct colours (red stays red), an estimator detects and Annotate draws, Display shows a rising frame number. Compare frame rate with the old version; report any drop. Set the Plan B row in the design's table to done, then commit in both repos.

```bash
git add graphs tests
git commit -m "chore: move graphs to image types"
```
