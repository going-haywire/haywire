# Haywire Dependency Report

Generated: 2026-05-17T11:56:29Z

> Updated 2026-06-26 (scoped re-audit of **haybale-visiongraph** after the vision
> estimator-node work): **no dependency errors.** A preliminary pass flagged a
> missing `haywire-studio` (because the package imports `haywire.ui.*`), but that
> was a **false positive** — the `haywire/ui` namespace is split across both
> framework packages, and the specific modules this library uses
> (`haywire.ui.skin.registry`, `haywire.ui.widget.{registry,base,decorator}`) are
> shipped by **`haywire-core`**, which is already declared. `haywire-studio` is
> NOT a dependency. The estimator-node code introduced no new dependency edge.
> Other packages were not re-scanned in this run.
>
> Fixed 2026-07-31: the false positive above was a bug in `detect_deps`, which
> routed any `haywire.ui.*` import to `haywire-studio`. It affected every barn
> library that touches a widget or panel (9 of 9 in this repo), not just
> visiongraph. `haywire/ui` is **not** split across the two packages — it is 96
> files in the `haywire-core` wheel and 0 in the `haywire-studio` wheel. The
> detector now maps every `haywire.*` import to `haywire-core`.

---

## Flat Dependency Graph

Direct haywire/haybale inter-package dependencies per package (from import analysis).

### haywire-core
(no haywire/haybale dependencies)

### haywire-studio
└─> haywire-core

### haybale-core
└─> haywire-core

### haybale-example
├─> haywire-core
└─> haybale-core

### haybale-visiongraph
├─> haywire-core
└─> haybale-core

### haybale-graph-editor
└─> haywire-core

### haybale-testing
├─> haywire-core
├─> haybale-core
└─> haybale-graph-editor

### haybale-studio
├─> haywire-core
└─> haywire-studio

### haybale-haystack
├─> haywire-core
├─> haybale-studio
└─> haybale-graph-editor

### haybale-TEST_A
└─> haywire-core

---

## Deep Transitive Tree

Fully expanded dependency chains. Shared subtrees shown in full at each occurrence.

### haywire-core
(no haywire/haybale dependencies)

### haywire-studio
└─> haywire-core

### haybale-core
└─> haywire-core

### haybale-example
├─> haywire-core
└─> haybale-core
    └─> haywire-core

### haybale-visiongraph
├─> haywire-core
└─> haybale-core
    └─> haywire-core

### haybale-graph-editor
└─> haywire-core

### haybale-testing
├─> haywire-core
├─> haybale-core
│   └─> haywire-core
└─> haybale-graph-editor
    └─> haywire-core

### haybale-studio
├─> haywire-core
└─> haywire-studio
    └─> haywire-core

### haybale-haystack
├─> haywire-core
├─> haybale-studio
│   ├─> haywire-core
│   └─> haywire-studio
│       └─> haywire-core
└─> haybale-graph-editor
    └─> haywire-core

### haybale-TEST_A
└─> haywire-core

---

### Advisories

#### [A10] Thin dependency — haybale-haystack → haybale-studio

Files that import from `haybale_studio` (1):
- `haybale_haystack/panels/file_browser/open_in_haystack.py`

Consider whether this dependency can be severed or moved (e.g., by moving `open_in_haystack.py`
into `haybale-studio`, or by abstracting the interface).

---

## Summary

| Package | pyproject errors | @library errors | Advisories |
|---------|-----------------|-----------------|------------|
| haywire-core | 0 | — | 0 |
| haywire-studio | 0 | — | 2 (A5, A6: pyproject excess) |
| haybale-core | 1 (nicegui, skipped) | 0 | 0 |
| haybale-example | 1 (nicegui, skipped) | 0 | 0 |
| haybale-visiongraph | 0 (2026-06-26 re-audit; haywire-studio false positive) | 0 | 0 |
| haybale-graph-editor | 1 (nicegui, skipped) | 0 | 2 (A1, A2: pyproject excess) |
| haybale-haystack | 1 (nicegui, skipped) | 0 | 3 (A3, A4: excess; A10: thin dep) |
| haybale-studio | 2 (nicegui skipped, packaging fixed) | 0 | 3 (A7, A8, A9: excess) |
| haybale-testing | 1 (nicegui, skipped) | 0 | 0 |
| haybale-TEST_A | 0 | 0 | 0 |
