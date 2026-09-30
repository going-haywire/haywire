---
name: propagation-mode-replaces-is-lazy
description: An edge's delivery timing is one Propagation mode — lazy, eager or immediate — replacing the is_lazy flag; immediate is locked by the flow type and a promoted outlet's edges are locked lazy
status: accepted
see-also: ADR-0014, ADR-0033, ADR-0036
level: architectural
---

# An edge's delivery timing is one Propagation mode, and some modes are locked

**Context.** An edge carried one flag, `is_lazy`, while the timing of a delivered value depended on more: whether the pipe pushes or pulls, whether the receiving port acts on the value at once (callback inlets did, through a cached `_is_callback`), and an override behind the user's back — edges out of a promoted outlet were forced lazy in `_refresh_pipes`, so switching one to eager in the menu was silently undone. Letting callbacks pass through reroutes added a case the flag could not express safely: a lazy edge into a reroute never delivers, because nothing on a callback path executes to pull it.

**Decision.** `Edge.is_lazy` becomes `Edge.propagation`, one of three `Propagation` values:

- **lazy** — the inlet pulls the outlet's current value when its node executes;
- **eager** — pushed on write, takes effect when the inlet's node executes;
- **immediate** — pushed on write and takes effect on write.

The fourth combination, pulled but acting at once, has no meaning, so one axis describes delivery completely.

Users choose lazy or eager. Two modes are **locked**, derived when asked and never read from a saved graph: `immediate` on an immediate flow (`FlowType.is_immediate`, only `CALLBACK` today), and `lazy` on an edge out of an `is_linked_lazy` outlet (every promoted outlet, ADR 0014). `EdgeWrapper.locked_propagation` names the lock; choosing `immediate`, or any mode on a locked edge, raises. Both edge panels show a locked mode read-only. A saved graph stores only the chosen mode, under `propagation`.

**Alternatives.** *Keep `is_lazy` and hide the toggle on callback edges* — smaller, but it adds a second silent override next to the promoted one, and EdgeKind would inherit a boolean that cannot name the callback case. *Let users choose `immediate` on DATA edges* — live updates, but `on_change` would fire on DATA nodes outside the scheduler frame, which is what ADR 0014 locks promoted outlets lazy to avoid.

**Consequences.**

- Saved graphs carry `propagation`; an older graph's `is_lazy` is ignored and its edges load eager. No migration.
- Farmhand `query_graph` detail reports `propagation` and `propagation_locked` instead of `is_lazy`.
- Copy/paste and Subgraph instantiation create edges eager, as they did before; locks apply to them as to any edge.
- EdgeKind can declare its allowed and locked modes per kind; a visual-only kind may allow none.
