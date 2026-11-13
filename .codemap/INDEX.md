# 🗺️ Codebase Map — Haywire

> Blueprint-inspired visual programming system (Python + NiceGUI) with a dual-flow node graph engine, reactive settings, and a plugin "barn" of haybale libraries.

| Generated | Last refreshed | Commit | Tool |
|-----------|----------------|--------|------|
| 2026-05-16 10:25 UTC | 2026-11-10 | 9b104fd36 (feat/exec-audio) | codebase-cartographer |

## Tech Stack

Python 3.10+, NiceGUI / Quasar / Vue 3, `injector` DI, `attrs`/`cattrs`, `duit[nicegui]`, uv workspace, pytest, ruff, mypy, mkdocs-material.

## Module Index

| Module | Purpose | Manifest |
|--------|---------|----------|
| haywire-core-engine | Graph engine, DI, nodes, edges, execution VM, settings, library system, marketstall, volumes, undo | [→ modules/haywire-core-engine.md](modules/haywire-core-engine.md) |
| haywire-core-ui | NiceGUI renderers: app shell, canvas, panels, editors, modals, surfaces, themes, skins, widgets | [→ modules/haywire-core-ui.md](modules/haywire-core-ui.md) |
| haywire-studio | `haywire` CLI and `HaywireApp`: config, init, auth gate, network/TLS, Farmhand host, security, docs/rename/share CLIs | [→ modules/haywire-studio.md](modules/haywire-studio.md) |
| haybale-core | Built-in plugin: flow-control, file/path and widget nodes, emitters, compound (array/pooled) types, widget-node skin | [→ modules/haybale-core.md](modules/haybale-core.md) |
| haybale-studio | Built-in workbench plugin: file browser, code/errors/log/properties editors, roster, volumes, themes | [→ modules/haybale-studio.md](modules/haybale-studio.md) |
| haybale-graph-editor | Graph editor: `GraphContainer` protocol, `GraphAppState`, canvas, promote/new-node flows, surfaces, skins | [→ modules/haybale-graph-editor.md](modules/haybale-graph-editor.md) |
| haybale-haystack | Multi-graph workspace manager; `GraphEntry` containers, persistence, run settings, flow meter | [→ modules/haybale-haystack.md](modules/haybale-haystack.md) |
| haybale-marketplace | Optional plugin: library browser and install/uninstall/refresh flows over engine marketstall | [→ modules/haybale-marketplace.md](modules/haybale-marketplace.md) |
| haybale-audio | Audio blocks, `EXEC_AUDIO`, DSP (reblock, resample, mix), device/file I/O, audio nodes | [→ modules/haybale-audio.md](modules/haybale-audio.md) |
| haybale-image | Image value/types, file I/O, viewer panels, image nodes | [→ modules/haybale-image.md](modules/haybale-image.md) |
| haybale-models | Model needs, local store, downloads, Hugging Face sources, Resolve Model node | [→ modules/haybale-models.md](modules/haybale-models.md) |
| haybale-share | Share editor: project publish flow UI over the engine publishing pipeline | [→ modules/haybale-share.md](modules/haybale-share.md) |
| haybale-libs-other | Example / testing / TEST_A plugin libraries | [→ modules/haybale-libs-other.md](modules/haybale-libs-other.md) |
| tests | pytest suite by area (core, ui, graph_editor, studio, libraries, per-library) | [→ modules/tests.md](modules/tests.md) |
| docs | mkdocs site: architecture, components, ADRs, haybale authoring, reference | [→ modules/docs.md](modules/docs.md) |

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

- Total modules: 15 mapped (11 prior + 4 new bundled libs: audio, image, models, share)
- Gitignored local-only libs, not mapped: `haybale-visiongraph`, `haybale-comfyui`, `haybale-spandrel`, `haybale-stream`
- Map coverage: top-level dirs in the tracked tree are covered except `workbench/`, `site/`, `graphs/`, `haystacks/`, `scripts/`, `benchmarks/`, `assets/`, `.insights/` (CLAUDE.md-referenced, not code)
- Cross-cuts: 3, refreshed 2026-11-10
