# haybale-models as the one place for model files — design

Status: settled by inquisition 2026-11-04 (MS-Q1–Q21); MS1 done 2026-11-04, MS2 done 2026-11-05, MS3 and MS3b done 2026-11-05, MS4, MS5 and MS7 done 2026-11-06 (merged to local master; haybale-visiongraph `feat/ms7-haybale-models` unmerged).
Builds on: S6 (haybale-models, [2026-10-31-s6-haybale-models.md](2026-10-31-s6-haybale-models.md)),
ADR 0065 (named volumes), ADR 0067 (models identified by digest), ADR 0068 (the Hugging Face cache is a volume),
[model-catalogs guide](../../guides/model-catalogs.md).

---

## 1. Charter

haybale-models is the one place where the model **files** a Haywire installation uses are described, found,
fetched, verified, listed and removed — for every kind of model Python can run (image restoration,
diffusion, image-to-3D, detection, LLM weights…).

**It does**
- describe models in **catalog entries** shipped by libraries;
- know where model files come from and where they live: **model sources** and their **volumes**;
- find files offline, fetch them with progress and cancel, verify them by digest or commit;
- show status, needs and licences in the Models editor, and remove what it fetched.

**It never**
- loads or runs a model (the consuming library does: ADR 0071);
- installs code a model needs (git repos, `trust_remote_code`, pip extras: the marketplace and the library do);
- manages what models *produce* (splat scenes, meshes, images: volumes and paths do) (MS-Q1);
- adds a heavy dependency (torch, ultralytics…) to itself.

**Vocabulary note.** "Consumer" keeps its existing meaning (`haybale_models.consumer`): the node or library
that *uses* a model. haybale-models owns the model sources; a library names addresses, never sources.

---

## 2. Decisions

