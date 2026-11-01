# Fetch models

`haybale-models:farmhand:fetch` · kind: farmhand

Queue downloads: everything an open graph needs, or catalog entries by key (admin).

## Agent Instructions

Queues the downloads and returns their job ids; progress is in models_list jobs. Pass binding_id to fetch everything that graph needs, or keys=[<catalog key>, ...] to fetch the preferred variant of each entry. Needs admin access.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string', 'default': None}, 'keys': {'type': 'array', 'items': {'type': 'string'}, 'default': None}}, 'required': []}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': True}`

## Notes

Queues downloads of missing models. Needs ADMIN access.

Pass `binding_id` to fetch everything that open graph needs, or `keys` to fetch the
preferred variant of each catalog entry. Returns the job ids at once; the files
arrive in the background, so call `models_list` to follow the jobs. Downloads use
network and disk: call it only when the user wants the models.
