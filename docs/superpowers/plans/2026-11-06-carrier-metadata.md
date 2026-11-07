# Carrier Types and Metadata Nodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any carrier value hold named fields, stamped and read through Metadata node pins declared in settings.

**Architecture:** A hidden `CARRIER` type and a `CarrierValue` class live in the core builtin library; `IMAGE`, the new `DEPTH` and the new `BUNDLE` derive from them. A `FIELD_LIST` settings type with its own widget declares fields, and a change rebuilds the node's pins through `rejig`, so saving and undo use the existing settings path.

**Tech Stack:** Python 3.12, NiceGUI, numpy, pytest, Playwright.

**Spec:** [2026-11-06-carrier-metadata-design.md](2026-11-06-carrier-metadata-design.md)

## Global Constraints

- Keys match `^[a-zA-Z0-9_]+$`, case-sensitive.
- Pin ids: `<key>_in`, `<key>_out`, `carrier_inlet`, `carrier_outlet`.
- `FIELD_LIST` settings use `Promotable.NONE`.
- Mismatch text: `Field 't' holds FLOAT, this pin reads STRING` (with the actual key and type names).
- No relative imports under `barn/`. Docstrings follow `.claude/rules/python-docs.md`.
- Never commit without the user's explicit consent; each "Commit" step waits for it.
- `tests/studio/test_docs/test_generate.py` reverts uncommitted edits under `barn/haybale-testing`; do not put work there.
- Take node keys from `Cls.class_identity.registry_key` and `isinstance`-check the node: an unknown key silently gives an `ErrorNode`.
- Undo tests run with merging and grouping on (`Editor(graph, factory)` defaults).

## Review Focus

1. A key that was present on an earlier frame and is absent now: the outlet must not keep the old value. Test in Task 6.
2. Two branches from one carrier: a stamp on one must not appear on the other or upstream. Test in Task 1.
3. A saved entry whose type's library is not installed: the node must still load and keep the entry for later. Test in Task 5.
4. A hand-edited graph with bad or duplicate keys: construction must not raise. Test in Task 3.
5. Saving with a removed field's wires still in the graph, then loading: no crash, and re-adding the key relinks. Test in Task 5.

---

### Task 1: `CarrierValue`, `CARRIER` and `BUNDLE`

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/carrier.py`
- Create: `packages/haywire-core/src/haywire/barn/builtin/types/carrier.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py`
- Test: `tests/barn/builtin/test_carrier.py`

**Interfaces:**
- Produces, in `carrier.py`:
  - `Stamp`: frozen dataclass with `value: Any`, `type_key: str`
  - `class CarrierValue` with `__slots__ = ("_fields",)`; `__init__()`; `fields -> Mapping[str, Stamp]` (read-only); `with_fields(fields: Mapping[str, Stamp]) -> Self`; `stamped(key: str, value: Any, type_cls: type[IType]) -> Self`; `describe() -> dict[str, str]`, default `{}`
  - `class BundleValue(CarrierValue)` with `__slots__ = ()`
- Produces, in `types/carrier.py`: `CARRIER`, `BUNDLE`, `CarrierField`, each type with classmethod `empty_value() -> CarrierValue`.

- [ ] **Step 1: Write the failing tests**

```python
def test_stamping_returns_a_new_carrier_and_leaves_the_original_alone():
    base = BundleValue()
    one = base.stamped("t", 1.5, FLOAT)
    other = base.stamped("x", 2, INT)
    assert dict(base.fields) == {}
    assert one.fields["t"] == Stamp(1.5, FLOAT.class_identity.registry_key)
    assert "x" not in one.fields
    assert "t" not in other.fields

def test_fields_cannot_be_written_through_the_mapping():
    with pytest.raises(TypeError):
        BundleValue().fields["t"] = Stamp(1, "k")

def test_bundle_is_a_carrier_and_starts_empty():
    assert issubclass(BUNDLE, CARRIER)
    assert isinstance(BUNDLE.create_field().get_value(), BundleValue)

def test_carrier_values_are_never_saved():
    assert BUNDLE.class_identity.store_strategy is StoreStrategy.NEVER

