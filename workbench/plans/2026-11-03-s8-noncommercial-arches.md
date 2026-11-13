# S8 Non-commercial Architectures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** haybale-spandrel can load the 10 `spandrel_extra_arches` architectures behind a library setting that is off by default, and says plainly wherever it matters that they are non-commercial.

**Architecture:** `spandrel_extra_arches` becomes a plain dependency of haybale-spandrel; no separate `haybale-spandrel-extra` library. Its code is imported only when the setting is on: the loader then passes spandrel's `ModelLoader` a *copy* of `MAIN_REGISTRY` plus `EXTRA_REGISTRY` (`ModelLoader(registry=...)`), so the global registry is never touched and the setting takes effect at the next model load. A model detected through an extra architecture carries a licence note on its card and reports itself as non-commercial.

**Tech Stack:** spandrel 0.4.2, spandrel_extra_arches 0.2.0, torch, haywire `LibrarySettings`, pytest.

**Spec:** [2026-10-30-spandrel-haybale-design.md](2026-10-30-spandrel-haybale-design.md) §2.7 "Extra arches" and the S8 row of §3. This plan **reverses Q19B/Q33A** (separate library, registered on load): decided with the user 2026-11-03 after a licence check (below). Task 5 records that in the spec.

**Repos:** code lives in `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-spandrel` (paths below are relative to it, `B = barn/haybale-spandrel/haybale_spandrel`). haywire-repo sees it through the symlink `barn/haybale-spandrel`; Task 1 touches haywire-repo's `pyproject.toml`/`uv.lock`, Task 5 its spec. Run tests from the haybale-spandrel repo: `uv run pytest tests/...`.

## Global Constraints

- Licence check (2026-11-03, from each `__arch/LICENSE` in chaiNNer-org/spandrel `libs/spandrel_extra_arches`) — the exact strings for `LICENSES`:
  `AdaCode` "CC BY-NC-SA 4.0" · `CodeFormer` "S-Lab License 1.0" · `DDColor` "Alibaba, academic and non-commercial use only" · `FeMaSR` "CC BY-NC-SA 4.0" · `M3SNet` "Academic Public License" · `MAT` "CC BY-NC 4.0" · `MIRNet2` "Academic Public License" · `MPRNet` "Academic Public License" · `Restormer` "Academic Public License" · `SRFormer` "CC BY-NC 4.0".
