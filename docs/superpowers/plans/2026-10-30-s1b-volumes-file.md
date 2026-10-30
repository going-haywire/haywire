# S1b — The volumes file is the volume list — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify volumes after the S1 live check: `~/.haywire/volumes.toml` becomes the single list of
volumes (key, label, description, location), everything in it is editable except the key, `project` is the
only built-in, libraries add their volumes once from an `AppState`, and the editor loses its source column.

**Architecture:** The Surface-style `Volume` class registry (S1-Q2) is removed. `VolumeStore` owns the file:
entries keyed by a registry-style volume key, plus the built-in `project`. Libraries call
`ensure_volume(...)` from their `AppState.on_enable`; it writes the entry only when the key is absent.
A PATH value stores the key. Branch `feat/s1-volumes` (unmerged), so no stored graphs need migrating.

**Spec:** [2026-10-30-spandrel-haybale-design.md](2026-10-30-spandrel-haybale-design.md) §2.1 (amended by
Task 1). Predecessor: [2026-10-30-s1-volumes.md](2026-10-30-s1-volumes.md).

## Decisions settled after the S1 live check (2026-10-30)

| # | decision |
|---|---|
| S1b-Q1 | `~/.haywire/volumes.toml` is the **single store**: one entry per volume with key, label, description, location. No volume exists outside it except `project`. |
| S1b-Q2 | Volume **key** follows the registry-key pattern `<library-id>:volume:<name>` (e.g. `haybale-models:volume:models`); volumes a user adds get `user:volume:<name>`. The key is **fixed once created**; renaming means a new volume. |
| S1b-Q3 | Everything stored in the file is **editable** (label, description, location). `project` (`haywire-core:volume:project`, = ambient workspace root) is built in, never stored, never editable. There is **no `home` volume**. |
| S1b-Q4 | A library adds its volume from its **`AppState.on_enable`** via `ensure_volume(key, label, description, location)`: writes the entry only when the key is absent, never creates the folder, safe on every enable / hot reload. |
| S1b-Q5 | **Deleting** a library's volume is a reset: the library adds it back with its suggested location on its next enable. Uninstalling a library leaves its entry as an ordinary volume. |
| S1b-Q6 | A PATH value stores the **key** (`VolumePath.volume`); the UI shows the label. |
| S1b-Q7 | **No source column, no state words.** Status carries facts: location (`None` = not set), exists, editable. |
| S1b-Q8 | Suggested model location: `~/.haywire/db/<module>/models` (S6, haybale-models) — suggested, not enforced. Any future "reset library data" tool must leave a `models` folder alone. |
| S1b-Q9 | The store serializes read-modify-write with a process lock and writes atomically (temp file + rename). |

## Global Constraints

- Volume key regex: `^[a-z][a-z0-9-]*:volume:[a-z][a-z0-9_-]*$`. User-added keys: `user:volume:<name>`.
- File layout (tomlkit via `haywire.core.tomlio` for reading/editing; atomic write):
  ```toml
  [volumes."haybale-models:volume:models"]
  label = "Models"
  description = "Models on this machine"
  location = "/Users/me/.haywire/db/haybale_models/models"
  ```
  `location` must be absolute; `label` defaults to the key's name part; `description` defaults to `""`.
- **Legacy entries** (S1 format `[volumes] name = "/abs"`) are read as `user:volume:<name>` with label
  `<name>` and rewritten in the new form on the next write. Bad entries are logged and skipped, never crash.
- `project` is resolved from `get_workspace_root()` on every call; with no root it is "not defined".
- Resolution: built-in `project` → file entry → `VolumeUndefinedError`. Escape refusal unchanged (S1).
  Resolving never creates folders.
- Tests never touch the real `~/.haywire/volumes.toml` (autouse tmp store in `tests/conftest.py` stays).
- Writing volumes is ADMIN (editor `requires=AccessTier.ADMIN`; CLI runs on the server).
- No relative imports under `barn/`. Line length 109. Docstrings per `.claude/rules/python-docs.md`.
- Glossary/ADR text lands in Task 7 with the code, not earlier.

## Review Focus

1. **Concurrent `ensure_volume`** from several libraries' `on_enable` worker threads — no lost entry, no
   torn file. → Task 2 test (threads).