def test_carrier_is_hidden_and_bundle_is_visible():
    assert CARRIER.class_identity.hidden is True
    assert BUNDLE.class_identity.hidden is False
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/barn/builtin/test_carrier.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement both modules**

`with_fields` uses `copy.copy(self)` and replaces `_fields`, so a subclass needs no override. `fields` returns a `MappingProxyType`. `CARRIER` derives from `PrimitiveType[CarrierValue]`, uses `DataWire`, `store_strategy=StoreStrategy.NEVER`, `default={"value": {}}`, `hidden=True`. `CarrierField(PrimitiveField)` follows `IMAGEField` in `barn/haybale-image/haybale_image/types/image.py`: a JSON default becomes `type_cls.empty_value()`. `to_dict` gives `{"value": {}}`; `from_dict` gives the empty value. `BUNDLE` derives from `CARRIER` and sets `element_type_cls = BundleValue`.

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/barn/builtin/test_carrier.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin tests/barn/builtin/test_carrier.py
git commit -m "feat(types): CARRIER, BUNDLE and carrier fields"
```

### Task 2: `IMAGE` and `ImageValue` become carriers

**Files:**
- Modify: `barn/haybale-image/haybale_image/types/image.py:27`
- Modify: `barn/haybale-image/haybale_image/value/image_value.py`
- Modify: `barn/haybale-image/haybale_image/value/layout.py`
- Test: `tests/image/test_image_fields.py`

**Interfaces:**
- Consumes: `CarrierValue`, `CARRIER` from Task 1.
- Produces: `ImageValue(CarrierValue)`; `describe()` returns `icc: <n> bytes` and `exif: <n> bytes` for whichever is present.

- [ ] **Step 1: Write the failing tests**

```python
def _img():
    return ImageValue.from_array(np.zeros((2, 2, 3), np.uint8))

def test_with_metadata_keeps_fields_and_the_cache():
    a = _img().stamped("t", 1.5, FLOAT)
    a.array()
    b = a.with_metadata(ImageMetadata(icc=b"x"))
    assert b.fields["t"].value == 1.5
    assert b._cache is a._cache

def test_derive_keeps_icc_and_drops_fields():
    src = _img().with_metadata(ImageMetadata(icc=b"x")).stamped("t", 1.5, FLOAT)
    out = src.derive(_img())
    assert out.metadata.icc == b"x"
    assert dict(out.fields) == {}

def test_convert_layout_keeps_fields_and_metadata():
    src = _img().with_metadata(ImageMetadata(icc=b"x")).stamped("t", 1.5, FLOAT)
    out = convert_layout(src, Layout.GRAY)
    assert out.fields["t"].value == 1.5
    assert out.metadata.icc == b"x"

def test_fields_do_not_change_the_saved_file():
    img = _img()
    options = EncodeOptions()
    assert encode_image(img.stamped("t", 1.5, FLOAT), Format.PNG, options) == encode_image(img, Format.PNG, options)

def test_describe_lists_icc_and_exif_sizes():
    img = _img().with_metadata(ImageMetadata(icc=b"abc"))
    assert img.describe() == {"icc": "3 bytes"}

def test_image_types_are_carriers_with_unchanged_keys():
    assert issubclass(IMAGE_RGB, CARRIER)
    assert IMAGE.element_type_cls is ImageValue
    assert IMAGE.class_identity.registry_key == "haybale-image:type:IMAGE"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/image/test_image_fields.py -q`
Expected: FAIL with `AttributeError` on `stamped`.

- [ ] **Step 3: Implement**

`class IMAGE(CARRIER)` with `element_type_cls = ImageValue` in its body; everything else in `types/image.py` stays. `ImageValue.__init__` calls `super().__init__()`. `with_metadata` uses `copy.copy` and sets `_metadata`, which keeps `_fields` and `_cache`. `derive` is unchanged: it now drops fields because `new` has none. `convert_layout` returns `out.with_fields(img.fields)` on both paths.

- [ ] **Step 4: Run the image tests**

Run: `uv run pytest tests/image/ -q`
Expected: PASS, including `test_import_without_torch.py`.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-image tests/image/test_image_fields.py
git commit -m "feat(image): images carry fields; derive drops them, layout keeps them"
```