- The `spandrel_extra_arches` wheel ships **no** licence files and its metadata says "MIT" (the wrapper's licence); our docs must carry the real terms.
- Our own code stays MIT (`license = {text = "MIT"}` unchanged): we depend on the restricted code, we do not vendor it.
- Setting off (default) ⇒ `spandrel_extra_arches` is never imported. Never call `spandrel_extra_arches.install()` (it mutates `MAIN_REGISTRY`).
- Dependency floor: `spandrel_extra_arches>=0.2.0` (verified to install beside spandrel 0.4.2 / torch 2.15.0 / torchvision 0.29.2; registry copy = 42 + 10 = 52).
- Copy: the setting's label is "Non-commercial architectures"; the user-facing word is "non-commercial" (hyphenated, lower case mid-sentence).

## Review Focus

1. **Setting toggled while a model is cached in the pool** — turning it off must not keep serving an extra-architecture model on the next graph start. The pool key includes the flag (Task 3, `test_toggle_changes_pool_key`).
2. **Model failed while off, user turns it on** — the next run must load it without editing the graph (failed-stays-dirty retry; Task 3, `test_failed_model_loads_after_enabling`).
3. **Unsupported model while off** — the error must tell the user the setting exists and which architectures it covers, without importing the extras to find out (Task 2, `test_unsupported_while_off_names_the_setting`).
4. **Upstream adds an architecture** to `EXTRA_REGISTRY` in a later release — it would load with no licence on record. A test pins `LICENSES` to the registry's ids (Task 1, `test_every_extra_arch_has_a_licence`).
5. **Off path really never imports the extras** — checked in a fresh interpreter, since another test in the session may already have imported them (Task 2, `test_off_never_imports_extras`).

---

### Task 1: Dependency, licence table and registry choice

**Files:**
- Modify: `barn/haybale-spandrel/pyproject.toml` (dependencies)
- Modify: haywire-repo `pyproject.toml` (mypy `ignore_missing_imports` list, after `"spandrel.*"`)
- Create: `B/runtime/noncommercial.py`
- Test: `tests/test_noncommercial.py`

**Interfaces:**
- Produces (in `haybale_spandrel.runtime.noncommercial`):
  - `LICENSES: dict[str, str]` — arch id → licence string (Global Constraints, verbatim).
  - `registry(noncommercial: bool) -> spandrel.ArchRegistry` — `MAIN_REGISTRY` itself when `False`; when `True`, one cached (`functools.cache`) copy of `MAIN_REGISTRY` with `EXTRA_REGISTRY` added. Imports `spandrel_extra_arches` only inside the `True` branch.
  - `licence_of(descriptor: Any) -> str | None` — the licence string when the descriptor's architecture comes from `spandrel_extra_arches` (decide by `type(descriptor.architecture).__module__.startswith("spandrel_extra_arches.")`, look up by `str(descriptor.architecture.id)`), else `None`.

- [ ] **Step 1: Add the dependency.** `"spandrel_extra_arches>=0.2.0",` after `"spandrel>=0.4.2",` in `barn/haybale-spandrel/pyproject.toml`; add `"spandrel_extra_arches",` and `"spandrel_extra_arches.*",` to haywire-repo's mypy override list. Run `uv lock && uv sync` in haybale-spandrel, then `uv lock && uv sync` in haywire-repo. Expected: both add exactly `spandrel-extra-arches==0.2.0`.

- [ ] **Step 2: Write the failing tests** in `tests/test_noncommercial.py`:

```python
def test_every_extra_arch_has_a_licence() -> None:
    from spandrel_extra_arches import EXTRA_REGISTRY
    assert set(LICENSES) == {str(a.architecture.id) for a in EXTRA_REGISTRY}

def test_off_is_the_main_registry() -> None:
    assert registry(False) is spandrel.MAIN_REGISTRY

def test_on_adds_the_extras_to_a_copy() -> None:
    before = len(spandrel.MAIN_REGISTRY)
    combined = registry(True)
    assert combined is not spandrel.MAIN_REGISTRY
    assert len(combined) == before + len(LICENSES)
    assert "SRFormer" in combined and "SRFormer" not in spandrel.MAIN_REGISTRY
    assert registry(True) is combined

def test_licence_of_main_arch_is_none(tiny_sr_path: Path) -> None:
    assert licence_of(spandrel.ModelLoader().load_from_file(tiny_sr_path)) is None
```

- [ ] **Step 3: Run** `uv run pytest tests/test_noncommercial.py -v` — FAIL (module missing).
- [ ] **Step 4: Implement `B/runtime/noncommercial.py`** per Interfaces; module docstring names the setting and says the extras are imported only when it is on.
- [ ] **Step 5: Run** the same command — PASS.
- [ ] **Step 6: Commit** (with the user's consent; both repos) — `feat(spandrel): non-commercial architecture registry and licence table` / `chore: lock spandrel_extra_arches`.

### Task 2: Loader picks the registry and marks non-commercial models

**Files:**
- Modify: `B/runtime/loader.py` (`load_model`)
- Modify: `B/value/spandrel_model.py` (`SpandrelModel`)
- Modify: `tests/conftest.py` (new fixture)
- Test: `tests/test_loader.py`

**Interfaces:**
- Consumes: Task 1's `registry`, `licence_of`, `LICENSES`.
- Produces:
  - `load_model(path, device, precision, *, notes=(), noncommercial: bool = False) -> SpandrelModel` — loads with `ModelLoader(device="cpu", registry=registry(noncommercial))`.
  - `SpandrelModel.licence: str | None = None` (new dataclass field, after `notes`) and `SpandrelModel.noncommercial -> bool` (`licence is not None`).
  - `SpandrelModel.status()` appends `" · non-commercial"` when `noncommercial`.
  - `UNSUPPORTED_HINT: str` in `loader.py`: `"if it is one of AdaCode, CodeFormer, DDColor, FeMaSR, M3SNet, MAT, MIRNet2, MPRNet, Restormer or SRFormer, turn on 'Non-commercial architectures' in the Spandrel settings"` — the names are `sorted(LICENSES)` joined, not typed out.
  - Fixture `srformer_path(model_dir) -> Path`: `SRFormer(embed_dim=12, depths=[1], num_heads=[1])` from `spandrel_extra_arches.architectures.SRFormer.__arch.SRFormer`, saved as `.safetensors` (~6.6k parameters; detects as `SRFormer`, Restoration, 1x; main registry rejects it — verified).

- [ ] **Step 1: Write the failing tests** in `tests/test_loader.py`:

```python
def test_extra_arch_loads_when_on(srformer_path: Path) -> None:
    model = load_model(srformer_path, CPU, "auto", noncommercial=True)
    assert model.architecture == "SRFormer"
    assert model.licence == "CC BY-NC 4.0"
    assert model.noncommercial
    assert model.status().endswith(" · non-commercial")
    assert any("CC BY-NC 4.0" in n and "non-commercial" in n for n in model.notes)

def test_unsupported_while_off_names_the_setting(srformer_path: Path) -> None:
    with pytest.raises(spandrel.UnsupportedModelError, match="Non-commercial architectures"):
        load_model(srformer_path, CPU, "auto")

def test_main_arch_is_not_marked(tiny_sr_path: Path) -> None:
    model = load_model(tiny_sr_path, CPU, "auto", noncommercial=True)
    assert model.licence is None and not model.noncommercial
    assert model.status() == "RealESRGAN Compact · 2x · RGB · cpu fp32"

def test_off_never_imports_extras(tiny_sr_path: Path) -> None:
    code = (
        "import sys; from pathlib import Path; import torch;"
        "from haybale_spandrel.runtime.loader import load_model;"
        f"load_model(Path({str(tiny_sr_path)!r}), torch.device('cpu'), 'auto');"
        "assert not any(m.startswith('spandrel_extra_arches') for m in sys.modules)"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
```

`test_garbage_file_is_unsupported` stays as it is (the hint keeps the exception type).

- [ ] **Step 2: Run** `uv run pytest tests/test_loader.py -v` — the four new tests FAIL.
- [ ] **Step 3: Implement.** In `load_model`: pick the registry; on `UnsupportedModelError` with `noncommercial=False`, raise `UnsupportedModelError(f"{exc} — {UNSUPPORTED_HINT}")` from it; after loading, `licence = licence_of(descriptor)` and, when set, append the note `f"{architecture name} is non-commercial only ({licence})"` to the notes and pass `licence=` to `SpandrelModel`. Update the docstring (`noncommercial` arg, the hint).
- [ ] **Step 4: Run** `uv run pytest tests/test_loader.py -v` — PASS.
- [ ] **Step 5: Commit** (with consent) — `feat(spandrel): load non-commercial architectures on request and mark them`.

### Task 3: Setting, Load Model wiring, Model Info outlet

**Files:**
- Modify: `B/settings/spandrel_settings.py`
- Modify: `B/nodes/load_model.py` (`worker`, class docstring)
- Modify: `B/nodes/model_info.py` (new outlet, docstring)
- Test: `tests/test_library.py`, `tests/test_load_model.py`

**Interfaces:**
- Consumes: Task 2's `load_model(..., noncommercial=)`, `SpandrelModel.licence`.
- Produces:
  - `SpandrelSettings.noncommercial_architectures = setting[BOOL](False, label="Non-commercial architectures", description=...)` — description (exact): `"Also load AdaCode, CodeFormer, DDColor, FeMaSR, M3SNet, MAT, MIRNet2, MPRNet, Restormer and SRFormer models. Their code is licensed for non-commercial use only (CC BY-NC, S-Lab, Academic Public License); leave this off for commercial work. Applies from the next graph start."` The settings panel renders it with no panel change (`render_schema`).
  - `LoadModelNode.worker` reads `bool(SpandrelSettings().noncommercial_architectures)` (the `memory_budget` pattern in `upscale_image.py:129`), puts it in the pool key — `key = (resolved.key, (str(device), precision, noncommercial))` — and passes it to `load_model`.
  - Model Info outlet `BOOL.as_outlet("noncommercial", label="Non-commercial", description="Whether the model's architecture is licensed for non-commercial use only")`, set from `model.noncommercial`; a `licence` STRING outlet is not added (the card note carries it).

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_library.py`: extend the defaults test — `assert bag.noncommercial_architectures is False`.
  - `tests/test_load_model.py`, using the existing `graph`/`models_env`/`add_loader`/`place_model`/`run_from` helpers and a fixture that sets `SpandrelSettings().noncommercial_architectures`, reads it back (settings writes can be dropped silently — `.insights/project_settings_bags_include_props.md`), and restores `False` on teardown:

```python
def test_toggle_changes_pool_key(...) -> None:
    # tiny_sr model, run once off and once on: the node's cache.key differs only in the flag
    assert key_off[1][2] is False and key_on[1][2] is True and key_off[0] == key_on[0]

def test_failed_model_loads_after_enabling(...) -> None:
    # srformer placed and picked; setting off → run → node failed, error text contains
    # "Non-commercial architectures"; set on → run again (no graph edit) → node succeeded,
    # status.loaded ends with " · non-commercial", and the card warnings include the licence note

def test_model_info_reports_noncommercial(...) -> None:
    # setting on, Load Model → Spandrel Model Info: outlet "noncommercial" is True for srformer,
    # False for tiny_sr
```

- [ ] **Step 2: Run** `uv run pytest tests/test_library.py tests/test_load_model.py -v` — new tests FAIL.
- [ ] **Step 3: Implement** per Interfaces. Load Model's docstring gains one bullet: models of the non-commercial architectures load only with the library setting on, and say so on the card. Model Info's docstring lists the new outlet.
- [ ] **Step 4: Run** the same command — PASS. Then the whole repo suite: `uv run pytest tests/ -q > /tmp/s8.log 2>&1; echo "exit=$?"` — exit 0.
- [ ] **Step 5: Commit** (with consent) — `feat(spandrel): Non-commercial architectures setting`.

### Task 4: Licence notes in the library docs

**Files:**
- Create: `B/NOTES.md`
- Modify: `B/haybale.toml` (`notes = "NOTES.md"`, uncomment the existing line)
- Regenerate: `barn/haybale-spandrel/README.md`, `B/OVERVIEW.md`, `B/QUICKREF.md`, `B/docs/*.md`

- [ ] **Step 1: Write `B/NOTES.md`** (the README prepends it, `render_readme`). Content, in this order:
  1. One paragraph: this library's own code is MIT. With the *Non-commercial architectures* setting on (off by default) it runs code from `spandrel_extra_arches`, whose architectures are licensed for **non-commercial use only**; with it off that code is installed but never imported.
  2. Table: architecture · licence — the ten rows of Global Constraints.
  3. One line: that package's metadata says "MIT", which covers only its wrapper; each architecture's licence is in its `__arch/LICENSE` in the spandrel repo (link `https://github.com/chaiNNer-org/spandrel/tree/main/libs/spandrel_extra_arches`).
  4. One line: model weights carry their own licence, whichever architecture runs them — check it on the model's page.
- [ ] **Step 2: Set `notes = "NOTES.md"`** in `B/haybale.toml`.
- [ ] **Step 3: Regenerate** from haywire-repo: `uv run haywire docs barn/haybale-spandrel`. Expected: README starts with the NOTES text above the share-url marker; the Settings and Model Info docs show the new setting/outlet.
- [ ] **Step 4: Lint** in haybale-spandrel: `uv run ruff check . && uv run ruff format --check .` — clean; mypy on `barn/haybale-spandrel/haybale_spandrel` — no new errors vs. the pre-edit baseline.
- [ ] **Step 5: Commit** (with consent) — `docs(spandrel): licence notes for the non-commercial architectures`.

### Task 5: Spec status and decision record

**Files:**
- Modify: haywire-repo `docs/superpowers/plans/2026-10-30-spandrel-haybale-design.md`
- Modify: haywire-repo `docs/reference/glossary.md`

- [ ] **Step 1: §2.7.** Replace the `haybale-spandrel-extra` mention in the scaffold bullet and the "Extra arches (Q19B, Q33A)" bullet with: "**Non-commercial architectures (S8, reverses Q19B/Q33A, 2026-11-03):** no separate library. haybale-spandrel depends on `spandrel_extra_arches` and imports it only when the library setting *Non-commercial architectures* (off) is on, loading through a copy of `MAIN_REGISTRY` + `EXTRA_REGISTRY`; all ten are non-commercial (licence table in the library's NOTES.md). A model that failed while off loads on the next run after turning it on (failed-stays-dirty)." Add any deviations from this plan.
- [ ] **Step 2: §3 table.** S8 row: slice "non-commercial architectures (setting)", where "haybale-spandrel", status `done` with merge commits of both repos, date, and a link to this plan.
- [ ] **Step 3: Glossary.** Add **Non-commercial architecture** — a spandrel architecture from `spandrel_extra_arches`, licensed for non-commercial use only; loaded only with the Spandrel setting of that name on.
- [ ] **Step 4: Commit** (with consent) — `docs(spandrel): S8 done — non-commercial architectures`.

---

## Out of scope

- Showing licences in the marketplace (it has no licence field today).
- A per-node override of the setting (library-wide only, by design: it is a licence decision, not a tuning knob).
- Making extra architectures useful beyond loading: FaceSR (CodeFormer) still needs the Face Upscale follow-up; DDColor colourisation and MAT inpainting run through the existing Upscale Image / Inpaint nodes as their purposes allow, untested here.
- The `size_requirements.square` gap (Uformer) — separate S7 follow-up.
