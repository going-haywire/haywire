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

## `-m unit` is not a usable tier

It currently fails on `test_split_edge_reroute` with
`assert <class ...EXEC> is <class ...EXEC>` — the module-reload identity trap in
[project_registry_force_reload_bug.md](project_registry_force_reload_bug.md).
The file passes when run alone, so this is cross-test pollution the `unit`
selection exposes, not a real defect in that test. Scope with a path or `-k`
instead.
