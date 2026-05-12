# Haystack Autosave + Rehydrate Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the broken on-enable haystack rehydrate (last_haystack_name is never written, so reload always skips), then add an opt-in autosave with three modes (off / on_exit / continuous) exposed through a new properties-editor panel.

**Architecture:** PR2's carve-out moved haystack persistence from the studio into the haybale-haystack library, but left the "which haystack is active" name pointing at workspace_manager.snapshot["haystack"] (legacy) on the write side and HaystackSettings.last_haystack_name (new) on the read side. Nothing wrote to the new location, so on_enable never rehydrated. This plan promotes save_haystack/load_haystack/start_execution/stop_execution to public methods on HaystackState (so the state owns its persistence end-to-end), wires the editor's UI calls through them, adds a three-mode autosave setting, and exposes it in a new "Haystack" panel pinned to AppFocus in the properties editor.

**Tech Stack:** Python 3, NiceGUI, haywire DI framework (LibraryState, LibrarySettings, panels, session signals), pytest, ruff, mypy, toml.

---

## Background context (read first)

- Bug summary: `HaystackState.on_enable` reads `self._haystack_settings.last_haystack_name` and calls `persistence.load_haystack(...)` if non-empty. Nothing in production code ever sets `last_haystack_name`, so it stays `""` forever and the rehydrate branch is dead.
- Pre-PR2, the legacy `HaywireApp.try_load_startup_haystack` read the name from `workspace_manager.snapshot["haystack"]`. The current editor save flow (`haystack_editor._on_save_haystack`) still writes there — a vestigial mirror of legacy behaviour. We will retire that mirror.
- Existing public surface on `HaystackState`: `create_new`, `open_graph`, `save_graph`, `rename_graph`, `remove_entry`, `get_by_id`, `get_by_path`, `get_by_graph`, `all_entries`, `has_unsaved`, `unsaved_entries`, `list_haystacks`, `list_graph_files`, `rename_haystack`, `delete_haystack`. We will add `save_haystack`, `load_haystack`, `start_execution`, `stop_execution`.
- Decisions locked during the design interview (see Q1–Q10):
  - Q1: `last_haystack_name` lives in `HaystackSettings`. The legacy `workspace_manager.snapshot["haystack"]` mirror goes away.
  - Q2/Q4: Default behaviour writes the TOML only on explicit save. A new three-mode setting (`off` / `on_exit` / `continuous`) gates auto-writes.
  - Q3: New `HaystackState.save_haystack(name, active_path)` and `.load_haystack(name)` own the dual write (TOML + last_haystack_name).
  - Q5/Q6: Continuous-mode triggers are open / save / remove / rename / start / stop. start/stop are wrapped on `HaystackState` (rehydrate keeps the direct `entry.start_execution` call).
  - Q7: Seven explicit `_autosave_if_continuous()` calls — one per mutator. Helper is independent of `_broadcast_data_mutated`.
  - Q8: Continuous mode silently skips untitled entries (matches `dump_haystack`'s existing contract); the limitation is documented in the setting's `description` field.
  - Q9: Single-control panel pinned to `AppFocus`, label "Haystack", icon `hui.icon.save`.
  - Q10: Continuous-mode dumps omit `active_graph` from the TOML; only explicit `save_haystack(name, active_path)` writes it.

## File Structure

### Files modified

- `barn/haybale-haystack/haybale_haystack/settings/haystack_settings.py` — add `autosave: setting[str]` field (Task 1).
- `barn/haybale-haystack/haybale_haystack/state/haystack_state.py` — add `save_haystack`, `load_haystack`, `start_execution`, `stop_execution`, `_autosave_if_continuous`; on_disable autosave-on-exit branch; seven mutator call-site additions (Tasks 2–6).
- `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py` — migrate save/load/start/stop call sites to the new HaystackState methods; drop the legacy `workspace_manager.snapshot["haystack"]` writes (Task 7).

### Files created

- `barn/haybale-haystack/haybale_haystack/panels/haystack_settings_panel.py` — new properties-editor panel for the autosave setting (Task 8).

### Test files

- `tests/haystack/test_haystack_settings.py` — add coverage for the new `autosave` field (Task 1).
- `tests/haystack/test_haystack_state.py` — add coverage for `save_haystack`/`load_haystack`/`start_execution`/`stop_execution`/`_autosave_if_continuous`/on_disable autosave (Tasks 2–6).
- `tests/haystack/test_haystack_settings_panel.py` — new file for the panel (Task 8).

---

## Task 1: Add the `autosave` field to HaystackSettings

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/settings/haystack_settings.py`
- Test: `tests/haystack/test_haystack_settings.py`

- [ ] **Step 1: Establish the pre-edit baseline**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/settings/haystack_settings.py tests/haystack/test_haystack_settings.py
uv run mypy barn/haybale-haystack/haybale_haystack/settings/haystack_settings.py
```
Expected: clean. (Per CLAUDE.md, the codebase has no errors. If anything fails, stop and fix the baseline first.)

- [ ] **Step 2: Write the failing test**

Append to `tests/haystack/test_haystack_settings.py`:

```python
def test_default_autosave_is_off():
    from haybale_haystack.settings.haystack_settings import HaystackSettings

    s = HaystackSettings()
    assert s.autosave == "off"


def test_can_set_and_read_autosave():
    from haybale_haystack.settings.haystack_settings import HaystackSettings
    from haywire.core.settings.registry import SettingsRegistry

    registry = SettingsRegistry()
    registry.register_schema(HaystackSettings)
    HaystackSettings._registry = registry
    try:
        s = HaystackSettings()
        s.autosave = "continuous"
        assert s.autosave == "continuous"
        s.autosave = "on_exit"
        assert s.autosave == "on_exit"
    finally:
        HaystackSettings._registry = None


def test_autosave_choices_are_off_on_exit_continuous():
    """The schema must declare the three valid options so UI selects can enumerate them."""
    from haybale_haystack.settings.haystack_settings import HaystackSettings

    field = HaystackSettings.__dict__["autosave"]
    assert set(field.choices or []) == {"off", "on_exit", "continuous"}
```

- [ ] **Step 3: Run the tests; confirm failure**

Run:
```sh
uv run pytest tests/haystack/test_haystack_settings.py -v
```
Expected: the three new tests fail with `AttributeError: ... 'autosave'` or similar — the field does not yet exist.

- [ ] **Step 4: Add the field**

Open `barn/haybale-haystack/haybale_haystack/settings/haystack_settings.py` and append after `new_counter`:

```python
    autosave = setting[str](
        "off",
        choices=["off", "on_exit", "continuous"],
        label="Autosave",
        description=(
            "When to auto-write the haystack TOML. "
            "'off' = save only on explicit user action. "
            "'on_exit' = also dump on app shutdown. "
            "'continuous' = also dump on every open/save/remove/rename/start/stop. "
            "Untitled (never-saved) graphs are not preserved by autosave; save them "
            "explicitly first."
        ),
        category="haystack",
        order=30,
    )
```

- [ ] **Step 5: Re-run the tests; confirm they pass**

Run:
```sh
uv run pytest tests/haystack/test_haystack_settings.py -v
```
Expected: all green, including the three new tests.

- [ ] **Step 6: Re-run lint + type-check baseline**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/settings/haystack_settings.py tests/haystack/test_haystack_settings.py
uv run mypy barn/haybale-haystack/haybale_haystack/settings/haystack_settings.py
```
Expected: clean.

- [ ] **Step 7: Commit**

```sh
git add barn/haybale-haystack/haybale_haystack/settings/haystack_settings.py tests/haystack/test_haystack_settings.py
git commit -m "feat(haystack): add autosave setting (off/on_exit/continuous)

Three-mode field on HaystackSettings; default 'off' preserves
existing behaviour. Wire-up to actual autosave triggers comes in
later commits."
```

---

## Task 2: Add `save_haystack` / `load_haystack` public methods on HaystackState

These wrap `persistence.dump_haystack` / `persistence.load_haystack` and atomically update `last_haystack_name`. They become the single public entry points for named-haystack persistence; the editor migrates onto them in Task 7.

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`
- Test: `tests/haystack/test_haystack_state.py`

- [ ] **Step 1: Establish the pre-edit baseline**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/state/haystack_state.py tests/haystack/test_haystack_state.py
uv run mypy barn/haybale-haystack/haybale_haystack/state/haystack_state.py
```
Expected: clean.

- [ ] **Step 2: Write the failing tests**

Append to `tests/haystack/test_haystack_state.py`:

```python
def test_save_haystack_calls_persistence_and_updates_last_name(state_with_mocked_deps, tmp_path, monkeypatch):
    """save_haystack delegates to persistence.dump_haystack and records the name in settings."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path

    dumped = {}

    def fake_dump(s, root, name, active_path=None):
        dumped["name"] = name
        dumped["root"] = root
        dumped["active_path"] = active_path
        return root / "haystacks" / f"{name}.toml"

    monkeypatch.setattr("haybale_haystack.persistence.dump_haystack", fake_dump)

    active = tmp_path / "graphs" / "foo.haywire"
    state.save_haystack("session1", active_path=active)

    assert dumped == {"name": "session1", "root": tmp_path, "active_path": active}
    assert state._haystack_settings.last_haystack_name == "session1"


def test_save_haystack_without_active_path(state_with_mocked_deps, tmp_path, monkeypatch):
    """active_path is optional; default None propagates through."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path

    captured = {}

    def fake_dump(s, root, name, active_path=None):
        captured["active_path"] = active_path
        return root / "haystacks" / f"{name}.toml"

    monkeypatch.setattr("haybale_haystack.persistence.dump_haystack", fake_dump)

    state.save_haystack("session1")
    assert captured["active_path"] is None
    assert state._haystack_settings.last_haystack_name == "session1"


def test_load_haystack_calls_persistence_and_updates_last_name(state_with_mocked_deps, tmp_path, monkeypatch):
    """load_haystack delegates to persistence.load_haystack and records the name in settings."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path

    expected_active = tmp_path / "graphs" / "foo.haywire"

    def fake_load(s, root, name):
        return expected_active

    monkeypatch.setattr("haybale_haystack.persistence.load_haystack", fake_load)

    result = state.load_haystack("session1")

    assert result == expected_active
    assert state._haystack_settings.last_haystack_name == "session1"
```

- [ ] **Step 3: Run the tests; confirm failure**

Run:
```sh
uv run pytest tests/haystack/test_haystack_state.py -v -k "save_haystack or load_haystack"
```
Expected: the new tests fail with `AttributeError: ... save_haystack` (no such method yet).

- [ ] **Step 4: Add the methods**

Open `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`. Locate the section header comment `# Haystack file management — thin wrappers over persistence.*` (around line 362). Just above it, add a new section:

```python
    # ------------------------------------------------------------------
    # Named-haystack persistence — the authoritative API
    # ------------------------------------------------------------------

    def save_haystack(self, name: str, active_path: Optional[Path] = None) -> Path:
        """Persist the current registry to the named haystack TOML.

        Atomically: writes the TOML via ``persistence.dump_haystack`` AND
        updates ``HaystackSettings.last_haystack_name = name`` so the next
        ``on_enable`` rehydrates from the same file.

        Returns the path to the written TOML file.
        """
        from haybale_haystack import persistence

        assert self._workspace_root is not None, "save_haystack requires on_enable to have run"
        target = persistence.dump_haystack(self, self._workspace_root, name, active_path=active_path)
        if self._haystack_settings is not None:
            self._haystack_settings.last_haystack_name = name
        return target

    def load_haystack(self, name: str) -> Optional[Path]:
        """Load the named haystack and open all graphs it lists.

        Returns the absolute path of the haystack's stored ``active_graph``
        (if any), so callers can route a ``Reveal`` to that entry. Updates
        ``HaystackSettings.last_haystack_name = name``.

        Note: caller is responsible for clearing existing entries first if
        the desired semantics are "replace" rather than "merge". Mirrors
        ``persistence.load_haystack`` (which does NOT clear).
        """
        from haybale_haystack import persistence

        assert self._workspace_root is not None, "load_haystack requires on_enable to have run"
        active = persistence.load_haystack(self, self._workspace_root, name)
        if self._haystack_settings is not None:
            self._haystack_settings.last_haystack_name = name
        return active
```

- [ ] **Step 5: Re-run the tests; confirm they pass**

Run:
```sh
uv run pytest tests/haystack/test_haystack_state.py -v -k "save_haystack or load_haystack"
```
Expected: all three new tests pass.

- [ ] **Step 6: Re-run the full haystack test suite to catch regressions**

Run:
```sh
uv run pytest tests/haystack/ -v
```
Expected: all green.

- [ ] **Step 7: Re-run lint + type-check**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/state/haystack_state.py tests/haystack/test_haystack_state.py
uv run mypy barn/haybale-haystack/haybale_haystack/state/haystack_state.py
```
Expected: clean.

- [ ] **Step 8: Commit**

```sh
git add barn/haybale-haystack/haybale_haystack/state/haystack_state.py tests/haystack/test_haystack_state.py
git commit -m "feat(haystack): add HaystackState.save_haystack/load_haystack

These wrap persistence.dump_haystack/load_haystack and atomically
keep HaystackSettings.last_haystack_name in sync — fixing the bug
where on_enable's rehydrate branch was dead because no production
code wrote to last_haystack_name."
```

---

## Task 3: Add `start_execution` / `stop_execution` wrappers on HaystackState

The state needs to observe execution transitions for continuous-mode autosave (Q5-B/Q6-A). Wrap the GraphEntry methods so the state is on the call path.

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`
- Test: `tests/haystack/test_haystack_state.py`

- [ ] **Step 1: Establish the pre-edit baseline**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/state/haystack_state.py
uv run mypy barn/haybale-haystack/haybale_haystack/state/haystack_state.py
```
Expected: clean.

- [ ] **Step 2: Write the failing tests**

Append to `tests/haystack/test_haystack_state.py`:

```python
def test_start_execution_calls_entry_method(state_with_mocked_deps):
    """HaystackState.start_execution forwards to entry.start_execution."""
    state = state_with_mocked_deps
    entry = MagicMock()

    state.start_execution(entry)

    entry.start_execution.assert_called_once_with()


def test_stop_execution_calls_entry_method(state_with_mocked_deps):
    """HaystackState.stop_execution forwards to entry.stop_execution."""
    state = state_with_mocked_deps
    entry = MagicMock()

    state.stop_execution(entry)

    entry.stop_execution.assert_called_once_with()
```

- [ ] **Step 3: Run the tests; confirm failure**

Run:
```sh
uv run pytest tests/haystack/test_haystack_state.py -v -k "start_execution or stop_execution"
```
Expected: failures with `AttributeError`.

- [ ] **Step 4: Add the wrapper methods**

In `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`, locate the comment `# Lookups` (around line 326). Just above it (after `remove_entry`), add a new section:

```python
    # ------------------------------------------------------------------
    # Execution wrappers — UI call sites route through these so the
    # state observes start/stop transitions (continuous autosave hook).
    # persistence.load_haystack still calls entry.start_execution()
    # directly during rehydrate — that is the one path that should NOT
    # trigger an autosave write back to the TOML.
    # ------------------------------------------------------------------

    def start_execution(self, entry: GraphEntry) -> None:
        """Start execution on *entry* and trigger continuous autosave."""
        entry.start_execution()
        # _autosave_if_continuous wired in Task 5.

    def stop_execution(self, entry: GraphEntry) -> None:
        """Stop execution on *entry* and trigger continuous autosave."""
        entry.stop_execution()
        # _autosave_if_continuous wired in Task 5.
```

- [ ] **Step 5: Re-run the tests; confirm they pass**

Run:
```sh
uv run pytest tests/haystack/test_haystack_state.py -v -k "start_execution or stop_execution"
```
Expected: both green.

- [ ] **Step 6: Re-run the full haystack test suite**

Run:
```sh
uv run pytest tests/haystack/ -v
```
Expected: all green.

- [ ] **Step 7: Re-run lint + type-check**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/state/haystack_state.py
uv run mypy barn/haybale-haystack/haybale_haystack/state/haystack_state.py
```
Expected: clean.

- [ ] **Step 8: Commit**

```sh
git add barn/haybale-haystack/haybale_haystack/state/haystack_state.py tests/haystack/test_haystack_state.py
git commit -m "feat(haystack): add start_execution/stop_execution wrappers on HaystackState

UI call sites will route through these so HaystackState can observe
execution transitions (needed for continuous-mode autosave). The
rehydrate path in persistence.load_haystack keeps calling
entry.start_execution() directly — by design, rehydrate must not
trigger an autosave back to the TOML."
```

---

## Task 4: Add `_autosave_if_continuous` helper

The helper checks the autosave mode and dumps the TOML when continuous. This task introduces the helper without yet wiring it from any mutator (Task 5 wires the call sites; Task 6 wires on_disable).

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`
- Test: `tests/haystack/test_haystack_state.py`

- [ ] **Step 1: Establish the pre-edit baseline**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/state/haystack_state.py
uv run mypy barn/haybale-haystack/haybale_haystack/state/haystack_state.py
```
Expected: clean.

- [ ] **Step 2: Write the failing tests**

Append to `tests/haystack/test_haystack_state.py`:

```python
def test_autosave_if_continuous_off_does_nothing(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "off"
    state._haystack_settings.last_haystack_name = "session1"

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state._autosave_if_continuous()
    assert called == []


def test_autosave_if_continuous_on_exit_does_nothing(state_with_mocked_deps, tmp_path, monkeypatch):
    """on_exit fires from on_disable, NOT from this helper."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "on_exit"
    state._haystack_settings.last_haystack_name = "session1"

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state._autosave_if_continuous()
    assert called == []


def test_autosave_if_continuous_dumps_when_enabled(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "continuous"
    state._haystack_settings.last_haystack_name = "session1"

    captured = {}

    def fake_dump(s, root, name, active_path=None):
        captured["name"] = name
        captured["active_path"] = active_path
        return root / "haystacks" / f"{name}.toml"

    monkeypatch.setattr("haybale_haystack.persistence.dump_haystack", fake_dump)

    state._autosave_if_continuous()
    assert captured["name"] == "session1"
    # Q10A: continuous-mode dumps must NOT include active_graph.
    assert captured["active_path"] is None


def test_autosave_if_continuous_skips_when_no_last_name(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "continuous"
    state._haystack_settings.last_haystack_name = ""

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state._autosave_if_continuous()
    assert called == []


def test_autosave_if_continuous_skips_when_settings_missing(state_with_mocked_deps, tmp_path, monkeypatch):
    """Defensive: tests/dev environments may have _haystack_settings = None."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings = None

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state._autosave_if_continuous()
    assert called == []
```

- [ ] **Step 3: Run the tests; confirm failure**

Run:
```sh
uv run pytest tests/haystack/test_haystack_state.py -v -k "autosave_if_continuous"
```
Expected: failures with `AttributeError: ... _autosave_if_continuous`.

- [ ] **Step 4: Add the helper**

In `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`, locate the `# Internal helpers` section (around line 396). Just above `_subscribe_validation`, add:

```python
    def _autosave_if_continuous(self) -> None:
        """Dump the haystack TOML if continuous-mode autosave is enabled.

        No-op in 'off' or 'on_exit' modes (on_exit fires from on_disable,
        not from per-mutator hooks). Continuous-mode dumps omit
        ``active_graph`` from the TOML — only explicit ``save_haystack``
        writes that field (Q10A: the active graph is a per-session
        concept; HaystackState is app-wide and has no single source of
        truth for it).

        Defensively skips when ``_haystack_settings`` is None or when
        ``last_haystack_name`` is empty — both indicate a not-yet-named
        workspace where no TOML target exists.
        """
        if self._haystack_settings is None:
            return
        if self._haystack_settings.autosave != "continuous":
            return
        name = self._haystack_settings.last_haystack_name
        if not name:
            return
        if self._workspace_root is None:
            return
        from haybale_haystack import persistence

        try:
            persistence.dump_haystack(self, self._workspace_root, name)
        except Exception as exc:
            logger.warning(f"HaystackState: continuous autosave failed: {exc}")
```

- [ ] **Step 5: Re-run the tests; confirm they pass**

Run:
```sh
uv run pytest tests/haystack/test_haystack_state.py -v -k "autosave_if_continuous"
```
Expected: all five new tests pass.

- [ ] **Step 6: Re-run lint + type-check**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/state/haystack_state.py
uv run mypy barn/haybale-haystack/haybale_haystack/state/haystack_state.py
```
Expected: clean.

- [ ] **Step 7: Commit**

```sh
git add barn/haybale-haystack/haybale_haystack/state/haystack_state.py tests/haystack/test_haystack_state.py
git commit -m "feat(haystack): add _autosave_if_continuous helper

Pure helper, not yet wired from any call site. Continuous-mode
dumps omit active_graph (Q10A). Defensive guards for missing
settings and empty last_haystack_name."
```

---

## Task 5: Wire `_autosave_if_continuous` into the seven mutators

The seven call sites (Q5-B / Q7-A): `create_new`, `open_graph`, `save_graph`, `rename_graph`, `remove_entry`, `start_execution`, `stop_execution`. Each gets one extra line.

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`
- Test: `tests/haystack/test_haystack_state.py`

- [ ] **Step 1: Establish the pre-edit baseline**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/state/haystack_state.py
uv run mypy barn/haybale-haystack/haybale_haystack/state/haystack_state.py
```
Expected: clean.

- [ ] **Step 2: Write the failing tests**

Append to `tests/haystack/test_haystack_state.py`:

```python
@pytest.fixture
def state_in_continuous_mode(state_with_mocked_deps, tmp_path):
    """state_with_mocked_deps + autosave=continuous + a named haystack."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "continuous"
    state._haystack_settings.last_haystack_name = "session1"
    return state


def _patch_dump(monkeypatch):
    """Capture every persistence.dump_haystack call into a list."""
    calls: list[dict] = []

    def fake_dump(s, root, name, active_path=None):
        calls.append({"name": name, "active_path": active_path})
        return root / "haystacks" / f"{name}.toml"

    monkeypatch.setattr("haybale_haystack.persistence.dump_haystack", fake_dump)
    return calls


def test_create_new_triggers_continuous_autosave(state_in_continuous_mode, monkeypatch):
    calls = _patch_dump(monkeypatch)
    state_in_continuous_mode.create_new()
    assert any(c["name"] == "session1" and c["active_path"] is None for c in calls)


def test_open_graph_triggers_continuous_autosave(state_in_continuous_mode, tmp_path, monkeypatch):
    calls = _patch_dump(monkeypatch)
    p = tmp_path / "graphs" / "foo.haywire"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")  # empty .haywire — load_from_file is mocked via the factory below

    # NodeFactory is a MagicMock from the fixture, and BaseGraph.load_from_file
    # will be called on a real BaseGraph; for this test we just need open_graph
    # to fire the autosave hook regardless of file content.
    with patch("haywire.core.graph.base.BaseGraph.load_from_file"), \
         patch("haywire.core.graph.base.BaseGraph.force_validation"):
        state_in_continuous_mode.open_graph(p)

    assert any(c["name"] == "session1" for c in calls)


def test_save_graph_triggers_continuous_autosave(state_in_continuous_mode, tmp_path, monkeypatch):
    calls = _patch_dump(monkeypatch)
    state = state_in_continuous_mode
    entry = state.create_new()
    entry.graph = MagicMock()
    entry.graph.save_to_file.return_value = True

    target = tmp_path / "graphs" / "foo.haywire"
    state.save_graph(entry, save_as=target)
    assert any(c["name"] == "session1" for c in calls)


def test_remove_entry_triggers_continuous_autosave(state_in_continuous_mode, monkeypatch):
    calls = _patch_dump(monkeypatch)
    state = state_in_continuous_mode
    entry = state.create_new()
    calls.clear()  # ignore the create_new call

    state.remove_entry(entry)
    assert any(c["name"] == "session1" for c in calls)


def test_rename_graph_triggers_continuous_autosave(state_in_continuous_mode, tmp_path, monkeypatch):
    calls = _patch_dump(monkeypatch)
    state = state_in_continuous_mode
    p = tmp_path / "graphs" / "foo.haywire"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")
    entry = MagicMock()
    entry.path = p
    entry.entry_id = str(p)
    state._entries[entry.entry_id] = entry
    calls.clear()

    state.rename_graph(entry, "bar")
    assert any(c["name"] == "session1" for c in calls)


def test_start_execution_triggers_continuous_autosave(state_in_continuous_mode, monkeypatch):
    calls = _patch_dump(monkeypatch)
    entry = MagicMock()
    state_in_continuous_mode.start_execution(entry)
    assert any(c["name"] == "session1" for c in calls)


def test_stop_execution_triggers_continuous_autosave(state_in_continuous_mode, monkeypatch):
    calls = _patch_dump(monkeypatch)
    entry = MagicMock()
    state_in_continuous_mode.stop_execution(entry)
    assert any(c["name"] == "session1" for c in calls)
```

- [ ] **Step 3: Run the tests; confirm failure**

Run:
```sh
uv run pytest tests/haystack/test_haystack_state.py -v -k "triggers_continuous_autosave"
```
Expected: 7 failures (none of the mutators call `_autosave_if_continuous` yet).

- [ ] **Step 4: Add the call to all seven mutators**

In `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`:

a. **`create_new`** — at end of the method (currently ends with `return entry`), add `self._autosave_if_continuous()` immediately before `return entry`:

```python
        self._broadcast_data_mutated()
        self._autosave_if_continuous()
        return entry
```

b. **`open_graph`** — same pattern, before `return entry`:

```python
        self._broadcast_data_mutated()
        self._autosave_if_continuous()
        return entry
```

c. **`save_graph`** — inside the `if success:` branch, immediately after `self._broadcast_data_mutated()`:

```python
        success = entry.graph.save_to_file(str(target))
        if success:
            entry.unsaved = False
            if save_as is not None and save_as != entry.path:
                old_id = entry.entry_id
                self._entries.pop(old_id, None)
                entry.path = save_as
                self._entries[entry.entry_id] = entry
            self._broadcast_data_mutated()
            self._autosave_if_continuous()
        return success
```

d. **`rename_graph`** — at end, just before `return True`:

```python
        entry.unsaved = False
        self._broadcast_data_mutated()
        self._autosave_if_continuous()
        return True
```

e. **`remove_entry`** — inside the success branch, after `self._broadcast_data_mutated()`:

```python
        if entry.entry_id in self._entries and self._entries[entry.entry_id] is entry:
            del self._entries[entry.entry_id]
            self._broadcast_data_mutated()
            self._autosave_if_continuous()
            return True
        return False
```

f. **`start_execution`** — replace the placeholder comment:

```python
    def start_execution(self, entry: GraphEntry) -> None:
        """Start execution on *entry* and trigger continuous autosave."""
        entry.start_execution()
        self._autosave_if_continuous()
```

g. **`stop_execution`** — same pattern:

```python
    def stop_execution(self, entry: GraphEntry) -> None:
        """Stop execution on *entry* and trigger continuous autosave."""
        entry.stop_execution()
        self._autosave_if_continuous()
```

- [ ] **Step 5: Re-run the new tests; confirm they pass**

Run:
```sh
uv run pytest tests/haystack/test_haystack_state.py -v -k "triggers_continuous_autosave"
```
Expected: all 7 green.

- [ ] **Step 6: Re-run the full haystack test suite to catch regressions**

Run:
```sh
uv run pytest tests/haystack/ -v
```
Expected: all green. If failures appear, they likely stem from existing tests that didn't expect the autosave hook to fire — but the helper is a no-op when `autosave="off"` (the default), so existing fixtures should be unaffected.

- [ ] **Step 7: Re-run lint + type-check**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/state/haystack_state.py
uv run mypy barn/haybale-haystack/haybale_haystack/state/haystack_state.py
```
Expected: clean.

- [ ] **Step 8: Commit**

```sh
git add barn/haybale-haystack/haybale_haystack/state/haystack_state.py tests/haystack/test_haystack_state.py
git commit -m "feat(haystack): wire continuous autosave into all seven mutators

create_new, open_graph, save_graph, rename_graph, remove_entry,
start_execution, stop_execution now each call
_autosave_if_continuous(). Helper is a no-op in 'off' (default)
mode, so existing behaviour is unchanged."
```

---

## Task 6: Wire on-exit autosave into `on_disable`

When `autosave == "on_exit"` and `last_haystack_name` is set, dump the TOML before teardown.

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`
- Test: `tests/haystack/test_haystack_state.py`

- [ ] **Step 1: Establish the pre-edit baseline**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/state/haystack_state.py
uv run mypy barn/haybale-haystack/haybale_haystack/state/haystack_state.py
```
Expected: clean.

- [ ] **Step 2: Write the failing tests**

Append to `tests/haystack/test_haystack_state.py`:

```python
def test_on_disable_dumps_when_autosave_is_on_exit(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "on_exit"
    state._haystack_settings.last_haystack_name = "session1"

    captured = {}

    def fake_dump(s, root, name, active_path=None):
        captured["name"] = name
        captured["active_path"] = active_path
        return root / "haystacks" / f"{name}.toml"

    monkeypatch.setattr("haybale_haystack.persistence.dump_haystack", fake_dump)

    state.on_disable()
    assert captured["name"] == "session1"
    assert captured["active_path"] is None  # on_disable has no session context


def test_on_disable_does_not_dump_when_autosave_is_off(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "off"
    state._haystack_settings.last_haystack_name = "session1"

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state.on_disable()
    assert called == []


def test_on_disable_does_not_dump_when_autosave_is_continuous(state_with_mocked_deps, tmp_path, monkeypatch):
    """Continuous mode handles dumps via per-mutator hooks; on_disable should NOT
    additionally fire — it would be a redundant write at shutdown."""
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "continuous"
    state._haystack_settings.last_haystack_name = "session1"

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state.on_disable()
    assert called == []


def test_on_disable_skips_when_last_name_empty(state_with_mocked_deps, tmp_path, monkeypatch):
    state = state_with_mocked_deps
    state._workspace_root = tmp_path
    state._haystack_settings.autosave = "on_exit"
    state._haystack_settings.last_haystack_name = ""

    called = []
    monkeypatch.setattr(
        "haybale_haystack.persistence.dump_haystack",
        lambda *a, **k: called.append((a, k)),
    )

    state.on_disable()
    assert called == []
```

- [ ] **Step 3: Run the tests; confirm failure**

Run:
```sh
uv run pytest tests/haystack/test_haystack_state.py -v -k "on_disable"
```
Expected: at least the first test fails (no on-exit hook yet).

- [ ] **Step 4: Add the on-exit autosave to `on_disable`**

In `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`, modify `on_disable`. The method currently starts with snapshotting `entry_ids` and broadcasting `HaystackTeardown`. Add the on-exit dump as the very FIRST action — before the teardown broadcast — so the TOML reflects state BEFORE we start tearing it down:

```python
    def on_disable(self) -> None:
        """Announce teardown, stop execution on every entry, clear the registry.

        Order matters: snapshot the entry_ids and broadcast
        ``HaystackTeardown`` BEFORE clearing, so HaystackEditor receivers
        can issue a local ``Close(binding_id=eid)`` for each vanishing tab.
        Receivers don't peek at the (about-to-be-cleared) registry — the
        signal binding_id is the source of truth for the teardown set.

        On-exit autosave (``HaystackSettings.autosave == 'on_exit'``)
        runs first so the TOML captures the registry as it was before
        teardown. Continuous mode does NOT also dump here — its
        per-mutator hooks have kept the file current.
        """
        # On-exit autosave (Q4-C "on_exit" branch).
        if (
            self._haystack_settings is not None
            and self._haystack_settings.autosave == "on_exit"
            and self._haystack_settings.last_haystack_name
            and self._workspace_root is not None
        ):
            from haybale_haystack import persistence

            try:
                persistence.dump_haystack(
                    self,
                    self._workspace_root,
                    self._haystack_settings.last_haystack_name,
                )
            except Exception as exc:
                logger.warning(f"HaystackState.on_disable: on-exit autosave failed: {exc}")

        entry_ids = tuple(self._entries.keys())
        # ... rest of existing on_disable body unchanged ...
```

(Keep the rest of `on_disable` exactly as-is.)

- [ ] **Step 5: Re-run the tests; confirm they pass**

Run:
```sh
uv run pytest tests/haystack/test_haystack_state.py -v -k "on_disable"
```
Expected: all four green.

- [ ] **Step 6: Re-run the full haystack test suite**

Run:
```sh
uv run pytest tests/haystack/ -v
```
Expected: all green.

- [ ] **Step 7: Re-run lint + type-check**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/state/haystack_state.py
uv run mypy barn/haybale-haystack/haybale_haystack/state/haystack_state.py
```
Expected: clean.

- [ ] **Step 8: Commit**

```sh
git add barn/haybale-haystack/haybale_haystack/state/haystack_state.py tests/haystack/test_haystack_state.py
git commit -m "feat(haystack): on-exit autosave in HaystackState.on_disable

When HaystackSettings.autosave == 'on_exit' (Q4-C branch), dump the
TOML at shutdown using the recorded last_haystack_name. Continuous
mode skips this hook — its per-mutator dumps already keep the file
current, so an on_disable dump would be redundant."
```

---

## Task 7: Migrate the editor to call HaystackState's new methods

The editor currently calls `persistence.dump_haystack` / `persistence.load_haystack` directly and writes the legacy `workspace_manager.snapshot["haystack"]` mirror. Switch all four UI paths (`save`, `load`, `start`, `stop`) to the new state methods, and delete the snapshot writes.

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py`

- [ ] **Step 1: Establish the pre-edit baseline**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py
uv run mypy barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py
```
Expected: clean.

- [ ] **Step 2: Survey existing call sites**

Run:
```sh
grep -n "persistence.dump_haystack\|persistence.load_haystack\|workspace_manager.snapshot\|entry.start_execution\|entry.stop_execution" barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py
```
Expected output (line numbers may differ slightly): one `dump_haystack` call (`_on_save_haystack`), one `load_haystack` call (`_on_load_haystack`), two `snapshot["haystack"]` writes (one per handler), one `entry.start_execution()` (`_on_start_execution`), one `entry.stop_execution()` (`_on_stop_execution`). If the count doesn't match, stop and reconcile before editing — the file may have drifted.

- [ ] **Step 3: Migrate `_on_save_haystack`**

Locate the body of `_on_save_haystack._do_save` (around line 752–771). Replace this block:

```python
                from haybale_haystack import persistence
                from haywire.core.di.context import get_workspace_root

                active_path = context.data[EditState].active_graph_path.value
                persistence.dump_haystack(hs, get_workspace_root(), name, active_path=active_path)

                context.app.workspace_manager.snapshot["haystack"] = name
                context.app.save_workspace(active_graph_path=active_path)
                self._update_header_title(context)
                ui.notify(f"Haystack '{name}' saved", type="positive")
                popup.close()
```

with:

```python
                active_path = context.data[EditState].active_graph_path.value
                hs.save_haystack(name, active_path=active_path)

                self._update_header_title(context)
                ui.notify(f"Haystack '{name}' saved", type="positive")
                popup.close()
```

Rationale: `hs.save_haystack` writes the TOML AND updates `last_haystack_name`. The legacy `workspace_manager.snapshot["haystack"]` write and the `app.save_workspace` call are obsolete (Q1-A retires the snapshot mirror).

- [ ] **Step 4: Migrate `_on_load_haystack`**

Locate the body of `_on_load_haystack._do_load` (around line 817–844). Replace this block:

```python
                # persistence.load_haystack does NOT clear the existing entries
                # — that responsibility was deliberately moved to the caller
                # when the I/O was extracted into pure helpers. Clear the
                # registry first so the loaded set replaces, not appends.
                for existing in list(hs.all_entries()):
                    hs.remove_entry(existing)

                from haybale_haystack import persistence
                from haywire.core.di.context import get_workspace_root

                workspace_root = get_workspace_root()
                active_path = persistence.load_haystack(hs, workspace_root, name)

                # Resolve the active entry from the returned absolute path,
                # falling back to the first entry if missing/None.
                active_entry: Optional["GraphEntry"] = None
                if active_path is not None:
                    active_entry = hs.get_by_path(active_path)
                if active_entry is None:
                    entries = hs.all_entries()
                    if entries:
                        active_entry = entries[0]

                context.app.workspace_manager.snapshot["haystack"] = name
                context.app.save_workspace(active_graph_path=context.data[EditState].active_graph_path.value)
```

with:

```python
                # hs.load_haystack does NOT clear existing entries — that
                # responsibility lives at the caller. Clear first so the
                # loaded set replaces, not appends.
                for existing in list(hs.all_entries()):
                    hs.remove_entry(existing)

                active_path = hs.load_haystack(name)

                active_entry: Optional["GraphEntry"] = None
                if active_path is not None:
                    active_entry = hs.get_by_path(active_path)
                if active_entry is None:
                    entries = hs.all_entries()
                    if entries:
                        active_entry = entries[0]
```

(Leave the subsequent `session.lifecycle(Reveal(...))` block, the `_update_header_title(context)` call, and the `popup.close()` call exactly as they are.)

- [ ] **Step 5: Migrate `_on_start_execution` and `_on_stop_execution`**

Replace the body of `_on_start_execution` (around line 704–710):

```python
    def _on_start_execution(self, entry_id: str, context: "SessionContext") -> None:
        """Start execution on a graph entry."""
        entry = self._resolve_entry(entry_id, context)
        if entry is None:
            return
        hs = context.app_data[HaystackState]
        hs.start_execution(entry)
        self._notify_data_mutated(context)
```

And `_on_stop_execution`:

```python
    def _on_stop_execution(self, entry_id: str, context: "SessionContext") -> None:
        """Stop execution on a graph entry."""
        entry = self._resolve_entry(entry_id, context)
        if entry is None:
            return
        hs = context.app_data[HaystackState]
        hs.stop_execution(entry)
        self._notify_data_mutated(context)
```

- [ ] **Step 6: Run the full test suite**

Run:
```sh
uv run pytest -m "not integration" -q
```
Expected: all green. If any test references `persistence.dump_haystack` / `persistence.load_haystack` from inside the editor, it needs updating to the new state-method path.

- [ ] **Step 7: Run integration tests**

Run:
```sh
uv run pytest -m integration -q
```
Expected: all green. The carve-out integration test (`tests/integration/test_haystack_carve_out.py`) exercises the rehydrate path; it should now succeed end-to-end because `last_haystack_name` actually gets written by the new `save_haystack` flow.

- [ ] **Step 8: Re-run lint + type-check**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py
uv run mypy barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py
```
Expected: clean.

- [ ] **Step 9: Commit**

```sh
git add barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py
git commit -m "refactor(haystack): editor calls HaystackState methods instead of persistence/snapshot

_on_save_haystack -> hs.save_haystack(name, active_path)
_on_load_haystack -> hs.load_haystack(name)
_on_start_execution -> hs.start_execution(entry)
_on_stop_execution  -> hs.stop_execution(entry)

Drops the workspace_manager.snapshot[\"haystack\"] writes and the
app.save_workspace calls — last_haystack_name lives in
HaystackSettings now (Q1-A). Fixes the on-enable rehydrate bug:
last_haystack_name is finally written from the user-facing save
flow."
```

---

## Task 8: Add the "Haystack" autosave panel pinned to AppFocus

A single-control panel that exposes the autosave setting in the properties editor.

**Files:**
- Create: `barn/haybale-haystack/haybale_haystack/panels/haystack_settings_panel.py`
- Test: `tests/haystack/test_haystack_settings_panel.py`

- [ ] **Step 1: Establish the pre-edit baseline**

The file does not yet exist; just confirm the rest is clean:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/panels/
```
Expected: clean.

- [ ] **Step 2: Write the failing tests**

Create `tests/haystack/test_haystack_settings_panel.py`:

```python
"""HaystackSettingsPanel — single-control panel for the autosave setting."""

from __future__ import annotations

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def test_panel_is_a_basepanel():
    from haybale_haystack.panels.haystack_settings_panel import HaystackSettingsPanel
    from haywire.ui.panel import BasePanel

    assert issubclass(HaystackSettingsPanel, BasePanel)


def test_panel_pinned_to_app_focus_via_decorator():
    """The @panel decorator stamps focus/action/label/icon onto the class."""
    from haybale_haystack.panels.haystack_settings_panel import HaystackSettingsPanel
    from haybale_studio.focuses import AppFocus
    from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions

    assert HaystackSettingsPanel._panel_focus is AppFocus
    assert HaystackSettingsPanel._panel_action is PropertiesEditorActions
    assert HaystackSettingsPanel._panel_label == "Haystack"


def test_panel_poll_returns_true():
    """AppFocus is always available, so the panel always polls true."""
    from haybale_haystack.panels.haystack_settings_panel import HaystackSettingsPanel
    from unittest.mock import MagicMock

    ctx = MagicMock()
    assert HaystackSettingsPanel.poll(ctx) is True
```

- [ ] **Step 3: Run the tests; confirm failure**

Run:
```sh
uv run pytest tests/haystack/test_haystack_settings_panel.py -v
```
Expected: all three fail with `ModuleNotFoundError: ... haystack_settings_panel`.

- [ ] **Step 4: Verify the panel decorator metadata attributes**

Before writing the panel, confirm the attribute names the test expects (`_panel_focus`, `_panel_action`, `_panel_label`) match what the decorator actually stamps:

```sh
grep -n "_panel_focus\|_panel_action\|_panel_label\|setattr" packages/haywire-core/src/haywire/ui/panel/decorator.py
```

If the actual stamped attribute names differ, update the test in step 2 to match before continuing. (As of writing, the conventional names are `_panel_focus`, `_panel_action`, `_panel_label` — but the canonical reference is the decorator source.)

- [ ] **Step 5: Create the panel file**

Create `barn/haybale-haystack/haybale_haystack/panels/haystack_settings_panel.py`:

```python
"""HaystackSettingsPanel — exposes HaystackSettings.autosave in the properties editor.

Pinned to AppFocus (always available) because autosave is a workspace-global
setting, not tied to a particular graph or node.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

from haybale_haystack.settings.haystack_settings import HaystackSettings
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haybale_studio.focuses import AppFocus

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


_AUTOSAVE_LABELS = {
    "off": "Off",
    "on_exit": "On exit",
    "continuous": "Continuous",
}


@panel(
    action=PropertiesEditorActions,
    focus=AppFocus,
    label="Haystack",
    icon=hui.icon.save,
    order=80,
)
class HaystackSettingsPanel(BasePanel):
    """Single-control panel exposing the haystack autosave mode."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return True

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        try:
            settings = HaystackSettings()
        except Exception:
            layout.error_label("HaystackSettings unavailable")
            return

        # NiceGUI ui.select uses dict mapping (value -> displayed label).
        # Bind value to the descriptor; on_change writes the new mode back.
        def _on_change(e):
            settings.autosave = e.value

        ui.select(
            options=_AUTOSAVE_LABELS,
            value=settings.autosave,
            label="Autosave",
            on_change=_on_change,
        ).props("dense").classes("w-full")
```

- [ ] **Step 6: Re-run the tests; confirm they pass**

Run:
```sh
uv run pytest tests/haystack/test_haystack_settings_panel.py -v
```
Expected: all three green.

- [ ] **Step 7: Run the full test suite to catch regressions**

Run:
```sh
uv run pytest -m "not integration" -q
```
Expected: all green. The library's `register_components` already auto-discovers panel files in `panels/` (see `barn/haybale-haystack/haybale_haystack/__init__.py:63-66`), so no additional registration code is needed.

- [ ] **Step 8: Run lint + type-check**

Run:
```sh
uv run ruff check barn/haybale-haystack/haybale_haystack/panels/haystack_settings_panel.py tests/haystack/test_haystack_settings_panel.py
uv run mypy barn/haybale-haystack/haybale_haystack/panels/haystack_settings_panel.py
```
Expected: clean.

- [ ] **Step 9: Commit**

```sh
git add barn/haybale-haystack/haybale_haystack/panels/haystack_settings_panel.py tests/haystack/test_haystack_settings_panel.py
git commit -m "feat(haystack): autosave panel pinned to AppFocus in properties editor

Single ui.select bound to HaystackSettings.autosave with three
labelled options (Off / On exit / Continuous). Auto-discovered by
the haystack library's register_components panels/ scan."
```

---

## Task 9: End-to-end smoke check + final lint pass

A final sweep to confirm the rehydrate bug is fixed end-to-end and to catch any drift before merging.

- [ ] **Step 1: Run the FULL test suite (including integration)**

Run:
```sh
uv run pytest -q
```
Expected: all green. The `tests/integration/test_haystack_carve_out.py` rehydrate test pre-seeds `last_haystack_name` directly; in addition, the editor migration (Task 7) means real production usage now writes the same field — so a manual smoke test is worthwhile.

- [ ] **Step 2: Manual smoke test**

```sh
uv run haywire
```

In the running app:
1. Open or create a couple of `.haywire` graphs.
2. Click "Save Haystack" in the haystack editor sidebar; pick a name (e.g. `smoke`).
3. Quit the app.
4. Inspect the workspace settings file: confirm the `[haystack]` namespace has `last_haystack_name = "smoke"`.
   ```sh
   grep -A1 '\[haystack\]' "$(uv run python -c 'from haywire.core.di.context import get_workspace_root; print(get_workspace_root())')"/settings.toml || true
   ```
   (If the settings file path differs, ask: where does this workspace persist `LibrarySettings`? — but `last_haystack_name` should be findable.)
5. Relaunch `uv run haywire` and confirm the same set of graphs auto-reloads.
6. Toggle the new "Haystack" panel in the properties editor; switch autosave to "Continuous"; perform any open/save/start; quit; relaunch. The TOML should reflect the most recent set without ever clicking "Save Haystack" again.

If any step fails, capture the failing observation, do NOT mark the plan complete, and surface the issue with file/line context.

- [ ] **Step 3: Repo-wide lint + type-check + tests**

Run all three quality gates:
```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-visiongraph/haybale_visiongraph/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest -q
```
Expected: all green. (Note: `barn/haybale-haystack/` isn't in the listed `mypy` command from CLAUDE.md, but the per-file `mypy` runs in earlier tasks have already exercised the modified files. If `barn/haybale-haystack/` should be added to the canonical command, surface that as a follow-up.)

- [ ] **Step 4: Commit any format-only fixes (if needed)**

If `ruff format --check` flagged anything, run `uv run ruff format .` and commit:

```sh
git add -p
git commit -m "style: ruff format autosave plan files"
```

- [ ] **Step 5: Final commit / PR readiness**

The work is complete. The branch should now have ~8 commits (one per task plus an optional format commit). Confirm:

```sh
git log --oneline main..HEAD
```

Expected: a clean sequence of feat/refactor commits, each with green tests at the time of commit.

---

## Self-review summary

- [x] **Spec coverage:** Every Q1–Q10 decision maps to at least one task — Q1 (Tasks 2, 7), Q2 (entire plan default), Q3 (Task 2), Q4 (Tasks 1, 6, 8), Q5 (Task 5), Q6 (Tasks 3, 5, 7), Q7 (Tasks 4, 5), Q8 (Task 1 description text), Q9 (Task 8), Q10 (Tasks 4, 5).
- [x] **Bug fix included:** the on-enable rehydrate is fixed by Task 2 (introduces the writer for `last_haystack_name`) + Task 7 (routes the editor's save flow through it). This is the root cause the user asked about.
- [x] **No placeholders:** every step contains the exact code, command, or test it requires.
- [x] **Type/method consistency:** `save_haystack(name, active_path)` is referenced identically in Tasks 2, 5, 7. `_autosave_if_continuous()` is defined in Task 4 and called in Task 5. `start_execution`/`stop_execution` signatures match across Tasks 3, 5, 7.
- [x] **Reversibility:** every task ends with a commit, so a partial implementation is recoverable. Default `autosave="off"` keeps the entire feature dormant for users who don't opt in.
