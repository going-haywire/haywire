---
name: verify
description: Run the full local quality suite (lint, format check, type check, both test tiers in parallel), the same checks CI runs on every PR, in about five minutes. Use it when the user asks for a local full run; it is not required before a commit, since CI runs these on every push.
---

The same checks as CI (`.github/workflows/ci.yml`), run locally. Not a commit gate:
commits run the checks of what changed, and CI runs everything on every push (see the
*Git and testing* section of CLAUDE.md).

Run each step in sequence, stopping at the first failure. Report a pass/fail status after each step.
Redirect the test output to a file and read its tail; the exit code is the signal.

## Steps

```sh
uv run ruff check .                                    # lint
uv run ruff format --check .                           # format check
uv run mypy <the paths of the types job in .github/workflows/ci.yml>   # type check
uv run pytest -m "not browser and not perf" -n 4 -q    # ~4 min
uv run pytest -m browser -n 4 -q                       # ~2 min
```

Use `-n 4`, never more (tests/README.md explains why). A run that hangs to the 120 s
timeout is a lock cycle, not flakiness.

## Reporting

For each step, show whether it passed or failed. On failure, show the relevant output and suggest what to fix:

- **ruff check**: show the lint errors; suggest `uv run ruff check --fix .` for auto-fixable issues
- **ruff format**: show which files need formatting; suggest `uv run ruff format .`
- **mypy**: show the type errors; suggest reviewing the flagged lines
- **pytest**: show failing test names and tracebacks

If all steps pass, confirm the changes are ready.
