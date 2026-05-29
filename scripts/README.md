# scripts/

Maintenance scripts run by humans or CI.

| Script                | Purpose                                                          |
| --------------------- | ---------------------------------------------------------------- |
| `bump_version.py`     | Bump every Tier 1+2 package to a new lockstep version.           |
| `check_deps.py`       | Audit declared vs. imported deps per package (wraps `deptry`).   |
| `generate_marketstall.py` | CI marketstall generator for the published packages.            |

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

## check_deps.py

```bash
# Audit every package in [tool.haywire.release].
uv run python scripts/check_deps.py

# Audit a single package.
uv run python scripts/check_deps.py haywire-core
```

Wraps `deptry`, running it once per package with a dist→module name map so
inter-package deps aren't mis-flagged. Reports three classes: MISSING (imported but
undeclared — can break a standalone PyPI install), UNUSED (declared but unused), and
NOT INSTALLED (imported but absent). Always exits 0 — it's a report, not a gate. The
`/haywire-release` skill runs it at Step 2.5. Known false positives (e.g. `attrs` as a
transitive of `cattrs`) are suppressed via the `KNOWN_OK` map in the script.

## generate_marketstall.py

```bash
# Print the generated marketplace to stdout.
uv run python scripts/generate_marketstall.py

# Write to a file (used by the publish workflow).
uv run python scripts/generate_marketstall.py --out dist/marketplace.toml
```

Reads `[tool.haywire.release].publish_order` and `[tool.haywire.marketstall]` from
the workspace root `pyproject.toml`. For each publishable package, lifts
`label` / `description` / `author` / `tags` from the package's `@library`
decorator and falls back to the pyproject `description` and `[tool.haywire.marketstall]`
defaults when the decorator omits a field.

The output is deployed to GitHub Pages on every release tag by
`.github/workflows/publish.yml`. Subscribers fetch it from
`https://going-haywire.github.io/haywire/marketplace.toml`.
