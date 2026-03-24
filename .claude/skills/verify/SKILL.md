---
name: verify
description: Run the full quality suite (lint, format check, type check, unit tests, integration tests) before marking a task done. Use this to confirm changes are ready.
---

Run each step in sequence, stopping at the first failure. Report a pass/fail status after each step.

## Steps

```sh
uv run ruff check .                   # lint
uv run ruff format --check .          # format check
uv run mypy packages/haywire-core/src/  # type check
uv run pytest -m "not integration"    # unit + other fast tests
uv run pytest -m integration          # integration tests (slow)
```

## Reporting

For each step, show whether it passed or failed. On failure, show the relevant output and suggest what to fix:

- **ruff check**: show the lint errors; suggest `uv run ruff check --fix .` for auto-fixable issues
- **ruff format**: show which files need formatting; suggest `uv run ruff format .`
- **mypy**: show the type errors; suggest reviewing the flagged lines
- **pytest (fast)**: show failing test names and tracebacks
- **pytest (integration)**: show failing test names and tracebacks

If all steps pass, confirm the changes are ready.
