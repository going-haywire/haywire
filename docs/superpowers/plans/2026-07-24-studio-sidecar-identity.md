# Studio Sidecar Identity File Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Haywire studio writes a self-describing JSON identity file at `<workspace>/.haywire/studio.json` when it starts the Farmhand MCP endpoint, so a later process (the farmhand4claude plugin's startup script) can identify which project owns the studio on port 8082 and decide whether to reuse, ask, or clean up.

**Architecture:** A new SDK-free module `farmhand/identity.py` in haywire-studio provides `write_identity(workspace_root, port)` and `read_identity(workspace_root)`, mirroring the existing `farmhand/auth.py:ensure_token()` pattern (same `<workspace>/.haywire/` directory, same `.gitignore` discipline). `HaywireApp.setup_farmhand(port)` calls `write_identity` right after mounting the host — so the sidecar exists exactly when the MCP endpoint the proxy needs is live, and only then. The file is stdlib-only JSON; the recycled-PID guard is best-effort (no `psutil` dependency).

**Tech Stack:** Python 3.12+, stdlib only (`json`, `os`, `socket`, `time`, `pathlib`), pytest (`unit` marker).

## Global Constraints

Every task's requirements implicitly include this section.

- **No new dependencies:** `psutil` is NOT a dependency and must not be added. Liveness is `os.kill(pid, 0)`; create-time verification is best-effort and degrades gracefully.
- **SDK-free:** `farmhand/identity.py` must not import from the `mcp` package (it lives beside `auth.py`, which is also SDK-free).
- **Sidecar location:** `<workspace>/.haywire/studio.json` — same directory as `farmhand_token`. The filename constant is `IDENTITY_FILENAME = "studio.json"`.
- **Gitignore:** `studio.json` is machine-local and MUST be gitignored, exactly like `farmhand_token` (append to `<workspace>/.haywire/.gitignore` if absent).
- **Write timing:** only when Farmhand is enabled and mounted — inside `setup_farmhand`, after `self.farmhand_host.mount(port)`. A studio with Farmhand disabled writes no sidecar (correct: no MCP endpoint to identify).
- **Never crash startup:** a failure to write the sidecar must be logged and swallowed — it must never break studio launch (mirror the "ledger must never break error reporting" discipline).
- **Quality gates per task:** `uv run ruff check <touched paths>`, `uv run ruff format <touched paths>` (CI runs `ruff format --check`), `uv run mypy packages/haywire-studio/src/`. Line length 109. The codebase is error-free — anything new is yours.
- **Commit style:** one commit per green task, message given in each task; end every commit message body with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

**Key reference files an implementer will keep open:**
- `packages/haywire-studio/src/haywire_studio/farmhand/auth.py` — the `ensure_token()` sibling this mirrors (`.haywire/` dir creation, `.gitignore` append, `chmod`).
- `packages/haywire-studio/src/haywire_studio/app.py:207` — `setup_farmhand(self, port)`, the call site.
- `tests/farmhand/test_auth_unit.py` — the test module to mirror for `test_identity_unit.py`.

---

### Task 1: `write_identity` + `read_identity` in `farmhand/identity.py`

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/farmhand/identity.py`
- Test: `tests/farmhand/test_identity_unit.py`

**Interfaces:**
- Consumes: nothing (stdlib only). Mirrors the directory/gitignore idiom of `haywire_studio.farmhand.auth.ensure_token(workspace_root: Path) -> str`.
- Produces (Task 2 relies on these exact names):
  - `IDENTITY_FILENAME = "studio.json"` (module constant).
  - `write_identity(workspace_root: Path | str, port: int) -> dict` — writes `<workspace>/.haywire/studio.json` with the current process identity, ensures the file is gitignored, returns the dict it wrote.
  - `read_identity(workspace_root: Path | str) -> dict | None` — returns the parsed dict, or `None` if the file is absent or unparseable.
  - `identity_status(ident: dict) -> str` — one of `"alive"`, `"dead"`, `"recycled"` (best-effort; `"alive"` when the pid is live and create-time cannot be verified).

- [ ] **Step 1: Write the failing tests**

```python
# tests/farmhand/test_identity_unit.py
"""Unit tests for the studio sidecar identity file (<workspace>/.haywire/studio.json)."""

