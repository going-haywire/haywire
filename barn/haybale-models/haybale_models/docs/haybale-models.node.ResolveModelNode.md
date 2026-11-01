# Resolve Model

`haybale-models:node:ResolveModelNode` · kind: node

Gives the file of a model on this machine, with its sha256 and size

## Ports

| id | direction | type | description |
|---|---|---|---|
| `model` | inlet | `haybale-models:type:MODEL_REF` | A model, named by a catalog entry or by a file (url and sha256). Resolve Model turns it into a path on disk. |
| `path` | outlet | `haywire-core:type:FILE_PATH` | A file inside a named volume such as the project folder or `models`. |
| `sha256` | outlet | `haywire-core:type:STRING` | Text data |
| `size` | outlet | `haywire-core:type:INT` | Whole number |

## Notes

Gives the file of a model on this machine, with its sha256 and size.

Pick the model on the card: a catalog entry, or a file by its address
(`hf://` or `https://`) or from the Models or Hugging Face cache folder.
Nothing is downloaded here: a model that is not on this machine is an
error until it is fetched in the Models editor.

- `Path`: the file, as a path inside the `Models` or `Hugging Face cache`
  volume. For a model made of several files, the folder holding them.
- `sha256`: the file's digest, empty when it is not known yet.
- `Size`: the size in bytes, of all files together for a model made of
  several files.

For a catalog entry with several variants, the first one on disk in the
port's preferred order is used.
