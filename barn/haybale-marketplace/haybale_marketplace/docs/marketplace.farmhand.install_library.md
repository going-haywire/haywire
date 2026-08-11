# Install library

`marketplace:farmhand:install_library` · kind: farmhand

Install a library via uv pip (streams progress). Destructive: changes the venv. Run marketplace_dry_run_install first.

## Agent Instructions

Install a library via uv pip (streams progress). DESTRUCTIVE: changes the venv. Run marketplace_dry_run_install first to preview what would be removed/upgraded. Raises install_failed with the underlying message on failure. On success, returns on_reload naming the follow-up action (e.g. whether a studio restart is needed) and broadcasts a catalog-changed signal.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'install_spec': {'type': 'string'}}, 'required': ['install_spec']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': True, 'idempotent_hint': False, 'open_world_hint': True}`
