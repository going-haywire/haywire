# S6 — haybale-models: model references, catalog, store, downloads, pool, graph notices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give haywire one way to name, find, fetch, verify, store and share-load ML model files: a `MODEL_REF` value a graph stores, catalog entries libraries ship, a digest-indexed store on a volume, the Hugging Face cache as a second volume, a download queue, a refcounted pool of loaded models, a Models editor, and a needs-list shown on the haystack row through a new, library-extensible graph-notice store.

**Architecture:** Core gains one registry kind (`CatalogRegistry`, a `DocumentRegistry` of OpenModelDB-shaped JSON files in a library's `catalog/` folder). graph-editor's `GraphAppState` gains an open/close listener and a notice store (Observable Store pattern); haystack draws notices on the row beside play; graph-editor itself posts the load-time compatibility findings as the first producer. Everything model-specific lives in the new `barn/haybale-models`: `ModelRef` + `MODEL_REF` type + widget, variant matcher, index, HF bridge, resolver, download queue, `LoadedModels` pool, `ModelsState` (AppState), needs-list, Models editor, Farmhand tools, `Resolve Model` node. haybale-example ships a demo catalog.

**Tech Stack:** Python 3.12, NiceGUI, `huggingface_hub>=1.0`, `httpx`, stdlib `hashlib` / `http.server` (tests).

**Spec:** [2026-10-30-spandrel-haybale-design.md](2026-10-30-spandrel-haybale-design.md) §2.5 (design), §2.1 (volumes), §3 (status). The S6 decisions below amend it.

## S6 decisions (inquisition 2026-10-31)

| # | decision |
|---|---|
| S6-Q1 | A **model reference** is either a **file reference** (URI(s) + sha256, digest optional) or a **catalog reference** (`<library>:catalog:<stem>`; the file is a host-picked variant of the entry). |
| S6-Q2 | `CatalogRegistry(DocumentRegistry)` in **haywire-core**; one JSON file per entry; key `<library>:catalog:<filestem>`. |
| S6-Q3 | Entry = **OpenModelDB superset**: every OpenModelDB field keeps its name; resources add `backend`, `precision`, `hf://` urls and `files[]` bundles; entries add `purpose`, `requires`. A missing tag = runs anywhere. |
| S6-Q4 | Port option `filter` (entry field → allowed values) narrows the picker across all libraries; never refuses a pasted ref. |
| S6-Q5 | A catalog reference **follows the catalog** (no digest pin). Bit-exact reproducibility = file reference. |
| S6-Q6 | Variant choice: ordered list of tag sets from the node's `model_preference(port_id)` (pure function of settings), else the port's `prefer`, else `[{}]`. A tag the resource lacks is a wildcard. haybale-models never imports torch. |
| S6-Q7 | The worker uses the **best local match**; if a higher preference exists unfetched, a `NodeWarning` says so and the needs-list offers it. |
| S6-Q8 | Core: registry + entry only. Everything else in haybale-models. |
| S6-Q9 | `huggingface_hub` is a **hard** dependency. HF cache = volume `haybale-models:volume:hf-cache`, suggested location = HF's own resolved default (`$HF_HUB_CACHE` → `$HF_HOME/hub` → `~/.cache/huggingface/hub`), written once; always passed as `cache_dir=`; never sets env vars; never deletes there. Amends §2.1 ("set `HF_HOME` from the volume"). |
| S6-Q10 | `LoadedModels` pool is owned by `ModelsState` (AppState); `on_disable` releases every entry. |
| S6-Q11 | One Models editor, three sections — **Catalog** (per library, per variant, status/size/license), **Local** (indexed files in no catalog), **HF cache** (read-only, "external") — plus disk usage per volume; per-row download / remove. |
| S6-Q12 | A pasted URI without digest is allowed; it resolves by source URI through the index; card warns "not pinned"; **Pin digest** is an explicit edit-route write. `hf://` fills the digest from `lfs.sha256` when the API answers. |
| S6-Q13 | **Graph notices**: `GraphAppState` gets a zero-arg graphs listener (open/close) and a notice store (`post_notice` / `retract_notice`), with a payload-free cross-session signal. Haystack shows them as an **icon with count beside play** + popup with each notice's action (shown only when the session meets `requires`). Play is never disabled. |
| S6-Q14 | The needs-list re-walks a graph (incl. Subgraph and macro interiors) on its validation and on store / index / catalog / download changes. Missing refs also get a per-card `NodeWarning`. |
| S6-Q15 | One process-wide **download queue** in `ModelsState`; `max_parallel_downloads` (default 2); jobs outlive sessions; HTTP Range resume on `.part`, mirrors tried in order, an HTML response or digest mismatch moves to the next mirror; digest computed while streaming. Progress in editor rows, live notice text and the Activity tracker. |
| S6-Q15b | The models notice's action is **"Show in Models"** (editor filtered to that graph's needs; Fetch all is there).  Deviation (live fix 11, 2026-11-01): it only opens the editor; the graph filter was dropped, the Needed section lists the graph's missing models. |
| S6-Q16 | Ships **Resolve Model** (MODEL_REF → `FILE_PATH` + sha256 + size) and a **demo catalog** in haybale-example. |
| S6-Q17 | MODEL_REF widget: catalog select (filtered, grouped by library, status + size) + "Other…" URI field + browse (shared tree, rooted at the two model volumes) + status line. Never downloads. |
| S6-Q18 | Store layout: catalog downloads `<library-id>/<entry-stem>/<file>`; bundles `<library-id>/<entry-stem>/<variant>/<file>`; pasted URLs `downloads/<host>/<file>`; a same-name, different-digest file gets `-<sha8>` before the extension. `hf://` never lands here. |
| S6-Q19 | Scan on library enable, Models editor open, and **Rescan**; hashing on a background thread; downloads index themselves; no file watcher. |
| S6-Q20 | Remove deletes file(s) + index entry after a confirmation that lists the open graphs using it and the bytes freed. HF rows: **Reveal location** only. |
| S6-Q21 | Pool hold is **per run**: nodes acquire lazily, release in `on_shutdown` (`on_teardown` as backstop). Refcount 0 → released at once. |
| S6-Q22 | Farmhand: `models_list`, `models_needs`, `models_fetch` (ADMIN). No remove. |
| S6-Q23 | Load-time `library_compatibility_findings` (computed, displayed nowhere today) become graph notices — the second producer. |
| S6-Q24 | One plan, ordered phases A (framework) → B (models core) → C (downloads & UI). |

**Small decisions made while planning (flag in review if wrong):**
- Catalog folder is `catalog/` (not `models/`: ML libraries already use `models/` for Python modules). Suffix `.json`.
- The graphs listener is a zero-arg Observable-Store listener on `GraphAppState`, not a bus `Signal`: AppStates receive no bus signals, and listeners re-read `all_containers()`.
- No "release on consumer-library reload" hook: per-run holds (Q21) mean a reload that stops graphs (`on_reload = "restart"`) or rebuilds nodes (`on_teardown`) drops every refcount to 0, which releases at once.
- HF download progress is read by polling the size of the blob's `.incomplete` file against the size from `get_paths_info` (`hf_hub_download` exposes no per-file callback).

## Global Constraints

- haywire-core never imports `huggingface_hub`, `httpx` or anything model-specific beyond `haywire/core/catalog/`; haybale-models never imports `torch`.
- Dependency direction: haybale-models → haybale-graph-editor → haywire-core; haystack never imports haybale-models; graph-editor never imports haybale-studio (memory: library independence).
- No relative imports under `barn/` (ruff TID252).
- Every file path inside a volume goes through `haywire.core.volumes.resolve()` / `location_of()`; nothing hardcodes `~/.haywire`.
- The resolver and every worker are **offline**: no network call on the run path (`huggingface_hub.try_to_load_from_cache`, never `hf_hub_download`, in resolution).
- Download and remove require `AccessTier.ADMIN`; Pin digest goes through the edit route (EDIT); browsing is VIEW.
- Library keys: volumes `haybale-models:volume:models`, `haybale-models:volume:hf-cache`; catalog keys `<library-id>:catalog:<stem>`.
- Displayed docstrings (registered components) use Markdown, others reST — `.claude/rules/python-docs.md`.
- Design tokens / anti-patterns: `docs/reference/design-guide.md` (use `hui.*`, not raw `ui.button`).
- Torch tests (none expected here): `uv run --with torch python -m pytest …`.
- `uv sync` / `uv lock` removes the local visiongraph link; reinstall with `uv pip install -e ../haybale-visiongraph/barn/haybale-visiongraph`, then `uv pip uninstall opencv-python opencv-contrib-python && uv pip install opencv-contrib-python==5.0.0.93`.
- Commit **only with the user's consent** (every "Commit" step asks first).
- Glossary / ADR / docs text is written in Task 18 from the text collected in "To land with the code", never earlier.
- Tests never read repo `graphs/`; fixtures live under `tests/` or haybale-testing.
- No test touches the network: HTTP via a local `http.server` fixture, HF via monkeypatched `huggingface_hub` functions.