### Task 3: `FIELD_LIST`, the type list and hidden types

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/types/field_list.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py`, `types/fold.py`, `types/progress.py`, `types/choices.py`, `widget_keys.py`
- Modify: `packages/haywire-core/src/haywire/core/types/registry.py`
- Test: `tests/barn/builtin/test_field_list.py`

**Interfaces:**
- Produces:
  - `is_valid_key(key: str) -> bool`
  - `FieldEntry`: frozen dataclass with `key: str`, `recipe: dict` (from `serialize_element_type`)
  - `FIELD_LIST(BaseType)`, a dataclass with `entries: tuple[FieldEntry, ...]`, `with_added(key: str, type_cls: type[IType]) -> FIELD_LIST`, `without(key: str) -> FIELD_LIST`
  - `TypeRegistry.list_value_type_keys() -> list[str]`
  - `widget_keys.FIELD_LIST_WIDGET = "haywire-core:widget:FieldListWidget"`

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("key,ok", [("t", True), ("cam_1", True), ("T", True), ("", False), ("a b", False), ("a:b", False), ("é", False)])
def test_key_rule(key, ok):
    assert is_valid_key(key) is ok

def test_from_dict_drops_bad_and_duplicate_keys_without_raising():
    r = {"registry_key": "haywire-core:type:INT"}
    data = {"entries": [{"key": "a", "recipe": r}, {"key": "a", "recipe": r}, {"key": "b c", "recipe": r}, {"key": "d"}, "junk"]}
    assert [e.key for e in FIELD_LIST.from_dict(data).entries] == ["a"]

def test_from_dict_tolerates_anything():
    assert FIELD_LIST.from_dict("junk").entries == ()

def test_with_added_refuses_a_duplicate_and_a_bad_key():
    one = FIELD_LIST().with_added("a", INT)
    with pytest.raises(ValueError):
        one.with_added("a", FLOAT)
    with pytest.raises(ValueError):
        one.with_added("b c", FLOAT)

def test_round_trip_and_equality():
    one = FIELD_LIST().with_added("a", INT)
    assert FIELD_LIST.from_dict(one.to_dict()) == one
    assert one.without("a") == FIELD_LIST()

@pytest.mark.integration
def test_the_type_list_offers_values_only(library_system):
    keys = library_system.get_type_registry().list_value_type_keys()
    assert "haywire-core:type:FLOAT" in keys
    assert "haybale-image:type:IMAGE_RGB" in keys
    for name in ("EXEC", "CALLBACK", "ADD", "OPTIONAL", "ANNOTATION", "FOLD", "PROGRESS", "CHOICES", "CARRIER"):
        assert f"haywire-core:type:{name}" not in keys
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/barn/builtin/test_field_list.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Follow `FILL` for tolerant construction and `to_dict`/`from_dict`. `list_value_type_keys` filters `list_visible_names()` with the module's `_is_value_type`. Add `hidden=True` to the `@type` of `FOLD`, `PROGRESS` and `CHOICES`, and grep tests that list those through the catalog.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/barn/builtin/ tests/farmhand/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire tests/barn/builtin/test_field_list.py
git commit -m "feat(types): FIELD_LIST and a registry list of value types"
```

### Task 4: `FieldListWidget`

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/widgets/field_list_widget.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/widgets/__init__.py`
- Modify: `tests/ui/harness/routes.py` (add `/field-list-widget`, modelled on `/fill-widget` at line 871, echoing keys in `data-testid="echo-fields"`)
- Test: `tests/ui/harness/test_field_list_widget.py`

**Interfaces:**
- Consumes: `FIELD_LIST`, `is_valid_key`, `list_value_type_keys()` through `haywire.core.di.context.get_type_registry()`.
- Produces: one row per entry (key, type label, remove button `data-field-remove="<key>"`), then an add row: input `data-field-key`, type select `data-field-type`, button `data-field-add`.

- [ ] **Step 1: Write the failing browser tests**

Use `goto_ready` from `tests/ui/harness/nav.py`. Name them `test_adding_a_field_writes_it_to_the_model`, `test_removing_a_field_writes_it_to_the_model`, `test_a_bad_key_cannot_be_added`, `test_a_duplicate_key_cannot_be_added`, `test_the_row_fits_a_narrow_panel`. Assert on the echo, and for the two refusals that the echo stays unchanged and the add button is disabled; the last asserts the add row's right edge lies inside the container's bounding box.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/ui/harness/test_field_list_widget.py -q`
Expected: FAIL, the route has no widget.

