# Follow-up: settings file watcher crashes on a missing parent directory

**Date raised:** 2026-05-29
**Severity:** latent robustness bug — platform-dependent (Linux only)
**Status:** RESOLVED 2026-05-29
**Found during:** cutting release v0.0.2 (CI publish gate failures)

## Resolution (2026-05-29)

Fixed in `SettingsRegistry._start_file_watcher`
(`packages/haywire-core/src/haywire/core/settings/registry.py`): the watcher
now `path.parent.mkdir(parents=True, exist_ok=True)` before scheduling the
observer (option 1 below), and wraps `observer.start()` in a try/except that
degrades to no-watch on `OSError` (option 3) so a watcher failure can never
break app init. Regression test added at
`tests/core/test_settings/test_settings_file_watcher.py` covering both the
missing-parent-dir case and the missing-file/existing-dir first-run case.

The `watch_settings=False` workaround in `tests/core/test_state/test_di_wiring.py`
was kept deliberately — unit tests should not spin up real OS watchers or
touch the developer's home directory, independent of this fix.

The related `ui` Playwright CI gap (see "Related" below) was also closed: a
dedicated `ui` job was added to `.github/workflows/tests.yml` that runs
`playwright install --with-deps chromium` then `pytest -m ui`.

---
*Original report below.*

## Symptom

On Linux, starting the settings file watcher against a settings path whose
**parent directory does not exist** raises:

```
FileNotFoundError: [Errno 2] No such file or directory
  at watchdog/observers/inotify_c.py _add_watch
```

This surfaced in CI when `tests/core/test_state/test_di_wiring.py` ran
`create_haywire_injector()` (which defaults `watch_settings=True`) on a fresh
GitHub runner where `~/.haywire/` had never been created. The log line right
before the crash is the tell: `Settings file not found, will create on save:
/home/runner/.haywire/settings.toml`.

macOS (FSEvents backend) tolerates watching a not-yet-existent target, so this
never reproduced locally — it only bit on the Linux publish runner.

## Root cause

`SettingsRegistry._start_file_watcher` schedules a watch on `path.parent`:

- File: `packages/haywire-core/src/haywire/core/settings/registry.py`
- Around line 687–689:
  ```python
  observer = Observer()
  observer.schedule(ConfigHandler(), str(path.parent), recursive=False)
  observer.start()
  ```

If `path.parent` doesn't exist, the Linux inotify backend throws on
`observer.start()`. The code assumes the directory is present (true once
settings have been saved at least once, false on a first-run/clean machine).

This affects **real app startup**, not just tests: any Linux user launching
Haywire for the first time with no `~/.haywire/` directory and
`watch_settings=True` would hit this during the global-tier settings load
(`config.py` `provide_settings_registry` → `load_from_toml(..., watch=True)`).

## What was done for the release (workaround, not a fix)

Test-only changes so the v0.0.2 publish gate could go green — the product
bug was intentionally left untouched mid-release:

- `tests/core/test_state/test_di_wiring.py`: pass `watch_settings=False` to
  all 5 `create_haywire_injector()` call sites (unit DI-wiring tests have no
  business spinning up a real OS file watcher).

So the product code path is still vulnerable.

## Suggested fix (for a future PR)

In `_start_file_watcher`, make the parent-directory requirement explicit
instead of assuming it. Options, roughly in order of preference:

1. **Ensure the directory exists before watching.** If the app is going to
   "create on save" anyway, `path.parent.mkdir(parents=True, exist_ok=True)`
   before scheduling the observer. Cheap, removes the foot-gun entirely.
2. **Skip watching gracefully** if the parent is missing, and log a warning
   (e.g. "settings dir not present yet; hot-reload disabled until first
   save"). Re-arm the watcher after the first save creates the file.
3. **Wrap `observer.start()` defensively** and degrade to no-watch on
   `OSError`, so a watcher failure can never take down app initialization.

Whichever path is chosen, add a regression test that starts the watcher with
a `tmp_path` pointing at a **non-existent** subdirectory and asserts it does
not raise (and behaves per the chosen option). This would have caught the
Linux divergence on macOS dev machines.

## Related

- The release gate marker was also narrowed (`-m "not integration and not ui"`
  in `.github/workflows/publish.yml`) so browser/Playwright `ui` tests don't
  run on the publish runner. Separate concern, noted here only because it was
  fixed in the same pass. If `ui` tests should run in CI, that needs a
  `playwright install` step somewhere — currently no CI job runs them.
