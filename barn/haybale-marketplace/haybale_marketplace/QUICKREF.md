# haybale-marketplace — component index (v0.1.3)

## farmhand
- `haybale-marketplace:farmhand:dry_run_install` — Dry-run install — Resolve what an install would remove/upgrade, without installing (informational valve).
- `haybale-marketplace:farmhand:get_library_docs` — Get library docs — Docs for an installed library (OVERVIEW/QUICKREF/README) or an available one.
- `haybale-marketplace:farmhand:install_library` — Install library — Install a library via uv pip (streams progress). Destructive: changes the venv. Run marketplace_dry_run_install first.
- `haybale-marketplace:farmhand:list_available` — List available — Merged AVAILABLE catalog (not-installed libraries) from the marketplace cache.
- `haybale-marketplace:farmhand:refresh` — Refresh catalog — Re-fetch all subscribed markets/stalls (network; rewrites the project cache).
- `haybale-marketplace:farmhand:uninstall_library` — Uninstall library — Uninstall an installed library via uv pip (streams progress). Destructive.

## state
- `haybale-marketplace:state:LibraryManagerState` — Library Manager State — 
- `haybale-marketplace:state:MarketplaceState` — Marketplace State — 

## editor
- `haybale-marketplace:editor:LibraryBrowserEditor` — Libraries — Searchable list of installed and available libraries.
- `haybale-marketplace:editor:LibraryOverviewEditor` — Library Detail — Detailed information for the selected library.