- [ ] **Step 3: Implement the widget**

Use `get_value()`/`set_value()` as `FillWidget` does, and always write a new `FIELD_LIST`. Rebuild the rows from the model's change event. `ui.input` takes `validation=` for the message. Query the type list when the select is built, so a hot-reloaded library shows up on the next draw. Follow `docs/reference/design-guide.md`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/ui/harness/test_field_list_widget.py tests/ui/widget/test_widget_keys.py -q`
Expected: PASS. If `test_widget_keys.py` is elsewhere, find it with `git ls-files | grep test_widget_keys`.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/widgets tests/ui/harness
git commit -m "feat(widgets): FieldListWidget"
```

### Task 5: `MetadataNode` pins

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/nodes/metadata.py`
- Test: `tests/core/test_undo/test_metadata_node_pins.py`

**Interfaces:**
- Consumes: `CARRIER`, `FIELD_LIST`.
- Produces:
  - `MetadataNodeBase(BaseNode)`, with `STAMP_FIELDS: ClassVar[FIELD_LIST]` and `READ_FIELDS: ClassVar[FIELD_LIST]`, both empty by default; `stamp_fields() -> FIELD_LIST`, `read_fields() -> FIELD_LIST`; `hb_carrier_connected(port, edge_wrapper)`; `hb_rebuild_field_pins()`
  - `MetadataFieldSettings(NodeSettings)`: `stamp`, `read`
  - `MetadataNode(MetadataNodeBase)`, `@node(label="Metadata", menu="core/metadata", node_type=NodeType.DATA)`, with bag accessor `metadata_fields`

- [ ] **Step 1: Write the failing tests**

Build real wires with `graph.create_edge_wrapper`, using `Editor(graph, factory)` and `editor.set_setting(SettingOwner(kind="node", accessor="metadata_fields", owner_id=node_id), "stamp", value)`.

```python
def test_adding_fields_makes_the_pins(...):
    # stamp "a" (FLOAT), read "b" (INT) -> a_in, b_out, of those types, origin DECLARED

def test_removing_a_field_then_undo_restores_pin_and_working_wires(...):
    # wire a_in and b_out; remove both; edges unlinked, still in graph
    # undo: edge.is_functional() for both, and a value written with node.out arrives
    # redo: unlinked again; undo: functional again

def test_a_constant_on_a_stamp_pin_survives_adding_another_field(...):
    # set a_in's own value to 7, add field c, a_in still 7

def test_a_field_named_carrier_does_not_clash(...):
    # stamp "carrier" -> carrier_in beside carrier_inlet

def test_the_pin_menu_cannot_remove_a_field_pin(...):
    # editor.remove_port(node_id, "a_in") is False

def test_carrier_outlet_follows_the_source_and_keeps_its_wires_on_a_type_it_can_carry(...):
    # IMAGE_RGB source -> carrier_outlet is IMAGE_RGB; wire it to an IMAGE_RGB inlet
    # swap source to IMAGE_GRAY: outlet IMAGE_GRAY, edge functional through the adapter
    # unplug the source: outlet stays IMAGE_GRAY

def test_bundle_and_image_connect_and_int_is_refused(...):
    # BUNDLE and IMAGE_RGB functional on carrier_inlet; TEST_INT not, and outlet unchanged

def test_a_saved_graph_restores_pins_wires_and_keeps_rebuilding(...):
    # to_dict, BaseGraph.load_from_dict, edges functional, then a write rebuilds pins

def test_save_with_a_removed_field_loads_and_re_adding_relinks(...):
    # remove field, to_dict, load: no raise, edge not functional; re-add key: functional

def test_an_entry_whose_type_is_missing_keeps_the_node_and_the_entry(...):
    # recipe for "nolib:type:GONE": node isinstance MetadataNode, no pin for it,
    # entry still in stamp list, to_dict still contains it, warning logged
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/core/test_undo/test_metadata_node_pins.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`init` adds `CARRIER.as_inlet("carrier_inlet", on_connect="hb_carrier_connected")` and `CARRIER.as_outlet("carrier_outlet")`, then calls the build helper directly (no enclosing `rejig`). `post_init` rebuilds and subscribes both fields with `_subscribe_field`; the load path calls `post_init` too. The rebuild uses `self.rejig(include=r"_(in|out)$")`. Resolve types with `type_registry.resolve_type_from_spec`; on `ValueError`, log a warning and skip the pin. Stamp pins are `T.as_inlet`; read pins are `T.as_outlet` with the default `show_widget`, so they show no widget. `hb_carrier_connected` retypes the outlet only if its type differs, because the callback fires again on every relink; the retype keeps the port id so edges survive (`.insights/project_rejig_orphans_edge_port_refs.md`). The class docstring is user documentation in Markdown and says that a field does nothing until listed, and that fields do not survive a manipulating node.

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/core/test_undo/test_metadata_node_pins.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/nodes/metadata.py tests/core/test_undo/test_metadata_node_pins.py
git commit -m "feat(nodes): Metadata node pins follow its field lists"
```

