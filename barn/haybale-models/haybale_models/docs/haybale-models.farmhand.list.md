# List models

`haybale-models:farmhand:list` · kind: farmhand

Catalog entries with per-variant status, indexed local files and download jobs.

## Agent Instructions

Lists the model catalog (every entry with each variant's size and status: local, HF cache, queued, downloading N %, failed, not downloaded), the files indexed in the models volume, and the download jobs. detail=true adds license, commercial and description to catalog rows.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'detail': {'type': 'boolean', 'default': False}}, 'required': []}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`

## Notes

Lists the model catalog, the local model files and the download jobs.

Returns every catalog entry with its variants (size and status: local, HF cache,
queued, downloading, failed or not downloaded), every file indexed in the models
volume, and every download job with its progress. Call it first, to learn the
catalog keys that `models_fetch` takes and to follow a download. Pass
`detail=true` to add license, commercial (whether the author states the model may be used
commercially) and description to the catalog rows.

A failed job with `assisted` true can be finished by the user: they get the file from one of its
`page_urls` and hand it over with Download in browser in the Models editor.
