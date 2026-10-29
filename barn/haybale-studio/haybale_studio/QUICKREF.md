# haybale-studio — component index (v0.3.0)

## setting
- `haybale-studio:setting:NetworkSettings` — Network — Where the studio's web server listens.
- `haybale-studio:setting:NodeThemeSettings` — Node Theme — Global settings controlling the active node theme.
- `haybale-studio:setting:WorkbenchThemeSettings` — Workbench Theme — Global settings controlling the active workbench theme.

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
- `haybale-studio:state:FileBrowserState` — File Browser State — Per-session state for the FileBrowser editor.

## panel
- `haybale-studio:panel:ActivitySettingsPanel` — Activity — Farmhand activity tracker: in-memory history size, audit log path.
- `haybale-studio:panel:CanvasSettingsPanel` — Grid — Grid, zoom, pan and background pattern.
- `haybale-studio:panel:DebugOverlaySettingsPanel` — Debug Overlay — Performance/debug HUD visibility and position.
- `haybale-studio:panel:DebugSettingsPanel` — Log Levels — Logging, execution visibility, visual debugging and data inspection.
- `haybale-studio:panel:DeveloperModePanel` — Developer mode — Toggles developer mode for this session.
- `haybale-studio:panel:EdgeDefaultSettingsPanel` — Edges — Computed edges' arrow head, head size, width and hit padding.
- `haybale-studio:panel:EditingSettingsPanel` — Editing — Undo history, and the external editor Haywire opens files in.
- `haybale-studio:panel:EditorZoomPanSettingsPanel` — Zoom & Pan — Canvas pan/zoom behaviour settings.
- `haybale-studio:panel:ExecutionSettingsPanel` — Execution — Auto-execute, timeouts, parallelism, caching and error handling.
- `haybale-studio:panel:LogoutPanel` — Sign out — Ends this browser session. Hidden entirely when authentication is off.
- `haybale-studio:panel:MinimapSettingsPanel` — Minimap — Minimap visibility, position and size.
- `haybale-studio:panel:NodeSkinDefaultPanel` — Default Skins — Node Default Skins.
- `haybale-studio:panel:OpenActivityPanel` — Agent activity — Opens the ActivityEditor.
- `haybale-studio:panel:OpenInCodeEditorMenuPanel` — Open in Code Editor — Open an editable text file in the CodeEditor.
- `haybale-studio:panel:OpenInFileViewerMenuPanel` — Open in File Viewer — Open any file in the read-only FileViewerEditor (catch-all fallback).
- `haybale-studio:panel:OpenRosterPanel` — Manage principals — Opens the RosterEditor. Admin-only, so a view principal never sees it.
- `haybale-studio:panel:RotateSecretPanel` — Sign everyone out — Rotates the cookie signing secret and evicts every live session.
- `haybale-studio:panel:SecurityPanel` — Security — What this studio's defences currently are — read-only.
- `haybale-studio:panel:ThemeSettingsPanel` — Workbench — Active workbench and node themes.

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
- `haybale-studio:editor:ShortcutsEditor` — Shortcuts — Keyboard shortcuts of every editor, grouped by editor.
- `haybale-studio:editor:TerminalEditor` — Log — Application output. Captures Python logging and print() output.

## theme
- `haybale-studio:theme:DefaultNodeTheme` — Default Node Theme — Default node rendering theme — works on both dark and light backgrounds.
- `haybale-studio:theme:HaywireDarkTheme` — Haywire Dark — Default dark workbench theme.
- `haybale-studio:theme:HaywireLightTheme` — Haywire Light — Default light workbench theme.