### Task 6: Stamping and reading

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/metadata.py`
- Test: `tests/barn/builtin/test_metadata_node.py`

**Interfaces:**
- Consumes: `CarrierValue.stamped`, `CarrierValue.fields`.
- Produces: `MetadataNodeBase.worker(self, context) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_stamps_reach_the_outlet_and_not_the_input(...):
    # input carrier c; stamp t=1.5 -> carrier_outlet holds t; c.fields empty

def test_one_node_can_stamp_and_read_the_same_key(...):
    # stamp t, read t -> t_out == 1.5

def test_a_present_key_is_written_to_its_pin(...):
def test_a_derived_type_reads_as_its_parent(...):
    # stamped IMAGE_RGB, read pin IMAGE -> value arrives

def test_a_key_absent_now_replaces_the_last_value_with_the_default(...):
    # present on run 1, absent on run 2 -> downstream TEST_INT inlet reads the default, not the old value

def test_a_type_mismatch_writes_defaults_and_raises_after_the_other_pins(...):
    # stamped FLOAT 't', read 't' as STRING, read 'ok' as INT present
    with pytest.raises(ValueError, match="Field 't' holds FLOAT, this pin reads STRING"):
        ...
    # afterwards t_out == "", ok_out holds its value, carrier_outlet is written

def test_an_unwired_stamp_pin_stamps_its_own_value(...):

def test_a_library_node_declares_fixed_fields(...):
    # test-local subclass with STAMP_FIELDS; patch src._node_factory.get_node for its key;
    # the pins exist, and no settings bag is needed
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/barn/builtin/test_metadata_node.py -q`
Expected: FAIL, the worker does nothing.

- [ ] **Step 3: Implement `worker`**

Read `carrier_inlet` with `self.value`. Apply each stamp with the pin's `stored_type`, then write `carrier_outlet`. For each read entry, write the value, or the pin type's default on absence or mismatch (`port.type_cls.create_field().get_value()`). A match means equal registry keys, or the recorded class from `get_type_registry()` derives from the pin's. Collect the first mismatch and raise `ValueError` after every pin is written, as `save_image.py:187` does.

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/barn/builtin/test_metadata_node.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/nodes/metadata.py tests/barn/builtin/test_metadata_node.py
git commit -m "feat(nodes): Metadata node stamps and reads fields"
```

