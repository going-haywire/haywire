# Studio

Library for haywire studio

## Settings
- **Node Theme** — Global settings controlling the active node theme.
- **Workbench Theme** — Global settings controlling the active workbench theme.

## Farmhands
- **Describe component** — One component's identity, docstring, and authoring-guide link.
- **Dismiss errors** — Dismiss one or all ledger entries.
- **Get errors** — Query the studio's error ledger.
- **List components** — Component catalog, filterable and searchable.
- **List libraries** — List installed libraries.
- **Read component source** — Line-numbered source of any installed component.
- **Scaffold component** — Write a canon-conformant skeleton for a new component into a project-local library.
- **Studio status** — Versions, workspace root, enabled-library counts, docs manifest URI.
- **Verify component** — Staged verification that a component registers and runs cleanly.
- **Write component source** — Full-source write into a project-local library only.

## States
- **File Browser State** — Per-session state for the FileBrowser editor.

## Panels
- **Activity** — Farmhand activity tracker: in-memory history size, audit log path.
- **Agent activity** — Opens the ActivityEditor.
- **Debug Overlay** — Performance/debug HUD visibility and position.
- **Default Skins** — Node Default Skins.
- **Developer mode** — Toggles developer mode for this session.
- **Edges** — Computed edges' arrow head, head size, width and hit padding.
- **Editing** — Undo history, and the external editor Haywire opens files in.
- **Execution** — Auto-execute, timeouts, parallelism, caching and error handling.
- **Grid** — Grid, zoom, pan and background pattern.
- **Log Levels** — Logging, execution visibility, visual debugging and data inspection.
- **Manage principals** — Opens the RosterEditor. Admin-only, so a view principal never sees it.
- **Minimap** — Minimap visibility, position and size.
- **Open in Code Editor** — Open an editable text file in the CodeEditor.
- **Open in File Viewer** — Open any file in the read-only FileViewerEditor (catch-all fallback).
- **Security** — What this studio's defences currently are — read-only.
- **Sign everyone out** — Rotates the cookie signing secret and evicts every live session.
- **Sign out** — Ends this browser session. Hidden entirely when authentication is off.
- **Workbench** — Active workbench and node themes.
- **Zoom & Pan** — Canvas pan/zoom behaviour settings.

## Editors
- **Accounts** — Manage who may reach this studio
- **Agent Activity** — Farmhand tool calls made by agent principals
- **Code Editor** — Text/code editor with syntax highlighting (Markdown, Python, JSON, TOML, YAML, JS/TS, CSS/HTML/XML, Shell, plain text). Markdown files have a Preview tab. Save and Save As supported.
- **Component Detail** — Detailed documentation for the selected component.
- **Component Source** — Source code of the currently selected component.
- **Errors** — Error ledger. Lists HaywireExceptions logged since startup; click one for details.
- **File Viewer** — Displays the contents of a file selected in the Files browser.
- **Files** — Project file tree, eager-then-lazy: three levels are loaded up front, then 'Click to load children' sentinels appear at deeper folders so the user can pull in three more levels on demand.
- **Log** — Application output. Captures Python logging and print() output.
- **Properties** — Context-sensitive property panels for the active selection.
- **Shortcuts** — Keyboard shortcuts of every editor, grouped by editor.

## Themes
- **Default Node Theme** — Default node rendering theme — works on both dark and light backgrounds.
- **Haywire Dark** — Default dark workbench theme.
- **Haywire Light** — Default light workbench theme.