## Review Focus

1. **A model file the user drops into the `models` volume while the studio runs** → invisible until Rescan / editor open (Q19), then resolves by digest wherever it sits, including a renamed or moved file. Tests: Task 8 `test_moved_file_resolves_by_digest`, `test_rescan_picks_up_dropped_file`.
2. **A mirror that answers 200 with an HTML page** (Google Drive / Mega interstitial) → treated as a failed mirror, the next URL is tried, the `.part` of the bad one is deleted, never indexed. Test: Task 13 `test_html_response_falls_through_to_next_mirror`.
3. **The studio restarts mid-download** → the `.part` file is resumed with a Range request and the final digest still verifies; a server ignoring Range (200 instead of 206) restarts from zero instead of appending. Tests: Task 13 `test_resume_appends_with_range`, `test_server_without_range_restarts`.
4. **The models volume is undefined or its drive is unplugged** → resolver reports "volume … not defined / missing" as the node error, the editor shows the volume as missing, scanning and downloading refuse with that message; nothing is created on the boot disk. Tests: Task 8 `test_scan_on_missing_volume_is_empty_and_reports`, Task 13 `test_download_refuses_missing_volume`.
5. **Two nodes in two running graphs use the same model** → one load; the first graph stopping keeps it loaded; the second stopping releases it. Test: Task 11 `test_two_holders_share_one_load`.

---

## File structure

```
packages/haywire-core/src/haywire/core/catalog/__init__.py      create: exports
packages/haywire-core/src/haywire/core/catalog/entry.py         create: ModelFile, Resource, CatalogEntry
packages/haywire-core/src/haywire/core/catalog/registry.py      create: CatalogRegistry
packages/haywire-core/src/haywire/core/di/config.py            modify: provide + wire + ambient set
packages/haywire-core/src/haywire/core/di/context.py           modify: set/get_catalog_registry
packages/haywire-core/src/haywire/core/library/kinds.py        modify: "catalog" kind
packages/haywire-core/src/haywire/core/library/base.py         modify: scan priority 76
packages/haywire-core/src/haywire/core/node/node_wrapper.py    modify: NodeWrapperState.replace_warnings(kind, ...)
packages/haywire-core/src/haywire/ui/elements/icons.py         modify: icon.models, icon.notice

barn/haybale-graph-editor/haybale_graph_editor/notices.py      create: GraphNotice, GraphNoticesChanged
barn/haybale-graph-editor/haybale_graph_editor/state/graph_app_state.py  modify: graphs listener, notice store, compat producer
barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py        modify: notice icon + popup on the row

barn/haybale-models/pyproject.toml                             create
barn/haybale-models/README.md                                  create (generated by `haywire docs`)
barn/haybale-models/haybale_models/__init__.py                 create: Library
barn/haybale-models/haybale_models/haybale.toml                create
barn/haybale-models/haybale_models/keys.py                     create: volume keys, notice key
barn/haybale-models/haybale_models/settings/models_settings.py create: ModelsSettings
barn/haybale-models/haybale_models/value/model_ref.py          create: ModelRef
barn/haybale-models/haybale_models/types/model_ref.py          create: MODEL_REF, MODEL_REFField
barn/haybale-models/haybale_models/matcher.py                  create: candidates()
barn/haybale-models/haybale_models/store/layout.py             create: target_path()
barn/haybale-models/haybale_models/store/index.py              create: ModelIndex
barn/haybale-models/haybale_models/hf.py                       create: HF bridge
barn/haybale-models/haybale_models/resolver.py                 create: resolve(), ResolvedModel, ModelMissing
barn/haybale-models/haybale_models/pool.py                     create: LoadedModels
barn/haybale-models/haybale_models/consumer.py                 create: preference_for(), resolve_port(), acquire_port()
barn/haybale-models/haybale_models/download.py                 create: DownloadQueue, DownloadJob
barn/haybale-models/haybale_models/needs.py                    create: collect_needs(), NeedsReport
barn/haybale-models/haybale_models/state/models_state.py       create: ModelsState
barn/haybale-models/haybale_models/state/models_view_state.py  create: ModelsViewState (SessionState)
barn/haybale-models/haybale_models/signals.py                  create: ModelsChanged
barn/haybale-models/haybale_models/widgets/model_ref_widget.py create: ModelRefWidget
barn/haybale-models/haybale_models/editors/models_editor.py    create: ModelsEditor
barn/haybale-models/haybale_models/nodes/resolve_model.py      create: ResolveModelNode
barn/haybale-models/haybale_models/farmhands/model_tools.py    create: three tools

barn/haybale-example/haybale_example/catalog/*.json            create: demo catalog (2–3 entries)
barn/haybale-example/haybale_example/__init__.py               modify: register catalog/
barn/haybale-example/pyproject.toml, haybale.toml              modify: depend on haybale-models

pyproject.toml, CLAUDE.md                                      modify: workspace member, dev dep, mypy_path, mypy command

tests/core/test_models/test_catalog_registry.py
tests/graph_editor/test_graph_notices.py
tests/haystack/test_notice_row.py
tests/models/conftest.py                                       volume-store + http server + fake HF fixtures
tests/models/test_*.py                                         one per haybale-models module
```

---

## Phase A — framework

### Task 1: `CatalogRegistry` and catalog entries in core

**Files:**
- Create: `packages/haywire-core/src/haywire/core/catalog/{__init__,entry,registry}.py`
- Modify: `di/config.py` (provider beside `provide_macro_registry` :217, `injector.get` beside :413, `add_class_registry` beside :437, `get_catalog_registry` beside :723), `di/context.py` (`_catalog_registry` global + `set_`/`get_catalog_registry`, mirroring `_type_registry`), `library/kinds.py` (`"model": CatalogRegistry`, folder `"catalog"`, area `"models"`), `library/base.py` `_REGISTRY_SCAN_PRIORITY` (`"CatalogRegistry": 76`)
- Modify: `tests/conftest.py` — add the new ambient global to the snapshot/restore that already covers `_type_registry`
- Test: `tests/core/test_models/test_catalog_registry.py`

**Interfaces:**
- Produces:
  - `ModelFile(path: str, sha256: str | None, size: int | None, urls: tuple[str, ...])` — frozen dataclass; `path` is the file's name inside a bundle (`""` for single-file resources).
  - `Resource(platform: str, type: str, size: int | None, sha256: str | None, urls: tuple[str, ...], files: tuple[ModelFile, ...], backend: str | None, precision: str | None)` — frozen; `.tags() -> dict[str, str]` returns the non-`None` of `platform`, `type`, `backend`, `precision`; `.variant_name() -> str` = `"-".join` of tag values in that order (`"pytorch-pth-fp16"`), or `"default"` when there are none; `.is_bundle -> bool`; `.total_size -> int | None`.
  - `CatalogEntry(name, author, license, architecture, scale, purpose, tags, description, size, input_channels, output_channels, requires, resources: tuple[Resource, ...], document: dict, path: Path, content_hash: str, identity: BaseIdentity, library: LibraryIdentity)` with `class_identity` / `class_library` properties (MacroTemplate shape), `.fields() -> dict[str, Any]` (entry-level fields a port `filter` matches against: `architecture`, `scale`, `purpose`, `tags`, `license`, `input_channels`, `output_channels`).
  - `CatalogRegistry(DocumentRegistry[CatalogEntry])`, `SUFFIX = ".json"`, key `f"{library.name}:catalog:{path.stem}"`, `.entry(key) -> CatalogEntry | None`, `.entries() -> list[CatalogEntry]`.
  - `haywire.core.di.context.get_catalog_registry() -> CatalogRegistry`.

