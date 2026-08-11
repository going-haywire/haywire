# Refresh catalog

`marketplace:farmhand:refresh` · kind: farmhand

Re-fetch all subscribed markets/stalls (network; rewrites the project cache).

## Agent Instructions

Re-fetch all subscribed markets/stalls over the network and rewrite the project's marketplace cache. Call this when marketplace_list_available looks stale — otherwise the cache is used as-is. Returns how many haybales were resolved.

## Details

- **input_schema**: `{'type': 'object', 'properties': {}, 'required': []}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': True}`
