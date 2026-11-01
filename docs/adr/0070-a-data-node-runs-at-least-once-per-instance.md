---
name: a-data-node-runs-at-least-once-per-instance
description: A data node runs its worker on its first execution after it is created, then only when a port is dirty; creation marks nothing dirty and fires no on_change
status: accepted
see-also: ADR-0066
level: framework
---

# A data node runs at least once per instance

**Context.**

- A data node runs its worker only when a port is dirty; a clean node returns without running, keeping the outlet values from its last run.
- Dirty ports are runtime-only. Every creation path leaves a node clean: adding it, loading a file, paste, a rebuild (hot-reload, rejig) and undo.
- A node whose inlets are all unlinked, or that has none, was therefore never dirtied this session and never ran. Its outlets kept their defaults: a Resolve Model node loaded from a saved graph showed no size, and downstream nodes read the defaults.
- A node wired to a source ran only because the source's write dirtied its inlet, which hid the gap.

**Decision.**

- A data node runs its worker on its first execution after it is created, then only when a port is dirty.
- The first run is recorded per node instance, once the worker has returned. A worker that raises leaves the node due, so it runs again at its next execution, whether or not `_fail` re-dirtied an inlet (ADR 0066 D1).
- Creation marks no port dirty and fires no `on_change`: the first run resolves only what is already dirty.
- A rebuild creates a new instance, so the node runs once more.

**Considered.**

- *Mark every inlet dirty when the node is created (`NodeWrapper._initialize`).* The first drain then fires each inlet's `on_change` with no change behind it, which can trigger spurious reactions such as port rebuilds, and it misses ports a `rejig` adds later. Suppressing the callbacks needs a second flag, which is this decision with more machinery.
- *Run every data node on every frame.* Gives up the lazy evaluation that keeps unchanged nodes from recomputing.

**Consequences.**

- Each data node runs one extra time after load, paste, undo or rebuild, even when its outlets already held the right values. Workers must tolerate that run.
- A data node that only reads state outside its ports (a file, the clock) is evaluated once and then stays put until a port is dirty; that is unchanged.