2. **Legacy file** (the user's real file has `[volumes] assets = "/Users/…"`) — still resolves as
   `user:volume:assets` and survives the next write. → Task 2 test.
3. **Delete then re-enable** — the library's entry comes back with its suggested location; a user's edits
   to an existing entry are never overwritten by `ensure_volume`. → Task 2 test.
4. **Key immutability** — no API, editor or CLI path changes a key. → Tasks 2, 5, 6.

---

### Task 1: Amend the spec

**Files:** Modify `docs/superpowers/plans/2026-10-30-spandrel-haybale-design.md`

- [ ] **Step 1.** In §2.1 replace the **Volumes**, **Locations** bullets and S1-Q2 consequences with the
  S1b decisions (copy the table above under "S1b decisions"); drop `home` from the volumes bullet; mark
  S1-Q2 "superseded by S1b-Q1/Q4". In §2.5 **Store** bullet: the `models` volume is added by
  haybale-models' AppState (S1b-Q4) with suggested location per S1b-Q8. §3: add an `S1b` row
  `planned — [plan](2026-10-30-s1b-volumes-file.md)` after S1.
- [ ] **Step 2. Commit.** `git commit -m "docs(plan): amend spandrel spec with S1b volume decisions"`

---

### Task 2: `VolumeStore` — entries, built-in project, `ensure_volume`, lock + atomic write

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/volumes/store.py`, `.../volumes/__init__.py`
- Delete: `packages/haywire-core/src/haywire/core/volumes/volume.py` (the class registry) — move anything
  still needed (key regex, `PROJECT_KEY`) into `store.py` or a small `keys.py`
- Test: `tests/core/test_volumes/test_store.py` (rewrite), `tests/core/test_volumes/conftest.py` (drop the
  registry snapshot fixture), delete `tests/core/test_volumes/test_volume.py`

**Interfaces (exported from `haywire.core.volumes`):**
- `PROJECT_KEY = "haywire-core:volume:project"`; `VOLUME_KEY_RE`; `user_volume_key(name: str) -> str`.
- `@dataclass(frozen=True) class VolumeEntry: key: str; label: str; description: str; location: Path | None`
  (`location is None` only for `project` when no workspace root is set).
- `class VolumeStore`:
  - `__init__(self, path: Path | None = None)` (default `~/.haywire/volumes.toml`), `path`.
  - `entries() -> list[VolumeEntry]` — `project` first, then file entries sorted by label (case-insensitive).
  - `entry(key: str) -> VolumeEntry | None`.
  - `add(key, *, label, description, location) -> None` — `ValueError` if key invalid, already present,
    `project`, or location not absolute.
  - `update(key, *, label=None, description=None, location=None) -> None` — changes given fields only;
    `ValueError` for `project`, unknown key, non-absolute location; never changes the key.
  - `remove(key) -> bool`.
  - `ensure(key, *, label, description, location) -> bool` — adds only when absent (True if added);
    never touches an existing entry; never creates folders.
- `ensure_volume(key, *, label, description, location, store=None) -> bool` — module-level convenience
  for libraries (uses `get_volume_store()`).
- `get_volume_store()` / `set_volume_store()` unchanged.
- Re-read on mtime/size change (as S1). Writes: one `threading.Lock` per store path held across
  read-modify-write; write to a temp file in the same folder then `os.replace`.

- [ ] **Step 1: Failing tests:** round trip add → fresh store sees it; `update` of label only keeps the
  rest; `update`/`remove`/`add` on `project` → `ValueError`; invalid key / relative location → `ValueError`;
  duplicate `add` → `ValueError`; `ensure` adds once, returns False the second time, never overwrites an
  edited entry (Review Focus 3); `remove` then `ensure` re-adds the suggested location; `project` entry
  follows `set_workspace_root` changes and has `location=None` with no root; legacy file
  `[volumes]\nassets = "/x"` → entry `user:volume:assets`, label `assets`, and after an unrelated `add` the
  file holds both in the new layout (Review Focus 2); malformed TOML → only `project` + logged error;
  bad entries skipped with a warning; 8 threads × `ensure` of distinct keys → all 8 present and the file
  parses (Review Focus 1); no temp file left behind after a write.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_volumes/test_store.py -v` → FAIL.
- [ ] **Step 3: Implement.** Remove the `Volume` registry and its exports; grep for `volume_by_name`,
  `all_volumes`, `ProjectVolume`, `HomeVolume`, `Volume` imports and fix every user in this task or leave a
  clear failing import for Tasks 3–6 only if they are in their files (prefer fixing compile-level users now).
- [ ] **Step 4: Run** the store tests → PASS; ruff + mypy on the package.
- [ ] **Step 5: Commit.** `git commit -m "feat(volumes): the volumes file is the volume list"`

---

### Task 3: Resolver and status on keys

**Files:** Modify `packages/haywire-core/src/haywire/core/volumes/resolve.py`, `.../value.py`,
`.../__init__.py`; Test `tests/core/test_volumes/test_resolve.py`, `test_value.py`

**Interfaces:**
- `location_of(key, store=None) -> Path` — `project` → workspace root, else the entry's location, else
  `VolumeUndefinedError(key)` (message `"volume 'user:volume:scans' is not defined on this machine"`;
  the UI may show the label/name part).
- `resolve(path, store=None)` — unchanged escape/NUL/loop handling (S1 fix wave), keyed by `path.volume`.
- `@dataclass(frozen=True) class VolumeStatus: key: str; label: str; description: str; location: Path | None;
  exists: bool; editable: bool` (`editable` False only for `project`).
- `list_volumes(store=None) -> list[VolumeStatus]` — same order as `entries()`.
- `VolumePath.from_dict({})` → `VolumePath(PROJECT_KEY, "")`; `__str__` → `"<name part>:<relative>"`.

- [ ] **Step 1: Failing tests:** port the S1 resolve tests to keys (escape, NUL, symlink loop, missing
  location still resolves, Windows input); `project` with no root → `VolumeUndefinedError`; unknown key →
  undefined; status facts (`editable`, `exists`, `location None`); no `source` attribute anywhere.
- [ ] **Step 2–4:** run → FAIL, implement (drop `_default_of`, `_locate` sources), run → PASS; ruff + mypy.
- [ ] **Step 5: Commit.** `git commit -m "feat(volumes): resolve and list volumes by key"`

---

### Task 4: PATH types and PathWidget on keys

**Files:** Modify `packages/haywire-core/src/haywire/barn/builtin/types/path.py` (defaults →
`PROJECT_KEY`), `packages/haywire-core/src/haywire/barn/builtin/widgets/path_widget.py`;
Test `tests/barn/builtin/test_path_types.py`, `tests/ui/widget/test_path_widget.py`

- [ ] **Step 1: Failing tests:** type default volume is `PROJECT_KEY`; the select's option values are keys
  and option labels are entry labels; choosing a volume stores its key; a value with an unknown key shows
  `volume '<name part>' is not defined on this machine` and stays selectable/kept verbatim; options refresh
  when the dropdown opens (S1 deferred minor) so a volume added in the editor appears without a value change.
- [ ] **Step 2–4:** run → FAIL, implement, run → PASS (+ `uv run pytest tests/ui/widget -n 4 -q`).
- [ ] **Step 5: Commit.** `git commit -m "feat(widgets): PathWidget picks volumes by key"`

---

### Task 5: Volumes editor without source wording

**Files:** Modify `barn/haybale-studio/haybale_studio/editors/volumes_editor.py`;
Test `tests/barn/test_volumes_editor.py`, `tests/ui/harness/test_volumes_editor_browser.py`

- [ ] **Step 1: Failing tests:** rows show label over the fitted location (no name/key line unless the
  label is empty — then the name part); no source text anywhere; `project` row → view icon, modal read-only;
  other rows (ADMIN) → edit modal with **Key (read-only)**, Label, Description, Location fields, Save and
  Delete; Save calls `update` and never changes the key; Delete calls `remove`; for a library key the modal
  says, near Delete, that the library adds it back with its suggested location (one line, plain words);
  the `+` modal has Name (→ `user:volume:<name>`, shown live as the key), Label, Description, Location;
  errors stay in the modal. Non-ADMIN → view icons only. Browser test still passes at 300 px.
- [ ] **Step 2–4:** run → FAIL, implement, run → PASS (+ `-m browser` for the harness test).
- [ ] **Step 5: Commit.** `git commit -m "feat(studio): Volumes editor edits label, description and location"`

---

### Task 6: CLI on keys

**Files:** Modify `packages/haywire-studio/src/haywire_studio/cli/volumescmd.py`; Test `tests/test_volumes_cli.py`

**Interfaces:** `haywire volumes list` (key, label, location, `(missing)`);
`add <name> <folder> [--label L] [--description D]` (creates `user:volume:<name>`);
`set <key> [--location F] [--label L] [--description D]` (at least one option);
`remove <key>`. A bare name in `set`/`remove` is accepted when exactly one key has that name part.
Folders: `~` expanded, absolutised against cwd, never created. Errors → stderr, exit 1.

- [ ] **Step 1: Failing tests** for each subcommand incl. bare-name lookup, ambiguous name → exit 1,
  `project` refused, malformed file → stderr + exit 1.
- [ ] **Step 2–4:** run → FAIL, implement, run → PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(cli): haywire volumes add/set/remove by key"`

---

### Task 7: Docs, glossary, ADR

**Files:** Modify `docs/architecture/volumes/volumes-arch.md` (rewrite to the S1b model; the live embed
moves from `ProjectVolume` to `ensure_volume` or `VolumeStore.ensure`), `docs/adr/0065-*.md` (rewrite the
decision to S1b: single file, keys, AppState `ensure_volume`, delete-is-reset, no home, project built in,
models note S1b-Q8; keep "anchor" rejected), `docs/reference/glossary.md` (**Volume**, **Volume key**,
**Volume path**, **Volumes file** updated; drop "declared/configured" wording), the `@library`/state docs
if they gain an `ensure_volume` example (`docs/components/states/state-canon.md`: short "A library that
needs a volume" example calling `ensure_volume` in `on_enable`).

- [ ] **Step 1–3:** write; `uv run mkdocs build --strict > /tmp/mk.log 2>&1; echo exit=$?` → `exit=0`.
- [ ] **Step 4: Commit.** `git commit -m "docs(volumes): the volumes file is the volume list"`

---

### Task 8: Verify and mark S1b done (status rule — mandatory last task)

- [ ] **Step 1:** `uv run ruff check . && uv run ruff format --check .`; full mypy command from CLAUDE.md;
  `uv run pytest -m "not browser and not perf" -n 4 -q` and `-m browser -n 4` → exit 0. The user's real
  `~/.haywire/volumes.toml` is byte-identical before and after the runs (`shasum` it).
- [ ] **Step 2:** spec §3 S1b row → `done (feat/s1-volumes @ <sha>, unmerged, <date>)`, deviations under §2.1.
- [ ] **Step 3: Commit.** `git commit -m "docs(plan): S1b done — volumes file"`
