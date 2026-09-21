---
name: a-placements-interior-is-runtime-state
description: A macro placement's interior is never serialized and is keyed by the card's node id, so the template file is the only copy of the definition; a reload is absorbed in place rather than rebuilt, which is what keeps port values, the label and surviving edges
status: accepted
see-also: ADR-0036, ADR-0037
level: architectural
---

# A placement's interior is runtime state

**Context.** ADR 0037 makes a macro a node kind whose component is a file, so a
save of that file reaches every placement through the ordinary per-key reload
relay. This record settles what a placement *is* between those saves: where its
interior lives, what the host file carries, and what happens when the event
arrives.

A **placement** is one card standing for a macro in a host graph. Unlike a Group,
whose Subgraph is its own and lives in the same `.haywire` file, a placement
stands for a definition that many cards share — as a template, never as an
object.

## Two things the naive shape gets wrong

**Sharing one interior between placements.** A `SubgraphDefinition` holds its
nodes **live**: the wrappers in `node_wrappers` are the same objects the canvas
draws and the VM executes. Two cards pointing at one definition would therefore
be two cards over one set of running nodes, with one set of port values and one
error location. Each placement must instantiate its own.

**Taking the generic rebuild on reload.** On `NODE_HOT_RELOADED` the validator
calls `node_wrapper.build()` with no `node_info`, which runs `init()` afresh: port
values, `props` — the user's label — and the store are gone, and only position
and edges survive, the latter rebinding by port id. That is deliberate for a node
class, because `_initialize_from_dict` restores the *serialized* port set without
calling `init()`, so carrying state across a class reload would hide an author's
new ports. Applied to a placement it is simply destructive: every value the user
typed into a macro card would reset on every save of the macro file, which is the
one moment the user is most likely to be iterating on it.

## Decision

**A placement's interior is never serialized, and its key is derived from the
card's node id.**

`MacroNode.subgraph_key` returns `macro_<node_id>` and never reads the store. A
derived key cannot be copied onto a second card, so pasting a placement yields a
second interior rather than two cards sharing one — the invariant holds by
construction rather than by a check. `bind_subgraph` raises: there is nothing to
bind, the key is already decided.

`SubgraphDefinition.template_key` marks a definition as instantiated from a
template, and `BaseGraph.to_dict` skips every marked entry. The host file
therefore carries the placement exactly as it carries any node — registry key,
position, the mirrored `ports` block with its values, `props` — and carries no
interior at all. On load, `post_init` instantiates the interior from the live
template and reconciles the restored pins against it, which is the path a Group
already takes.

**A reload is absorbed in place, never rebuilt.** `BaseNode.on_class_reloaded()`
returns `False` by default, and `NodeWrapper` consults it first on a successful
lifecycle event, returning early when it answers `True`. `MacroNode` answers
`True`: it swaps the definition — removing the old one from the host table and
instantiating the new template under the same derived key — and calls
`reconcile_interface()`, the funnel every interface change already goes through.
Values, the label and edges on surviving pins are untouched because nothing
touched them; a pin that is gone drops its edges to the ghost pin.

## Consequences

- **The file is the only copy of the definition.** A placement can be
  reconstructed from the host file plus the template, and never from the host
  file alone. A macro whose library is absent loads its placement as the error
  node, from the pins the host file restored.

- **A reload is not an undo subject** — not an action, no fence. The interface is
  owned by the template, so undoing past a reload cannot resurrect a pin that the
  template no longer has, and the undo stack is unchanged by a save of the macro
  file.

- **Lost connections report themselves.** An edge whose pin vanished fails formal
  validation with "Ports not found" and logs into the error ledger with its
  `edge_id` and `graph_id`. The cross-graph report a fan-out needs already
  existed; nothing macro-specific reports it.

- **The label write-back is Group-only.** A Group's card renames its Subgraph
  because it is the only card standing for it. `MacroNode._on_label_changed` is a
  no-op: renaming one placement must not rename the interior of every other
  placement of the same macro.

- **A placement's displayed identity is its template's**, not its class's. Every
  placement of every macro is an instance of one `MacroNode` class, whose class
  identity says only "Macro", so `identity` is overridden to return the
  template's — falling back to the class identity when the template is absent.

- **`_is_graph_node` is cleared explicitly on `MacroNode`.** Identity flags are
  inherited, and leaving it set would make a placement the registry's Graph-node
  — so collapsing a selection into a Group would build a macro card instead.

- **Descending into a placement is refused**, and opens the macro document
  instead. There is nothing in the interior a user may edit in place: it is
  rebuilt from the template on the next load or save. Looking inside a running
  placement waits on a read-only editor mode.

- **Promotion writes a file and swaps a card, in one undoable group.** "Promote to
  Macro…" writes `<library>/macros/<Name>.hwm`, registers it synchronously — the
  watcher's later CREATED is a no-op by content hash — then removes the Group card
  and its definition and creates a placement at the same position, edges
  re-attaching by pin id. Undo restores the Group; the file stays, because a file
  on disk is not the undo stack's to remove.
