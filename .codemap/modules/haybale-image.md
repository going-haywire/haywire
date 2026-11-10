# Module: haybale-image

> Image types, IO, viewers and nodes for Haywire: the image value and port types, file and buffer I/O, image settings, an image viewer panel, and the nodes that load, inspect and emit images. Vision and ML libraries build on it.

**Path:** `barn/haybale-image/haybale_image/`
**Language:** Python 3.10+
**Owner:** Haywire core team (bundled plugin)
**Tree hash:** `ccfaa1943ac6c3c9b11403cf193f2c51948a6075`
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

`haybale-image` defines what an image is in a Haywire graph. It provides the image value (`value/`), its port types (`types/`) and adapters, file and buffer I/O (`io/`), an image viewer (`viewer/`, `panels/`), image settings (`settings/`), widgets for image nodes, and the nodes that load, describe and emit images (including an image emitter and image event pair, parallel to audio). It is shared by vision and ML libraries such as [haybale-models](haybale-models.md). Removing it breaks image nodes across the barn.

## 2. Folder Architecture

```
haybale_image/
├── __init__.py       ← `Library` subclass
├── value/            ← image value type
├── types/            ← image port/type definitions
├── adapters/         ← type adapters for image ports
├── io/               ← file and buffer I/O for images
├── helpers.py        ← shared image helpers
├── nodes/            ← load, info, emit and event nodes (e.g. Image Info, Image Event)
├── viewer/           ← image viewer rendering
├── panels/           ← image viewer and inspector panels
├── settings/         ← image settings
├── widgets/          ← widgets for image nodes
└── haybale.toml      ← library manifest
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` and `register_components()`.
- `value/` and `types/` — the image value and port contract that nodes and panels share.

### On-demand

- `io/` — file and buffer loading. Read before changing how images enter the graph.
- `viewer/` and `panels/` — rendering. Follow [haywire-core-ui](haywire-core-ui.md) panel rules.
- `nodes/` — one file per node.
- `settings/` — image settings groups.

## 4. Rules & Boundaries

- Image values flow through the value and type modules, not through ad hoc dicts in nodes.
- Viewer rendering belongs in `viewer/` and `panels/`, not in nodes.
- Register components through `Library.register_components()`.
- Follow `docs/reference/design-guide.md` for viewer UI.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Image value | `value/` | Shared by nodes and viewers |
| Image types | `types/` | Port contract |
| Image I/O | `io/` | Load and save |
| Library manifest | `haybale.toml` | Read from disk at runtime |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md).
- [haybale-core](haybale-core.md) — shared types and widgets.

### Depended on by

- [haybale-models](haybale-models.md) — model inputs and outputs use image types. ⚠️ TODO: confirm with a grep for `haybale_image` imports.
- [tests](tests.md) — `tests/image/`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | `haywire.libraries` entry point |
| Image viewer | `viewer/` | Rendering |
