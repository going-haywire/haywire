---
name: haywire-ui
description: Load Haywire UI architecture docs into context. Use when the user wants to build or modify editors, panels, the app shell, or any UI feature in the workspace system.
---

# Load Haywire UI Architecture

Read the following documentation files in order and use them as the authoritative reference for any UI implementation task. After reading, output a brief recap of the key patterns before proceeding with the user's task.

## Files to read

1. `docs/documentation/build_editors.md` — how to create a `BaseEditor` subclass, the `@editor` decorator, registration in `app.py`, and how editors interact with `SessionContext`
2. `docs/documentation/build_panels.md` — how to create a `BasePanel` subclass, the `@panel` decorator, poll/draw lifecycle, and panel-to-editor binding
3. `docs/documentation/architecture/haywire_app.md` — overall `HaywireApp` structure: shared services, session lifecycle, `project_state` wiring
4. `docs/documentation/architecture/app_ui/haywire-ui-architecture-spec_details.md` — detailed spec of the full workspace layout (AppShell, areas, tabs, ActivityBar, ContextBar, WorkspaceState, WorkspaceManager)

## After reading

Summarise in 6–10 bullet points:
- The `@editor` / `@panel` decorator contract (what fields are required, what they do)
- The `BaseEditor.render(container, context)` and `on_context_changed(event, context)` contract
- How editors are registered (`_editor_registry._register_class()` in `setup_shared_services()`)
- How middle-area tab switching works (`context.metadata['middle_tabs'].set_value(...)`)
- What `SessionContext` carries and how `context.metadata` is used for app-specific state
- How `ContextChangedEvent` / `ContextChangeType` is used to broadcast state changes
- Any gotchas called out in the docs (NiceGUI slot context rules, per-session vs shared state, etc.)

Then proceed with the user's task using these patterns as the guide.
