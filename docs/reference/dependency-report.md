# Haywire Dependency Report

Generated: 2026-05-17T00:00:00

---

## Flat Dependency Graph

Direct haywire/haybale inter-package dependencies per package (from import analysis).

### haywire-core
(no haywire/haybale dependencies)

### haywire-studio
└─> haywire-core

### haybale-core
└─> haywire-core

### haybale-studio
├─> haywire-core
├─> haywire-studio
├─> haybale-core
└─> haybale-graph-editor

### haybale-graph-editor
├─> haywire-core
└─> haywire-studio

### haybale-haystack
├─> haywire-core
├─> haywire-studio
├─> haybale-studio
└─> haybale-graph-editor

### haybale-example
├─> haywire-core
└─> haybale-core

### haybale-visiongraph
├─> haywire-core
└─> haybale-core

### haybale-testing
├─> haywire-core
├─> haybale-core
└─> haybale-graph-editor

### haybale-TEST_A
└─> haywire-core

---

## Deep Transitive Tree

Fully expanded dependency chains. Shared subtrees shown in full at each occurrence.

### haywire-core
(no dependencies)

### haywire-studio
└─> haywire-core

### haybale-core
└─> haywire-core

### haybale-studio
├─> haywire-core
├─> haywire-studio
│   └─> haywire-core
├─> haybale-core
│   └─> haywire-core
└─> haybale-graph-editor
    ├─> haywire-core
    └─> haywire-studio
        └─> haywire-core

### haybale-graph-editor
├─> haywire-core
└─> haywire-studio
    └─> haywire-core

### haybale-haystack
├─> haywire-core
├─> haywire-studio
│   └─> haywire-core
├─> haybale-studio
│   ├─> haywire-core
│   ├─> haywire-studio
│   │   └─> haywire-core
│   ├─> haybale-core
│   │   └─> haywire-core
│   └─> haybale-graph-editor
│       ├─> haywire-core
│       └─> haywire-studio
│           └─> haywire-core
└─> haybale-graph-editor
    ├─> haywire-core
    └─> haywire-studio
        └─> haywire-core

### haybale-example
├─> haywire-core
└─> haybale-core
    └─> haywire-core

### haybale-visiongraph
├─> haywire-core
└─> haybale-core
    └─> haywire-core

### haybale-testing
├─> haywire-core
├─> haybale-core
│   └─> haywire-core
└─> haybale-graph-editor
    ├─> haywire-core
    └─> haywire-studio
        └─> haywire-core

### haybale-TEST_A
└─> haywire-core

---

### Advisories


#### [A5] Thin dependency — haybale-studio → haybale-graph-editor
Only 1 file in `haybale-studio` imports from `haybale_graph_editor`:
- `barn/haybale-studio/haybale_studio/editors/node_source_editor.py`

Consider whether this coupling can be removed or moved.

---

## Summary

| Package | pyproject errors | @library errors | Advisories |
|---------|-----------------|-----------------|------------|
| haywire-core | 0 | — | 0 |
| haywire-studio | 0 | — | 1 (A1) |
| haybale-core | 0 | 0 | 0 |
| haybale-studio | 0 | 1 → fixed (E2) | 2 (A5, A6) |
| haybale-graph-editor | 0 | 1 → fixed (A2 advisory) | 1 (A2) |
| haybale-haystack | 0 | 0 | 0 |
| haybale-example | 0 | 0 | 1 (A3) |
| haybale-visiongraph | 0 | 0 | 0 |
| haybale-testing | 1 → fixed (E1) | 1 → fixed (E3) | 1 (A4) |
| haybale-TEST_A | 0 | 1 → fixed (E4) | 0 |
