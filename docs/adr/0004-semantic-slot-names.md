---
name: semantic-slot-names
description: Replace positional-string AppShell slot identifiers with the semantic SlotName StrEnum as a clean break, no migration shim
status: accepted
level: architectural
---

# Rename workspace slots to semantic `SlotName` members, clean break

The four AppShell slots were identified by positional strings — `left`, `right`, `main`, `bottom` — scattered as bare literals across the `@editor(default_slot=...)` decorator, `EditorIdentity`, the workspace JSON persistence, the drag-resize JS bridge, and the docs. We replaced them with a semantic `StrEnum`, `SlotName` (`ACTION` / `CONTEXT` / `EDIT` / `INFO`), made it the single source of truth for both the wire value and the human label, and did so as a **clean break with no migration shim**. This required raising the repo's Python floor to 3.11.

## Why rename at all

The positional names conflated *where a slot sits* with *what it is for*. "left" and "right" already had semantic bar names in the glossary (ActivityBar = actions, ContextBar = context), so the slot strings and the bar names disagreed. The new names state intent: ACTION (launchers / navigation, left edge), CONTEXT (reacts to selection, right edge), EDIT (the primary editing surface, centre — formerly "main", and "middle" before that), INFO (supplementary output, bottom). Position is now a property of the slot, not its identity.

## Why `StrEnum`, not a plain `Enum` or a `Literal`

The slot value crosses four boundaries that a plain `Enum` would force `.value` / `SlotName(raw)` conversions at: the decorator (authors type a literal), JSON persistence, dict lookups in `_managed_slots`, and `==` against raw strings emitted by the drag JS. Because a `StrEnum` member *is* a `str`, all of these work with zero conversion — `SlotName.EDIT == "edit"`, `json.dumps` yields `"edit"`, `f"hw-slot-{SlotName.EDIT}"` yields `hw-slot-edit`. A bare `Literal` alias would give mypy coverage but no runtime guardrail and no place to hang the `.label` (human-facing) accessor. `StrEnum` is 3.11+, which is the proximate reason for the Python-floor bump (see below).

## Why a clean break, not a migration shim

We considered (a) an old→new alias map applied on snapshot load, and (b) `SlotName._missing_` coercing legacy strings transparently. Both were rejected. The project is pre-1.0 (v0.0.x); the only persisted artifact is `workspace_state.json`, which already re-derives its editor roster from the registry on load — a workspace keyed by the old names simply falls back to defaults, costing a user at most one re-arrange. A shim would have been permanent surface area (every future reader would wonder whether the old names are still "real") guarding against a one-time, low-cost event. Instead the `@editor` decorator now **raises `ValueError` at class-definition time** on an unknown `default_slot`, so a stale `default_slot="main"` fails loudly at import rather than silently landing an editor in no slot. The guardrail replaces the shim.

## Why the Python 3.11 bump rides along

`StrEnum` landed in the stdlib in 3.11. The repo previously floored at `>=3.10` (some barn packages at `>=3.9`). Rather than subclass `(str, Enum)` to emulate `StrEnum` on 3.10, we raised every package's `requires-python` to `>=3.11` (and the mypy `python_version`) — touching eleven `pyproject.toml` files and re-resolving `uv.lock`. The floor has since moved to `>=3.12` for unrelated reasons; this ADR's contribution was the 3.10→3.11 step.

## Consequences

- Third-party libraries still passing `default_slot="main"` (or any old name) break at import with a clear `ValueError`. This is intentional and the reason no deprecation window exists.
- The JS drag bridge is the one place that speaks raw strings; its DOM ids (`hw-slot-action` / `-context` / `-info`) are generated from `SlotName.value` and inbound `slot` strings are re-validated via `SlotName(...)` in `_on_slot_resize`, so JS and Python agree by construction.
- The `bar_place` constructor arg (`"left"`/`"right"`/`"top"`/`"bottom"`) is a separate, purely directional concept and was deliberately **not** renamed.
- A doc-drift correction rode along: the glossary documented `SlotState` / `MainSlotState` / `BottomSlotState` / `TabState` dataclasses and an `active_tab_key` field that no longer exist in code — the real persistence is a uniform `Slot.to_snapshot()` dict (`active_key`, `visible`, `size`, `editors`). The glossary now describes the dict.