import json
import os
from pathlib import Path

import pytest

from haywire_studio.farmhand.identity import (
    IDENTITY_FILENAME,
    identity_status,
    read_identity,
    write_identity,
)

pytestmark = pytest.mark.unit


def test_write_creates_sidecar_with_expected_fields(tmp_path):
    ident = write_identity(tmp_path, port=8082)
    sidecar = tmp_path / ".haywire" / IDENTITY_FILENAME
    assert sidecar.exists()
    on_disk = json.loads(sidecar.read_text(encoding="utf-8"))
    assert on_disk == ident
    assert ident["pid"] == os.getpid()
    assert ident["port"] == 8082
    assert ident["project_path"] == str(Path(tmp_path).resolve())
    assert ident["project"] == Path(tmp_path).resolve().name
    assert ident["url"] == "http://127.0.0.1:8082"
    assert ident["role"] == "haywire-studio"
    assert isinstance(ident["started_at"], float)


def test_write_gitignores_the_sidecar(tmp_path):
    write_identity(tmp_path, port=8082)
    gitignore = (tmp_path / ".haywire" / ".gitignore").read_text(encoding="utf-8")
    assert IDENTITY_FILENAME in gitignore


def test_write_accepts_str_workspace(tmp_path):
    ident = write_identity(str(tmp_path), port=9000)
    assert ident["port"] == 9000
    assert (tmp_path / ".haywire" / IDENTITY_FILENAME).exists()


def test_read_returns_none_when_absent(tmp_path):
    assert read_identity(tmp_path) is None


def test_read_returns_none_on_garbage(tmp_path):
    haywire = tmp_path / ".haywire"
    haywire.mkdir(parents=True)
    (haywire / IDENTITY_FILENAME).write_text("not json{", encoding="utf-8")
    assert read_identity(tmp_path) is None


def test_read_round_trips_write(tmp_path):
    written = write_identity(tmp_path, port=8082)
    assert read_identity(tmp_path) == written


def test_status_alive_for_current_process(tmp_path):
    ident = write_identity(tmp_path, port=8082)  # pid == this test process
    assert identity_status(ident) == "alive"


def test_status_dead_for_unused_pid(tmp_path):
    ident = write_identity(tmp_path, port=8082)
    ident["pid"] = 999999  # not a live pid
    assert identity_status(ident) == "dead"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/farmhand/test_identity_unit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haywire_studio.farmhand.identity'`

- [ ] **Step 3: Implement the module**

