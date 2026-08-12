---
name: Slow tests — the two shapes that actually cost minutes
description: A multi-second test in a suite that otherwise runs tens of milliseconds each is almost always an accidental network call paid as a timeout, or serial subprocess spawns — not real work. Also covers sys.modules.pop() teardown bugs and the historical BaseRegistry force-reload duplicate-class bug, both producing the same 'assert Foo is Foo' signature.
type: project
---

# Slow tests: the two shapes that actually cost minutes

The non-browser suite is ~2.5 min for ~2985 tests, i.e. tens of milliseconds
each. Anything taking **seconds** is doing something categorically different,
and it is usually one of two things — neither of which is "this test does a lot
of work".

Find them first, always, instead of guessing:

```sh
uv run pytest -m "not browser and not perf" -q --durations=25
```

## 1. An accidental network call, paid as a timeout

A test that points a code path at an unroutable host does not fail fast — it
blocks until whatever timeout the production code sets, then passes.

`test_add_origin_round_trip_clears_the_missing_origin_failure` set origin to
`git@example.com:foo/bar.git`. `check_preconditions()` runs a real
`git ls-remote` once a remote exists, with `timeout=60.0`. The test asserted
only that the *missing-remote* failure cleared, and its docstring even said
reachability was allowed to fail — so the 60s bought nothing. Pointing it at the
existing `bare_remote` fixture (a local `git init --bare`, whose docstring is
literally "makes ls-remote real without a network") took it to 0.2s.

**Tell:** a duration suspiciously equal to a timeout constant (60s, 30s, 10s).
Grep the exercised code path for `timeout=` and check whether a fixture already
exists for the offline case — in this repo it usually does.

## 2. Serial subprocess spawns

`test_every_share_module_imports_standalone` spawns one interpreter per module
to prove each imports without its siblings loaded first. The isolation is the
whole point and cannot be pooled away — but the modules are independent of each
other, so the *spawns* can overlap. A `ThreadPoolExecutor` (the work is I/O-bound
on process startup, so threads suffice) took ~44s to ~7s with the guarantee
unchanged.

**Tell:** a loop containing `subprocess.run`. Ask whether the isolation must be
sequential or merely separate. Usually only separate.

## Reading long runs without fighting the terminal

`addopts` carries `-v`, so a full run is thousands of lines, and the studio's
post-run update banner can bury the summary entirely — a bare `| tail` will
sometimes show you nothing but the banner. Redirect and read the exit code,
which is the real signal:

```sh
uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/t.log
grep -E "passed|failed" /tmp/t.log | tail -1
```

## `sys.modules.pop()` in a teardown is not cleanup

`-m unit` used to fail on `test_split_edge_reroute` with
`assert <class ...EXEC> is <class ...EXEC>`. Fixed — but the shape recurs.

`test_registry_remove_library.py` overwrites the real `haybale_core` in
`sys.modules` with a fake, then cleans up with `sys.modules.pop()`. That is not
symmetric: `pop` *removes* an entry that existed beforehand, so the next
importer re-executes the module and builds a second set of class objects.
Anything holding the originals then fails `is` against identically-named
classes.

Two details make it hard to find:

- **It needs two files.** A test that imports the real module must run first for
  there to be anything to clobber, so it only appears under selections that
  order them that way — `-m unit` did, the full suite did not.
- **Restoring only what you planted is not enough.** `remove_library()` ejects
  every `haybale_core.*` submodule by prefix, including ones the test never
  touched but the package had already imported. `haybale_core.types.specs` is
  where `EXEC` lives; a fixture listing only the planted keys leaves exactly the
  entry whose loss causes the failure. Snapshot **by prefix**.

Whenever a test mutates `sys.modules`, snapshot and restore — same discipline
the DI context and settings registry already require. `assert Foo is Foo`
failing with two identical reprs is the signature; see also
[feedback_barn_module_reload_test_trap.md](feedback_barn_module_reload_test_trap.md).

### Historical case of the same signature: `BaseRegistry` force-reload (fixed)

**Fixed in commit `7b7d86e` (2026-05-06).** `_on_creation`
(`packages/haywire-core/src/haywire/core/registry/base.py`) used to pass
`force_reload=True` to `module_scan_for_classes` on the *initial* scan. If the
module was already in `sys.modules` (some earlier import path loaded it
first), the registry deleted and re-imported it, producing a fresh class
object — anyone holding a reference to the pre-scan class was left dangling
with the exact `assert Foo is Foo` signature above. The fix dropped the `True`
so `force_reload` defaults to `False` on initial scan; hot-reload of an
actually-changed file still passes `force_reload=True` via
`_reload_managed_module`, correctly.

Regression test:
`tests/core/test_libraries/test_registries.py::TestBaseRegistryClassIdentity::test_panel_pre_imported_class_matches_registered_class`.
If this signature ever recurs, check first whether a new call site passes
`force_reload=True` on an initial (non-hot-reload) scan.
