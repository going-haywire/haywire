# Slot Rename — Term Mapping

Unified vocabulary for the workspace layout: every slot consists of a **bar**
(control strip — either vertical icons or horizontal tabs) and an **area**
(the content panel where the active editor renders).

The four slots are `left`, `right`, `main`, `bottom`. Each has exactly one
bar. Bars are always visible when the slot has at least one editor.

Active-tab storage is unified on `active_tab_key` (the editor key string) for
all four slots. Indices are gone; keys are stable across registry changes.

This is a **breaking rename** — no legacy migration, no backwards-compatible
shims. Old workspace files will fail to load and fall back to auto-populate.

## Renamed

Editor class attribute: `canvas_area` -> `default_slot`

Editor decorator parameter: `canvas_area=...` -> `default_slot=...`

BaseIdentity / ClassIdentity field: `canvas_area` -> `default_slot`

Slot value string: `"middle"` -> `"main"`

Registry method: `get_by_default_area(area)` -> `get_by_default_slot(slot)`

Registry method parameter: `area: str` -> `slot: str`

Dataclass: `AreaState` -> `SlotState`

Dataclass: `MiddleAreaState` -> `MainSlotState`

Dataclass: `BottomAreaState` -> `BottomSlotState`

WorkspaceState field: `middle: MiddleAreaState` -> `main: MainSlotState`

WorkspaceState field: `bottom: BottomAreaState` -> `bottom: BottomSlotState`

WorkspaceState field: `left: AreaState` -> `left: SlotState`

WorkspaceState field: `right: AreaState` -> `right: SlotState`

Persisted JSON top-level key: `"middle"` -> `"main"`

Shell slot name in `_area_slots` / `_render_area(slot=...)`: `"middle"` -> `"main"`

Shell slot registry: `_area_slots` -> `_slots`

Shell render method: `_render_middle_area` -> `_render_main_slot`

Shell render method: `_render_bottom_area` -> `_render_bottom_slot`

Shell render method: `_render_area` -> `_render_slot`

Shell helper: `_render_tab_bar_row` -> `_render_tab_bar`

Shell state attribute: `_middle_column` -> `_main_slot`

Shell state attribute: `_left_column` -> `_left_slot`

Shell state attribute: `_right_column` -> `_right_slot`

Shell state attribute: `_bottom_column` -> `_bottom_slot`

Main slot bar: (no name) -> `MainTabBar`

Bottom slot bar: (no name) -> `BottomTabBar`

Design guide §9.1 diagram label: `Middle Area` -> `Main Slot`

Design guide §9.1 diagram label: `Tab Bar (36px)` -> `MainTabBar (36px)`

Design guide §9.7 prose: `bottom area` -> `bottom slot`

Design guide §9.7 prose: `middle-area tab bar` -> `main slot's MainTabBar`

Design guide §9.7 prose: `bottom tab bar row` -> `BottomTabBar`

Design guide §10.2 `hw-tabs` class: `hw-tabs` -> `hw-slot-bar-tabs`

Design guide §10.2 `hw-tabs` description: `Middle- and bottom-area tab bar styling` -> `Tab-style slot bar (main and bottom slots)`

CSS class (icon-style slot bar, new): (none) -> `hw-slot-bar-icons`

CSS class (slot bar base, new): (none) -> `hw-slot-bar`

Docs `build_editors.md` examples: `canvas_area="middle"` -> `default_slot="main"`

Docs `haywire_app.md` references: `middle area` / `canvas_area` -> `main slot` / `default_slot`

Docs `haywire-ui-architecture-spec_details.md` references: `middle area` / `canvas_area` -> `main slot` / `default_slot`

Barn editor files (10x) decorators / class attrs: `canvas_area="middle"` -> `default_slot="main"`

Test fixture method: `_FakeEditorRegistry.get_by_default_area` -> `get_by_default_slot`

Test helper kwarg: `_make_registry(middle=[...])` -> `_make_registry(main=[...])`

Test assertions: `active.middle.tabs` -> `active.main.tabs`

## Unified (active-tab storage)

MainSlotState: `active_tab_index: int` -> `active_tab_key: Optional[str]`

MainSlotState tab lookup: `main.tabs[main.active_tab_index]` -> lookup `main.tabs` by `main.active_tab_key`

WorkspaceState field: `left_bar_active: Optional[str]` -> (removed — moved onto `left.active_tab_key`)

WorkspaceState field: `right_bar_active: Optional[str]` -> (removed — moved onto `right.active_tab_key`)

SlotState (base): gains `active_tab_key: Optional[str]` field

BottomSlotState: `active_tab_key: Optional[str]` (already present) -> unchanged

## Unified (bar visibility)

Rule: a slot's bar is visible whenever the slot has at least one editor; it is hidden entirely when the slot has none. Applied uniformly to all four slots (left, right, main, bottom).

## Added

Design guide §10.1 Terminology table: add `Slot` row (left, right, main, bottom)

Design guide §10.1 Terminology table: add `Bar` row (the control strip on a slot — icons or tabs)

Design guide §10.1 Terminology table: add `Area` row (the content panel of a slot, where the active editor renders)

Design guide §10.1 Terminology table: add `MainTabBar` row (the main slot's bar)

Design guide §10.1 Terminology table: add `BottomTabBar` row (the bottom slot's bar)

Design guide §10.1: ActivityBar documented as "the left slot's bar — hosts activity-minded editors (browsers, navigators)"

Design guide §10.1: ContextBar documented as "the right slot's bar — hosts reactive context-minded editors (properties, inspectors)"

## Unchanged (deliberately preserved)

Slot value: `"left"` -> `"left"`

Slot value: `"right"` -> `"right"`

Slot value: `"bottom"` -> `"bottom"`

Dataclass: `TabState` -> `TabState`

CSS class: `hw-panel` -> `hw-panel`

Name kept as synonym for left slot bar: `ActivityBar` -> `ActivityBar`

Name kept as synonym for right slot bar: `ContextBar` -> `ContextBar`

Graph canvas Vue file attribute (`canvas.vue`): `canvas_area` -> `canvas_area`

Graph canvas Vue file attribute (`pan.vue`): `canvas_area` -> `canvas_area`

Class: `GraphCanvas` -> `GraphCanvas`

Class: `ZoomPanContainer` -> `ZoomPanContainer`

Module path: `haywire.ui.graph_canvas` -> `haywire.ui.graph_canvas`

Edge-strip concept: `TopBar` -> `TopBar`

Edge-strip concept: `StatusBar` -> `StatusBar`

Edge-strip concept: `ScopeToolbar` -> `ScopeToolbar`

## Breaking changes (no migration path)

Persisted workspace files using the old `middle` key or `canvas_area="middle"` editors will fail to load and auto-populate from the registry. This is intentional — no legacy reader branch in `_deserialize_workspace`.

The `middle.bottom_*` legacy migration (added earlier for the BottomSlotState extraction) is also removed as part of this cleanup, since those files predate even the previous rename.
