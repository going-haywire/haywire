# Install library

`marketplace:farmhand:install_library` · kind: farmhand

Install a library via uv pip (streams progress). Destructive: changes the venv. Run marketplace_dry_run_install first.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'install_spec': {'type': 'string'}}, 'required': ['install_spec']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': True, 'idempotent_hint': False, 'open_world_hint': True}`
