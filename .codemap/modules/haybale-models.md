# Module: haybale-models

> Model references for Haywire: resolve a model to a file on this machine, a local model store and download pool, Hugging Face and other sources, a graph "needs" list of the models a graph uses, and the editor, panels and Farmhand tools that manage them.

**Path:** `barn/haybale-models/haybale_models/`
**Language:** Python 3.10+
**Owner:** Haywire core team (bundled plugin)
**Tree hash:** `1d0650db8cc3858b04766e0159878973bd4176dd`
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

`haybale-models` makes model files a first-class part of a graph. A graph declares which models it needs (`needs.py`). The library matches those needs against what is installed locally (`matcher.py`, `resolver.py`, `store/`), downloads what is missing (`download.py`, `pool.py`, `sources/`, `hf.py`), and reports status (`status.py`, `describe.py`). Nodes such as Resolve Model give a graph the file path, sha256 and size of a model. The library also provides the models editor, panels, widgets, Farmhand tools and an upload route for receiving models. Removing it breaks model-consuming graphs but not other libraries.

## 2. Folder Architecture

```
haybale_models/
├── __init__.py        ← `Library` subclass
├── keys.py            ← model keys and identity
├── needs.py           ← graph "needs" list: models a graph declares
├── matcher.py         ← matches needs to available models
├── resolver.py        ← resolves a need to a file on this machine
├── describe.py        ← model description
├── status.py          ← availability and download status
├── filters.py         ← source and model filters
├── consumer.py        ← consumes resolved models for nodes
├── receive.py, upload_route.py ← receiving model uploads
├── download.py        ← download implementation
├── pool.py            ← download pool
├── hf.py              ← Hugging Face access
├── sources/           ← remote model sources
├── store/             ← local model store
├── signals.py         ← model signals
├── types/, value/, widgets/ ← model port types, values and widgets
├── nodes/             ← nodes, incl. Resolve Model
├── editors/           ← models editor
├── panels/            ← model panels
├── states/             ← models state container
├── settings/          ← models settings
├── farmhands/         ← Farmhand tools for models
└── haybale.toml       ← library manifest
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` and `register_components()`.
- `keys.py`, `needs.py`, `resolver.py` — the identity and resolution contract every model node relies on.

### On-demand

- `download.py`, `pool.py`, `sources/`, `hf.py` — download and remote access. Read before changing fetch behavior.
- `store/` — the local store layout.
- `matcher.py`, `status.py` — when changing how needs are matched or reported.
- `upload_route.py`, `receive.py` — inbound model uploads.
- `editors/`, `panels/`, `states/` — models UI. Follow [haybale-studio](haybale-studio.md) and [haywire-core-ui](haywire-core-ui.md) panel rules.
- `farmhands/` — Farmhand tools.

## 4. Rules & Boundaries

- A model's identity is its key (`keys.py`). Do not derive identity from file names in nodes.
- Downloads go through `pool.py`, not directly from nodes.
- Graph needs are declared by the graph and matched here. Nodes must not re-resolve on their own.
- Register components through `Library.register_components()`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Model identity | `keys.py` | Key scheme |
| Graph needs | `needs.py` | Declared models per graph |
| Resolution | `resolver.py` | Need → local file |
| Download pool | `pool.py` | Fetch scheduling |
| Local store | `store/` | Installed model layout |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md).
- [haybale-core](haybale-core.md), [haybale-studio](haybale-studio.md), [haybale-graph-editor](haybale-graph-editor.md) — graph and studio surfaces.
- [haybale-image](haybale-image.md) — image types for model inputs and outputs.

### Depended on by

- [tests](tests.md) — `tests/models/`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | `haywire.libraries` entry point |
| Graph needs | `needs.py` | Declared models per graph |
| Resolve | `resolver.py` | Need to local file |
| Models editor | `editors/` | UI |
