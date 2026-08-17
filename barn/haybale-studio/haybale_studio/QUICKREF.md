# studio — component index (v0.1.0)

## setting
- `studio:setting:NodeSkinSettings` — Node Skin — 
- `studio:setting:NodeThemeSettings` — Node Theme — 
- `studio:setting:WorkbenchThemeSettings` — Workbench Theme — 

## farmhand
- `studio:farmhand:describe_component` — Describe component — One component's identity, docstring, and authoring-guide link.
- `studio:farmhand:dismiss_errors` — Dismiss errors — Dismiss one or all ledger entries.
- `studio:farmhand:get_errors` — Get errors — Query the studio's error ledger.
- `studio:farmhand:list_components` — List components — Component catalog, filterable and searchable.
- `studio:farmhand:list_libraries` — List libraries — List installed libraries.
- `studio:farmhand:read_component_source` — Read component source — Line-numbered source of any installed component.
- `studio:farmhand:scaffold_component` — Scaffold component — Write a canon-conformant skeleton for a new component into a project-local library.
- `studio:farmhand:status` — Studio status — Versions, workspace root, enabled-library counts, docs manifest URI.
- `studio:farmhand:verify_component` — Verify component — Staged verification that a component registers and runs cleanly.
- `studio:farmhand:write_component_source` — Write component source — Full-source write into a project-local library only.

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
- `studio:panel:SecurityPanel` — Security — 
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