```python
# packages/haywire-studio/src/haywire_studio/farmhand/identity.py
"""Studio sidecar identity file: <workspace>/.haywire/studio.json.

Written when the studio mounts the Farmhand MCP endpoint so a later process
(the farmhand4claude plugin's startup script) can identify WHICH project owns
the studio on a given port — reuse it, ask the user, or clean up a stale one.

Sits beside farmhand_token (see auth.py) and follows the same .haywire/ +
.gitignore discipline. Stdlib only — no psutil. The recycled-pid guard is
best-effort: os.kill(pid, 0) proves liveness; a matching create_time (when
obtainable) proves it is the same process, but its absence never blocks.
"""

from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path

IDENTITY_FILENAME = "studio.json"


def _ensure_gitignored(haywire_dir: Path) -> None:
    gitignore = haywire_dir / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if IDENTITY_FILENAME not in existing:
        with gitignore.open("a", encoding="utf-8") as fh:
            fh.write(f"{IDENTITY_FILENAME}\n")


def write_identity(workspace_root: Path | str, port: int) -> dict:
    """Write the current process's studio identity to <workspace>/.haywire/studio.json.

    Returns the dict written. Ensures the sidecar is gitignored.
    """
    root = Path(workspace_root).resolve()
    haywire_dir = root / ".haywire"
    haywire_dir.mkdir(parents=True, exist_ok=True)
    _ensure_gitignored(haywire_dir)

    ident = {
        "pid": os.getpid(),
        "port": port,
        "project": root.name,
        "project_path": str(root),
        "started_at": time.time(),
        "host": socket.gethostname(),
        "role": "haywire-studio",
        "url": f"http://127.0.0.1:{port}",
    }
    (haywire_dir / IDENTITY_FILENAME).write_text(
        json.dumps(ident, indent=2), encoding="utf-8"
    )
    return ident


def read_identity(workspace_root: Path | str) -> dict | None:
    """Return the parsed sidecar, or None if absent or unparseable."""
    sidecar = Path(workspace_root) / ".haywire" / IDENTITY_FILENAME
    if not sidecar.exists():
        return None
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def identity_status(ident: dict) -> str:
    """Best-effort: 'dead' (pid gone), 'recycled' (pid alive but a provably
    different process), or 'alive' (pid live; same process or unverifiable)."""
    pid = ident.get("pid")
    if not isinstance(pid, int) or not _pid_alive(pid):
        return "dead"
    recorded = ident.get("started_at")
    try:
        import psutil  # optional; absent by default — guarded import

        actual = psutil.Process(pid).create_time()
        if isinstance(recorded, (int, float)) and abs(actual - recorded) > 2.0:
            return "recycled"
    except Exception:
        pass  # psutil absent or lookup failed — cannot disprove liveness
    return "alive"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/farmhand/test_identity_unit.py -v`
Expected: all PASS.

- [ ] **Step 5: Lint, type-check, commit**

```bash
uv run ruff check packages/haywire-studio/src/haywire_studio/farmhand/identity.py tests/farmhand/test_identity_unit.py
uv run ruff format packages/haywire-studio/src/haywire_studio/farmhand/identity.py tests/farmhand/test_identity_unit.py
uv run mypy packages/haywire-studio/src/
git add packages/haywire-studio/src/haywire_studio/farmhand/identity.py tests/farmhand/test_identity_unit.py
git commit -m "feat(farmhand): studio sidecar identity file (write/read/status)"
```

---

### Task 2: Write the sidecar from `setup_farmhand`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/app.py:207-216` (`setup_farmhand`)
- Test: `tests/farmhand/test_identity_startup.py`

**Interfaces:**
- Consumes: `haywire_studio.farmhand.identity.write_identity(workspace_root, port)` (Task 1); `HaywireApp.workspace_root: str` (`app.py:42`); `HaywireApp.setup_farmhand(self, port: int)` (`app.py:207`).
- Produces: after `setup_farmhand(port)` runs with Farmhand enabled, `<workspace>/.haywire/studio.json` exists and records that `port`. When Farmhand is disabled, no sidecar is written.

- [ ] **Step 1: Write the failing test**

Read `setup_farmhand` at `app.py:207` and `tests/farmhand/conftest.py` first. `FarmhandSettings().enabled` gates the body; the test toggles it via monkeypatch to avoid a real mount. Then write:

