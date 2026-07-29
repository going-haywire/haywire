# Dry-run install

`marketplace:farmhand:dry_run_install` · kind: farmhand

Resolve what an install would remove/upgrade, without installing (informational valve).

## Details

- **input_schema**: `{'type': 'object', 'properties': {'install_spec': {'type': 'string'}}, 'required': ['install_spec']}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': True}`
