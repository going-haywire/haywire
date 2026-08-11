# Dry-run install

`marketplace:farmhand:dry_run_install` · kind: farmhand

Resolve what an install would remove/upgrade, without installing (informational valve).

## Agent Instructions

Resolve what installing install_spec would remove or upgrade, WITHOUT actually installing — a preview only, no changes to the venv. Run this before marketplace_install_library to see the blast radius. Returns the list of affected distributions; raises resolver_failed if resolution itself fails.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'install_spec': {'type': 'string'}}, 'required': ['install_spec']}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': True}`
