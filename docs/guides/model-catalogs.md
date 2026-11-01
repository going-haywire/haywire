---
status: draft
doc_template: guide
scope: Shipping a model catalog from a library, and using a MODEL_REF port in a node — catalog file format, filter/prefer options, per-run pool holds
see-also:
  - ../adr/0067-models-are-identified-by-digest.md
  - ../adr/0068-the-hugging-face-cache-is-a-volume.md
  - ../adr/0065-named-volumes-instead-of-absolute-paths.md
  - graph-notices.md
  - ports.md
  - ../reference/glossary.md
---

# Model catalogs — Authoring Guide

## 1. What it solves

Nodes that run a neural network need a weights file. A graph must not carry an absolute path to it, and a machine that lacks the file should be told so before the run, not fail in a worker. The `haybale-models` library gives you three things:

- A **model catalog**: your library ships one JSON file per model, and the Models editor lists every library's entries with status, size and license.
- A **MODEL_REF** port: the user picks a catalog entry (or a file) on the card; the node reads it as a **model reference**.
- A **loaded-models pool**: nodes share one in-memory copy of a model and free it when the last running node lets go.

Models are identified by digest, and a catalog reference follows the catalog: the variant used is the one that best fits the machine ([ADR 0067](../adr/0067-models-are-identified-by-digest.md)).

## 2. Shipping a catalog

Put one `.json` file per **catalog entry** in a `catalog/` folder of your library and register the folder:

```python
--8<-- "barn/haybale-example/haybale_example/__init__.py:48:51"
```

The entry's registry key is `<library-id>:model:<file stem>`, such as `haybale-example:model:1x-BroadcastToStudio-Compact-onnx`. A stem starts with a letter or digit and continues with letters, digits, `_` or `-`.

### 2.1 File format

The format is OpenModelDB's: every OpenModelDB field keeps its name, so an OpenModelDB file can be dropped in verbatim. Our additions:

| Where | Field | Meaning |
| --- | --- | --- |
| entry | `purpose` | List of what the model is for, such as `["upscale"]`, `["restoration"]` |
| entry | `requires` | An object of requirements for the entry; kept on the entry as `entry.requires` (not part of `fields()`), not interpreted by haybale-models |
| resource | `backend` | Runtime that loads the file, such as `torch` |
| resource | `precision` | `fp32`, `fp16`, `bf16`... |
| resource | `urls` | `https://` and `hf://org/repo/path@rev` addresses, tried in order |
| resource | `files` | A bundle: a list of `{path, sha256, size, urls}`; `path` is the file's name inside the variant's folder |

A **variant** is one item of `resources`. Its tags are `platform`, `type`, `backend` and `precision`; a tag the resource lacks is a wildcard, so a resource without tags runs anywhere. The variant's name joins its tags (`onnx-onnx-fp16`), or is `default`.

A single-file entry with two variants that differ in precision (the whole file is shipped in the demo library):

```json
--8<-- "barn/haybale-example/haybale_example/catalog/1x-BroadcastToStudio-Compact-onnx.json:24:45"
```

A bundle, whose variant is several files stored together (a sketch; `files` replaces `urls` and `sha256` on the resource). This block is a schematic example: the `"…"` placeholders stand for real values, so it is not valid JSON as written.

```json
{
    "resources": [
        {
            "platform": "onnx",
            "type": "onnx",
            "backend": "onnxruntime",
            "files": [
                {"path": "encoder.onnx", "sha256": "…", "size": 41000000, "urls": ["hf://org/repo/encoder.onnx"]},
                {"path": "decoder.onnx", "sha256": "…", "size": 22000000, "urls": ["hf://org/repo/decoder.onnx"]}
            ]
        }
    ]
}
```

Give every file a `sha256` where you can: a download is verified against it, and a file with a digest is found again wherever it moves. `hf://` urls land in the Hugging Face cache, never in the models folder ([ADR 0068](../adr/0068-the-hugging-face-cache-is-a-volume.md)).

## 3. Using a MODEL_REF port

Add the port in `init()`:

```python
MODEL_REF.as_inlet("model", widget_config={"properties": {"filter": {"scale": [4]}}})
```

Two options go in `properties`:

- **`filter`** maps a catalog field to its allowed values (`{"architecture": ["esrgan"], "scale": [4]}`). It narrows the picker across all libraries. It never refuses a pasted reference.
- **`prefer`** is an ordered list of tag sets (`[{"precision": "fp16"}, {}]`). The first set that matches a resource wins; `{}` matches anything.

For a preference that depends on settings (device, precision), define `model_preference(self, port_id)` on the node. It must be a pure function of settings and returns the same list shape. It wins over the port's `prefer`; haybale-models never imports torch.

The worker uses the best match **on this machine**. If a higher preference exists but is not downloaded, the node gets a warning and the needs-list offers it.

### 3.1 Loading and releasing

**Workers never download.** The resolver and every worker are offline; a missing model raises `ModelMissing`, and the user fetches it in the Models editor.

A node acquires its model lazily, in the worker, and releases it when the run ends. The pool is keyed by the resolved file plus a variant key you choose (device and dtype, say):

```python
--8<-- "barn/haybale-models/haybale_models/consumer.py:95:112"
```

Call `release_node(self)` from `on_shutdown`, and again from `on_teardown` as a backstop. The pool frees a model at once when its last holder releases it. There is no eviction: a model stays loaded while any running node holds it.

## 4. Where files live

The models volume (`haybale-models:volume:models`) holds catalog downloads as `<library-id>/<entry-stem>/<file>` (bundles: `…/<variant>/<file>`) and pasted urls as `downloads/<host>/<file>`. Files you drop into it are indexed on the next scan. The Hugging Face cache is a second volume, listed read-only. Both locations are the user's to move in the Volumes editor ([ADR 0065](../adr/0065-named-volumes-instead-of-absolute-paths.md)).

Download and remove need ADMIN access; browsing is VIEW; pinning a digest goes through the edit route.