```python
# tests/farmhand/test_identity_startup.py
"""setup_farmhand writes the studio sidecar when Farmhand is enabled."""

import pytest

from haywire_studio.farmhand.identity import IDENTITY_FILENAME, read_identity

pytestmark = pytest.mark.unit


class _FakeHost:
    def __init__(self, *args, **kwargs):
        pass

    def mount(self, port):  # no real network mount in a unit test
        self.mounted_port = port


@pytest.fixture()
def app_state(tmp_path, monkeypatch):
    # Import lazily and build a minimal HaywireApp rooted at tmp_path.
    from haywire_studio import app as app_module

    monkeypatch.setattr(app_module, "FarmhandHost", _FakeHost, raising=False)
    state = app_module.HaywireApp(workspace_root=str(tmp_path))
    # library_service is referenced by setup_farmhand's FarmhandHost(...) call;
    # _FakeHost ignores it, so a bare attribute is enough.
    state.library_service = object()
    return state, tmp_path, app_module


def _set_enabled(monkeypatch, app_module, value: bool):
    class _Settings:
        enabled = value

    # setup_farmhand imports FarmhandSettings locally from farmhand.settings.
    import haywire_studio.farmhand.settings as settings_module

    monkeypatch.setattr(settings_module, "FarmhandSettings", _Settings)


def test_sidecar_written_when_enabled(app_state, monkeypatch):
    state, tmp_path, app_module = app_state
    _set_enabled(monkeypatch, app_module, True)

    state.setup_farmhand(8082)

    ident = read_identity(tmp_path)
    assert ident is not None
    assert ident["port"] == 8082
    assert (tmp_path / ".haywire" / IDENTITY_FILENAME).exists()


def test_no_sidecar_when_disabled(app_state, monkeypatch):
    state, tmp_path, app_module = app_state
    _set_enabled(monkeypatch, app_module, False)

    state.setup_farmhand(8082)

    assert read_identity(tmp_path) is None
```

