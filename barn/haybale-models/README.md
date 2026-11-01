# Models

<!-- marketstall:share-url:start -->
*Subscribe URL not yet published — run `haywire share --save`.*
<!-- marketstall:share-url:end -->

Model references, local model store, downloads and graph needs-list

## Nodes
### Models
- **Resolve Model** — Gives the file of a model on this machine, with its sha256 and size

## Types
- **Model** — A model, named by a catalog entry or by a file (url and sha256). Resolve Model turns it into a path on disk.

## Widgets
- **ModelRefWidget** — Pick a model

## Settings
- **Models** — Model download behaviour

## Farmhands
- **Fetch models** — Queue downloads: everything an open graph needs, or catalog entries by key (admin).
- **List models** — Catalog entries with per-variant status, indexed local files and download jobs.
- **Models a graph needs** — The models an open graph references and does not have locally.

## States
- **Models** — Model volumes, file index, download queue and the pool of loaded models
- **Models View** — Per-session view state of the Models editor.

## Editors
- **Models** — Model files on this machine and where they come from