Parsing rules: OpenModelDB field names are read as-is (`inputChannels`, `outputChannels`, `resources[].platform/type/size/sha256/urls`); a single-file resource with no `files` becomes `files=(ModelFile("", sha256, size, urls),)`; a bundle resource has `files: [{path, sha256, size, urls}]` and no top-level `sha256`. Refused (→ `CLASS_RELOAD_FAILED`, previous element kept): not a JSON object; no `resources` or an empty list; a resource with neither `urls`/`sha256` nor `files`; a `sha256` that is not 64 hex chars; a filestem failing MacroRegistry's `_STEM_RULE` (skip with the same logged message). `purpose` and `tags` are lists of strings; `scale`/`size`/channels ints or absent.

- [ ] **Step 1: Write failing tests**

```python
def test_openmodeldb_file_parses_unchanged(tmp_path, catalog_registry, lib_identity):
    # verbatim OpenModelDB shape: one resource, pth, sha256, two mirror urls
    write(tmp_path / "4x-Demo.json", OMDB_DEMO)
    catalog_registry.add_folder(str(tmp_path), lib_identity)
    entry = catalog_registry.entry("haybale-x:catalog:4x-Demo")
    assert entry.architecture == "esrgan" and entry.scale == 4
    (res,) = entry.resources
    assert res.tags() == {"platform": "pytorch", "type": "pth"}
    assert res.files[0].urls == ("https://a.example/4x.pth", "https://b.example/4x.pth")
    assert res.variant_name() == "pytorch-pth"

def test_variant_tags_and_bundle(...):           # backend/precision read; files[] bundle, is_bundle True, total_size summed
def test_bad_sha256_is_refused_and_keeps_previous(...):  # CLASS_RELOAD_FAILED queued; old entry still returned
def test_empty_resources_refused(...):
def test_kind_maps_know_catalog():
    assert kind_registry_map()["catalog"] is CatalogRegistry
    assert KIND_FOLDERS["catalog"] == "catalog"
def test_library_gets_the_registry(test_injector):  # a library's get_registry(CatalogRegistry) is the DI singleton
```

- [ ] **Step 2: Run, expect failures** — `uv run pytest tests/core/test_models/ -q` → ImportError.
- [ ] **Step 3: Implement** entry dataclasses, registry (`_parse`, `_document_key`, `add_folder` stem filter as in `MacroRegistry`), DI/context/kinds/priority wiring.
- [ ] **Step 4: Run** `uv run pytest tests/core/test_models/ tests/core/test_libraries/ -q` → PASS. Then `uv run pytest -m "not browser and not perf" -n 4 -q tests/core tests/studio/test_docs > /tmp/t.log 2>&1; echo exit=$?` → 0 (the docs generator iterates `kind_registry_map()`; if it renders a page per entry, give `CatalogEntry` what it reads, mirroring `MacroTemplate`).
- [ ] **Step 5: Commit (ask first)** — `feat(core): model catalog registry`

### Task 2: Graph notices and the graphs listener on `GraphAppState`

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/notices.py`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/state/graph_app_state.py`
- Test: `tests/graph_editor/test_graph_notices.py`

**Interfaces:**
- Consumes: `AppState._signal_emit`, `nicegui.core.loop` (same hop as `_on_history_changed`).
- Produces:
  - `GraphNotice(key: str, text: str, action_label: str | None = None, action: Callable[[SessionContext], None] | None = None, requires: AccessTier = AccessTier.VIEW, dismissable: bool = False)` — frozen dataclass. `key` is namespaced by the producer (`haybale-models:needs`, `haywire:compatibility:<n>`).
  - `GraphNoticesChanged(Signal)`, `cross_session = True`, payload-free.
  - `GraphAppState.add_graphs_listener(cb: Callable[[], None])`, `remove_graphs_listener(cb)` — fired after `register`, `unregister`, `rekey` (snapshot list, each isolated in try/except, outside any lock; Observable Store).
  - `GraphAppState.post_notice(binding_id: str, notice: GraphNotice) -> None` — replaces the notice with the same key; no-op (logged at debug) when `binding_id` is not registered.
  - `GraphAppState.retract_notice(binding_id: str, key: str) -> None` — idempotent.
  - `GraphAppState.notices(binding_id: str) -> list[GraphNotice]` — insertion order.
  - `unregister` drops the binding's notices; `rekey` moves them.
  - Every change that alters what `notices()` returns emits `GraphNoticesChanged` through the loop hop (thread-safe: downloads post from worker threads). Re-posting an identical notice emits nothing.

- [ ] **Step 1: Failing tests**

```python
def test_post_replace_retract(app_state, container):
    app_state.register(container)
    app_state.post_notice(container.binding_id, GraphNotice("lib:a", "one"))
    app_state.post_notice(container.binding_id, GraphNotice("lib:a", "two"))
    assert [n.text for n in app_state.notices(container.binding_id)] == ["two"]
    app_state.retract_notice(container.binding_id, "lib:a")
    assert app_state.notices(container.binding_id) == []

def test_unregister_drops_and_rekey_moves_notices(...)
def test_post_to_unknown_binding_is_ignored(...)
def test_graphs_listener_fires_on_register_unregister_rekey(...)
def test_raising_listener_does_not_block_others(...)
def test_identical_repost_emits_nothing(app_state, emitted):  # emitted = patched _signal_emit capture
```

- [ ] **Step 2: Run, expect failures** — `uv run pytest tests/graph_editor/test_graph_notices.py -q`.
- [ ] **Step 3: Implement** in `notices.py` and `graph_app_state.py`.
- [ ] **Step 4: Run** `uv run pytest tests/graph_editor/ -q` → PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(graph-editor): graph notices and graphs listener`

### Task 3: Notices on the haystack row; compatibility findings as the first producer

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py` (`_render_entry` :257, `@redraw_on` at :83 adds `GraphNoticesChanged`)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/state/graph_app_state.py` (`register` posts compatibility notices)
- Modify: `packages/haywire-core/src/haywire/ui/elements/icons.py` (`notice: Final[str] = "error_outline"`, `models: Final[str] = "model_training"`)
- Test: `tests/haystack/test_notice_row.py`, extend `tests/graph_editor/test_graph_notices.py`

**Interfaces:**
- Consumes: Task 2.
- Produces: row markers `data-hw-mark="graph-notice"` (icon) and `graph-notice-action` (each popup button) for tests and the live check.

Row: when `notices(eid)` is non-empty, after the play/stop control, draw `hui.icon_action(hui.icon.notice, tooltip=<texts joined by newline>)` with a count badge (number of notices not dismissed in this editor instance). Click opens a `Popup` (`haywire.ui.components.popup`) listing one line per notice: text, then the action button when `action` is set **and** `context.can_access(notice.requires)`, else nothing; a dismiss `×` when `dismissable` (hides it for this editor instance only — a `set[tuple[binding_id, key]]` on the editor). Click handlers capture `ui.context.client` first and return coroutines (`.insights/feedback_nicegui_async.md`). The row click must not fire through the icon (`.on("click.stop", …)` pattern the row already uses for its buttons).

Compatibility producer: in `register`, for each finding in `container.editor.graph.library_compatibility_findings`, post `GraphNotice(key=f"haywire:compatibility:{i}", text=finding, dismissable=True)`.

- [ ] **Step 1: Failing tests** (NiceGUI `user` fixture, as `tests/studio/test_haystack_editor_tiers.py`)

```python
async def test_row_shows_notice_icon_with_count(user, haystack_with_one_graph, graph_app_state):
    graph_app_state.post_notice(eid, GraphNotice("t:a", "Needs 2 models (10 MB)", "Show", action, AccessTier.ADMIN))
    await user.open("/")
    user.find(marker="graph-notice")          # present, tooltip carries the text

