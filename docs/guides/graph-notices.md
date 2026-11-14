---
status: draft
doc_template: guide
scope: Graph notices — posting a message about an open graph from a library, and what the haystack row shows
see-also:
  - ../adr/0069-graph-notices-are-a-library-extensible-store.md
  - model-catalogs.md
  - ../reference/glossary.md
---

# Graph notices

## 1. What the user sees

A **graph notice** is a message a library posts about one open graph. In the **HaystackEditor**, a row whose graph has notices shows a notice icon with a count beside play. Clicking it opens a popup that lists every notice. A notice with an action shows its button, such as **Show in Models**, but only to a session that meets the notice's `requires` tier. A notice marked `dismissable` has a dismiss button; dismissal hides it in that editor only.

Notices never disable play. Two producers exist today: the models **needs-list** (models the graph refers to that this machine does not have) and the load-time library compatibility findings (a library version differing from the one the graph was saved with).

## 2. Posting a notice

A notice is a `GraphNotice` in `haybale_graph_editor.notices`:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/notices.py:22:38"
```

Post and retract through `GraphAppState`; both are safe to call from any thread:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/states/graph_app_state.py:76:101"
```

Key the notice with your library id (`haybale-models:needs`); posting under an existing key replaces it, so a producer re-posts on every change without checking first. Retract when the reason is gone. To know when to re-walk graphs, register a zero-argument listener with `GraphAppState.add_graphs_listener`; it fires when a graph opens or closes.

Posting fires the payload-free cross-session signal `GraphNoticesChanged`, and every haystack editor re-reads the store. Notices are runtime state: they are neither saved with the graph nor kept after it closes.

See [ADR 0069](../adr/0069-graph-notices-are-a-library-extensible-store.md) for why the store lives on `GraphAppState` and not in the haystack.
