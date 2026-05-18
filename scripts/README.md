# scripts/

Maintenance scripts run by humans or CI.

| Script                | Purpose                                                          |
| --------------------- | ---------------------------------------------------------------- |
| `bump_version.py`     | Bump every Tier 1+2 package to a new lockstep version.           |
| `generate_marketstall.py` | (planned) CI marketstall generator for the published packages.  |

## bump_version.py

```bash
# Preview what would change.
uv run python scripts/bump_version.py 0.0.2 --dry-run

# Apply with confirmation prompt.
uv run python scripts/bump_version.py 0.0.2

# Apply without prompting (CI / scripts).
uv run python scripts/bump_version.py 0.0.2 --yes
```

Reads `[tool.haywire.release]` in the workspace root `pyproject.toml` for the canonical
package list. To add or remove a publishable package, edit that block — not the script.
