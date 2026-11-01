# haybale-models — component index (v0.3.0)

## node
- `haybale-models:node:ResolveModelNode` — Resolve Model — Gives the file of a model on this machine, with its sha256 and size  _tags: model, resolve, file, path, weights, catalog, sha256_

## type
- `haybale-models:type:MODEL_REF` — Model — A model, named by a catalog entry or by a file (url and sha256). Resolve Model turns it into a path on disk.

## widget
- `haybale-models:widget:ModelRefWidget` — ModelRefWidget — Pick a model

## setting
- `haybale-models:setting:ModelsSettings` — Models — Model download behaviour

## farmhand
- `haybale-models:farmhand:fetch` — Fetch models — Queue downloads: everything an open graph needs, or catalog entries by key (admin).
- `haybale-models:farmhand:list` — List models — Catalog entries with per-variant status, indexed local files and download jobs.
- `haybale-models:farmhand:needs` — Models a graph needs — The models an open graph references and does not have locally.

## state
- `haybale-models:state:ModelsState` — Models — Model volumes, file index, download queue and the pool of loaded models
- `haybale-models:state:ModelsViewState` — Models View — Per-session view state of the Models editor.

## editor
- `haybale-models:editor:ModelsEditor` — Models — Model files on this machine and where they come from