### Task 7: New Bundle, Metadata Info and `DEPTH`

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/metadata.py`
- Create: `barn/haybale-image/haybale_image/value/depth_value.py`
- Create: `barn/haybale-image/haybale_image/types/depth.py`
- Modify: `barn/haybale-image/haybale_image/value/__init__.py`
- Test: `tests/barn/builtin/test_metadata_info_node.py`, `tests/image/test_depth.py`

**Interfaces:**
- Produces:
  - `NewBundleNode` (outlet `bundle: BUNDLE`), `MetadataInfoNode` (inlet `carrier: CARRIER`, outlets `text: STRING`, `count: INT`)
  - `DepthValue(CarrierValue)`, `from_array(data: np.ndarray) -> DepthValue`, `empty()`, `array() -> np.ndarray` (read-only), `width`, `height`, `is_empty`
  - `DEPTH(CARRIER)` with `element_type_cls = DepthValue`, `store_strategy=NEVER`, colour `#00838f`

- [ ] **Step 1: Write the failing tests**

```python
def test_info_lists_fields_and_describe_lines(...):
    # image with icc b"abc", field t=1.5 FLOAT -> text contains "t", "FLOAT", "1.5" and "icc: 3 bytes"; count == 1

def test_info_on_an_empty_bundle_says_so(...):

def test_new_bundle_gives_a_fresh_empty_bundle(...):

def test_depth_refuses_anything_but_uint16_hw():
    with pytest.raises(TypeError):
        DepthValue.from_array(np.zeros((2, 2), np.uint8))
    with pytest.raises(ValueError):
        DepthValue.from_array(np.zeros((2, 2, 3), np.uint16))

def test_depth_array_is_read_only_and_keeps_fields():
    d = DepthValue.from_array(np.zeros((2, 3), np.uint16)).stamped("t", 1.5, FLOAT)
    assert (d.width, d.height) == (3, 2)
    assert d.array().flags.writeable is False
    assert d.fields["t"].value == 1.5

@pytest.mark.integration
def test_depth_cannot_reach_an_image_inlet_but_reaches_a_carrier_inlet(...):
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/barn/builtin/test_metadata_info_node.py tests/image/test_depth.py -q`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement**

The Info value summary uses `repr` cut to 60 characters, so a stamped image cannot flood the text. Do not add an adapter for `DEPTH`.

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/barn/builtin/test_metadata_info_node.py tests/image/test_depth.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/nodes/metadata.py barn/haybale-image tests/barn/builtin tests/image/test_depth.py
git commit -m "feat(nodes): New Bundle, Metadata Info and the DEPTH type"
```

### Task 8: Landing

**Files:**
- Create: `docs/adr/0075-fields-travel-on-a-carrier.md`, `.insights/project_optional_outlet_keeps_stale_value.md`
- Modify: `docs/reference/glossary.md`, `CLAUDE.md`, `docs/components/datatypes/datatype-canon.md`, `docs/superpowers/plans/2026-10-30-spandrel-haybale-design.md`, `docs/superpowers/plans/2026-11-06-carrier-metadata-design.md`

- [ ] **Step 1: Land the design's section 8**

ADR, glossary, insight and its `CLAUDE.md` line. In the canon, add `CARRIER` and how a type becomes a carrier. Point the spandrel spec's non-goal 8 and S9 row at the design.

- [ ] **Step 2: Regenerate library docs**

Run: `uv run haywire docs --all`
Expected: exit 0, coverage gaps reported for no new component.

- [ ] **Step 3: Run all quality gates**

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ barn/haybale-image/haybale_image/ barn/haybale-models/haybale_models/ tests/
uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"
uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"
```

Expected: each exits 0.

- [ ] **Step 4: Live check in the studio**

Using the `haywire-live-studio` skill, confirm what no test covers, and report each: fields edit in the properties panel and pins appear on the card; a removed field's leftover wire is visible and can be deleted; undo through the real keys; Upscale drops fields and keeps colour on a wide-gamut photo; Metadata Info shows `icc`. If the leftover wire cannot be seen or deleted, stop and ask.

- [ ] **Step 5: Mark plan A done and commit**

Set the Plan A row in the design's table to done, with commit, date and deviations.

```bash
git add docs .insights CLAUDE.md barn packages
git commit -m "docs: land carrier fields"
```