async def test_action_hidden_below_requires(user, ... view_principal ...):  # popup line has no action button
async def test_action_runs_with_session_context(user, ...):                 # action called once with a SessionContext
async def test_dismiss_hides_for_this_editor_only(user, ...):
async def test_no_icon_without_notices(user, ...)
def test_register_posts_compatibility_findings(app_state, container_with_findings):
    assert [n.key for n in app_state.notices(eid)] == ["haywire:compatibility:0"]
```

- [ ] **Step 2: Run, expect failures.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/haystack/ tests/studio/test_haystack_editor_tiers.py tests/graph_editor/ -q` → PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(haystack): graph notices on the haystack row; compatibility findings shown`

---

## Phase B — haybale-models core

### Task 4: Library scaffold, settings, `ModelsState` with the two volumes

**Files:**
- Create: `barn/haybale-models/pyproject.toml`, `haybale_models/{__init__.py,haybale.toml,keys.py,py.typed}`, `settings/models_settings.py`, `state/models_state.py`
- Modify: root `pyproject.toml` (`[tool.uv.sources] haybale-models`, dev group, `mypy_path`), `CLAUDE.md` mypy command (add `barn/haybale-models/haybale_models/`)
- Test: `tests/models/conftest.py`, `tests/models/test_library.py`, `tests/models/test_models_state.py`

**Interfaces:**
- Produces:
  - pyproject deps: `haywire-core>=0.3.0`, `haybale-graph-editor>=0.3.0`, `huggingface_hub>=1.0`, `httpx>=0.28`; entry point `models = "haybale_models:Library"`; version `0.3.0` (lockstep); `haybale.toml` `name = "haybale-models"`, `label = "Models"`, `linked_libraries = ["haybale_graph_editor"]`.
  - `keys.py`: `MODELS_VOLUME = "haybale-models:volume:models"`, `HF_VOLUME = "haybale-models:volume:hf-cache"`, `NEEDS_NOTICE = "haybale-models:needs"`.
  - `ModelsSettings(LibrarySettings)`, namespace `models`: `max_parallel_downloads = setting[INT](2, min=1, max=8, label="Parallel downloads", …)`.
  - `hf_default_cache() -> Path` in `state/models_state.py`: `$HF_HUB_CACHE`, else `$HF_HOME/hub`, else `~/.cache/huggingface/hub` (read from `os.environ`, `expanduser`).
  - `ModelsState(AppState)` (`@state(label="Models")`), `on_enable`: `ensure_volume(MODELS_VOLUME, label="Models", description="Model files downloaded or added on this machine", location=library_storage_dir("haybale_models") / "models")`; `ensure_volume(HF_VOLUME, label="Hugging Face cache", description="Shared Hugging Face download cache; haywire never deletes here", location=hf_default_cache())`. Later tasks add attributes; `on_disable` releases the pool (Task 11) and stops the queue (Task 13).
  - `Library.register_components`: folders `state`, `settings`, `types`, `widgets`, `nodes`, `editors`, `farmhands` (create the folders empty now with `__init__.py`).
- Fixture `models_env` (tests/models/conftest.py): temp `VolumeStore` via `set_volume_store`, both volumes pointed at `tmp_path` subfolders, restored after.

- [ ] **Step 1: Failing tests**

```python
def test_on_enable_adds_both_volumes(temp_volume_store, monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hf"))
    ModelsState().on_enable()
    assert temp_volume_store.entry(HF_VOLUME).location == tmp_path / "hf"
    assert temp_volume_store.entry(MODELS_VOLUME).location.name == "models"

def test_hf_default_order(monkeypatch, tmp_path):   # HF_HUB_CACHE > HF_HOME/hub > ~/.cache/huggingface/hub
def test_user_edited_location_survives_enable(...)   # ensure_volume never overwrites
def test_library_is_discoverable():                  # entry point "models" resolves to haybale_models.Library
def test_import_without_torch():                     # subprocess: import haybale_models; "torch" not in sys.modules
```

- [ ] **Step 2: Run, expect failures.**
- [ ] **Step 3: Implement**; `uv lock && uv sync --all-packages` then reinstall visiongraph + opencv per Global Constraints.
- [ ] **Step 4: Run** `uv run pytest tests/models/ -q` and `uv run mypy barn/haybale-models/haybale_models/` → clean.
- [ ] **Step 5: Commit (ask first)** — `feat(models): haybale-models library scaffold and volumes`

### Task 5: `ModelRef` value and the `MODEL_REF` type

**Files:**
- Create: `haybale_models/value/model_ref.py`, `haybale_models/types/model_ref.py`
- Test: `tests/models/test_model_ref.py`

**Interfaces:**
- Produces:
  - `ModelRef` frozen dataclass: `catalog: str | None = None`, `urls: tuple[str, ...] = ()`, `sha256: str | None = None`, `size: int | None = None`, `label: str = ""`. Exactly one form: catalog (`catalog` set, rest empty) or file (`urls` and/or `sha256` set). `ModelRef.empty()` = neither (the default; resolves to "no model chosen"). `.is_catalog`, `.is_file`, `.is_empty`, `.source -> str | None` (first url). `to_dict()` / `from_dict()` — omits empty fields; `from_dict` of `{}` → `empty()`. A local file picked from a volume is a file ref with its `sha256`, `size`, `label` and `urls=()` — it resolves by digest. `pinned(sha256, size) -> ModelRef`.
  - `MODEL_REF(PrimitiveType[ModelRef])`, `@type(label="Model", color=…, default={"value": {}}, widget_key="haybale-models:widget:ModelRefWidget", store_strategy=…default…)`; `to_dict`/`from_dict` like `PATH`; `_configure_port` copies the type's widget `properties` defaults (`filter: {}`, `prefer: []`) like `PATH._configure_port`. `MODEL_REFField(PrimitiveField)` converts dicts on default and every write (`PATHField` pattern).
  - Port usage: `MODEL_REF.as_inlet("model", label="Model", widget_config={"properties": {"filter": {"purpose": ["SR"]}, "prefer": [{"precision": "fp16"}, {}]}})`.

- [ ] **Step 1: Failing tests**

```python
def test_round_trip_both_forms():
    for ref in (ModelRef(catalog="haybale-x:catalog:4x-Demo"),
                ModelRef(urls=("hf://org/repo/m.safetensors@main",), sha256="a"*64, size=10)):
        assert ModelRef.from_dict(ref.to_dict()) == ref
def test_both_forms_at_once_raises():   # ModelRef(catalog=..., urls=(...)) → ValueError
def test_field_converts_dict_writes():  # MODEL_REFField(...).set(dict) stores a ModelRef (PATHField precedent test)
def test_port_gets_type_widget_defaults():  # filter/prefer present in port.widget_config["properties"]
def test_default_is_empty_and_graph_round_trips(test_injector):  # node with MODEL_REF inlet saves/loads its value
```

- [ ] **Step 2–4:** run → fail; implement; `uv run pytest tests/models/test_model_ref.py -q` → PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(models): MODEL_REF type`

### Task 6: Variant matcher

**Files:** Create `haybale_models/matcher.py`; Test `tests/models/test_matcher.py`

**Interfaces:**
- Produces:
  - `Preference = list[dict[str, str]]`.
  - `matches(resource: Resource, tagset: dict[str, str]) -> bool` — every key in `tagset` either absent from `resource.tags()` (wildcard) or equal.
  - `candidates(resources: Sequence[Resource], preference: Preference) -> list[tuple[int, Resource]]` — `(rank, resource)` for each tag set in order, each resource at its first matching rank only; empty preference = `[{}]`.
  - `entry_matches(entry: CatalogEntry, filter: dict[str, list[Any]]) -> bool` — for list-valued entry fields (`purpose`, `tags`) any overlap; scalars membership.

- [ ] **Step 1: Failing tests**

```python
def test_missing_tag_is_wildcard():
    assert matches(res(platform="pytorch"), {"precision": "fp16"})
def test_rank_follows_preference_order():
    fp16, fp32 = res(precision="fp16"), res(precision="fp32")
    assert candidates([fp32, fp16], [{"precision": "fp16"}, {}]) == [(0, fp16), (1, fp32)]
def test_resource_listed_once_at_best_rank(): ...
def test_entry_filter_list_overlap_and_scalar(): ...
```

- [ ] **Step 2–4:** fail → implement → `uv run pytest tests/models/test_matcher.py -q` PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(models): variant matcher`

### Task 7: Store layout

**Files:** Create `haybale_models/store/layout.py`; Test `tests/models/test_layout.py`

**Interfaces:**
- Produces: `target_path(*, entry: CatalogEntry | None, resource: Resource | None, file: ModelFile | None, url: str, sha256: str | None, root: Path) -> Path` per Q18: catalog single file `root/<library.name>/<entry stem>/<basename(url)>`; bundle `root/<library.name>/<stem>/<resource.variant_name()>/<file.path>`; file ref `root/downloads/<host>/<basename(url path)>`. If the target exists **and** its indexed digest differs from `sha256`, insert `-<sha256[:8]>` before the suffix. Basenames are URL-decoded and stripped of query strings; an empty basename becomes `model.bin`.

- [ ] **Step 1: Failing tests** — `test_catalog_single_file`, `test_bundle_uses_variant_folder`, `test_pasted_url_goes_to_downloads_host`, `test_name_clash_gets_sha8_suffix`, `test_query_string_and_percent_encoding_stripped`.
- [ ] **Step 2–4:** fail → implement → PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(models): store layout`

### Task 8: `ModelIndex` — digest index of the `models` volume

**Files:** Create `haybale_models/store/index.py`; Test `tests/models/test_index.py`

**Interfaces:**
- Consumes: `location_of(MODELS_VOLUME)`.
- Produces:
  - `IndexRecord(sha256: str, relative: str, size: int, mtime_ns: int, source: str | None)` frozen.
  - `ModelIndex(root_key: str = MODELS_VOLUME)`: file `<root>/.index.json` (`{"version": 1, "files": [IndexRecord…]}`, atomic write temp + `os.replace`, thread lock).
  - `.scan() -> list[Path]` — `stat` walk (skip dot-names, `.part`, `.index.json`); unchanged `(size, mtime_ns)` keeps its record; vanished files drop out; returns the paths queued for hashing. Missing/undefined volume → `[]` and `.problem` set to the `VolumeError` message.
  - `.hash_pending(on_progress: Callable[[Path, int, int], None] | None = None) -> None` — hashes queued files (1 MiB chunks), on the calling thread; `ModelsState` runs it on a daemon thread.
  - `.pending() -> dict[Path, float]` (fraction hashed, for "indexing… 40 %").
  - `.by_sha256(sha) -> Path | None`, `.by_source(uri) -> IndexRecord | None`, `.records() -> list[IndexRecord]`.
  - `.add(path: Path, sha256: str, source: str | None) -> None` (downloads; no re-hash), `.remove(sha256) -> None`.
  - `.add_listener(cb)` / `remove_listener` (zero-arg; fired after scan, hash completion, add, remove).

- [ ] **Step 1: Failing tests**

```python
def test_rescan_picks_up_dropped_file(models_env):
    drop(models_env.models / "mine" / "x.pth", b"abc")
    index.scan(); index.hash_pending()
    assert index.by_sha256(sha(b"abc")) == models_env.models / "mine" / "x.pth"
def test_moved_file_resolves_by_digest(...):        # move + rescan → same sha, new path; source kept
def test_unchanged_file_is_not_rehashed(...):       # patch hashlib.sha256 counter
def test_scan_on_missing_volume_is_empty_and_reports(...):
def test_index_file_written_atomically_and_reloaded(...)
def test_part_and_dot_files_skipped(...)
```

- [ ] **Step 2–4:** fail → implement → PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(models): digest index`

### Task 9: Hugging Face bridge

**Files:** Create `haybale_models/hf.py`; Test `tests/models/test_hf.py`

**Interfaces:**
- Produces:
  - `HfUri(repo_id: str, path: str, revision: str = "main")`; `parse_hf(uri: str) -> HfUri` for `hf://org/repo/path/in/repo@rev` (`@rev` optional; `repo_id` = first two segments); `ValueError` on fewer than three segments.
  - `cached_path(uri: str, cache_dir: Path) -> Path | None` — `huggingface_hub.try_to_load_from_cache(repo_id, path, cache_dir=cache_dir, revision=revision)`; non-`str` results → `None`. Offline.
  - `remote_sha256(uri: str) -> tuple[str, int] | None` — `HfApi().get_paths_info(repo_id, [path], revision=revision)`; returns `(lfs.sha256, lfs.size)`; `None` on any exception or non-LFS file.
  - `download(uri: str, cache_dir: Path, expected_size: int | None, on_progress: Callable[[int, int | None], None], cancel: threading.Event) -> Path` — `hf_hub_download(..., cache_dir=cache_dir)` on the calling thread while a helper thread polls `<cache_dir>/models--org--repo/blobs/*.incomplete` sizes every 0.5 s into `on_progress`. Cancel: checked by the poller; on cancel the result is discarded (HF keeps its `.incomplete` for its own resume).
  - `list_cache(cache_dir: Path) -> list[HfCachedFile]` — `scan_cache_dir(cache_dir)` flattened to `(repo_id, revision, path_in_repo, size, blob_path)`; empty list when the folder does not exist.

- [ ] **Step 1: Failing tests** (monkeypatch the three `huggingface_hub` functions; no network)

```python
def test_parse_with_and_without_revision():
    assert parse_hf("hf://org/repo/sub/m.safetensors@v1") == HfUri("org/repo", "sub/m.safetensors", "v1")
def test_cached_path_never_downloads(monkeypatch):  # hf_hub_download patched to raise; cached_path still works
def test_remote_sha_none_on_error(monkeypatch): ...
def test_download_reports_progress_from_incomplete_file(monkeypatch, tmp_path): ...
def test_list_cache_missing_folder_is_empty(tmp_path): ...
```

- [ ] **Step 2–4:** fail → implement → PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(models): Hugging Face bridge`

### Task 10: Resolver

**Files:** Create `haybale_models/resolver.py`; Test `tests/models/test_resolver.py`

**Interfaces:**
- Consumes: Tasks 1, 5, 6, 8, 9.
- Produces:
  - `ResolvedModel(files: dict[str, Path], sha256: str, size: int, ref: ModelRef, entry: CatalogEntry | None, resource: Resource | None, rank: int, better_unfetched: Resource | None)` — `files[""]` is the single file; `.path` = `files[""]` or the bundle folder; `sha256` is the single file's digest or, for a bundle, `sha256` of the sorted `"path:sha"` lines (the pool key).
  - `FetchSpec(entry: CatalogEntry | None, resource: Resource | None, ref: ModelRef | None)` — frozen; what to fetch: a catalog variant, or a file ref's sources. `.identity -> tuple` (`(entry key, resource.variant_name())` or `(ref.sha256 or ref.source,)`) for dedup.
  - `ModelMissing(Exception)` with `.ref`, `.wanted: list[FetchSpec]` (what the needs-list would fetch), `.reason: str` — message `"model missing — fetch it from Models"`, or `"no model chosen"` for an empty ref, or the volume problem text.
  - `resolve(ref: ModelRef, preference: Preference, *, catalog: CatalogRegistry, index: ModelIndex, hf_cache: Path | None) -> ResolvedModel`.

Order (spec §2.5, Q7): catalog ref → `candidates(entry.resources, preference)`; walk in rank order, return the **first resource whose every file is local** (index by sha256; HF cache for `hf://` urls); set `better_unfetched` to the best-ranked candidate if it is not the one returned. File ref → index by `sha256`, else HF cache (`hf://`), else index `by_source(first url)` when `sha256` is `None`. Nothing local → `ModelMissing` with the rank-0 candidate (catalog) or the ref's source (file) in `wanted`. Unknown catalog key → `ModelMissing(reason="catalog entry … is not installed")`. A resource whose `sha256` is `None` resolves only through `by_source`.

- [ ] **Step 1: Failing tests**

```python
def test_best_local_wins_and_reports_better(models_env, catalog_with_fp16_fp32):
    put_local(fp32_bytes)
    r = resolve(ModelRef(catalog=KEY), [{"precision": "fp16"}, {}], **deps)
    assert r.resource.precision == "fp32" and r.better_unfetched.precision == "fp16"
def test_missing_lists_rank0_variant(...)
def test_hf_ref_resolves_from_cache_offline(...)
def test_unpinned_file_ref_resolves_by_source(...)
def test_bundle_needs_every_file(...)
def test_empty_ref_says_no_model_chosen(...)
def test_unknown_catalog_key(...)
```

- [ ] **Step 2–4:** fail → implement → PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(models): resolver`

### Task 11: `LoadedModels` pool and the consumer helpers

**Files:**
- Create: `haybale_models/pool.py`, `haybale_models/consumer.py`
- Modify: `packages/haywire-core/src/haywire/core/node/node_wrapper.py` — `NodeWrapperState.replace_warnings(kind: str, warnings: Iterable[NodeWarning]) -> bool` (returns whether the list changed); `set_previous_setup` uses it
- Modify: `haybale_models/state/models_state.py` — `pool`, `index`, `catalog` attributes; `on_disable` → `pool.release_all()`
- Test: `tests/models/test_pool.py`, `tests/models/test_consumer.py`, `tests/core/test_node/test_replace_warnings.py`

**Interfaces:**
- Produces:
  - `LoadedModels.acquire(key: tuple[str, Hashable], holder: object, load: Callable[[], T], release: Callable[[T], None]) -> T` — `key = (sha256, variant_key)`; loads once under a per-key lock (a second caller waits, then shares); holders are a set (acquiring twice with one holder counts once).
  - `.release(holder: object) -> None` — drops the holder from every key; a key with no holders is released at once (`release(obj)` exceptions logged, never raised).
  - `.release_all()`, `.entries() -> list[PoolEntry(key, holders: int, loaded_at: float)]`.
  - `consumer.preference_for(node: BaseNode, port_id: str) -> Preference` — `node.model_preference(port_id)` if the node defines it, else the port's `widget_config["properties"]["prefer"]`, else `[{}]`.
  - `consumer.resolve_port(node: BaseNode, port_id: str) -> ResolvedModel` — reads the port value, resolves with the ambient `ModelsState`, and sets the node's `"model"` warnings via `replace_warnings`: `better_unfetched` → "Preferred variant <variant> is not downloaded — Show in Models"; unpinned file ref → "Not pinned — Pin digest on the card"; none → cleared. Raises `ModelMissing`.
  - `consumer.acquire_port(node, port_id, *, variant_key: Hashable, load: Callable[[ResolvedModel], T], release: Callable[[T], None]) -> T` — `resolve_port` + `pool.acquire(..., holder=node, load=lambda: load(resolved))`.
  - `consumer.release_node(node) -> None` — `pool.release(node)`; nodes call it from `on_shutdown` and `on_teardown`.
  - `models_state() -> ModelsState` — ambient lookup through `get_library_state_container().get(ModelsState)`.

- [ ] **Step 1: Failing tests**

```python
def test_two_holders_share_one_load():
    loads = []
    a = pool.acquire(("s", "cpu"), holder=h1, load=lambda: loads.append(1) or object(), release=rel)
    b = pool.acquire(("s", "cpu"), holder=h2, load=..., release=rel)
    assert a is b and loads == [1]
    pool.release(h1); assert released == []
    pool.release(h2); assert released == [a]
def test_concurrent_acquire_loads_once(): ...      # 8 threads, one load
def test_raising_load_leaves_no_entry(): ...
def test_release_all_on_disable(): ...
def test_preference_from_node_hook_beats_port(): ...
def test_resolve_port_sets_and_clears_model_warnings(): ...
def test_replace_warnings_keeps_other_kinds():      # core
```

- [ ] **Step 2–4:** fail → implement → `uv run pytest tests/models/ tests/core/test_node/ -q` PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(models): loaded-models pool and consumer helpers`

### Task 12: `MODEL_REF` widget, `Resolve Model` node, demo catalog

**Files:**
- Create: `haybale_models/widgets/model_ref_widget.py`, `haybale_models/nodes/resolve_model.py`, `barn/haybale-example/haybale_example/catalog/*.json`
- Modify: `barn/haybale-example/haybale_example/__init__.py` (`add_folder_to_registry(base/"catalog", CatalogRegistry)`), its `pyproject.toml` (`haybale-models>=0.3.0`) and `haybale.toml` (`linked_libraries += "haybale_models"`)
- Test: `tests/models/test_model_ref_widget.py`, `tests/models/test_resolve_model.py`, `tests/models/test_demo_catalog.py`

**Interfaces:**
- Consumes: Tasks 5, 6, 10, 11; `PathWidget` (`packages/haywire-core/src/haywire/barn/builtin/widgets/path_widget.py`) as the structural template; the shared folder-tree popup it opens.
- Produces:
  - `ModelRefWidget(BaseWidget)` `@widget(description="Pick a model", min_width=220)`. Select options: entries passing `entry_matches(entry, filter)`, grouped by library label, option text `"<name> — <status>, <size>"` with status `local` / `HF cache` / `not downloaded` (from `resolve` with the port's preference; `ModelMissing` → not downloaded); last option `Other…`. `Other…` shows a URI input (`hf://` / `https://`) and a browse button rooted at the two model volumes; a picked local file writes `ModelRef(sha256=…, size=…, label=name)` from the index (hash on pick if unindexed). Status line: `resolved: <variant>, <size>` / `missing — Show in Models` / `not pinned — Pin digest` / `no model chosen`. **Pin digest** (EDIT) writes `ref.pinned(sha, size)` through the widget's routed write; for `hf://` without digest the widget calls `remote_sha256` once on a thread when the URI is entered and pins if it answers. Writes go only through the edit route (ADR 0055); the widget never downloads. Marks: `model-ref-select`, `model-ref-uri`, `model-ref-pin`, `model-ref-status`.
  - `ResolveModelNode` (`@node`, category `models`, label "Resolve Model"): inlet `model: MODEL_REF`; outlets `path: FILE_PATH` (volume path into `MODELS_VOLUME` or `HF_VOLUME`, relative to that volume's location), `sha256: STRING`, `size: INT`. Data node; worker = `resolve_port(self, "model")`; `ModelMissing` raises with its message (node error via ledger). Displayed docstring per python-docs rules.
  - Demo catalog: two entries copied **verbatim** from the OpenModelDB data repo (`github.com/OpenModelDB/open-model-database`, `data/models/*.json`), each with a resource under 20 MB, plus one hand-written entry with two resources tagged `precision: fp32` / `fp16` (both pointing at real, small files whose sha256 the implementer computes once at authoring time). Note the source and date in a `README.md` in that folder.

- [ ] **Step 1: Failing tests**

```python
async def test_select_lists_only_filtered_entries(user, node_with_sr_filter): ...
async def test_other_uri_writes_file_ref(user, ...): ...
async def test_pin_digest_is_an_undoable_edit(user, ...): ...    # history gains one step; undo restores sha256=None
async def test_view_mode_widget_is_read_only(user, ...): ...
def test_resolve_model_outputs_volume_path(models_env, ...):
    assert out["path"] == VolumePath(MODELS_VOLUME, "mine/x.pth")
def test_resolve_model_missing_raises_named_message(...)
def test_demo_catalog_parses(test_injector):   # every file in haybale_example/catalog registers, ≥1 entry has 2 variants
```

- [ ] **Step 2–4:** fail → implement → `uv run pytest tests/models/ -q` PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(models): MODEL_REF widget, Resolve Model, demo catalog`

---

## Phase C — downloads, needs-list, editor, agents

### Task 13: Download queue

**Files:** Create `haybale_models/download.py`, `haybale_models/signals.py`; Modify `state/models_state.py`; Test `tests/models/test_download.py` (+ `http_server` fixture in conftest: `ThreadingHTTPServer` serving bytes with optional Range support, HTML mode, per-path delays)

**Interfaces:**
- Consumes: Tasks 7, 8, 9; `activity_tracker()` from `haywire.core.di.context`.
- Produces:
  - `DownloadJob(id: str, label: str, sha256: str | None, size: int | None, sources: tuple[str, ...], target: Path | None, state: Literal["queued","running","done","failed","cancelled"], done_bytes: int, total_bytes: int | None, error: str | None, principal: str | None)`.
  - `DownloadQueue(index: ModelIndex, hf_cache: Callable[[], Path], max_parallel: Callable[[], int])`: `.enqueue(spec: FetchSpec, principal: str | None) -> str` (dedup: a queued/running job with the same `sha256`, else same first source, returns the existing id); `.cancel(job_id)`; `.jobs() -> list[DownloadJob]`; `.add_listener(cb)` / `remove_listener` (zero-arg, fired at most every 0.25 s per job for progress, at once for state changes); `.stop()` (cancel all, join).
  - Takes `FetchSpec` (Task 10); a bundle enqueues one job per missing file under one label.
  - HTTPS: `httpx.stream("GET", url, headers={"Range": f"bytes={part_size}-"} if part_size else {}, follow_redirects=True, timeout=30)`; 206 → append; 200 with a `.part` present → truncate and restart; `Content-Type` starting `text/html` → mirror failed; hash while streaming (resumed `.part` is hashed first); size or digest mismatch → delete `.part`, next mirror; success → `os.replace(part, target)`, `index.add(target, sha, source=url)`. Mirrors in listed order; all fail → `failed` with the last error.
  - `hf://` → `hf.download(...)` into `hf_cache()`; verified against `sha256` when known.
  - Refuses (job `failed`, error = volume message) when `location_of(MODELS_VOLUME)` raises or the location does not exist.
  - Activity: `activity_tracker().start(principal, "models.download", {"label": …, "source": …})` per job, `finish(token, ok=…, error=…)`.
  - `ModelsChanged(Signal)`, `cross_session = True`, payload-free; `ModelsState` bridges queue + index listeners to it through the loop hop (same as `GraphAppState._on_history_changed`).
  - `ModelsState.queue`, `ModelsState.fetch(specs: list[FetchSpec], principal: str | None) -> list[str]`.

- [ ] **Step 1: Failing tests**

```python
def test_downloads_verifies_and_indexes(models_env, http_server): ...
def test_html_response_falls_through_to_next_mirror(...):
    job = run(spec(urls=(server.html("/a"), server.file("/b", DATA))))
    assert job.state == "done" and job.target.read_bytes() == DATA and not list(tmp.glob("*.part"))
def test_digest_mismatch_fails_over_then_fails(...)
def test_resume_appends_with_range(...)          # pre-seed .part with first half; server counts bytes sent == second half
def test_server_without_range_restarts(...)
def test_parallel_limit_respected(...)            # max_parallel=2, 4 slow jobs → never >2 running
def test_duplicate_enqueue_returns_same_job(...)
def test_cancel_removes_part(...)
def test_download_refuses_missing_volume(...)
def test_activity_record_per_job(...)
```

- [ ] **Step 2–4:** fail → implement → `uv run pytest tests/models/test_download.py -q` PASS (each test under 5 s; no sleeps longer than the throttle).
- [ ] **Step 5: Commit (ask first)** — `feat(models): download queue`

### Task 14: Needs-list → graph notice + card warnings

**Files:** Create `haybale_models/needs.py`; Modify `state/models_state.py`; Test `tests/models/test_needs.py`

**Interfaces:**
- Consumes: Tasks 2, 10, 11, 13; `BaseGraph.node_wrappers`, `BaseGraph.subgraphs` (recurse: `SubgraphDefinition` is a `BaseGraph`), `subscribe_to_validation` / `unsubscribe_from_validation`.
- Produces:
  - `NeedsReport(missing: list[NeededModel], total_bytes: int, unknown_size: int)`; `NeededModel(node_id: str, port_id: str, label: str, spec: FetchSpec, size: int | None)` — deduplicated by spec identity across nodes.
  - `collect_needs(graph: BaseGraph, resolve_fn) -> NeedsReport` — every node in the tree; every `MODEL_REF` inlet that holds its own value (not linked) and is not empty; preference via `preference_for`; `ModelMissing` → its `wanted[0]`. Wired refs are skipped (Q13 recap).
  - `ModelsState` on enable: `GraphAppState.add_graphs_listener(self._sync_graphs)`, catalog registry batch subscription, index + queue listeners → `_recheck(binding_id)` (debounced 0.2 s per binding, run off the UI thread). `_sync_graphs` subscribes validation on every graph in each new container's tree and unsubscribes on close; re-walk re-reconciles subgraph subscriptions.
  - Notice text: `"Needs {n} model(s) ({size})"`, `"Needs {n} model(s) ({size}, {k} of unknown size)"`; while any of the graph's specs has a running job: `"Fetching {i} of {n} — {pct} %"`. `action_label="Show in Models"`, `requires=AccessTier.VIEW` (showing is harmless; fetching inside the editor is ADMIN), `action` = sets `context.data[ModelsViewState].graph_filter = binding_id` and publishes `Reveal(editor=ModelsEditor)` (import `ModelsEditor` inside the action; Task 15 creates it — until then the test asserts only `graph_filter` and that a `Reveal` was published). Create `ModelsViewState` here (`state/models_view_state.py`, `graph_filter: str | None = None`). No missing models → `retract_notice`.
  - Card: nodes with a missing ref get `NodeWarning(kind="model", message="Model missing — Show in Models")` via `replace_warnings`, then `wrapper.redraw()` when it changed.

- [ ] **Step 1: Failing tests**

```python
def test_notice_posted_on_open_and_retracted_when_resolved(models_env, graph_app_state, graph_with_missing):
    graph_app_state.register(container); settle()
    assert graph_app_state.notices(eid)[0].text == "Needs 1 model (12.0 MB)"
    put_local(DATA); index.scan(); index.hash_pending(); settle()
    assert graph_app_state.notices(eid) == []
def test_subgraph_and_macro_interiors_counted(...)
def test_wired_ref_not_counted(...)
def test_edit_adding_a_ref_rechecks(...)         # via validation
def test_same_model_on_two_nodes_counted_once(...)
def test_progress_text_while_fetching(...)
def test_card_warning_set_and_cleared(...)
def test_close_unsubscribes_validation(...)
```

- [ ] **Step 2–4:** fail → implement → PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(models): needs-list notice and card warnings`

### Task 15: Models editor

**Files:** Create `haybale_models/editors/models_editor.py`; Test `tests/models/test_models_editor.py`

**Interfaces:**
- Consumes: Tasks 8, 9, 10, 13, 14; `VolumesEditor` (`barn/haybale-studio/haybale_studio/editors/volumes_editor.py`) as layout template (slot header, scroll area, rows); `ConfirmModal` for remove.
- Produces:
  - Reads `ModelsViewState.graph_filter` (Task 14).
  - `@editor(label="Models", icon=hui.icon.models, default_slot=SlotName.ACTION, requires=AccessTier.VIEW, description="Model files on this machine and where they come from")`, `@redraw_on(ModelsChanged, GraphNoticesChanged)`; scan + `hash_pending` thread on draw (Q19).
  - Header: title; disk usage `models: <used>`, `HF cache: <used>` (sum of index records / `list_cache`); **Rescan** (VIEW); filter chip "Needed by <graph name>" with clear when `graph_filter` is set, plus **Fetch all** (ADMIN) enqueuing every `NeededModel.spec` of that graph.
  - **Catalog** section: per library, per entry, one row per resource: name, variant, size, license, status (`local` / `HF cache` / `downloading 45 %` / `not downloaded` / `failed: <error>`), actions Download (ADMIN, not local) / Cancel (ADMIN, running) / Remove (ADMIN, local in models volume). With `graph_filter`, only resources in that graph's needs.
  - **Local** section: index records whose digest is in no catalog resource: relative path, size, `sha256[:12]`, source, "indexing… N %" for pending; Remove (ADMIN).
  - **HF cache** section: `list_cache` rows, read-only, **Reveal location** shows the absolute path in a copyable field (no delete).
  - Remove: `ConfirmModal` text "Delete <file> (<size>)? Used by: <graph names>" (open graphs whose `collect_needs`-style walk references that digest; "not used by an open graph" otherwise); on confirm delete file(s), `index.remove`. A file held by the pool stays loaded (Q20).
  - Marks: `models-row`, `models-download`, `models-remove`, `models-fetch-all`, `models-rescan`.
  - Handlers capture `ui.context.client` before redraw-causing work; download/remove re-check `context.can_access(AccessTier.ADMIN)` at click time.

- [ ] **Step 1: Failing tests** — `test_sections_list_catalog_local_and_hf`, `test_filter_shows_only_graph_needs_and_fetch_all_enqueues`, `test_download_button_hidden_below_admin`, `test_remove_confirm_lists_using_graphs_and_deletes`, `test_hf_rows_have_no_remove`, `test_progress_shown_from_queue`.
- [ ] **Step 2–4:** fail → implement → `uv run pytest tests/models/test_models_editor.py -q` PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(models): Models editor`

### Task 16: Farmhand tools

**Files:** Create `haybale_models/farmhands/model_tools.py`; Test `tests/models/test_model_tools.py`

**Interfaces:**
- Consumes: `farmhand`, `Farmhand`, `FarmhandContext`, `FarmhandError`, `ToolAnnotations` (shape of `barn/haybale-marketplace/haybale_marketplace/farmhands/catalog_tools.py`); `ctx.state(ModelsState)`, `ctx.state(GraphAppState)`.
- Produces (registry ids → MCP names `models_list`, `models_needs`, `models_fetch`):
  - `list` (`read_only_hint=True`, VIEW): `{catalog: [{key, name, variants: [{variant, size, status}]}], local: [{relative, size, sha256}], jobs: [{id, label, state, done_bytes, total_bytes, error}]}`; `detail=false` drops license/description.
  - `needs` (VIEW): arg `binding_id`; returns the `NeedsReport` rows (`label`, `size`, `node_ids`); unknown binding → `FarmhandError("graph_not_open", …, help="Call haystack_list_graphs …")`.
  - `fetch` (`requires=AccessTier.ADMIN`): args `binding_id` (fetch all its needs) or `keys: list[str]` (catalog keys, rank-0 variant per the default preference `[{}]`); returns job ids. No remove tool.

- [ ] **Step 1: Failing tests** — `test_list_shape_and_detail_flag`, `test_needs_for_open_graph`, `test_needs_unknown_binding_errors`, `test_fetch_requires_admin`, `test_fetch_enqueues_and_returns_ids`.
- [ ] **Step 2–4:** fail → implement → PASS.
- [ ] **Step 5: Commit (ask first)** — `feat(models): Farmhand model tools`

### Task 17: Full suite, generated docs, live check

**Files:** generated `barn/haybale-models/README.md`, `OVERVIEW.md`, `QUICKREF.md`, `docs/*.md`; regenerated haybale-example docs.

- [ ] **Step 1:** `uv run ruff check . && uv run ruff format --check .` → clean (fix with `ruff format` on touched files only).
- [ ] **Step 2:** full mypy command from CLAUDE.md (now including `barn/haybale-models/haybale_models/`) → clean.
- [ ] **Step 3:** save any dirty `barn/haybale-testing` edits first (`.insights/project_docs_test_reverts_barn_testing.md`), then `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo exit=$?` → `exit=0`; `uv run pytest -m browser -n 4 -q` → pass.
- [ ] **Step 4:** `uv run haywire docs barn/haybale-models` and `uv run haywire docs barn/haybale-example` → commit generated files with the docs commit.
- [ ] **Step 5: Live check** (`haywire-live-studio` skill; Chrome extension for UI):
  1. Start the studio; Volumes editor lists *Models* and *Hugging Face cache* (location = this machine's HF cache).
  2. Open a test graph with a Resolve Model node pointing at a demo-catalog entry → haystack row shows the notice icon (count 1); popup text "Needs 1 model (… MB)"; as VIEW the button "Show in Models" still shows; Models editor opens filtered.
  3. As ADMIN: Fetch all → notice text counts "Fetching 1 of 1 — … %", Models row shows progress, Activity shows a `models.download` record; when done the notice disappears and the node outputs a `models:` volume path.
  4. Drop a file into the models volume, Rescan → appears under Local; paste an `https://` URL into the widget → "not pinned"; Pin digest → undoable.
  5. Remove the downloaded model → confirmation names the graph; notice returns.
  6. `models_list` / `models_needs` / `models_fetch` via Farmhand.
  7. Open a graph saved with an older library version that has library-wide compatibility warnings (or post one by hand via Farmhand-free Python) → compatibility notice on the row, dismissable.
- [ ] **Step 6: Commit (ask first)** — `docs(models): generated library docs`

### Task 18: Glossary, ADRs, docs, spec status

**Files:**
- Modify: `docs/reference/glossary.md`, `docs/superpowers/plans/2026-10-30-spandrel-haybale-design.md` (§2.1 HF line, §2.5, §3 row S6, §5 lists)
- Create: three ADRs under `docs/adr/` (next free numbers), `docs/guides/model-catalogs.md` (or the docs section `docs/reference/doc-authoring.md` says such guides go in; wire nav per that page)

- [ ] **Step 1: Glossary** — add the terms below (format of existing entries).
- [ ] **Step 2: ADRs** — write the three below (format of existing ADRs).
- [ ] **Step 3: Library-author guide** — catalog file format (OpenModelDB fields + our additions, one example single-file entry and one bundle with variant tags), `filter` / `prefer` port options, `model_preference`, `acquire_port` / `release_node` in `on_shutdown` + `on_teardown`, and the rule that workers never download. Embed live snippets per `doc-authoring.md`.
- [ ] **Step 4: Spec** — §2.1: replace "Libraries that need env vars (`VISIONGRAPH_ASSET_DIR`, `HF_HOME`) set them *from* the volume" with "…read their location from the volume and pass it explicitly (`cache_dir=`); haybale-models sets no env var (S6-Q9)". §2.5: add "**S6 decisions**: see the [S6 plan](2026-10-31-s6-haybale-models.md)" and an "S6 deviations from plan" list (record every deviation made during execution, or "none"). §3: S6 row → `done (<merge commit>, <date>; live check …) — [plan](2026-10-31-s6-haybale-models.md)`. §5: strike the glossary terms and ADR candidate 4 that this slice landed.
- [ ] **Step 5: Commit (ask first)** — `docs(models): glossary, ADRs, catalog guide; S6 done`

---

## To land with the code (Task 18 text)

### Glossary terms
- **Model reference** — what a graph stores to name a model: a file reference or a catalog reference.
- **File reference** — a model reference to one file by source URI(s) and, once pinned, its sha256.
- **Catalog reference** — a model reference to a catalog entry; the file used is the variant that best fits this machine.
- **Model catalog** — the catalog entries all libraries ship; one JSON file per entry in a library's `catalog/` folder, OpenModelDB-shaped.
- **Catalog entry** — one model with metadata (architecture, scale, license, purpose) and its variants.
- **Variant** — one downloadable form of a catalog entry (format, backend, precision; a single file or a bundle of files).
- **Model store** — the `models` volume: human folders plus a digest index; files resolve by sha256 wherever they sit.
- **Needs-list** — the models an open graph's nodes refer to that this machine does not have; shown as a graph notice.
- **Graph notice** — a message a library posts about one open graph, shown on its haystack row with an optional action.
- **Loaded-models pool** — models loaded into memory, shared between nodes and freed when no running node holds them.

### ADRs
1. **Models are identified by digest; catalog references follow the catalog with host-picked variants.** Context: graphs must run on other machines and architectures. Decision: Q1, Q5, Q6, Q7. Alternatives: digest pin per catalog ref (foreign on another host), user-chosen variant stored in the graph (not portable). Consequence: bit-exact reproduction needs a file reference.
2. **The Hugging Face cache is a volume, shared by default, never deleted by haywire.** Decision: Q9 / 9b-C. Alternatives: HF default untouched (not relocatable), private haywire cache (multi-GB duplicates), plain HTTPS (no sharing; Xet risk). Consequence: `cache_dir=` everywhere, no env mutation; the volume's location is fixed at first enable.
3. **Graph notices are a library-extensible store on `GraphAppState`, shown on the haystack row.** Decision: Q13, 13b-B, 13d-A, Q23. Alternatives: haystack depends on haybale-models (makes it baseline), per-card warnings only, notice strip in the editor. Consequence: any library can tell the user about a graph without the graph manager knowing it; play is never gated.

### Docs to add
- Library-author guide for model catalogs (Task 18 Step 3).
- Haystack docs: the notice icon on a row and what its popup offers.
