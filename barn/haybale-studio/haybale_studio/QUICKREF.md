# haybale-studio — component index (v0.1.3)

## setting
- `haybale-studio:setting:NodeSkinSettings` — Node Skin — 
- `haybale-studio:setting:NodeThemeSettings` — Node Theme — 
- `haybale-studio:setting:WorkbenchThemeSettings` — Workbench Theme — 

## farmhand
- `haybale-studio:farmhand:describe_component` — Describe component — One component's identity, docstring, and authoring-guide link.
- `haybale-studio:farmhand:dismiss_errors` — Dismiss errors — Dismiss one or all ledger entries.
- `haybale-studio:farmhand:get_errors` — Get errors — Query the studio's error ledger.
- `haybale-studio:farmhand:list_components` — List components — Component catalog, filterable and searchable.
- `haybale-studio:farmhand:list_libraries` — List libraries — List installed libraries.
- `haybale-studio:farmhand:read_component_source` — Read component source — Line-numbered source of any installed component.
- `haybale-studio:farmhand:scaffold_component` — Scaffold component — Write a canon-conformant skeleton for a new component into a project-local library.
- `haybale-studio:farmhand:status` — Studio status — Versions, workspace root, enabled-library counts, docs manifest URI.
- `haybale-studio:farmhand:verify_component` — Verify component — Staged verification that a component registers and runs cleanly.
- `haybale-studio:farmhand:write_component_source` — Write component source — Full-source write into a project-local library only.

## state
- `haybale-studio:state:FileBrowserState` — File Browser State — 

## panel
- `haybale-studio:panel:ActivitySettingsPanel` — Activity — 
- `haybale-studio:panel:CanvasSettingsPanel` — Canvas — 
- `haybale-studio:panel:DebugOverlaySettingsPanel` — Debug Overlay — 
- `haybale-studio:panel:DebugSettingsPanel` — Log Levels — 
- `haybale-studio:panel:EdgeUISettingsPanel` — Edges — 
- `haybale-studio:panel:EditorSettingsPanel` — Editor — 
- `haybale-studio:panel:EditorZoomPanSettingsPanel` — Zoom & Pan — 
- `haybale-studio:panel:ExecutionSettingsPanel` — Execution — 
- `haybale-studio:panel:LogoutPanel` — Sign out — 
- `haybale-studio:panel:MinimapSettingsPanel` — Minimap — 
- `haybale-studio:panel:NodeSkinDefaultPanel` — Default Skins — 
- `haybale-studio:panel:NodeSkinSettingsPanel` — Skins — Skin Configuration:Node dimensions, typography and label visibility.
- `haybale-studio:panel:OpenActivityPanel` — Agent activity — 
- `haybale-studio:panel:OpenInCodeEditorMenuPanel` — Open in Code Editor — 
- `haybale-studio:panel:OpenInFileViewerMenuPanel` — Open in File Viewer — 
- `haybale-studio:panel:OpenRosterPanel` — Manage principals — 
- `haybale-studio:panel:RotateSecretPanel` — Sign everyone out — 
- `haybale-studio:panel:SecurityPanel` — Security — 
- `haybale-studio:panel:ThemeSettingsPanel` — Workbench — 

## editor
- `haybale-studio:editor:ActivityEditor` — Agent Activity — Farmhand tool calls made by agent principals
- `haybale-studio:editor:CodeEditor` — Code Editor — Text/code editor with syntax highlighting (Markdown, Python, JSON, TOML, YAML, JS/TS, CSS/HTML/XML, Shell, plain text). Markdown files have a Preview tab. Save and Save As supported.
- `haybale-studio:editor:ComponentDocsEditor` — Component Detail — Detailed documentation for the selected component.
- `haybale-studio:editor:ComponentSourceEditor` — Component Source — Source code of the currently selected component.
- `haybale-studio:editor:ErrorsEditor` — Errors — Error ledger. Lists HaywireExceptions logged since startup; click one for details.
- `haybale-studio:editor:FileViewerEditor` — File Viewer — Displays the contents of a file selected in the Files browser.
- `haybale-studio:editor:LazyFileBrowserEditor` — Files — Project file tree, eager-then-lazy: three levels are loaded up front, then 'Click to load children' sentinels appear at deeper folders so the user can pull in three more levels on demand.
- `haybale-studio:editor:PropertiesEditor` — Properties — Context-sensitive property panels for the active selection.
- `haybale-studio:editor:RosterEditor` — Accounts — Manage who may reach this studio
- `haybale-studio:editor:TerminalEditor` — Log — Application output. Captures Python logging and print() output.

## skin
- `haybale-studio:skin:DefaultNodeSkin` — DefaultNodeSkin — Default skin with collapsible group support

## theme
- `haybale-studio:theme:DefaultNodeTheme` — Default Node Theme — 
- `haybale-studio:theme:HaywireDarkTheme` — Haywire Dark — 
- `haybale-studio:theme:HaywireLightTheme` — Haywire Light —