Note: `setup_farmhand` does `from haywire_studio.farmhand.settings import FarmhandSettings` and `from haywire_studio.farmhand.host import FarmhandHost` *inside* the method. Patch `FarmhandSettings` on `haywire_studio.farmhand.settings` and `FarmhandHost` on the `app` module (its local import binds the name into `app`'s namespace only at call time, so patch the source module for `FarmhandHost` if the app-module patch does not take — verify which by running the test). Adapt the two patch targets to whichever the local imports actually resolve.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/farmhand/test_identity_startup.py -v`
Expected: FAIL — `test_sidecar_written_when_enabled` fails because no sidecar is written yet (`read_identity` returns `None`).

- [ ] **Step 3: Add the write to `setup_farmhand`**

In `packages/haywire-studio/src/haywire_studio/app.py`, the current method is:

```python
    def setup_farmhand(self, port: int) -> None:
        """Mount the Farmhand MCP server if enabled (flag read once; restart to apply)."""
        from haywire_studio.farmhand.host import FarmhandHost
        from haywire_studio.farmhand.settings import FarmhandSettings

        if not FarmhandSettings().enabled:
            logging.getLogger(__name__).info("Farmhand: disabled by settings (farmhand.enabled = false)")
            return
        self.farmhand_host = FarmhandHost(self.library_service, self.workspace_root)
        self.farmhand_host.mount(port)
```

Change it to (append the sidecar write after the mount, guarded so it can never crash startup):

```python
    def setup_farmhand(self, port: int) -> None:
        """Mount the Farmhand MCP server if enabled (flag read once; restart to apply)."""
        from haywire_studio.farmhand.host import FarmhandHost
        from haywire_studio.farmhand.settings import FarmhandSettings

        if not FarmhandSettings().enabled:
            logging.getLogger(__name__).info("Farmhand: disabled by settings (farmhand.enabled = false)")
            return
        self.farmhand_host = FarmhandHost(self.library_service, self.workspace_root)
        self.farmhand_host.mount(port)

        # Write the sidecar identity file so a later process (the farmhand4claude
        # plugin startup script) can identify which project owns this studio on
        # this port. Must never break studio launch.
        from pathlib import Path

        from haywire_studio.farmhand.identity import write_identity

        try:
            write_identity(Path(self.workspace_root), port)
        except Exception:
            logging.getLogger(__name__).warning("Farmhand: failed to write studio identity sidecar", exc_info=True)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/farmhand/test_identity_startup.py -v`
Expected: both PASS.

- [ ] **Step 5: Run the full farmhand suite (no regressions)**

Run: `uv run pytest tests/farmhand/ -m "not browser and not perf" -q`
Expected: all PASS (existing farmhand tests unaffected by the additive write).

- [ ] **Step 6: Lint, type-check, commit**

```bash
uv run ruff check packages/haywire-studio/src/haywire_studio/app.py tests/farmhand/test_identity_startup.py
uv run ruff format packages/haywire-studio/src/haywire_studio/app.py tests/farmhand/test_identity_startup.py
uv run mypy packages/haywire-studio/src/
git add packages/haywire-studio/src/haywire_studio/app.py tests/farmhand/test_identity_startup.py
git commit -m "feat(farmhand): write studio identity sidecar on mount"
```

---

### Task 3: Docs — record the sidecar in the glossary and Farmhand arch

**Files:**
- Modify: `docs/reference/glossary.md` (Farmhand section — add a `studio.json` term)
- Modify: `docs/architecture/farmhand/farmhand-arch.md` IF it exists (else skip — verify first)

**Interfaces:**
- Consumes: the landed behavior from Tasks 1–2.
- Produces: a glossary term future readers can find; no code.

- [ ] **Step 1: Verify the Farmhand arch doc path**

Run: `ls docs/architecture/farmhand/ 2>/dev/null; ls docs/components/*/farmhand* 2>/dev/null`
Expected: note whether a Farmhand architecture doc exists. If none exists, this task modifies only the glossary.

- [ ] **Step 2: Add the glossary term**

In `docs/reference/glossary.md`, inside the "Farmhand — the AI harness" table, add this row after the **Farmhand proxy** row:

```markdown
| **Studio identity sidecar** (`studio.json`) | The self-describing JSON the studio writes to `<workspace>/.haywire/studio.json` when it mounts the Farmhand endpoint: `pid`, `port`, `project`, `project_path`, `started_at`, `host`, `role`, `url`. Lets a later process (the farmhand4claude plugin's startup script) identify which project owns the studio on a port and decide to reuse / ask / clean up. Gitignored, machine-local; written only when `farmhand.enabled`. Sits beside `farmhand_token`. | pid file (studioctl's is a bare integer; this is structured identity) |
```

- [ ] **Step 3: Verify the doc builds**

Run: `uv run mkdocs build --strict 2>&1 | tail -5`
Expected: build succeeds (no broken-link/strict errors introduced by the new row).

- [ ] **Step 4: Commit**

```bash
git add docs/reference/glossary.md
git commit -m "docs(farmhand): document the studio identity sidecar (studio.json)"
```

---

## Self-Review

**Spec coverage:**
- Studio writes `<project>/.haywire/studio.json` at startup → Task 1 (`write_identity`) + Task 2 (call site). ✓
- Fields pid/port/project/project_path/started_at/url/host/role → Task 1 test asserts each. ✓
- Beside `farmhand_token`, same `.haywire/` + gitignore discipline → Task 1 (`_ensure_gitignored`, mirrors `auth.py`). ✓
- Written only when Farmhand enabled → Task 2 `test_no_sidecar_when_disabled`. ✓
- Never crashes startup → Task 2 try/except guard. ✓
- stdlib-only, no psutil hard dep → Global Constraints + Task 1 guarded import; `identity_status` degrades to `"alive"`. ✓
- read/status helpers for the plugin script's later use → Task 1 (`read_identity`, `identity_status`) with `dead`/`alive` tests. ✓
- Documented → Task 3 glossary row. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows full code; every test step shows the assertions. ✓

**Type consistency:** `IDENTITY_FILENAME`, `write_identity(workspace_root, port) -> dict`, `read_identity(workspace_root) -> dict | None`, `identity_status(ident) -> str` used identically across Tasks 1–2 and the Task 3 glossary. `workspace_root` accepted as `Path | str` in Task 1; Task 2 passes `Path(self.workspace_root)`. ✓

**Out of scope (belongs to the farmhand4claude repo plan, NOT here):** the plugin startup script that *reads* the sidecar, the `lsof` port→PID→cwd fallback, and the ask-user prompt. This plan only makes the studio *produce* the identity the plugin will later consume.
