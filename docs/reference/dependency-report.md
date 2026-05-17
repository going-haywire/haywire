# Haywire Dependency Report

Generated: 2026-05-17T11:56:29Z

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
| haybale-visiongraph | 1 (nicegui, skipped) | 0 | 0 |
| haybale-graph-editor | 1 (nicegui, skipped) | 0 | 2 (A1, A2: pyproject excess) |
| haybale-haystack | 1 (nicegui, skipped) | 0 | 3 (A3, A4: excess; A10: thin dep) |
| haybale-studio | 2 (nicegui skipped, packaging fixed) | 0 | 3 (A7, A8, A9: excess) |
| haybale-testing | 1 (nicegui, skipped) | 0 | 0 |
| haybale-TEST_A | 0 | 0 | 0 |
