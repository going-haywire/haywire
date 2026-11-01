# List models

`haybale-models:farmhand:list` · kind: farmhand

Catalog entries with per-variant status, indexed local files and download jobs.

## Agent Instructions

Lists the model catalog (every entry with each variant's size and status: local, HF cache, queued, downloading N %, failed, not downloaded), the files indexed in the models volume, and the download jobs. detail=true adds license and description to catalog rows.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'detail': {'type': 'boolean', 'default': False}}, 'required': []}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`

## Notes

Lists the model catalog, the local model files and the download jobs.

Returns every catalog entry with its variants (size and status: local, HF cache,
queued, downloading, failed or not downloaded), every file indexed in the models
volume, and every download job with its progress. Call it first, to learn the
catalog keys that `models_fetch` takes and to follow a download. Pass
`detail=true` to add license and description to the catalog rows.
