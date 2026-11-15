---
name: NiceGUI make_sortable needs Sortable imported at module load
description: make_sortable imports the Sortable class only at render time, after the page's importmap was written, so the "nicegui-sortable" ESM specifier fails to resolve in an already-served page
type: feedback
---
`element.make_sortable(...)` imports `nicegui.elements.sortable.sortable.Sortable` lazily, when it first runs. Importing that class is what registers the `"nicegui-sortable"` ESM module, and a page's importmap is written when the page is served. A page already in the browser therefore has no entry for the bare specifier, and the sortable silently fails to load.

**Why:** in Haywire, panels and editors draw long after page serve (on selection, on redraw, after hot reload), so the lazy import always comes too late.

**How to apply:** any module that calls `make_sortable` imports the class at module level, as [node_ports.py](../barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py) does:

```python
from nicegui.elements.sortable.sortable import Sortable as _Sortable  # noqa: F401
```
