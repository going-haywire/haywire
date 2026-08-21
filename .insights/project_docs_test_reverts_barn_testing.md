# Running the docs-generator test discards uncommitted work in `barn/haybale-testing/`

**Symptom.** You edit a file under `barn/haybale-testing/`, verify the edit, run
the test suite — and the edit is gone. Re-apply it, run the suite again, gone
again. `git status` shows the file as unmodified, so it looks like an IDE or an
external process is fighting you.

**Cause.** `tests/studio/test_docs/test_generate.py` has a `clean_haybale_testing`
fixture whose teardown runs:

```python
subprocess.run(["git", "checkout", "--", str(lib_dir)], cwd=repo, check=False)
```

`git checkout -- <dir>` restores **every tracked file** in that directory to
HEAD. The fixture's intent is narrow — `generate_docs()` writes `OVERVIEW.md`,
`QUICKREF.md`, `README.md` and `docs/*.md` in place against the *real* library
(library discovery is entry-point/import based, so `folder_path` is baked to the
repo location and cannot be redirected to a scratch copy), and those generated
files must not be left behind. But the blast radius is the whole directory, so
any unrelated uncommitted edit under `barn/haybale-testing/` is collateral.

The teardown also deletes untracked files there (it enumerates `??` entries from
`git status --porcelain` and removes them, because a repo hook blocks
`git clean -fd`). So a *new* file you add under that directory is destroyed too.

**Why it is confusing.** The revert happens on fixture teardown, so it lands in
the middle of a long suite run. If the affected module was already imported
earlier in the same run, `importlib` serves it from `sys.modules` and the suite
still passes — the damage only surfaces on the *next* run, or in a later `mypy`
pass. A green suite is therefore not evidence the file survived.

**Rule.** Commit changes under `barn/haybale-testing/` before running anything
broader than a single test file. If you must keep them uncommitted, run with
`--deselect tests/studio/test_docs/test_generate.py` (or `-m "not integration"`,
which deselects it along with the rest of the integration tier).

**Bisecting a mystery revert.** Fix the file, run one test directory, check;
repeat. The check is a one-liner:

```sh
grep -q '<the-old-text>' <file> && echo REVERTED || echo ok
```

Directory-level bisection found this in two passes — the culprit is invisible to
grep, because no test mentions the affected file by name.
