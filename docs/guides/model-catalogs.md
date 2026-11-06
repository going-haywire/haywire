---
status: draft
doc_template: guide
scope: Shipping a model catalog from a library, and using a MODEL_REF port in a node — catalog file format, filter/prefer options, per-run pool holds
see-also:
  - ../adr/0067-models-are-identified-by-digest.md
  - ../adr/0068-the-hugging-face-cache-is-a-volume.md
  - ../adr/0072-model-sources.md
  - ../adr/0074-the-catalog-entry-entitles-remove.md
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

The entry's registry key is `<library-id>:catalog:<file stem>` (component kind `catalog`, registered by `CatalogRegistry`), such as `haybale-example:catalog:1x-BroadcastToStudio-Compact-onnx`. A stem starts with a letter or digit and continues with letters, digits, `_` or `-`.

### 2.1 File format

The format is OpenModelDB's: every OpenModelDB field keeps its name, so an OpenModelDB file can be dropped in verbatim. Our additions:

| Where | Field | Meaning |
| --- | --- | --- |
| entry | `purpose` | List of what the model is for, such as `["upscale"]`, `["restoration"]` |
| entry | `recommended` | Optional: `true` offers the model under the `Recommended` filter of the Choose a model picker; see [§2.3](#23-recommended-and-commercial) |
| entry | `commercial` | Optional: `true` states the model may be used commercially; left out, it reads `non-commercial`; see [§2.3](#23-recommended-and-commercial) |
| entry | `requires` | An object of requirements for the entry; kept on the entry as `entry.requires` (not part of `fields()`), not interpreted by haybale-models |
| resource | `backend` | Runtime that loads the file, such as `torch` |
| resource | `precision` | `fp32`, `fp16`, `bf16`... |
| resource | `urls` | `https://` and `hf://org/repo/path@rev` addresses, tried in order; `hf://org/repo@<commit>` names a whole repo ([§2.2](#22-whole-repo-hf-addresses)) |
| resource | `include` | Optional, with a whole-repo address: file patterns (`allow_patterns`, fnmatch) selecting part of the repo; empty means the whole repo |
| resource | `cache` | Optional: the cache volume address where the file belongs, such as `torchhub://resnet18-f37072fd.pth`; see [§5.3](#53-cache-sources) |
| resource | `files` | A bundle: a list of `{path, sha256, size, urls}`; `path` is the file's name inside the variant's folder |
| file | `cache` | Optional, per file of a bundle: the same address, for that file |

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

### 2.2 Whole-repo hf:// addresses

`hf://org/repo@<commit>` names a whole Hugging Face repository (a model folder such as a transformers or diffusers checkout). Rules:

- **A commit, not a branch.** The revision is 40 lower-case hex characters; a branch or tag is refused ("a whole-repo hf:// address needs a commit (40 hex characters), not a branch"). The commit is the identity: there is no digest.
- **`include`** (on the resource) narrows the download to matching files, such as `["*.json", "*.safetensors"]`. Two entries with the same `repo@commit` but different `include` are separate downloads and resolve separately.
- **It resolves to the folder.** The Resolve Model node and workers get the snapshot folder in the Hugging Face cache; status reads `HF cache`.
- **Offline completeness.** The snapshot counts as present only when Hugging Face's cached tree listing for the commit exists and says it is complete, and at least one file matches `include`. A snapshot without a listing (per-file downloads, other tools) is fetched again; cached files are reused. A fetch that leaves it incomplete fails with `incomplete snapshot of …`, and one where `include` matches nothing fails with `no file of … matches include […]`.
- **Remove** deletes the entry's snapshot files (those matching `include`), and each blob no other snapshot of the repo links to.
- **Catalog only.** The model picker refuses a whole-repo address.
- Other addresses in the same resource's `urls` that do not name a folder are skipped.

### 2.3 recommended and commercial

Both are `true` or left out; any other value counts as left out.

**`recommended`** is a filter in the Choose a model picker. Its `Recommended` chip appears when the entries fitting the port hold both flagged and unflagged ones, and starts off. It sorts nothing, and the Models editor ignores it.

**`commercial`** is your statement, as the author, that the model may be used commercially. Haywire does not read `license` to decide: it is free text. Left out, the Models editor and hover tips read `<licence> · non-commercial`, whatever the licence says, so setting the record straight is on you. Weigh the weights' licence and the architecture's.

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

**Pass the resolved path, never a name.** A node hands the path the resolver returned (for a file in a cache volume too) to its framework's loader. It never passes the framework a model name: the framework would look in its own cache, fetch behind haybale-models' back, and bypass the offline guarantee above.

A node acquires its model lazily, in the worker, and releases it when the run ends. The pool is keyed by the resolved file plus a variant key you choose (device and dtype, say):

```python
--8<-- "barn/haybale-models/haybale_models/consumer.py:95:112"
```

Call `release_node(self)` from `on_shutdown`, and again from `on_teardown` as a backstop. The pool frees a model at once when its last holder releases it. There is no eviction: a model stays loaded while any running node holds it.

A node that needs what a catalog entry says about a model, not just its file, sets `catalog_only: true` in `properties`: the picker then offers catalog entries only.

## 4. Where files live

The models volume (`haybale-models:volume:models`) holds catalog downloads as `<library-id>/<entry-stem>/<file>` (bundles: `…/<variant>/<file>`) and pasted urls as `downloads/<host>/<file>`. Files you drop into it are indexed on the next scan. The Hugging Face cache is a second volume, listed read-only. A framework's cache folder becomes a **cache volume** the first time a file is fetched into it ([§5.3](#53-cache-sources)). Each location is the user's to move in the Volumes editor ([ADR 0065](../adr/0065-named-volumes-instead-of-absolute-paths.md)).

Download and remove need ADMIN access; browsing is VIEW; pinning a digest goes through the edit route.

## 5. Model sources

A **model source** is what haybale-models uses to find and fetch the files behind one kind of address. An address starts with a prefix (`hf://org/repo/file`, `https://host/file`); the source that owns the prefix knows where such files live and how to get them. `label` is the source's human-readable name.

Built in:

| Prefix | Label | Files live in |
|---|---|---|
| `https`, `http` | Web | the models volume (`downloads/<host>/<file>` for pasted addresses) |
| `hf` | Hugging Face | the Hugging Face cache volume, read-only to lookups |

Cache sources (below) serve folders that other tools use too.

A source offers `find` (offline lookup of a file already present; it never hashes a whole cache) and `fetch` (get the file with progress, and cancel where the source declares `cancels_running`), `remove` (delete one of its files). A failed fetch raises `SourceFailed`, and the next address of the resource is tried.

### 5.1 Lookup

A source is found by the address prefix alone (case-insensitive); an address is tried in the order the resource lists it. A library that keeps its models somewhere else manages those files itself.

### 5.2 Source unavailable

An address whose prefix no source provides is never hidden. Its row shows `source unavailable: <prefix>:// not provided`, and the editor offers no Download for it. This also applies to prefixes such as `ftp://`.

### 5.3 Cache sources

A resource or a file of a bundle may carry `cache`, an address such as `torchhub://resnet18-f37072fd.pth`: where the file belongs, so the framework's own loader finds it. `urls` keeps meaning where to download from; `hf://` is never a `cache` (it stays in `urls`). When the catalog loads, it checks only the form of a `cache` address: one that is not an address like `torchhub://<file>` refuses the entry. A `cache` whose prefix no cache source serves shows as "source unavailable", and one that reaches outside its cache folder fails the fetch.

Four cache sources are built in. Each follows the framework's own environment variables and reads no framework code:

| Prefix | Label | Default folder | Environment |
|---|---|---|---|
| `torchhub` | Torch Hub | `~/.cache/torch/hub/checkpoints` | `TORCH_HOME` (else `XDG_CACHE_HOME/torch`) |
| `rembg` | rembg | `~/.rembg` when it exists, else `~/.u2net` | `U2NET_HOME`, then `REMBG_HOME`; `XDG_DATA_HOME` |
| `keras` | Keras | `~/.keras/models` | `KERAS_HOME` |
| `ultralytics` | Ultralytics | `weights_dir` of its `settings.json`, else `<config dir>/weights` | `YOLO_CONFIG_DIR`, `XDG_CONFIG_HOME` |

The Ultralytics config dir is `~/Library/Application Support/Ultralytics` on macOS, `~/AppData/Roaming/Ultralytics` on Windows, `~/.config/Ultralytics` elsewhere. Its fallback is a Haywire choice: Ultralytics' own default depends on the working directory.

- **Cache volumes appear on first need.** A volume `haybale-models:volume:<prefix>` (such as `haybale-models:volume:torchhub`) is created only when a fetch fills it, or when its suggested folder already exists. A framework never used on this machine adds nothing to the Volumes editor. The user may relocate a cache volume there; status, lookup and Remove follow.
- **Torch Hub names carry a digest.** A file name ends in `-<sha256 prefix>.<ext>`; a pinned reference never accepts a name whose prefix contradicts the pin. The other three sources identify a file by name only; `find` never hashes a cache.
- **Status.** A file in a cache volume reads `<label> cache`, for example `Torch Hub cache`. The Resolve Model node outputs its path.
- **The picker never accepts cache addresses.** A pasted `torchhub://...` is refused; only `https://`, `http://` and `hf://` are download addresses. Cache addresses come from catalog entries.
- **An unserved `cache` reads "source unavailable".** If no cache source serves the address's prefix, the row reads `source unavailable: <prefix>:// not provided` and offers no Download.
- **Fetching into a cache** goes through the entry's `https://` urls to the `cache` address. A fetch never overwrites a file in a cache that haybale-models did not fetch: an accepted existing file counts as present; a different one fails the job with `a different file already exists at <path>`.
- **The catalog entry entitles Remove.** A catalog row whose files are found offers Remove for exactly those files, in whichever volume holds them (Models volume, a cache volume, the Hugging Face cache), whoever fetched them: the same row can download them again. The confirmation names every catalog entry and graph that uses the files, and for a cache says: "This file is in the shared <label> cache; other tools may use it." Files no catalog entry resolves to are never touched. Remove needs ADMIN, like Fetch.
- **Fetch records.** Every file fetched into a cache volume is recorded in `fetched.json` (in the library's storage folder), keyed by volume and relative path. A record supplies the file's digest for pin checks; Remove deletes it.
- **Cancel only where a download can stop.** A queued download can always be cancelled; a running one only when its source stops mid-transfer (`https://`). A running Hugging Face download shows no Cancel and runs to the end.

See [ADR 0072](../adr/0072-model-sources.md) and [ADR 0074](../adr/0074-the-catalog-entry-entitles-remove.md).

### 5.4 Assisted download

Some hosts (Mega, Google Drive, OneDrive…) answer a script with a web page, not the file. Nothing recognises such a host: the download fails like any other, and the row then offers **Download in browser** (ADMIN). The dialog links each address of the file; the user gets it in their browser and drops it on the dialog. It is checked and stored like a downloaded file, under its uploaded name where the entry does not fix one.

The offer needs something that would find the stored file: a digest, a `cache` address, or an `https://` address. A whole-repo `hf://` address and an `hf://` file without a digest get no offer.

**Give every file a `sha256`.** With one, a wrong file is refused with what was expected. Without one, the dialog warns `No digest in the catalog: this file can't be verified.` and accepts what it gets. List a direct address first and a file host after it: the automatic download then succeeds without the user.

Agents see a failed job's `assisted` and `page_urls` in `models_list`, and send the user to the dialog; they have no upload path.
