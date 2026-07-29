# Studio

<!-- marketstall:share-url:start -->
*Subscribe URL not yet published — run `haywire share --save`.*
<!-- marketstall:share-url:end -->

Library for haywire studio

## Settings
- **Node Skin** — 
- **Node Theme** — 
- **Workbench Theme** — 

## Farmhands
- **Describe component** — One component's identity and docstring, plus the canon_doc_uri for its kind's authoring guide. For nodes: read before graph_editor_add_node.
- **Dismiss errors** — Dismiss ledger entries: pass seq=<n> to remove one, or all=true to clear every retained entry. Removal is permanent for that entry but leaves the monotonic cursor untouched, so incremental since_seq polling stays correct. Broadcasts so open studio Errors editors refresh. Dismissing an absent seq is a no-op (idempotent).
- **Get errors** — Query the studio's error ledger (since_seq/library/registry_key filters); results carry the current cursor for incremental polling and first_retained_seq so a client can detect when older history was evicted or deleted.
- **List components** — ALWAYS pass at least one of kind=/library=/search= — omitting all three returns every installed component (100+) and is slow and almost never what you want. Component catalog, filterable and searchable.
Start with count_only=true to see totals per library/kind before listing rows — the cheapest way to survey scope.
kind: one of adapter, editor, farmhand, node, panel, setting, skin, state, theme, type, widget
library: exact library id (see studio_list_libraries)
search: substring match against label/description/search_tags (same algorithm as the node-menu search)
count_only: return counts grouped by library/kind instead of rows
include_hidden: include internal components (e.g. reroute/error nodes), excluded by default
include_system: include synthetic libraries (dunder ids like '__system__'), excluded by default
- **List libraries** — Installed libraries: id, label, version, description, tags, enabled. Synthetic libraries (dunder ids like '__system__') are excluded unless include_system=true.
- **Read component source** — Line-numbered source of any installed component.
- **Scaffold component** — Write a canon-conformant skeleton for any component kind into a project-local library; returns the path and expected registry key. Read the kind's canon first — find it via the farmhand://docs/_manifest index (e.g. components/nodes/node-canon.md).
- **Studio status** — Versions, workspace root, enabled-library and open-graph counts, docs manifest URI. Call this first when connecting — the summary points at how to find documentation.
- **Verify component** — Staged verification: registered -> (nodes) trial instantiation -> on_testrun(); error-ledger entries from the failing stage are attached.
- **Write component source** — Full-source write into a project-local library only. Existing components are hot-reloaded by the file watcher; follow with studio_verify_component.
