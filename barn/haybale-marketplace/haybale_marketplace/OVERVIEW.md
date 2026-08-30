# Marketplace

Library installer + browser editors

## Farmhands
- **Dry-run install** — Resolve what an install would remove/upgrade, without installing (informational valve).
- **Get library docs** — Docs for an installed library (OVERVIEW/QUICKREF/README) or an available one.
- **Install library** — Install a library via uv pip (streams progress). Destructive: changes the venv. Run marketplace_dry_run_install first.
- **List available** — Merged AVAILABLE catalog (not-installed libraries) from the marketplace cache.
- **Refresh catalog** — Re-fetch all subscribed markets/stalls (network; rewrites the project cache).
- **Uninstall library** — Uninstall an installed library via uv pip (streams progress). Destructive.

## States
- **Library Manager State** — 
- **Marketplace State** — 

## Editors
- **Libraries** — Searchable list of installed and available libraries.
- **Library Detail** — Detailed information for the selected library.
