# Lock

`haybale-graph-editor:panel:LockToolbarPanel` · kind: panel

## Details

- **surface**: `toolbar`
- **order**: `27`

## Notes

Lock or unlock ONE node — protection against accidental manipulation.

**Single-selection only, deliberately.** Unlike its neighbours, this panel
polls: locking is never applied to a group. That is what spares the design
a mixed-state rule — with no way to lock a set, a set is never partly
locked, so the button has exactly two states to render instead of three.
The cost is accepted: there is no bulk unlock, on the expectation that
locking is a rare, deliberate act on a few precious nodes.

Reads ``active_node`` (the Active axis — the inspector subject) rather than
the Selection axis its siblings act on, and writes ``props.locked``
directly: a plain prop write, NOT an undoable action. Ctrl-Z must never be
able to silently strip protection an undo was not aiming at.

A locked node refuses drag and resize in canvas.vue (which reads the
``data-node-props-locked`` attribute UINode stamps) and is skipped by
delete. Nothing marks the card at rest — locked is a protection mechanism,
not a display state; the missing resize gadget is the signal once you
select it.

**Icon and tooltip report the STATE**, unlike CollapseToolbarPanel beside
it, which names the action its next press performs. The two differ because
the buttons answer different questions: a fold is a gesture you repeat
while reading, so "what will this do?" is what helps; a lock is a standing
condition you glance at, so "what is true now?" is. A closed padlock
meaning "click to lock" would also read backwards against every padlock a
user has met. What both buttons keep is icon and tooltip agreeing.
