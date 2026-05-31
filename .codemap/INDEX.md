# 🗺️ Codebase Map — Haywire

> Blueprint-inspired visual programming system (Python + NiceGUI) with a dual-flow node graph engine, reactive properties, and a plugin "barn" of haybale libraries.

| Generated | Last refreshed | Commit | Tool |
|-----------|----------------|--------|------|
| 2026-05-16 10:25 UTC | 2026-05-31 | a08a6931 | codebase-cartographer |

## Tech Stack

Python 3.10+, NiceGUI / Quasar / Vue 3, `injector` DI, `attrs`/`cattrs`, `duit[nicegui]`, uv workspace, pytest, ruff, mypy, mkdocs-material.

## Module Index

| Module | Purpose | Manifest |
|--------|---------|----------|
| haywire-core-engine | Graph engine, DI, nodes, edges, execution VM, settings, registries | [→ modules/haywire-core-engine.md](modules/haywire-core-engine.md) |
| haywire-core-ui | NiceGUI renderers: canvas, panels, editors, themes, skins, modals | [→ modules/haywire-core-ui.md](modules/haywire-core-ui.md) |
| haywire-studio | Studio CLI app (`haywire` entry point): app shell, config, init, share CLI, workspace | [→ modules/haywire-studio.md](modules/haywire-studio.md) |
| haybale-core | Built-in plugin library: core node types, adapters, widgets, themes | [→ modules/haybale-core.md](modules/haybale-core.md) |
| haybale-studio | Built-in studio plugin: editors, panels, file focus, state container | [→ modules/haybale-studio.md](modules/haybale-studio.md) |
| haybale-graph-editor | Visual graph editor plugin: GraphContainer protocol, GraphAppState registry, GraphEditor surface | [→ modules/haybale-graph-editor.md](modules/haybale-graph-editor.md) |
| haybale-haystack | File-centric multi-graph manager plugin; registers GraphEntry containers into GraphAppState | [→ modules/haybale-haystack.md](modules/haybale-haystack.md) |
| haybale-marketplace | Optional plugin: library installer + browser UI, `LibraryManager` service over `core/marketstall` | [→ modules/haybale-marketplace.md](modules/haybale-marketplace.md) |
| haybale-libs-other | Example / testing / TEST_A plugin libraries (visiongraph now gitignored) | [→ modules/haybale-libs-other.md](modules/haybale-libs-other.md) |
| tests | pytest suite (unit + integration) covering core, ui, studio, libraries | [→ modules/tests.md](modules/tests.md) |
| docs | mkdocs site: architecture, components, reference, guides | [→ modules/docs.md](modules/docs.md) |

## Cross-cutting Concerns

| Concern | Doc |
|---------|-----|
| Dual-flow execution model (control vs data pins) | [→ cross-cuts/dual-flow-model.md](cross-cuts/dual-flow-model.md) |
| Library plugin system (discovery, hot-reload, DI) | [→ cross-cuts/library-plugin-system.md](cross-cuts/library-plugin-system.md) |
| Signals & reactive props | [→ cross-cuts/signals-and-reactive.md](cross-cuts/signals-and-reactive.md) |

## How to Use This Map

1. **Start here.** Scan the Module Index above to find the area relevant to your task.
2. **Load the manifest.** Open only the module manifest you need.
3. **Follow the Always-load guidance** in that manifest to pull in the minimum source files required.
4. **Check cross-cuts** if your task spans modules (e.g., a feature touching both engine and a haybale library).
5. **Follow inter-module links** to trace dependencies.

## Quick Stats

- Total modules: 11 (added `haybale-marketplace`; `haybale-visiongraph` now gitignored)
- Estimated source files: ~330 Python files (+ Vue/JS frontends)
- Map coverage: ~95% of top-level dirs (excludes `playground/`, `site/`, `internals/`, `graphs/`, `haystacks/`, `scripts/`, `src/` ephemera)
