# marketplace — component index (v0.0.31)

## farmhand
- `marketplace:farmhand:dry_run_install` — Dry-run install — Resolve what an install would remove/upgrade, without installing (informational valve).
- `marketplace:farmhand:get_library_docs` — Get library docs — Docs for an installed library (OVERVIEW/QUICKREF/README from its folder) or an available one (network fetch of its docs_url). Pass component=<registry_key> to fetch one component's deep doc (installed: wheel; available: docs_url).
- `marketplace:farmhand:install_library` — Install library — Install a library via uv pip (streams progress). Destructive: changes the venv. Run marketplace_dry_run_install first.
- `marketplace:farmhand:list_available` — List available — Merged AVAILABLE catalog (not-installed libraries) from the marketplace cache.
- `marketplace:farmhand:refresh` — Refresh catalog — Re-fetch all subscribed markets/stalls (network; rewrites the project cache).
- `marketplace:farmhand:uninstall_library` — Uninstall library — Uninstall an installed library via uv pip (streams progress). Destructive.

## state
- `marketplace:state:LibraryManagerState` — Library Manager State — 
- `marketplace:state:MarketplaceState` — Marketplace State — 

## editor
- `marketplace:editor:LibraryBrowserEditor` — Libraries — Searchable list of installed and available libraries.
- `marketplace:editor:LibraryComponentEditor` — Component Detail — Detailed documentation for the selected node component.
- `marketplace:editor:LibraryOverviewEditor` — Library Detail — Detailed information for the selected library.
