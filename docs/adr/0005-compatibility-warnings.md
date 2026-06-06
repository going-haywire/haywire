# Compatibility Warnings are advisory-only, append-only, and node-keyed

**Context.** Graphs are deserialized purely from the saved spec; node `init()`
is not re-run on load (`NodeWrapper._initialize` calls `_initialize_from_dict`,
not `init()`). So any code-defined port attribute absent from an older file
silently reverts to its dataclass default — e.g. an inlet's `show_widget`
strategy reverting from `WHEN_LINKED` to `NOT_LINKED`, hiding its widget.

**Decision.** We surface, but never auto-fix, this drift. A library author
declares an APPEND-ONLY history of `CompatibilityWarning` entries on its
`BaseLibrary`; on load, a stateless `CompatibilityChecker` compares each node's
SAVED `library.version` against each warning's explicit `version` and, on
`saved < version`, attaches an advisory `NodeWarning` (per-node badge) or a
graph-level library-wide notice (on-open summary). The existing Reset Node
action (full `init()` rebuild) is the suggested — not promised — remedy.

**Why not auto-migrate.** Ports can be created dynamically, outside `init()`.
Re-running `init()` on load to "correct" attributes would drop those dynamic
ports and their wiring — data loss. And a stranded value may be exactly what
the user intends. There is no sound automatic reconciliation, so the feature
is strictly read-only.

**Why explicit, append-only versions.** The version a change landed in is a
historical fact; deriving it from the library's current version would re-date
every entry on each release and break the `saved < version` trigger for users
who saved in between. Entries are therefore never removed or re-dated.

**Consequences.** Re-saving an old graph silences the warning by advancing the
saved version without fixing the underlying value — accepted: the warning's
contract ends at *surfacing*; fixing is the user's judgement (Reset, or leave
as-is). Nodes gained a `warnings` channel on `NodeWrapperState`, closing a
prior asymmetry with `EdgeWrapperState`.