| # | Decision |
|---|---|
| MS-Q1 | haybale-models manages **model files only** (charter above). |
| MS-Q2 | A file in a framework's cache is named by an **address prefix per cache** (`torchhub://`, `ultralytics://`…), like `hf://`. |
| MS-Q3, Q17 | The thing behind a prefix is a **model source** (parts in §3.1). **Reversed 2026-11-04** (user decision): libraries do not provide sources; the set is the fixed built-ins of haybale-models, new locations become built-ins by need, and a library with an unusual location manages its own files. Cross-library registration was lost on a haybale-models reload and the need is rare (MS-Q18). ~~A library may provide its own in `AppState.on_enable`, registered per library (keyed by library name; a library's sources are unique by prefix), released on disable, replaced on hot reload. No component kind, no global key: a source is library-owned machinery, like a volume.~~ |
| MS-Q4 | An unknown prefix shows "source unavailable: `<prefix>://` not provided" (never hidden). **Library part reversed 2026-11-04** (no library-provided sources, so no library-first lookup; a pasted reference and a catalog entry resolve alike). ~~An entry resolves through **its own library's sources first**, then haybale-models' built-ins; a **pasted** reference resolves through the built-ins only.~~ |
| MS-Q5 | **Whole-repo Hugging Face address** `hf://org/repo@<commit>` with optional `include` patterns, fetched with `snapshot_download`; the commit identifies the bundle. A catalog entry must give a commit, never a branch. Per-file bundles stay. |
| MS-Q6 | Fetch runs **in-process** with progress and cancel when the source supports it; a source that cannot cancel declares it and fetches in a **subprocess** (cancel = kill, progress = size watcher on the target). Built-in sources are all in-process; the subprocess route is specified, built only when a source needs it. **Amended 2026-11-05 (MS3b):** `hf` cannot stop mid-transfer and declares `cancels_running = False`; until MS6 a running `hf` download offers no Cancel (ADR 0074). |
| MS-Q7 | Entry field **`recommended: true`** (optional, per catalog entry). **Amended 2026-11-06 (user decision, MS5):** it is a filter in the Choose a model picker only: a `Recommended` chip, off by default, shown only when the entries fitting the port hold both flagged and unflagged ones. Nothing sorts by it, and the Models editor ignores it. **Tags** (OpenModelDB's) are one of the editor's filter fields. |
| MS-Q8 | **Commercial use** is the author's statement: entry field **`commercial`**, default false, reading `non-commercial` unless set. `license` stays free text and nothing interprets it. Advice, never a gate. **Reversed 2026-11-06 (user decision, MS5):** ~~combines the entry's `license` with architecture licences the library declares~~; spandrel keeps `LICENSES` for its own setting. |
| MS-Q9 | File hosts (Google Drive, Mega, OneDrive…): **assisted download** only; host-specific automation later, one host at a time, each justified by numbers. **Sharpened 2026-11-05 (MS4):** nothing recognises a file host. Assisted download is offered after any failed download of a file with a known place. |
| MS-Q10 | The assisted download receives the file through a **drop zone** (browser upload), streamed as the raw request body into `<name>.part` in the target volume. The server watches no folder outside the project. |
| MS-Q11 | **Reversed 2026-11-05 (user decision, MS4):** no "Pick file on this machine". The upload is fast and uses no temp folder (§5 item 1), so a server-side dialog would save only a moment's second copy, at the price of per-OS code and a server moving user files. ~~When the browser runs on the server's machine, also "Pick file on this machine": a server-side file dialog; the file is checked and moved into the target volume.~~ |
| MS-Q12 | **Reversed 2026-11-05 (user decision, MS3b):** the catalog entry entitles Remove of its files from any volume that holds them (Models volume, framework caches, Hugging Face cache), whoever fetched them, because the same row offers to download them again. ADR 0074 supersedes ADR 0073. ~~In framework caches, Remove exists only on a catalog entry, for files haybale-models fetched for it (amends ADR 0068's "read-only").~~ |
| MS-Q13 | The Models volume stays fully removable (any file), as today. |
| MS-Q14 | Nodes pass the **resolved path** (never a name) to the framework, so it never downloads by itself. A documented **recommendation**, not enforced. |
| MS-Q15 | Editor filters: library, purpose, tags, architecture, scale, commercial use, status; each added on demand. **Reversed 2026-11-06 (user decision, MS5):** ~~plus facets a library declares~~: the entry's own fields cover every facet asked for. |
| MS-Q16 | One spec, charter first, slices in the order of §4. |
| MS-Q18, Q20 | **haybale-models ships a broad set of built-in sources** — `https`, `hf`, `torchhub`, then frameworks by real need (`ultralytics`, `insightface`, `rembg`, `keras`, `facexlib`…). A built-in framework source knows **location and layout only**; download URLs come from the entries. Library-provided sources (MS-Q17) were dropped 2026-11-04. |
| MS-Q21 | A resource gets an optional **`cache`** field (`"cache": "ultralytics://yolo11n.pt"`): where the file belongs. **`urls`** keeps meaning "where to download from", unchanged and OpenModelDB-compatible. Without `cache`, downloads land in the Models volume as today. For `hf://`, the address is both location and download, so it stays in `urls`. |

---

## 3. Mechanisms

### 3.1 A model source

| Part | Meaning | `hf` (built in) | `ultralytics` (built in, by need) |
|---|---|---|---|
| name | the address prefix | `hf` | `ultralytics` |
| label | planned: shown in the editor ("Source: …"); not shown yet | Hugging Face | Ultralytics |
| volume | where its files live, with a **suggested location** (the framework's default, honouring its env var) | `haybale-models:volume:hf-cache` | `haybale-models:volume:ultralytics` |
| parse | check and split an address | `org/repo/path@rev`, `org/repo@commit` | `yolo11n.pt` |
| find | offline: the paths of a file or bundle, or none — **never hashes a whole cache** | `cached_path` / snapshot folder | file exists under its name |
| identify | what proves it is right | blob sha256, or commit | sha256 checked once after our own fetch; name + size to find |
| fetch | get it here, progress + cancel (or "needs subprocess") | `huggingface_hub` | HTTPS from the entry's `urls` into the cache |
| remove | delete what haybale-models fetched for an entry | `delete_revisions` | delete the file |

Rules:
- A built-in source never adds a heavy dependency to haybale-models: folders and HTTP. A framework that needs its API
  to locate files is managed by the library that depends on it, not by a source.
- `https` (Models volume) and `hf` (Hugging Face cache) are today's `download.py` / `hf.py` behind this shape.

### 3.2 Cache volumes on first need

A source suggests its volume (key, label, description, suggested location). haybale-models calls
`ensure_volume(...)`:
- when **find** sees the suggested location already exists (another tool filled it: manage it at once), or
- on the **first fetch** for that source; the fetch creates the default folder (`ensure_volume` never creates folders).

No volume appears for a framework this machine never used. Cache volumes are haybale-models' own: they follow
S1b (not deletable, reset to the suggested location).

### 3.3 Resolution order

For a catalog resource: digest in the Models volume → the resource's `cache` (its source's find) → its `urls`'
sources' find (today's `hf://` lookup) → unpinned source URI. A source is looked up by the address prefix alone.

### 3.4 Records of what was fetched

haybale-models records each file it fetched into a framework cache, with the catalog entry it was fetched for, in its per-library storage (`library_storage_dir`). The records carry known digests and back the guard against overwriting a file nobody recorded. Remove does not need one: the catalog entry entitles it (ADR 0074).

### 3.5 Assisted download journey

1. A download fails on every address. Its row (Catalog, Needed, Downloads) offers **Download in browser** when the
   file has a place: a digest, a `cache` target, or an address the models index answers for. Whole-repo jobs and
   `hf://` files without a digest get no offer: nothing would find the stored file.
2. The dialog shows one slot per failed file: name, size, digest (or `No digest in the catalog: this file can't be
   verified.`), the last error, one link per address that has a web page (`ModelSource.page_url`), and a drop zone.
   Nothing opens by itself.
3. The user downloads the file and drops it on the slot. The browser posts it as the raw body to a route for that
   slot (an unguessable address, the admin tier re-checked on each post). It runs as a job (`begin_receive`, outside
   the parallel limit), writing `<name>.part` in the target volume and hashing as it streams.
4. A wrong `Content-Length` is refused before the body is read; more bytes than expected stop at that write; a wrong
   digest is refused at the end, with what was expected. A refused slot takes another file. Otherwise the file is
   stored like a fetched one, under its uploaded name where the target is not fixed. A different file already at that
   path is kept: the new one gets `-<sha8>`.
5. Closing the dialog (with a confirmation while one is running), closing the tab or losing the connection stops the
   upload: `.part` is deleted and the job ends `cancelled`.

Farmhand: a failed job that qualifies reports `assisted: true` and `page_urls`; agents have no upload path.

### 3.6 Editor filters and recommendation

- A `filter_alt` icon in the `Models` header opens the filter section (Show row, search, fields), which starts closed.
  Closing switches Show, search and fields off, so a closed section always means the full list; reopening brings them
  back (user decision 2026-11-06). They reset when the editor reopens.
- Its **+** button lists the fields: Library, Purpose, Tags, Architecture, Scale, Commercial use (`commercial` /
  `non-commercial`), Status (`on this machine`, `needed`: an open graph misses it, `available`: not on this machine; a
  row can be both `needed` and `available`). Choosing one adds a row: a multi-select with chips and type-to-find, and
  an × that removes it. Every field works alike, however many values it has, none included. OR within a field, AND
  between fields. They narrow the Catalog section only. Status is per row, the rest per entry.
- Search, in the editor and the picker, matches word by word in any order, and also looks at scale, licence and commercial use (`commercial` does not match `non-commercial`).
- A catalog row reads `<licence> · non-commercial` unless its entry sets `commercial`.
- The picker's port `filter` keeps working, and can use `recommended` and `commercial` as well.

---

## 4. Build order

| # | slice | needs | status |
|---|---|---|---|
| MS1 | Model-source shape; `https` and `hf` moved behind it; built-in sources only (`SourceSet` looks up by prefix; "source unavailable" for a prefix no built-in serves) — **gate: today's download and HF tests pass unchanged** | — | done 2026-11-04 (c7155be8c, de9c1c374, 73daffb47, 90eaf491d, 50147c67b, bf976cbee, 804e4ae78, b236119d1, a360cf83c; ff-merged into `feat/s8-noncommercial`, head a360cf83c); deviations and follow-ups below |
| MS2 | `cache` field (MS-Q21); built-in `torchhub` + first framework sources by need; cache volumes on first need; fetch records + Remove from framework caches | MS1 | done 2026-11-05 (64f88c841, 494780246, d2b115b67, eb086ce85, 8ea6f4fb3, 8bff975a3, 1fe740d01, aa1c53c4c, 70ca0a0ae, 36a667263, 85976928d, 8c1fc20f1, 4de5a4f71, d412d91da, 2a5eae9f8; ff-merged into `feat/s8-noncommercial`); deviations and follow-ups below |
| MS3 | Whole-repo `hf://org/repo@<commit>` + `include` | MS1 | done 2026-11-05 (3d8bfc0a4, 24b61e303, 974750059, 1335a90cb, c46e0200d, c687b33c1, 4e5226544; ff-merged into `feat/s8-noncommercial`); deviations below |
| MS3b | Remove from any cache by catalog entitlement; Cancel only where a download stops | MS3 | done 2026-11-05 (3690a67, c80fb24 + docs; ff-merged into `feat/s8-noncommercial`); ADR 0074 |
| MS4 | Assisted download: Download in browser dialog, drop zone | MS1 | done 2026-11-06, live-checked (offer, wrong file refused, right file stored); merged to local master; deviations below |
| MS5 | Editor filter section, `commercial`; picker `Recommended` chip | — | done 2026-11-06, live-checked; merged to local master |

| MS7 | haybale-visiongraph adopts haybale-models: catalog entries `hf://cansik/visiongraph/<file>` (OpenVINO `.xml`+`.bin` as bundles, sha256 from the HF repo), model ports, nodes pass `LocalAsset(resolved)` — work in the haybale-visiongraph repo; needs no new source | MS1 | done 2026-11-06, live-checked; haywire part merged to local master, haybale-visiongraph `feat/ms7-haybale-models` unmerged |

MS6 (only when a source needs it): subprocess fetch with the size watcher (MS-Q6).

**MS2 scope (user decision 2026-11-04).** No library needs a framework cache yet; MS2 pre-builds the common approach
anyway: one generic `FolderSource` (a folder of files named by file name, located by env vars with a home default),
`TorchHubSource` on top of it (sha256 prefix in the file name), and the built-ins `torchhub`, `rembg`, `keras`,
`ultralytics`. `insightface` (zip packs to unpack) and `facexlib` (default folder inside site-packages) wait for need.
visiongraph needs no source: everything it downloads comes from one Hugging Face repo (MS7).

**Commits.** MS1–MS5 and MS7 were squashed into one commit and merged to master on 2026-11-06. The commit hashes in the rows above, and each slice's implementation plan, live on in the tag `haybale-models-ms1-ms7-full`.

**Status rule.** `open` → `planned` (slice plan written, linked) → `done` (implemented, verified, merged). The last
task of every slice plan updates this table with the merge commit and date, and notes deviations in §2/§3.

---

### MS1 deviations (2026-11-04)

- Library-provided sources were built and then dropped (user decision 2026-11-04): `register_sources`/`unregister_sources`, the per-library registry, the library argument of lookup and `library_of` are gone; the hot-reload limitation went with them. See ADR 0072.
- Tests' construction lines changed: `hf_cache=` became `sources=`. Two monkeypatch targets were retargeted because the code moved. No assertion changed.
- "Models volume folder does not exist" is now a per-address `SourceFailed`: the job error is prefixed with the address and the next mirror is tried.
- An address with a prefix other than `https`, `http`, `hf` (e.g. `ftp://`) now fails with "source unavailable"; before, it took the HTTP path.
- The offline lookup walks addresses in the order listed (§3.3); before, it tried `hf://` first.
- A pinned reference rejects a found file only when its digest is known and differs from the pin (known via `index.sha256_at` or a 64-hex HF blob name); an unknown digest is accepted.
- The editor's `_graph_uses` passes an https-only `SourceSet`, keeping today's `by_source` lookup.
- The model picker accepts `http://`; its hint text still reads `An address starts with hf:// or https://`.
- "Models volume unavailable" is now also per address: a broken models volume no longer fails a job before an `hf://` address is tried.
- Known follow-up: the `.part` file left by a failed mirror is no longer deleted when a later mirror has a different target path. Also, `fresh` is now set whenever an earlier address of the job exists, so a resumable `.part` is discarded even when the earlier address was skipped or was `hf://`; before, the discard happened only after an HTTP mirror had actually been tried.

### MS2 deviations (2026-11-05)

- The picker accepts every prefix of the download sources (`SourceSet.download_prefixes()`: `https`, `http`, `hf`), so `http://` stays accepted; the hint uses their primary prefixes (`primary_download_prefixes()`). Cache prefixes such as `torchhub://` are refused there.
- Ultralytics without `settings.json` or `weights_dir` suggests `<config dir>/weights`, not `<cwd>/weights`: a cwd-based location changes per launch; nodes pass resolved paths (MS-Q14).
- rembg location: `U2NET_HOME`, `REMBG_HOME`, the current home if it exists, else `~/.u2net` (covers released and main layouts).
- `locate()` never raises on `~user` or a missing home (`~` kept as a literal segment).
- The queue never overwrites an unrecorded file in a cache: at run time an existing file the pin accepts is done without fetch or record; one it does not accept fails with `a different file already exists at <path>`; a recorded file may be replaced. A cache file of unknown digest passes the pinned guard (find never hashes).
- An `hf://` url of a file with a `cache` fails that address ("cannot fill a cache") and the next mirror is tried. Fetching into a cache is declared by `ModelSource.fills_target` (true only for `HttpsSource`), not by a class check.
- A failing `FetchRecords.add` is logged; the job stays done.
- `FetchRecords` keeps one record per (volume, relative): Remove belongs to the entry that fetched, but the confirmation names every catalog entry whose file resolves to the path. Records notify listeners (`ModelsChanged`, watcher).
- `SourceSet.holding` picks the deepest matching root, so a cache nested in the Models volume reads as a cache and gets no Models Remove.
- One existing assertion changed: `test_a_file_outside_both_volumes_is_refused` matches `is in no model volume` (more than two volumes now).
- A `cache` address with `:` or reaching outside its folder is refused (`target()` is confined to the root).
- Out of MS2: insightface, facexlib, visiongraph (MS7), whole-repo `hf://` (MS3), subprocess fetch (MS6).
- Final review: §3.1 "name + size" is implemented. A file found by address (every source, and the queue's run-time guard) is refused when its known size (pin, `ModelFile.size` or resource size) differs from `stat().st_size`; a failing `stat` refuses it and is logged. A file the model index has hashed is judged by its digest alone.
- Final review: `FolderSource.prepare_root()` creates the folder only when the volume is at its suggested location; a volume moved to a missing folder fails the job with `<label> cache volume folder does not exist: <path>`, and nothing is created.
- Final review: `FetchRecord` keeps `size` (absent in older files: unknown, still counts). A record whose size differs from the file's is stale: no Remove, and the overwrite guard treats the file as unrecorded. A current record's `sha256` is the known digest in `accepts()` (cache sources get the records through `builtin_sources(records=...)`), which ends the torchhub refetch loop for a fetched file whose name prefix contradicts the pin.
- Final review: a catalog row whose files lie partly in a cache and partly in the Models volume gets Remove (admin) when every Models file is indexed and every cache file is recorded for the entry; Remove deletes both parts (cache path, then the Models path with `index.remove`). A failing save in `FetchRecords.remove` is logged and listeners still fire.

### MS3 deviations (2026-11-05)

- Folder addresses are a `ModelSource` capability (`names_folder`, `find_folder`), not hf-specific code in the resolver or queue.
- `huggingface_hub>=2.4` floor: cached tree listing and `IncompleteSnapshotError`.
- huggingface_hub 2.4 does not raise when `include` matches nothing (it warns and returns); haybale-models checks for a matching file after the download and fails the job with `no file of … matches include […]`.
- The picker refuses whole-repo addresses ("A whole-repo address belongs in a catalog entry."); whole-repo is catalog-only.
- A resource's whole-repo urls are all tried in order; non-folder addresses in such a resource are skipped ("not a folder address").
- Resolved key is `path:<folder>|<include,…>`; two entries with the same `repo@commit` but different `include` are separate jobs and resolve separately.
- A snapshot counts as present only with huggingface_hub's cached tree listing for the commit; a listing-less snapshot (per-file downloads, other tools) is fetched again — cached files are reused.

### MS7 deviations (2026-11-06)

- New widget option `catalog_only`: a node that needs what the entry says about a model offers catalog entries only.
- A loaded node's ports come from its saved file, so `post_init` replaces a stale `model` or `selection.model` string port with the new empty one. No value is migrated.
- `@library(dependencies=...)` no longer exists: `haybale_models` goes in `linked_libraries` of `haybale.toml`, for hot-reload scope tracking, and in `pyproject.toml`.
- Visiongraph's dependency floors stay at `>=0.3.0` until the first haywire release carrying MS4, MS5 and MS7: they cannot be raised before it, because a floor above the local 0.3.0 breaks local resolution. **Raise them when releasing, and release haywire first.**
- Only `graphs/webcam.haywire` has estimator nodes; the plan's other two graphs needed no change.
- Found in the live check: `huggingface_hub` 2.4's cache-wide shared store (snapshot → `models--x/blobs/<sha256>` → `hub/blobs/<xx>/<xet hash>`) made every pinned `hf://` file read as a digest mismatch, and Remove leave its payload behind. The digest now comes from the first link (`blob_name`), and Remove sweeps the shared file through the Hub's own manifest, keeping it while another repo links to it.
- Found in the live check: removing a cache file with no fetch record told nobody, as only the index, queue and records signal, so a node using it stayed unaware (Models-volume files, such as Spandrel's, go through the index). `ModelsState.files_changed` now reports it.
- A loaded estimator skips `resolve_port`; with no estimator it runs each frame (offline, cheap), so a fetched file is picked up. A failed load is retried after a change of model or build setting, a stop and start, or its file going away and coming back.

### MS5 deviations (2026-11-06)

- `entry_facts` takes no resource: status arrives as `on_machine` and `needed`.
- `entry_description` also carries the `non-commercial` label, so the picker's and editor's hover tips say it.
- User decision 2026-11-06, after the final review: filter fields are multi-selects added by a + button, not loose chips, and every field works alike (decision 3's more-than-one-value rule reversed). `hui.filter_chip` (in the design guide) stays for the picker's `Recommended`. The field area is capped with its own scroll; the row's `non-commercial` is its own element so a long summary cannot cut it off.

### MS4 deviations (2026-11-05)

- Pick file dropped (MS-Q11); §3.5 rewritten; no host recognition (MS-Q9).
- `assistable` needs a digest, a `cache` target or an index-answered address. A declared bundle path alone does not qualify: a digest-less `hf://` bundle file would be stored where nothing finds it.
- `-<sha8>` keep-apart applies to any non-cache, non-bundle target, pinned or not.
- `mount_upload_route` gained `on_refused`, so a post refused before a job exists reaches the slot's status line.
- Page-gone-mid-upload is pinned by the route's ASGI disconnect test, not a browser test (loopback finishes first).
- Added after the final review: a connection silent for 60 s ends the upload `failed` (a connection dying without a close raises nothing), and Cancel stops a silent connection; a missing Models volume folder refuses the upload, as a download does.
- User decision 2026-11-06: a failed job's error reads `<reason> (<address>)`, so a cut-off row still shows why. Expected download failures stay on the row; only unexpected exceptions in the queue or upload route reach the error ledger, through `report_failure`. Expected ones are raised as `Refusal`.

### MS1 follow-ups (deferred minor review findings, 2026-11-04)

None blocks a later slice; pick up when touching the code. Findings made obsolete by dropping library-provided
sources, or fixed before merge, are left out.

Code

1. `.part` handling across mirrors — see the last deviation above (litter at another target path; resume loss after a skipped or `hf://` address). Fix: set `fresh` only when an earlier address reached the same source's `fetch`.
2. `SourceSet.unavailable()` returns `None` for addresses without `://`, which reads as "available"; unspecified and untested.
3. `SourceSet` does not check that `prefixes` is a tuple: a `str` splits into single characters.
4. `HfSource.root_problem()` falls back to the placeholder text "location unknown" (`sources/hf.py`).
5. `HttpsSource(root=...)` override is never used by `builtin_sources` (kept per plan; drop if MS2 has no use).
6. `_CHUNK` is defined twice (`sources/https.py`, `sources/hf.py`).
7. `resolver._known_digest` repeats `_digest_of`'s `sha256_at` and HF-blob-name steps — extract one helper.
8. `resolver.addresses_of` repeats `locate_resource`'s per-file URL fallback expression — extract one helper.
9. `models_editor._graph_uses` builds `SourceSet([HttpsSource(...)])` once per ref inside the loop; hoist it and say why it is https-only.
10. `status.resource_status` tests `if unavailable:` while the editor tests `is None` — they disagree on an empty prefix (`"://w"`).
11. "source unavailable" outranks a running download in the status text, while Cancel is still drawn (plan-mandated ordering).
12. A bundle's availability is judged over all its files' addresses: one file served, another not → Download is offered, then the unserved file's job fails.

Tests

13. `test_hf_volume_problem_falls_through_to_https` does not assert that the `hf://` address was tried and skipped.
14. No tests for: "source unavailable" on needed rows (the picker accepting `http://` is tested since MS2); the Farmhand status path with an unserved prefix; `ModelSource.root()`/`root_problem()` on a `VolumeError`.
15. `test_pinned_ref_rejects_a_found_file_with_another_digest` lacks type annotations.

Docs

16. Glossary: the **Consumer** *(models)* row sits inside the file-reference group; `<library-id>` wording in model-catalogs guide §4 and the glossary's catalog-key rows predates MS1 (it is the distribution name).

### MS2 follow-ups (deferred minor review findings, 2026-11-05)

Numbered on from the MS1 list. None blocks a later slice; findings fixed before merge are left out.

Code

17. `FolderSource.relative()`: the `""` part check is dead (`PurePosixPath` already collapses `a//b`).
18. `TorchHubSource.matches`: the name's hash prefix has no minimum length (`model-1.0.pth` → prefix `1`); a record's digest now outweighs it, but an unrecorded file can still be judged by one hex digit.
19. `HttpsSource.fetch` with a `target`: its "folder does not exist" / "outside" errors still say "models volume" when the root is a cache volume.
20. `hf.py`'s blob-name digest check repeats the resolver's 64-hex check and uses `isalnum()` (accepts non-hex).
21. `FetchRecords` writes through the fixed temp name `fetched.json.tmp`; two studio processes sharing `~/.haywire/db` would clash and lose each other's updates.
22. `find_accepted` calls `accepts()` / `source.matches()` outside its `try`: a raising `matches` would escape `_plan` (today's sources are pure).
23. The queue's early return for an already-present cache file skips the cancel check and the write claim (harmless: nothing is written).
24. An unpinned file the index knows still gets the size check (the ruling was "digest alone"); matters only if a catalog's `size` changes after the download.
25. A mixed-bundle Remove is not atomic: with the Models volume unavailable, the cache part is deleted and the Models part skipped silently.
26. `resolver.place_of` reads `local` for a found file that no source's volume holds (status text wrong; Remove stays safe).
27. `volume_path_of(path)` without `sources` has no caller left; `SourceSet.holding`'s docstring overstates the path order.
28. `SourceSet.primary_download_prefixes` repeats `primary_prefixes`' expression — one helper.
29. `_cache_files` runs per catalog row per draw (`holding` + a linear `records.at` scan); the cache Remove confirmation is one long line.
30. Import order: `download.py`, `store/records.py`.
31. Older ultralytics 8.x may read `YOLO_CONFIG_DIR` without the `/Ultralytics` suffix (unverified); a relative `weights_dir` resolves against the cwd, as ultralytics does.
32. `CatalogRegistry`'s class docstring does not list the malformed-`cache` refusal; the catalog accepts degenerate `x://` (folder sources refuse it later).

Tests

33. No cancel / digest-mismatch test for a fetch with a `target` (shared code path with the tested one).
34. `test_cache_source_that_raises_does_not_break_enqueue` asserts `state in ("done", "failed")` — should assert `"done"`; no run-time test for an unrecorded, pinned, unknown-digest cache file.
35. The editor and download test harnesses don't pass `records=` to `builtin_sources`; the record-digest path is tested only at resolver level.
36. `test_records.py` hygiene: an unexplained `mkdir`, a hand-rolled poll loop, `queue.stop()` outside `finally`.
37. rembg's `XDG_DATA_HOME` legacy and current-home branches are untested, and `rembg_dir` reads awkwardly; `test_ultralytics_without_a_weights_key_uses_its_default` asserts the Haywire fallback, not ultralytics' default (rename).
38. The "record for another entry" editor test does not pin which row carries Remove; the `http://` picker test's negative assertion is weak; the catalog refusal test imports private `_parse_resource`.
39. Resolve Model's new tests are `integration`-marked and had no recorded RED run (valid by reading).

Docs

40. §5 items 3–4 cite approximate upstream line numbers; keep the function names, drop the numbers.

### MS3 follow-ups (deferred minor review findings, 2026-11-05)

Numbered on from the MS2 list. None blocks a later slice.

Code

41. ~~Live check owed: cancel during a Xet-backed snapshot.~~ Checked 2026-11-05: the raise was swallowed and printed as an uncaught error; the snapshot downloaded in full. Resolved by MS3b (no Cancel on a running `hf` job; the hook no longer raises); a real stop needs MS6.
42. `download_snapshot`'s progress total grows as each file starts (HF adds sizes per file), so the percent can jump back; `on_progress` is called outside the lock, so counts may arrive out of order.
43. HF's file-count bar prints to stderr under a TTY.
44. `snapshot_path` uses the private `huggingface_hub._tree_cache.read_tree_cache` (same call `snapshot_download` uses); a rename in a later huggingface_hub breaks it loudly in tests.
45. `resolver.find_folder_accepted` is public but not in `__all__` (make it private); `_folder_addresses` falls back to `files[0].urls`.
46. `folder_address` looks only at the first address while `_locate_folder` tries all; a resource `[https://…, hf://o/r@C]` counts as a file resource. Document "the whole-repo address goes first" or decide by any address.
47. `download.py`: `_Plan` is a 6-tuple and `_add` takes 8 positional parameters (a small dataclass would be safer); `folder_address` is computed in both `_plan` and `_download`.
48. Each catalog redraw runs `snapshot_download(local_files_only=True)` plus a file walk per whole-repo resource; watch with large diffusers repos.
49. The model card's "Here" line falls back to `resolved.path.name`, so a whole-repo row shows the 40-hex commit.
50. Models editor `entry_urls` applies a resource's `include` to its per-file urls too (harmless); `users_of` is O(rows × uses).

Tests

51. `test_snapshot_path_never_downloads` patches `huggingface_hub.hf_hub_download`, which `_snapshot_download` never calls by that name (target `huggingface_hub._snapshot_download.hf_hub_download`).
52. No positive `find_folder` / `HfSource.find(whole-repo)` asserts in `test_sources.py` (covered via resolver tests); no tests for whole-repo uses from open graphs, the picker refusing `@main`, `_name_of` of a whole-repo source.
53. `test_include_not_a_list_of_strings_is_refused` reuses one file for both bad values (the registry-level assert does not prove the `[1]` case alone); local imports in that test, in `test_needs.py` and `whole_sources`.
54. The fake `release.wait(3) and Path(...)` in the queue include tests returns `False` on timeout.

Docs

55. `snapshot_path` / `download_snapshot` docstrings lack `Example::` blocks (python-docs rule).
56. Glossary "Model source" row does not mention folder addresses; MS1 follow-up 1 says "see the last deviation above", which no longer points at the `.part` deviation.

### MS3b follow-ups (deferred minor review findings, 2026-11-05)

57. The editor tells cache volumes from the Models volume by `place != "local"` (a display string); `volume != MODELS_VOLUME` is sturdier.
58. A cancel landing between the address loop's cancel check and the `cancellable` flip lets an `hf` fetch run in full, then end `cancelled`; check `task.cancel` in the same locked block.
59. `HfSource.remove` alone does not check where the path resolves (a symlinked snapshot sub-folder); only the editor's `_cache_files` guards it, while ADR 0074 says "nothing outside the volume, through a link or otherwise".
60. The confirmation's "frees N" counts an HF blob another snapshot keeps, and a folder-cache link's target although only the link is deleted.
61. The glossary's **Model store** row and ADR 0068's front-matter description still say the HF cache is never deleted by haywire.
62. Two whole-repo entries of one commit with overlapping `include` share snapshot links: removing one deletes the overlap, the other then reads `not downloaded` (the confirmation names both). Kept: the link is each entry's file.

### MS4 follow-ups (deferred minor review findings, 2026-11-06)

63. `uploading 0 %` for a whole transfer when the size is unknown, the usual no-digest case: `UploadReceiver.write` reports the expected size only. The drop zone's own bar stays right; pass `Content-Length` as the total.
64. `safe_name` passes dotfiles and `*.part`: `index.add` records such a file, the next scan skips it and drops the record, so after a restart the file is on disk and the row reads `not downloaded`. On Windows, `a:b.pth` targets an NTFS alternate stream.
65. The same content uploaded under a second address replaces the record's `source`, so a no-digest file at the first address stops resolving. `HttpsSource` has the same weakness.
66. `UploadReceiver.abort` and `finish` are not synchronized: on `CancelledError` at server shutdown, `abort` can run while `finish` is in its thread, so the job goes cancelled, then done, and `end` runs twice. No file is lost.
67. A mirror that died mid-file leaves `<url-basename>.part`; an upload under another name succeeds and that partial stays. Delete it on success.
68. The assisted dialog's link label shows the address's first segment, so an `hf://` link reads as the org (`xinntao`), not `huggingface.co`.
69. Downloads section: on a non-catalog job each refused drop adds a failed row with its own offer, and the old `failed: …` row stays after success.

### MS5 follow-ups (deferred minor review findings, 2026-11-06)

70. `tags: [""]` offers a blank filter value and `[null]` one reading `None`, as does `purpose`, on hand-written files. Drop empties in `entry_facts`, and decide on `null` in `_str_list`.
71. Filter fields stay usable with Catalog hidden, with no visible effect.
72. A filter that hides a row with a running or failed job moves that job to a Downloads section that suddenly appears. It stays reachable, and fits "Catalog only".
73. The filters button is a hand-built `size=sm` button, 24 px beside Rescan's 19 px; `hui.icon_action` would match.
74. The `needed` status filter has no editor-level test, and a graph's file reference by sha or URL never marks a catalog row, so Needed can list a model no row matches.
75. `entry_licence_text` is missing from `describe.__all__`.
76. The picker's `Recommended` chip sits below the search, not beside it.
77. The `+` tooltip overlaps the first menu items until the pointer moves.
78. The `available` status also covers rows that cannot be downloaded (no source, failed); the word misleads there.

### MS7 follow-ups (deferred minor review and live-check findings, 2026-11-06)

79. A foreign entry on an estimator node redraws the card twice per frame: `resolve_port` clears the warning and the node sets it again. Needs a hand-edited graph. Check `MODELS` before `resolve_port`.
80. `hb_on_model_change` leaves `This node cannot run this model` on a stopped graph until the next frame; call `replace_warnings(KIND, [])` there.
81. A saved non-catalog reference with no file reads `Choose a model` alongside the `Model missing` warning, because the status tests `ref.catalog`; test `ref.is_empty`.
82. An old graph's wire to the replaced `model` port survives load and re-save as a broken edge, which the user deletes by hand; for `selection.model`, the new port also lands after `inference.min_score`. Optionally drop the edge in `hb_replace_stale_model_port`.
83. Visiongraph's compatibility text in `__init__.py` still says to re-enter `model` in the properties panel, and nothing tells a user this release empties their model. Reword it, and add a `CompatibilityWarning` at the next version bump.
84. The MS7 plan says the estimator's cache key is the resolved key; it is built as the catalog key. No effect while each entry has one resource.
85. Stale "dropdown" wording in `estimator_settings.py` and `base_estimator_node.py`, a history sentence in `hb_replace_stale_model_port`'s docstring, and reST plus "family node" in the nodes' displayed docstrings, which also say nothing about picking or fetching a model.
86. `SSDDetector` alone ignores its `weights` argument, so an `.xml` found apart from its `.bin` gives `Load error: Empty weights data`. The usual same-folder layout works.
87. Needed section: `hui.button` keeps `w-full` beside the row's `w-auto`, squeezing the graph name to nothing, so groups show no name (seen in the live check; user chose to leave it for now). Merging duplicates across graphs would be a design change of its own.
88. Spandrel's `uv.lock` still floors `huggingface-hub` at `>=1.0` while haybale-models needs `>=2.4`; any `uv` run there rewrites it.
89. Earlier Removes on the shared-store layout may have left payloads in the Hugging Face cache's `blobs/`. Remove does not sweep old leftovers.

## 5. Research items (resolve in the slice plans)

1. ~~NiceGUI `ui.upload` with multi-GB files.~~ Resolved in MS4: stock `ui.upload` does not buffer in memory, but passes the file through two temp files in the system temp folder (Starlette's spool, then NiceGUI's copy) and calls the handler only at the end, so MS4 posts the raw body (`send-raw`) to its own route, writing straight into the target volume. Measured on loopback, sha256 and disk write included: 4 GB by `curl` 930 MB/s; 2 GB through the real dialog, headless, Chromium 444 MB/s, Firefox 459 MB/s. Real Mega links answer `200 text/html`, refused by `HttpsSource` as an HTML page.
2. ~~`pooch` vs our own HTTPS fetcher: simpler or not (MS1).~~ Resolved in MS1: the existing fetcher moved behind `HttpsSource` unchanged (resume, claims, digest check already there); no new dependency.
3. ~~Current default cache locations and env vars of each framework in the first MS2 batch (MS2).~~ Resolved in MS2 (read on each framework's main branch, 2026-11-05; code in `sources/caches.py`):
   - torch hub: `torch/hub.py` `_get_torch_home` (l. 184-191: `$TORCH_HOME`, else `$XDG_CACHE_HOME/torch`, else `~/.cache/torch`), `get_dir` (l. 443: `/hub`), `load_state_dict_from_url` (l. 872-874: `/checkpoints`). `hub.set_dir()` is a runtime override no file or env shows.
   - rembg: `rembg/sessions/base.py` `rembg_home` (l. 162-169: `$U2NET_HOME` wins, else `$REMBG_HOME`, else `$XDG_DATA_HOME/rembg` or `~/.rembg`), `legacy_home` (l. 149-153: `$U2NET_HOME`, else `$XDG_DATA_HOME/.u2net` or `~/.u2net`), `model_dir` (l. 181-185: `<home>/models/<name>`), `resolve_existing` (l. 195-198: model dir first, then the flat legacy folder). Main moved the default off `~/.u2net`; released versions still use it. The source takes `$U2NET_HOME`, then `$REMBG_HOME`, then the current default home if it exists, else `~/.u2net`; addresses are paths below that folder.
   - keras: `keras/src/backend/config.py` (l. 403-409: `$KERAS_HOME`, else `~/.keras`; `/tmp/.keras` when home is not writable, not followed), `keras/src/applications/resnet.py` (l. 206-211: `cache_subdir="models"`). Source folder: `<keras home>/models`.
   - ultralytics: `ultralytics/utils/__init__.py` `get_user_config_dir` (`$YOLO_CONFIG_DIR/Ultralytics`, else `$XDG_CONFIG_HOME` or `~/.config`, `~/Library/Application Support`, `~/AppData/Roaming` + `/Ultralytics`), `SETTINGS_FILE = USER_CONFIG_DIR / "settings.json"` (JSON, `weights_dir` key). Its default `weights_dir` is `<git root or cwd>/weights`, a property of the framework process, not of the machine: without the file or key the source suggests `<config dir>/weights` (a Haywire choice, not Ultralytics' default: Ultralytics uses `<git root or cwd>/weights`, which changes with every launch of the studio).
4. ~~Identification without hashing per cache layout (torch hub hash prefix, HF blob names) (MS2).~~ Resolved in MS2: torch hub file names end in `-<sha256 prefix>.<ext>` (`torch/hub.py` `HASH_REGEX`), checked by `TorchHubSource.matches`; HF blob names are the sha256 (MS1); rembg, Keras and Ultralytics names carry no digest, so their files are identified by size and hash on first need only.

---

## 6. Non-goals

1. Loading or running models; installing model code (charter).
2. Managing model-produced assets (splats, meshes, images).
3. Watching folders outside the project, including `~/Downloads` (MS-Q10).
4. ~~Deleting files in shared caches that haybale-models did not fetch (MS-Q12).~~ Dropped 2026-11-05: a catalog entry entitles Remove of its own files in any cache (MS-Q12 reversed, ADR 0074).
5. Host-specific download automation (Google Drive, OneDrive…) until justified one at a time (MS-Q9).
6. Ollama's store, Civitai tokens, gated Hugging Face repos (tokens wait for the security document).
7. Subscribable catalog feeds / bulk OpenModelDB import (spandrel spec non-goal 5 stands).

---

## 7. Glossary and ADR candidates (land with the code, not before)

**Glossary**
- **Model source** — what haybale-models uses to find, fetch, identify and remove the files behind one kind of
  address (`hf://`, `torchhub://`…), with the volume they live in. Built into haybale-models, keyed by address prefix. Not to be confused with `HaywireLibrarySource` / `SignalSource`.
- **Cache volume** — a volume a model source suggests for its framework's cache; created on first need.
- **Whole-repo address** — `hf://org/repo@<commit>`: a bundle identified by its commit.
- **Assisted download** — fetching a file through the user's browser after automatic download failed, received by drop zone. Landed in the glossary with MS4.
- Note on **consumer**: unchanged meaning.

**ADRs**
- Model sources: built into haybale-models with location/layout only, URLs from entries, no library-provided sources (MS-Q3/Q17 reversed) (MS-Q20/Q21). **Landed as ADR 0072 (MS1)**; MS2 amends it for `cache` and framework sources.
- Amend ADR 0068: framework caches are read-only except files haybale-models fetched for a catalog entry (MS-Q12).

**Docs to update when slices land**
- [model-catalogs guide](../../guides/model-catalogs.md): `cache`, `recommended`, `commercial`, whole-repo `hf://`; §3.1 "Workers never download" gains MS-Q14's recommendation.
- Node canon: pass the resolved path to the framework (MS-Q14).
