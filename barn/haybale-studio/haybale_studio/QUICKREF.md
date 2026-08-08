# studio — component index (v0.0.39)

## setting
- `studio:setting:NodeSkinSettings` — Node Skin — 
- `studio:setting:NodeThemeSettings` — Node Theme — 
- `studio:setting:WorkbenchThemeSettings` — Workbench Theme — 

## farmhand
- `studio:farmhand:describe_component` — Describe component — One component's identity and docstring, plus the canon_doc_uri for its kind's authoring guide. For nodes: read before graph_editor_add_node.
- `studio:farmhand:dismiss_errors` — Dismiss errors — Dismiss ledger entries: pass seq=<n> to remove one, or all=true to clear every retained entry. Removal is permanent for that entry but leaves the monotonic cursor untouched, so incremental since_seq polling stays correct. Broadcasts so open studio Errors editors refresh. Dismissing an absent seq is a no-op (idempotent).
- `studio:farmhand:get_errors` — Get errors — Query the studio's error ledger (since_seq/library/registry_key filters); results carry the current cursor for incremental polling and first_retained_seq so a client can detect when older history was evicted or deleted.
- `studio:farmhand:list_components` — List components — ALWAYS pass at least one of kind=/library=/search= — omitting all three returns every installed component (100+) and is slow and almost never what you want. Component catalog, filterable and searchable.
Start with count_only=true to see totals per library/kind before listing rows — the cheapest way to survey scope.
kind: one of adapter, editor, farmhand, node, panel, setting, skin, state, theme, type, widget
library: exact library id (see studio_list_libraries)
search: substring match against label/description/search_tags (same algorithm as the node-menu search)
count_only: return counts grouped by library/kind instead of rows
detail: add each component's one-line description to the row (registry_key/label only by default — descriptions dominate a large listing)
include_hidden: include internal components (e.g. reroute/error nodes), excluded by default
include_system: include synthetic libraries (dunder ids like '__system__'), excluded by default
- `studio:farmhand:list_libraries` — List libraries — Installed libraries: id, label, version, enabled. Pass detail=true to add description and tags. Synthetic libraries (dunder ids like '__system__') are excluded unless include_system=true.
- `studio:farmhand:read_component_source` — Read component source — Line-numbered source of any installed component. Returns the first 400 lines by default; pass offset= to window further in, or full=true for the entire file. Truncated results say so in the summary and report total_lines.
- `studio:farmhand:scaffold_component` — Scaffold component — Write a canon-conformant skeleton for any component kind into a project-local library; returns the path and expected registry key. Read the kind's canon first — find it via the farmhand://docs/_manifest index (e.g. components/nodes/node-canon.md).
- `studio:farmhand:status` — Studio status — Versions, workspace root, enabled-library counts, docs manifest URI. Call this first when connecting — the summary points at how to find documentation.
- `studio:farmhand:verify_component` — Verify component — Staged verification: registered -> (nodes) trial instantiation -> on_testrun(); error-ledger entries from the failing stage are attached.
- `studio:farmhand:write_component_source` — Write component source — Full-source write into a project-local library only. Existing components are hot-reloaded by the file watcher; follow with studio_verify_component.

## state
- `studio:state:FileBrowserState` — File Browser State — 

## panel
- `studio:panel:CanvasSettingsPanel` — Canvas — 
- `studio:panel:DebugOverlaySettingsPanel` — Debug Overlay — 
- `studio:panel:DebugSettingsPanel` — Log Levels — 
- `studio:panel:EdgeUISettingsPanel` — Edges — 
- `studio:panel:EditorSettingsPanel` — Editor — 
- `studio:panel:EditorZoomPanSettingsPanel` — Zoom & Pan — 
- `studio:panel:ExecutionSettingsPanel` — Execution — 
- `studio:panel:MinimapSettingsPanel` — Minimap — 
- `studio:panel:NetworkSettingsPanel` — Network — 
- `studio:panel:NodeSkinDefaultPanel` — Default Skins — 
- `studio:panel:NodeSkinSettingsPanel` — Skins — Skin Configuration:Node dimensions, typography and label visibility.
- `studio:panel:OpenInCodeEditorMenuPanel` — Open in Code Editor — 
- `studio:panel:OpenInFileViewerMenuPanel` — Open in File Viewer — 
- `studio:panel:ThemeSettingsPanel` — Workbench — 

## editor
- `studio:editor:CodeEditor` — Code Editor — Text/code editor with syntax highlighting (Markdown, Python, JSON, TOML, YAML, JS/TS, CSS/HTML/XML, Shell, plain text). Markdown files have a Preview tab. Save and Save As supported.
- `studio:editor:ComponentSourceEditor` — Component Source — Source code of the currently selected component.
- `studio:editor:ErrorsEditor` — Errors — Error ledger. Lists HaywireExceptions logged since startup; click one for details.
- `studio:editor:FileViewerEditor` — File Viewer — Displays the contents of a file selected in the Files browser.
- `studio:editor:LazyFileBrowserEditor` — Files — Project file tree, eager-then-lazy: three levels are loaded up front, then 'Click to load children' sentinels appear at deeper folders so the user can pull in three more levels on demand.
- `studio:editor:PropertiesEditor` — Properties — Context-sensitive property panels for the active selection.
- `studio:editor:TerminalEditor` — Log — Application output. Captures Python logging and print() output.

## skin
- `studio:skin:DefaultNodeSkin` — DefaultNodeSkin — Default skin with collapsible group support
