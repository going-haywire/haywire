# Marketplace

Library installer + browser editors for Haywire

## Farmhands
- **Dry-run install** — Resolve what an install would remove/upgrade, without installing (informational valve).
- **Get library docs** — Docs for an installed library (OVERVIEW/QUICKREF/README from its folder) or an available one (network fetch of its docs_url). Pass component=<registry_key> to fetch one component's deep doc (installed: wheel; available: docs_url). Long documents are truncated at 12000 chars with total_chars reported; pass full=true for everything.
- **Install library** — Install a library via uv pip (streams progress). Destructive: changes the venv. Run marketplace_dry_run_install first.
- **List available** — Merged AVAILABLE catalog (not-installed libraries) from the marketplace cache. Returns name/version/label/install_spec per row; pass detail=true for the full record (description, author, tags, dependencies, source_url, docs_url, ...).
- **Refresh catalog** — Re-fetch all subscribed markets/stalls (network; rewrites the project cache).
- **Uninstall library** — Uninstall an installed library via uv pip (streams progress). Destructive.
