# REPORT: Framework self-update and restart

**Status:** research complete, design undecided
**Date:** 2026-08-02
**Question:** Haywire is a NiceGUI/uvicorn server the user launches themselves (`uv run haywire`) inside a uv-managed project venv. The framework ships as two pip packages (`haywire-core`, `haywire-studio`) pinned per-project with `~=X.Y.Z` at scaffold time. We want an in-app "a newer Haywire is available — update" affordance with a forced restart. How can a running process upgrade its own venv and restart itself, and how do comparable apps solve this?

---

## Recommendation

**Build C (supervisor parent), but ship A (instructional) first. Reject B (`os.execv`) outright.**

The decisive constraint is not the restart — it is the **upgrade window**. Electron, Squirrel, VS Code, Home Assistant, and uvicorn itself all converge on one invariant:

> The entity performing the swap must be outside the entity being swapped, and the swap must happen when the swapped thing is not running.

B violates this invariant. A and C satisfy it.

Candidate approaches as framed during design:

- **A. Instructional restart** — app detects and writes the new pin, then tells the user to quit and re-run.
- **B. Self re-exec** — `os.execv` after upgrading in place.
- **C. Supervisor parent** — `haywire` becomes a thin parent that spawns the studio as a child, upgrades the venv between generations, and respawns.

---

## Findings

### 1. uvicorn never re-execs — it binds the socket in the parent and spawns fresh children

In the installed uvicorn 0.49.0 source:

- `uvicorn/main.py:613-618` — binds via `config.bind_socket()` *before* handing off to a supervisor.
- `uvicorn/supervisors/basereload.py:87-101` — terminates the child, joins it, and spawns a new one.
- `uvicorn/_subprocess.py:18` — pins `multiprocessing.get_context("spawn")`, i.e. a **fresh interpreter**, which is exactly what loading upgraded code requires.

NiceGUI 3.13.0 copies this wholesale (`nicegui/ui_run.py:303-310`, whose comment reads "basically a copy of `uvicorn.run`").

Consequence: **the listening port is never unbound across a restart.** This is the reference pattern for C.

### 2. `os.execv` on Windows is not an in-place replacement at all

- CPython's docs scope the "same process id" guarantee to **Unix only**.
- Microsoft's CRT reference states all `_exec` functions "use the same operating-system function (`CreateProcess`)", and that "signal settings aren't preserved… reset to the default in the new process."

So on Windows: new PID, reset signal handlers, broken shell foreground job.

Separately, Python file descriptors are **`CLOEXEC` by default since Python 3.4** — so `exec` *closes the listening socket*, and the successor process must re-bind blind, with no backlog preservation.

### 3. Home Assistant — the closest analogue — deliberately does NOT restart itself

Verified in source:

- `homeassistant/const.py:999` → `RESTART_EXIT_CODE: Final = 100`
- `homeassistant/components/homeassistant/__init__.py:476-480` — the restart service validates config first, then converts "restart" into that exit code via a graceful `hass.async_stop(exit_code)`.
- `homeassistant/__main__.py:227` — the code propagates out through `sys.exit(main())`.

The CLI `--help` epilog even advertises the sentinel exit code.

**Crucially: Home Assistant's in-app restart button exists *because* there is a supervisor.** The bare pip/venv "Core" install gets neither managed updates nor managed restarts. This is the single most transferable precedent for Haywire.

### 4. Windows file locking hits Haywire's own entry point

Primary mechanism, from the `DeleteFileW` remarks: deletion "fails if an application attempts to delete a file that has other handles open for normal I/O or as a memory-mapped file."

Measured empirically in this repo's interpreter: after import, `.py` sources have **no open descriptor**, while loaded native extensions stay mapped (e.g. `_json…so` held as `txt`).

So `.py` files are replaceable under a running process, but `.pyd` files and the running `.exe` wrapper are not — cf. pypa/pip#9395, where upgrading pip cannot delete the running `pip.exe`.

`haywire-studio` owns the `haywire` console script (`packages/haywire-studio/pyproject.toml:26-27`), so **upgrading it on Windows means replacing `haywire.exe` while it runs.**

### 5. `uv run` stays alive as a parent — measured here (uv 0.7.19)

`ppid` resolves to `uv run python -c …`; uv does **not** exec away. The terminal's foreground job is `uv`, not Python, so a Python-side exec orphans it.

This also means approach A can defer the entire sync to the next `uv run` invocation.

### 6. Electron / VS Code pattern (Part 2)

Electron's restart primitive is explicitly **spawn-then-exit, not exec**: `app.relaunch()` "does not quit the app when executed. You have to call `app.quit` or `app.exit` after."

VS Code stages installers in `path.join(tmpdir(), 'vscode-…')` and spawns them `{ detached: true }`, so the parent can die without killing the installer.

Neither ever overwrites the running bundle in place; both stage alongside and swap on quit/relaunch.

### 7. Lifespan-trap assessment

Re: `.insights/feedback_nicegui_lifespan_task_scope.md`.

**No collision under A or C.** `app.shutdown()` already takes the `Server.instance.should_exit = True` branch under Haywire's `reload=False` (`nicegui/app/app.py:203-204`), so lifespan unwinds normally and `farmhand/host.py:282-299` (already using the documented single-runner-task fix) stops cleanly.

**Under B the handlers never run at all** — which bypasses rather than avoids the problem, leaving a stale identity sidecar (`app.py:221`) and a hard MCP transport drop.

---

## Suggested staging

1. **A first, in pin-bump-only form:** detect, write the new `~=X.Y.Z` pin, instruct restart. **Do not run `uv sync` in-process** — this eliminates the mixed-version window entirely and sidesteps the Windows `haywire.exe` lock completely.
2. **Then C:** Home Assistant's sentinel-exit-code contract out of a graceful `should_exit` shutdown, plus uvicorn's spawn-a-fresh-child. Upgrade strictly *between* generations.

---

## Open questions / unverified claims

- **uv's install atomicity** — the sync docs confirm exact syncing but say nothing about hardlink-vs-copy, write atomicity, or behaviour when the env is in use. **Directly load-bearing for C**; worth a targeted experiment.
- **Windows behaviour for Haywire specifically** — the `.py`-vs-`.so` handle measurement was done on macOS. Whether Haywire's deps load blocking `.pyd`s, and whether `uv run haywire` dodges the `haywire.exe` lock, is **untested on Windows**. Highest-value remaining experiment.
- **Squirrel.Mac/ShipIt internals** — the README does not describe the staging dir or atomicity; the "separate helper" claim rests on Electron/VS Code evidence rather than Squirrel's own docs.
- **Streamlit/Gradio** — "no documented feature found", which is not the same as "verified absent".
- **Home Assistant's 2022.2.0 rationale** — the mechanism is fully verified in source, but the explanatory sentence came via a search summary (secondary). Same for the HA install-method feature matrix.
- **Whether the C launcher can avoid upgrading itself** — unresolved, and an architectural choice rather than a research gap.
