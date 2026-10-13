---
name: instance-edit-by-detach-with-origin
description: A placement is edited by detaching it into a Group that remembers where it came from (its origin); a modified instance then goes back through three verbs, Revert to Macro, Update Macro and Save new Macro, each one undo step, and no verb writes a file except through the macro tab's own Save
status: accepted
see-also: ADR-0037, ADR-0038, ADR-0051
level: ui
---

# Instance edit by detach, with an origin

**Context.**

- ADR 0038 made a placement's interior runtime state and its level read-only, and deferred "Edit Instance". A user who wants the interior of one placement to differ from the macro had one route: Detach from Macro, which cut the card loose with no memory of where it came from.
- Once detached, nothing could say "this Group was a copy of macro X", so there was no way back and no way to send the changes to the macro.

**Decision.**

- **A detached placement records its origin.** `MacroOrigin(key, hash)` is stored on the `SubgraphDefinition` (`origin`) and saved as `"origin": {"key", "hash"}`. `DetachPlacementFromMacroAction` stamps it. `hash` is the template's `content_hash` (sha256 of the `.hwm` text) at the moment of detach. A Group with an origin is a **modified instance**.
- **Two entry points, one action.** Unlocking a placement's own interior level asks ("Edit Instance"), then detaches and unlocks. The selection-menu row **Edit Instance** (formerly "Detach from Macro") detaches and enters the new Group. Both need `edit`.
- **Only a placement's own level offers it.** A level deeper inside a placement keeps the ADR 0038 refusal: the unit that detaches is the placement card, and a nested level has no card of its own to detach.
- **An open level follows its Subgraph to the new key** (`_rekey_level`), so the level the user is looking at survives the detach. Undo moves it back and re-locks it.
- **Three verbs on a modified instance, each a swap, each one undo step, each needing `edit`** (they reuse the swap that Promote used):
  - **Revert to Macro** swaps the card for a placement of the current template. Connections to pins the template lacks are dropped; undo restores them. It writes nothing.
  - **Update Macro…** (haystack editor) swaps the card for a placement, then opens the origin `.hwm` in a macro tab holding the instance's contents, unsaved. The user's Save writes the file and the ordinary reload updates every placement. It is greyed out when the macro is not installed, on a read-only install, or while its macro tab has unsaved edits, and it warns when the template's hash differs from `origin.hash` (the macro changed since the detach). It does not drop edges: connections to newly added pins re-bind after the save's reload.
  - **Save new Macro…** (formerly "Promote to Macro…") writes a new `.hwm` without an origin.
- **Update Macro writes through the macro tab's Save, never itself.** The tab already owns write, validate and reload; a second writer would bypass its unsaved-edit guard.
- **Undo restores the card and never touches files.** Undoing an Update Macro leaves a saved `.hwm` as saved, exactly as Promote already behaved.

**Considered options.**

- *Edit the interior in place, writing through to the macro.* Rejected: every other placement would change under the user's hands, and the lock exists to prevent that.
- *Origin as a reference only (no hash).* Rejected: Update Macro could not tell that the macro had moved on since the detach.
- *Update Macro writing the file directly.* Rejected: see above; it bypasses the macro tab's unsaved-edit guard and validation.
- *Dropping edges to new pins on Update Macro.* Rejected: they re-bind after the reload, so dropping loses connections for nothing. Revert is different: the template will not gain those pins.

**Consequences.**

- Amends [ADR 0038](0038-a-placements-interior-is-runtime-state.md): Edit Instance is now built; the refusal remains for deeper levels.
- Old files without `origin` load as plain Groups: no verbs beyond Save new Macro.
- Update Macro on a stale origin is the user's call; the warning is the only guard.
- The hash is evidence of change, not a lock: two edits of the same macro can still conflict at the macro tab's Save, which is its existing behavior.
