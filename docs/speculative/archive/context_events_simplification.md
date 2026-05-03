# Speculative: rethinking `ContextChangedEvent` and `ContextChangeType`

> Status: speculative analysis, no code changes proposed yet.
> Audience: anyone who will design a new editor or touch the workspace
> orchestration layer.
> Date written against branch `code_refactoring_squashed`.

## 1. The job we are actually doing

Strip everything else away and the AppShell does one thing:

> **"Something in the world changed. Decide which editors need to redraw,
> and reveal the editor that should now be in front."**

Two observations follow from that single sentence:

1. The shell is a **broadcast bus** (one writer fans out to N readers).
2. The thing being broadcast is **a hint that some part of `SessionContext`
   moved**, not a free‑form domain event.

Everything in `context_events.py` and `context.py` should serve that
sentence. The current design serves it, but with significant accretion.

---

## 2. What the code actually does today

### 2.1 The two parallel things `SessionContext` carries

When you read [context.py](../../../packages/haywire-core/src/haywire/ui/context.py)
the fields fall into two distinct families that aren't named or grouped:

| Family | Fields | Lifetime |
| --- | --- | --- |
| **Selection / cursor** — what the user is pointing at right now | `active_node`, `active_edge`, `active_port`, `selected_nodes`, `selected_edges`, `context_menu_trigger` | transient, mouse-scale |
| **Workspace cursor** — what the user is currently looking at | `active_graph`, `active_graph_path`, `active_file`, `active_library`, `active_component`, `active_workbench_theme_key`, `active_node_theme_key`, `workspace_name` | session-scale |

This is a **navigation state vs. selection state** split that the type
system never makes explicit. They live in the same dataclass, get mutated
by the same setters, and travel through the same event stream — but the
editors that care about each family are almost completely disjoint.

### 2.2 The ContextChangeType enum, regrouped by what it actually announces

The 14 enum values fall into four clusters when you sort by *who emits
them and what they really say*:

#### Cluster A — "Navigation: the user moved to a different thing"

- `ACTIVE_GRAPH_CHANGED` — switched graph
- `FILE_SELECTED` — switched file
- `ACTIVE_COMPONENT_CHANGED` — switched library component
- `LIBRARY_STATE_CHANGED` — library list / selection changed (overloaded; see §3)
- `EDITOR_FOCUSED` — used purely as a "please reveal the following editor"
  sentinel; nothing about the change-event itself is about focus

#### Cluster B — "Selection: the user is pointing at a different sub-thing"

- `SELECTION_CHANGED` — node/edge selection in the canvas

#### Cluster C — "Underlying data was mutated"

- `DATA_MUTATED` — graph contents changed, redraw whatever depends on graph data
- `GRAPH_REMOVED` — special case: a graph entry was deleted; close its tabs

#### Cluster D — "UI shell event, not really 'context' at all"

- `WORKSPACE_CHANGED` — a tab was clicked / icon-slot switched
- `WORKBENCH_THEME_CHANGED` — visual theme swap

The clusters do not share consumers. **Properties** subscribes to A+B+C
but not D. **CodeEditor** subscribes only to D
(`WORKBENCH_THEME_CHANGED`). **GraphCanvasManager** subscribes to nothing
context-event-wise — it has its own internal Vue event bus.

### 2.3 What the `ContextChangedEvent` fields are really doing

```python
change_type: ContextChangeType
detail: Optional[Any] = None
reveal_editor: Optional[str] = None
reveal_payload: Optional[str] = None
reveal_label: Optional[str] = None
```

| Field | Real role today |
| --- | --- |
| `change_type` | Reader's filter ("is this for me?") |
| `detail` | **One real consumer:** `_handle_graph_removed` reads it for the entry id. Everywhere else it carries either `entry` or `path` redundantly with what is already on `SessionContext` |
| `reveal_editor` | A *command* ("open this editor"), tunneled through an event |
| `reveal_payload` | Disambiguator for multi-instance editors, only meaningful with `reveal_editor` |
| `reveal_label` | Display label for a newly created tab, only meaningful with `reveal_editor` |

So three of the five fields exist solely to support the **reveal-this-tab**
operation, not to describe what changed. The event is structurally
two events stapled together.

---

## 3. The smells

### 3.1 The enum is a mix of *axes*

Look at what each value answers:

- `ACTIVE_GRAPH_CHANGED` answers **"which session-context field moved?"**
- `WORKSPACE_CHANGED` answers **"which UI surface moved?"**
- `DATA_MUTATED` answers **"is the underlying data fresh?"**
- `EDITOR_FOCUSED` answers **"please switch the active tab"**

Four different *kinds of question* are crammed into one enum.

### 3.2 `EDITOR_FOCUSED` is a misnomer

It is **never about focus**. Every emit site of `EDITOR_FOCUSED`
([file_browser.py:316](../../../barn/haybale-studio/haybale_studio/editors/file_browser.py#L316),
[haystack_editor.py:620](../../../barn/haybale-studio/haybale_studio/editors/haystack_editor.py#L620),
etc.) carries `reveal_editor=...`. It's the sentinel "I have nothing
new to say about context, but please switch tabs to *X*". It would
be honestly named `REVEAL_EDITOR` — or, better, not be a context-change
type at all (see §4).

### 3.3 `WORKSPACE_CHANGED` is the same idea from the other direction

The slots themselves emit `WORKSPACE_CHANGED` after a tab click. Nobody
in `barn/` subscribes to it; only the slot-test suite does. Its real job
is to drive a "the active wrapper just changed; let it redraw if it
wants" handshake, but it is shaped as an event when really it should be
a **focus lifecycle hook on the wrapper**, which the codebase already
has via `BaseEditor.on_focus`.

### 3.4 `LIBRARY_STATE_CHANGED` is overloaded

`LibraryBrowserEditor._select_library`
([library_browser_editor.py:245](../../../barn/haybale-studio/haybale_studio/editors/library_browser_editor.py#L245))
fires `LIBRARY_STATE_CHANGED` for **two different things**: "user
clicked a library row" (selection) and "library was installed/enabled"
(data mutation). Subscribers can't tell them apart and have to redraw
on both. This is exactly the conflation that `DATA_MUTATED` vs.
`SELECTION_CHANGED` keeps separate elsewhere.

### 3.5 The reveal payload tunnels through an event

`reveal_editor` / `reveal_payload` / `reveal_label` are **imperative
commands**, not observations. The shell handles them in
`_on_context_changed` *before* the per-slot poll loop
([shell.py:592-596](../../../packages/haywire-core/src/haywire/ui/app/shell.py#L592-L596)).
If you read the codebase as a newcomer, the orchestrator's first job is
"obey a command embedded in the event". That's a hint that the bus is
carrying two things.

---

## 4. A simpler story

The proposal below is *one* way to retell the same mechanism. It is
not the only way, and it deliberately doesn't propose new code yet —
the goal is to find the cleanest mental model first.

### 4.1 Two channels, not one

Stop calling everything a "context change". There are really two
different things flowing through the AppShell:

- **Signal channel** — observations. ``ContextSignal`` subclasses
  describe state moves on the session ("the world looks different
  now; if you depend on X, redraw"). Fan-out, idempotent, anyone
  may emit, anyone may subscribe.
- **Lifecycle channel** — commands. ``LifecycleCommand`` subclasses
  describe imperative mutations of the workspace tree (which editor
  instances exist, in which slot, which is in front). ``Reveal``
  brings an editor to the front; ``Close`` removes tabs bound to a
  payload. The shell is the only consumer; routing is per-command
  (Reveal is point-to-point, Close is fan-out across slots).

Today everything rides one struct (`ContextChangedEvent`) on one bus.
Two channels with their own typed vocabularies make the categories
honest: signals have no command fields, commands have no
"what-kind-of-change-is-this" pretence.

The lifecycle channel is named after the *category* of operation
("editor lifecycle: create, reveal, close…") rather than after one
specific command. Today's vocabulary has only ``Reveal`` and
``Close``, but the shape is open: future commands like "minimize",
"split", "move to other slot" would slot in as additional
``LifecycleCommand`` subclasses without expanding the API surface.

### 4.2 Re-cut the vocabulary along a single axis: **what moved in `SessionContext`**

The vocabulary should let editors filter on *the field that moved*,
not on *the action that caused the move*. That gives a developer a
one-to-one mapping between session-context state and the signals
they subscribe to:

| Editor field of interest | Subscribes to signal |
| --- | --- |
| `active_graph` / `active_graph_path` | `ActiveGraphMoved` |
| `active_file` | `ActiveFileMoved` |
| `active_library` | `ActiveLibraryMoved` |
| `active_component` | `ActiveComponentMoved` |
| `active_node` / `active_edge` / selection sets | `SelectionMoved` |
| graph data (nodes, edges, props) | `GraphDataMutated` |
| installed library catalog | `LibraryCatalogChanged` |
| theme tokens | `ThemeMoved` |
| (entry removed) | `GraphRemoved` |

Naming signals "what's authoritative now" rather than "what action
just happened" makes them composable without overlap. You can
subscribe to any subset and never wonder whether
`LIBRARY_STATE_CHANGED` includes a selection click. The §7 design
takes this one step further by making each signal a typed dataclass
rather than an enum value, which is what unlocks the open
vocabulary; the table above is the *core-declared* set (see §7.5,
§11 for the per-enum-value derivation).

`WORKSPACE_CHANGED` and `EDITOR_FOCUSED` are not in the table —
they describe UI shell events, not session-context state moves, and
re-home onto other channels (§4.3).

### 4.3 Re-home the orphans

| Today | Proposed home |
| --- | --- |
| `EDITOR_FOCUSED` | becomes a ``Reveal`` lifecycle command, no signal |
| `WORKSPACE_CHANGED` | drop; `BaseEditor.on_focus` already fires (verified §5) |
| `LIBRARY_STATE_CHANGED` | split: selection click → `ActiveLibraryMoved`, install/enable/disable → `LibraryCatalogChanged` (`cross_session=True` — see §11) |
| `GRAPH_REMOVED` | split: ``GraphRemoved`` (cross-session signal, payload-less observation) + ``Close(payload=entry_id)`` (local lifecycle command). Together these give the originating session local tab-close + peer sessions an observation to refresh haystack-derived views. |

### 4.4 Shrink `ContextChangedEvent` to its actual payload

The base `ContextSignal` is empty — concrete signal classes derive
from it (see §7.1 for the real shape). The discriminator is *the
type itself*, not a field on a single dataclass. The four
reveal-related fields drop entirely:

- `reveal_editor` / `reveal_payload` / `reveal_label` — they belong
  on lifecycle commands (``Reveal``), not on signals
- `change_type` (the enum field) — replaced by the typed signal
  class, filtered with plain `isinstance` (§7.4)
- `detail` (the typed-nothing payload) — gone; signals are
  pointer-only by default (§6.3). When `GRAPH_REMOVED` previously
  used `detail` to carry an entry id, that information now lives on
  the ``Close(payload=entry_id)`` lifecycle command emitted alongside
  the (payload-less) ``GraphRemoved`` signal.

The shell's orchestrator splits cleanly:

```text
session.signal(ContextSignal(...))         →  fan out to slots
session.lifecycle(LifecycleCommand(...))   →  route per-command type
                                              (Reveal: point-to-point;
                                               Close: fan-out)
```

#### Ordering: signal before lifecycle

The two methods are deliberately separate; there is no batched
`dispatch(...)` API. Authors who want a state change to be visible to
a freshly-revealed editor call them in order:

```python
context.active_graph = entry.graph
context.active_graph_path = entry.path
session.signal(ActiveGraphMoved())
session.lifecycle(Reveal(editor=GraphEditor, payload=entry.entry_id))
```

Or, for a remove flow:

```python
session.lifecycle(Close(payload=removed_id))   # close my tabs
session.signal(GraphRemoved())                 # tell peers to refresh
```

The contract:

- `session.signal(...)` runs fan-out **synchronously** to every
  subscribed slot in the current session, then returns. The subsequent
  `session.lifecycle(...)` therefore observes the post-signal context.
- A revealed editor's `draw()` runs against the post-signal context
  — same as today's accidental ordering in `shell.py:591-595`, made
  explicit.
- **Cross-session delivery is asynchronous in spirit and best-effort
  sequential per peer** (`session_manager.py:99-105` iterates peers
  and swallows per-peer exceptions). Authors must not assume any
  ordering between a `cross_session=True` signal arriving at a peer
  and any other event in that peer's session.
- **Lifecycle commands are local-only.** ``Reveal`` and ``Close`` do
  not cross session boundaries (Q4A). A peer session is responsible
  for its own workspace state; one session cannot reach into
  another's tab order. Cross-session synchronization of "the
  underlying entity is gone, react accordingly" is the job of the
  signal channel (e.g. ``GraphRemoved``).

### 4.5 Naming `SessionContext`

The dataclass carries two families of fields (§2.1: workbench focus
and live selection). Considered nesting them into `workbench` /
`selection` sub-objects, but rejected — the typed signal vocabulary
in §4.2 / §7 already encodes the split (a reader who understands
`ActiveGraphMoved` vs `SelectionMoved` already understands the
distinction), and nesting would add an access-site hop everywhere
for a benefit that's pure documentation.

### 4.6 The story you tell a new editor author

After the rework, the developer-facing pitch fits in a paragraph:

> **An editor is a function of `SessionContext`. When the workbench
> moves (different graph, different file) or the selection moves
> (different node/edge), the shell sends a ``ContextSignal`` so you
> can redraw. Subscribe to the signals whose fields you read; ignore
> the rest. If you want to mutate the workspace tree itself — bring
> an editor to the front, close tabs bound to a removed entity —
> send a ``LifecycleCommand`` (``Reveal`` / ``Close``). Signals are
> observations; lifecycle commands are imperatives. They live on
> separate channels so neither can pretend to be the other.**

Compare to today's pitch, which has to explain a 14-value enum where
most values overlap, three values are unused, two values are commands
masquerading as observations, and one value (`LIBRARY_STATE_CHANGED`)
means two different things depending on emit site.

---

## 5. What stays exactly the same

The mental model and runtime mechanism are unchanged; only the
vocabulary tightens. The LOC scope is non-trivial (see §11 for the
full migration surface), but every site is touched in a mechanical
way — no behavioural change is expected outside the two
flagged latent-bug fixes (§11 notes for `LibraryCatalogChanged` and
`GraphRemoved`). Specifically:

- The poll/draw cycle on `BaseEditor` is unchanged.
- The slot orchestration in `AppShell._on_context_changed` is
  unchanged in shape — it just splits into ``_on_signal`` (fans
  ``ContextSignal`` to slots) and ``_on_lifecycle`` (routes
  ``Reveal`` / ``Close`` to the appropriate slot or fan-out helper).
- Cross-session broadcast (`Session.notify_cross_session_context_change`
  → `SessionManager.broadcast`) is unchanged. It only ever needed to
  carry *signals*, not commands; this is already true today (no caller
  cross-broadcasts a lifecycle command).
- `BaseEditor.on_focus` already exists and already does the
  "wrapper just became active" job that `WORKSPACE_CHANGED` was trying
  to express. Verified against `Slot._activate` (slot.py:499-505),
  which is the sole path to setting the active wrapper and
  unconditionally calls `wrapper.on_focus()`. Every activation route
  — initial render (slot.py:441-446), `switch_to` (slot.py:532, used
  by both user tab clicks and programmatic reveals via
  `shell._reveal_editor`), and `add_binding(activate=True)` — goes
  through `_activate`. Today's `WORKSPACE_CHANGED` emission in
  `tab_slot._on_tab_clicked` (lines 114-116) fires *after* `switch_to`
  has already run, so dropping the bus event loses no behavior.
- All the emit sites stay where they are — they just emit smaller,
  more honestly-named structs.

Mechanically nothing changes. The mental model is what gets simpler.

---

## 6. Multi-actor signals

The §4 model implicitly assumes one authoritative state per session.
Haywire's collaboration story already breaks that assumption — multiple
sessions share one `BaseGraph`, edits propagate via
`notify_cross_session_context_change` → `SessionManager.broadcast`
(absorbed into the unified bus by Q9B + Q2C, see §6.2) — and
plausible future directions (peer cursors, follow-mode, presence
indicators, conflict-aware undo) push it further.

The structural fact those features share:

> A signal from session B is meaningful to session A's editors, but it
> describes session B's state, not session A's.

A field-named signal model breaks here without help. `SELECTION` on
session A's bus today means *my* selection moved, and an editor
filtering on it expects to read `context.selected_nodes`. If a
peer-cursor library starts firing `SELECTION` for peer events, every
existing subscriber misreads it.

### 6.1 Signals carry a subject

The fix is to make the implicit explicit. Every signal names *whose*
state moved:

```python
class Subject:
    SELF: ClassVar["Subject"]      # this session — default for local-bus signals

    @classmethod
    def peer(cls, session_id: str) -> "Subject":
        # stamped by the transport on cross-session delivery; never
        # set by emit sites
        ...
```

Two subject values, both meaningful: `SELF` for signals delivered to
the session that emitted them (and the default for purely local
signals), `peer(id)` for signals that arrived from another session.
**Emit sites never set the subject** — the transport stamps
`peer(origin_id)` on signals delivered to non-origin sessions during
cross-session fan-out (see §6.2 for routing). A peer-aware editor
opts in explicitly:

```python
class PeerCursorEditor(BaseEditor):
    def poll(self, context, signal):
        # Only react to peer selection signals; ignore my own.
        return isinstance(signal, SelectionMoved) and signal.is_from_peer()
```

(`is_local` and `is_from_peer` are predicates on `ContextSignal`
itself — see §7.4. There is no `is_a` predicate; plain `isinstance`
is the recommended idiom — Q3A.)

### 6.2 Why this works

1. **Existing editors keep working.** Without an explicit subject filter
   they implicitly mean "self" — which is what they already mean today.
   No subscriber accidentally renders a peer's selection as their own.
2. **Cross-session fan-out becomes a property of the signal class**,
   not a separate transport method or a per-emit choice. Today there
   are two parallel APIs (`notify_context_changed` and
   `notify_cross_session_context_change`); tomorrow each signal class
   declares `cross_session=True` or `False` once, and routing is
   derived from that:
   - signal class `cross_session=False` → local fan-out only; the
     emitting session's subscribers receive `subject = SELF`
   - signal class `cross_session=True` → local fan-out *and*
     transport-stamped peer delivery; the emitting session receives
     `subject = SELF`, every other session receives `subject = peer(origin_id)`
3. **`SessionContext` doesn't grow a `peer_selections` dict.** Peers
   expose their own context through the `SessionManager`; the signal's
   subject identifies whose, and editors traverse to peer state when
   they care.

### 6.3 Inline state vs. pointer

Signals are pointers, not inline payloads — universally. Today's
`DATA_MUTATED` broadcast carries no graph data; receivers re-read
the shared `BaseGraph`. The new vocabulary follows the same rule
across the board: every core signal is empty (or carries only a
``subject``). A peer-cursor signal says "go look" rather than
carrying the new selection inline. Editors that care fetch from
`session_manager.get(peer_id).context`.

Inline payloads couple the wire format to the sender's data model
and break the moment a library adds new fields to its peer-visible
state. Pointer is more flexible and matches the existing pattern.

**No exceptions in the core vocabulary.** Earlier drafts of this doc
proposed ``GraphRemoved(entry_id: str)`` as a one-off exception —
because the entry is gone from the haystack by the time the signal
fires, so a "go look" pointer would point at nothing. The lifecycle
channel resolves this cleanly: ``GraphRemoved`` becomes a
payload-less *observation* (peers refresh haystack-derived views
from their own ground truth), and the originating session emits a
separate ``Close(payload=entry_id)`` *lifecycle command* to close
its own tabs. Identifiers that are needed for routing live on the
command channel, not the observation channel.

### 6.4 What stays sealed

`Subject` is one of the few places where closing the vocabulary is
correct. Peers are sessions, sessions are managed by core, and a
library has no business inventing new subject kinds. `field` opens up
(see §7); `subject` does not.

### 6.5 Cross-session delivery semantics

The broadcast path is structurally identical pre- and post-migration
— Q9B (class-level routing) decides *whether* a signal crosses
session boundaries, but does not change *how* the
`SessionManager.broadcast` loop delivers it. Documenting today's
behaviour explicitly so authors don't read more into `cross_session=True`
than the loop provides:

- **Per-peer sequential, arbitrary peer order.** The broadcast loop
  iterates the session dict in dict-iteration order (effectively
  insertion order in CPython 3.7+, but not stable across reconnects).
  Peer A's `dispatch_signal` returns before peer B's begins. There is
  no fairness or priority — first peer in dict order goes first,
  every time, until session lifecycle shifts the order.
- **Per-peer exceptions are swallowed.** A subscriber raising in one
  session does not abort delivery to other sessions. The framework
  logs a warning and continues.
- **No cross-peer ordering guarantee.** If peer B's subscriber emits
  its own follow-on signal during its handling, that signal interleaves
  arbitrarily with the rest of the broadcast. Authors must not assume
  causal ordering across peers.
- **No response-awaiting.** Broadcast does not wait for peers to
  *finish* processing the signal before returning to the caller. A
  call site that emits then immediately reads peer state via
  `session_manager.get(peer_id).context` may observe pre-signal state
  on the peer side.
- **Subject is stamped by the transport, not the emitter.** Per Q2C,
  the broadcast loop sets `subject = Subject.peer(origin_session_id)`
  on signals delivered to non-origin sessions; the origin session
  receives the signal with `subject = Subject.SELF`. Emit sites stay
  subject-free.

**Known weak spot, flagged separately.** Per-peer exception swallowing
combined with warning-only logging means a subscriber that crashes on
every signal will produce a warning per signal but never surface as
an error. This is a pre-existing weakness of today's broadcast path,
not a migration regression — but worth revisiting once the open
vocabulary attracts heavier broadcast traffic (peer-cursor library,
collaboration features). Out of scope for the bus-split PR.

---

## 7. Open vocabulary — replacing the enum

The closed enum is incompatible with Haywire's plug-in story. A
`haybale-debugger` library that adds an `active_breakpoint` to the
session's effective context state has nowhere to land its signal —
it can't rebuild core to add an enum value, and shouldn't have to.

Three options were considered. For Haywire's specific shape, **typed
signal classes** fit best.

### 7.1 The shape

```python
@dataclass(frozen=True)
class ContextSignal:
    subject: Subject = Subject.SELF
    # cross_session is a class-level attribute, not an instance field
    # — the transport reads it from type(signal) to decide routing
    cross_session: ClassVar[bool] = False

@dataclass(frozen=True)
class ActiveGraphMoved(ContextSignal):
    pass

@dataclass(frozen=True)
class SelectionMoved(ContextSignal):
    # No payload: subscribers read context.selected_nodes / active_node
    # for SELF, or session_manager.get(peer_id).context for peer subjects
    # (§6.3 pointer rule).
    pass

@dataclass(frozen=True)
class GraphDataMutated(ContextSignal):
    cross_session: ClassVar[bool] = True

@dataclass(frozen=True)
class GraphRemoved(ContextSignal):
    # The §6.3 inline-payload exception: the entry is gone from the
    # haystack by the time this fires, so a pointer would point at
    # nothing.
    entry_id: str
    cross_session: ClassVar[bool] = True

# A library declares its own:
@dataclass(frozen=True)
class ActiveBreakpointMoved(ContextSignal):
    pass
```

Editors filter by class with plain `isinstance` (Q3A — no `is_a`
predicate):

```python
def poll(self, context, signal):
    return isinstance(signal, (SelectionMoved, ActiveGraphMoved, GraphDataMutated))
```

### 7.2 Why typed classes, not strings or per-concern events

- **String keys with a registry** keep the stringly-typed problem the
  enum already has: typo-prone, no payload typing, no IDE autocomplete.
  The registry becomes documentation only — and documentation we'd
  have anyway via the class hierarchy.
- **One typed event per concern** (VS Code's `onDidChangeX` / `onDidChangeY`)
  is the purest model but loses the **single linearized bus** that
  makes recording/replay, audit logging, and peer broadcasting
  straightforward. It also adds a lot of wiring per library — Haywire's
  libraries are meant to be cheap to write.
- **Typed classes** match how the rest of Haywire already works:
  events in `event_definitions.py` are typed dataclasses, settings
  descriptors are typed objects, nodes are typed classes. A signal
  class hierarchy is the same pattern, applied to one more place.

Library authors declare their own signal classes alongside their
library's nodes, settings, and themes — same authoring pattern they
already know.

### 7.3 Hot-reload and class identity

`isinstance` interacts with hot-reload, but the failure surface is
narrower than it first appears. The thing that breaks `isinstance` is
**reloading the signal class itself** while subscribers that imported
it stay loaded against the old class object. Reloading the *editor* or
the *emitter* doesn't break anything — both re-resolve the import on
load, landing on whichever class object is current.

That gives three cases, only one of which is a problem:

| Case | What reloads | `isinstance` filtering |
| --- | --- | --- |
| Editor reloads, signal class doesn't | editor module | Fine — fresh import, same class object as the emitter uses |
| Both editor and signal class reload together | the whole library | Fine, as long as they reload in the same pass |
| **Signal class reloads, subscriber doesn't** | only the signal-declaring module | **Breaks** — subscriber holds a reference to the old class |

Two consequences:

1. **Core-declared signals are entirely safe.**
   `SelectionMoved`, `ActiveGraphMoved`, `GraphDataMutated`, etc. live
   in `haywire-core`, which is not a hot-reload target. Plain
   `isinstance` works. Every editor in the codebase today filters on
   core-declared types only, so the §7.3 problem doesn't exist for the
   current vocabulary.

2. **Library-declared signals are safe within their own library.**
   When `haybale-debugger` reloads, both its `ActiveBreakpointMoved`
   class *and* the editors that filter on it reload in the same pass.
   The new editor binds to the new class on its fresh import; emit and
   filter both land on the same class object.

The only real failure case is **cross-library subscription**: a signal
class declared in library A, subscribed to by an editor in library B,
where A reloads without B. The fix is to make the dependency
explicit: a library that subscribes to another library's signal
classes must declare that library as a hot-reload sibling, so they
reload as a pair. The framework refuses (or warns on) cross-library
subscriptions without a declared dependency. This pushes the cost
onto the rare case (cross-library subscription) instead of taxing
every subscription site in the codebase with framework machinery
(Q3A — explicit dependency, not author-declared identity keys, not
qualified-name comparison).

### 7.4 Filter ergonomics

Plain `isinstance` is the recommended idiom (Q3A). Combined with the
subject predicates from §6:

```python
class ContextSignal:
    subject: Subject = Subject.SELF
    cross_session: ClassVar[bool] = False

    def is_local(self) -> bool:
        """True if this signal describes *this* session's state."""
        return self.subject == Subject.SELF

    def is_from_peer(self) -> bool:
        """True if this signal describes a peer session's state."""
        return self.subject != Subject.SELF
```

Filter sites read as the question they're asking:

```python
# Properties: redraw on local selection / graph / data changes.
def poll(self, context, signal):
    return (isinstance(signal, (SelectionMoved, ActiveGraphMoved, GraphDataMutated))
         and signal.is_local())

# PeerCursor: only peers' selections.
def poll(self, context, signal):
    return isinstance(signal, SelectionMoved) and signal.is_from_peer()
```

A few design choices worth being explicit about:

- **Signal classes are flat by convention.** One class per concern,
  no inheritance for specialisation between `ContextSignal` and the
  leaves. `isinstance` walks the MRO normally; subclassing a leaf
  signal *would* widen subscriptions, which is exactly the silent
  widening to avoid. Specialisation belongs in payload fields
  (`SelectionMoved(kind=...)` if needed), not in subclasses. Code
  review enforces this — the framework adds no machinery.
- **The class itself is the identity.** Subscribers and emitters
  share the same class object via normal Python imports. No
  framework-side identity registry, no qualified-name comparison —
  the cross-library hot-reload edge case from §7.3 is handled by the
  explicit-dependency rule, not by stripping `isinstance` of its
  natural semantics.
- **No `is_a` predicate.** Plain `isinstance` everywhere. The
  predicates that *do* live on `ContextSignal` (`is_local`,
  `is_from_peer`) ask questions about the *subject*, not the
  *class* — and those questions can't be answered by `isinstance`
  alone, which is why they exist.

### 7.5 What core declares vs. what libraries declare

Core declares **9 signal classes** (signal channel) and
**2 lifecycle commands** (lifecycle channel) for state core owns —
see §11 for the per-enum-value mapping that derives these from the
audit.

Signals (observations, all payload-less per §6.3):

- `ActiveGraphMoved`
- `ActiveFileMoved`
- `ActiveLibraryMoved`
- `ActiveComponentMoved`
- `LibraryCatalogChanged` (`cross_session=True`)
- `SelectionMoved`
- `GraphDataMutated` (`cross_session=True`)
- `GraphRemoved` (`cross_session=True`, payload-less observation —
  routing of "close my tabs" lives on the lifecycle channel)
- `ThemeMoved`

Lifecycle commands (imperatives, all local-only):

- `Reveal(editor, payload=None, label=None)` — point-to-point
- `Close(payload)` — fan-out across slots

This corrects an earlier draft that listed 7 signal classes — the
audit in §11 surfaced two additions: `LibraryCatalogChanged` (the
`LIBRARY_STATE_CHANGED` overload split per §3.4) and `GraphRemoved`
staying as its own class (rather than collapsing into
`ActiveGraphMoved`).

Libraries declare new signal classes when they add new context state.
Examples:

- `haybale-debugger`: `ActiveBreakpointMoved`, `DebuggerSessionAttached`
- A future `haybale-presence`: subscribes to existing signals with
  `subject != SELF`, declares no new signals (presence is a
  cross-cutting view, not new state)
- A future `haybale-versioning`: `BranchSwitched`, `MergeConflictRaised`

Each library's signal classes live in the library package alongside its
nodes — co-located with the state they describe.

---

## 8. Worked example: context menus

The graph-canvas context menu pipeline is the most tangled current
consumer of the bus, and it's a useful test of the new model — partly
because it exercises every problem the proposal is trying to fix, and
partly because cleaning it up surfaces a more general "popup scope"
pattern worth flagging.

### 8.1 What the pipeline does today

From [context_menu.py](../../../packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py):

1. User right-clicks. `SessionContextMenuProvider._open_menu` sets
   `context.context_menu_trigger = "canvas" | "node" | "edge" | "selection"`.
2. Builds a `Popup`, queries `PanelRegistry` for panels matching the
   trigger scope, draws them.
3. Stuffs callbacks and intermediate state into `context.metadata`:
   `on_emit_event`, `edge_state`, `pending_connection`,
   `context_menu_screen_pos`, `edge_reconnect_end`.
4. On close: clears `context_menu_trigger`, drains the metadata keys.

Panels themselves use the bus too —
[create_node_panel.py:64-70](../../../barn/haybale-core/haybale_core/panels/context_menu/create_node_panel.py#L64-L70)
sets `context.active_component`, fires `ACTIVE_COMPONENT_CHANGED`, and
attaches `reveal_editor=LibraryComponentEditor` to the same event.

### 8.2 Two problems, all instances of the §3 smells

1. **`metadata` is popup-internal state masquerading as session
   context.** Five of six `metadata` keys are popup ephemera; they live
   on `SessionContext` only because that's the object the panels
   receive. The dict is doing the job of "popup-scoped state" without
   a name for it.

2. **`create_node_panel.py` does three unrelated things in one event.**
   State mutation (`context.active_component = ...` already happened),
   observation (`ACTIVE_COMPONENT_CHANGED`), and command
   (`reveal_editor=...`) are all glued to one `notify_context_changed`
   call. The §3.5 conflation, in miniature.

### 8.3 What the new model gives them

**Move popup-internal state onto a typed scope object.** Instead of
panels reading `context.metadata['edge_state']`, they read a typed
field on a `ContextMenuScope`:

```python
@dataclass
class ContextMenuScope:
    trigger: Literal["canvas", "node", "edge", "selection"]
    screen_pos: tuple[float, float]
    on_emit_event: Callable
    pending_connection: Optional[PendingConnection] = None
    edge_state: Optional[EdgeState] = None
    edge_reconnect_end: Optional[str] = None
```

Panels receive `(context, scope)` instead of just `context`. The
five popup-ephemeral keys leave `metadata` entirely; `context_menu_trigger`
leaves `SessionContext` (it becomes `scope.trigger`). `SessionContext`
shrinks; `metadata` may end up containing only the one true
session-level UI key (`properties_scope`).

**Split panel emit sites along the §4 channels.** The
`create_node_panel.py` site becomes:

```python
context.active_component = node_info.identity.registry_key
context.session.signal(ActiveComponentMoved())
context.session.lifecycle(Reveal(editor=LibraryComponentEditor))
```

Three lines, three things, each named after what it actually is. A
reader new to the codebase can tell at a glance: *set state, announce
it, switch the right-hand tab.*

### 8.4 The pitch for a context-menu panel author, after the rework

> A context-menu panel is drawn into a `Popup`. It receives the session
> context (read-only background state) and a `ContextMenuScope`
> (popup-local state: what was right-clicked, where, which callbacks).
> If the panel mutates session state, it does so on the context and
> emits a signal naming the field that moved. If it wants to open
> another editor, it sends a ``Reveal`` lifecycle command. The
> popup's open/close is the popup's own lifecycle — not a signal
> anyone subscribes to.

Compare to today's pitch, which has to explain: that
`context_menu_trigger` lives on the context but is only meaningful
while a menu is open; that `metadata` is a typed-nothing dict
carrying popup callbacks; that panel emits combine state changes with reveal
commands; and that the popup pipeline is simultaneously a registry
lookup and a session-context mutation.

### 8.5 The follow-on: a general "popup scope" pattern

`ContextMenuScope` is one example of a more general shape — popup-local
state with its own type, passed alongside the session context to
children. The same shape would apply to other popups in the codebase:
the Save-As dialog, the rename dialog in haystack_editor, the
remove-confirm popup. Today they all carry their state in closures
and local variables (which works because they're short-lived) — but
the *pattern* of "ephemeral UI state that isn't session-scoped but
does need to be passed to children" doesn't have a name yet.

Formalising it isn't required for the bus split, but the bus split
is what makes the missing pattern visible: once popup state stops
hiding inside `metadata`, it becomes obvious that several popups
have the same shape and could share a name. Worth considering as a
follow-on once §6 / §7 land — see open question §9.4.

### 8.6 What the bus PR commits to (so §8 stays unblocked)

§8 is deferred to a separate refactor (Q7D), but the bus-split PR
will rewrite every panel's emit site from
`notify_context_changed(ContextChangedEvent(...))` to
`session.signal(...)` + `session.lifecycle(...)`. The context-menu
panels in `barn/haybale-core/haybale_core/panels/context_menu/` are
the overlap zone — they get touched by the bus PR *and* by §8 later.
To prevent double-touch and keep §8 a clean follow-up, the bus PR
commits to:

1. **Not change panel signatures.** Panels stay `(cls, context)` for
   poll/draw. The §8 PR is the one that adds the `scope` parameter.
2. **Not move popup-internal state.** `context.metadata` stays
   `dict[str, Any]` carrying the popup-ephemeral keys
   (`edge_state`, `pending_connection`, `context_menu_screen_pos`,
   `edge_reconnect_end`, `on_emit_event`). The §8 PR is the one that
   moves them onto `ContextMenuScope`.
3. **Co-locate signal+lifecycle at the call site exactly as §8 will
   leave it.** After the bus PR, the
   [create_node_panel.py:64-70](../../../barn/haybale-core/haybale_core/panels/context_menu/create_node_panel.py#L64-L70)
   site reads as the §8.3 example shows:

   ```python
   context.active_component = node_info.identity.registry_key
   session.signal(ActiveComponentMoved())
   session.lifecycle(Reveal(editor=LibraryComponentEditor))
   ```

   The §8 PR will rewrite signature/reads (replacing
   `context.metadata['x']` with `scope.x`), but these three emit
   lines stay byte-identical. No re-touch.

Together: the bus PR touches ~30 emit sites once, the §8 PR touches
~6 context-menu panels' read sites once — no overlap.

The remaining open question for whoever lands §8 is the panel
signature shape (one base class with `scope: Optional[ScopeBase] =
None` everywhere, vs. splitting `ContextMenuPanel(BasePanel)` from
non-popup panels). The bus PR does not commit to either — it leaves
§8 free to choose based on whether other popup types (§8.5) join the
pattern.

---

## 9. Open questions

1. **Are `active_workbench_theme_key` and `active_node_theme_key` really
   "session context"?** They're set once at session creation and
   replaced only on a settings event. They're more like host-state
   pointers. They could move out of `SessionContext` to a
   `SessionAppearance` carrier passed via DI — leaving `SessionContext`
   strictly about workbench focus and selection.

2. **Should `metadata: dict[str, Any]` survive?** It's currently used
   for: `properties_scope`, `on_emit_event`, `edge_state`,
   `context_menu_screen_pos`, `edge_reconnect_end`, `pending_connection`.
   Most of those are popup-internal; one (`properties_scope`) is true
   per-session UI state. The dict-of-anything is a typed-nothing escape
   hatch — worth auditing once the signal split clarifies what is
   actually session-scoped vs. interaction-scoped.

3. **Should ``Reveal`` carry a "create if missing" flag, or is
   that always-on?** Today the shell decides: TabSlot auto-creates
   on miss, IconSlot just switches. The behaviour is fine; the
   question is whether the lifecycle command should make it
   explicit.

4. **Is `ContextMenuScope` an instance of a more general "popup
   scope" pattern?** §8.5 notes that several other popups in the
   codebase (Save-As, rename dialog, remove-confirm) carry similar
   ephemeral state in closures and locals. After the bus split makes
   popup state stop hiding inside `metadata`, the pattern becomes
   visible. Worth a separate design pass once §6 / §7 are real — the
   shape is roughly *"typed scope object passed alongside
   `SessionContext` to popup children"*, and a shared base might be
   warranted, or the popups might stay independent and just follow a
   convention. Don't decide now.

### 9.5 Resolved during inquisition

These started as open questions and were settled during the design
review pass; recorded here so the rationale doesn't get lost.

- **Does `notify_cross_session_context_change` survive as a separate
  API?** No — absorbed into the unified bus (§6.2). Routing comes
  from the class-level `cross_session` attribute on the signal class
  (Q9B), not from a subject value at the emit site. Today's call
  sites are all `DATA_MUTATED` and migrate to
  `session.signal(GraphDataMutated())`; the transport stamps
  `subject = peer(origin_id)` on non-origin sessions (Q2C). One
  emit method, class-level routing, transport-stamped subjects.

---

## 10. TL;DR

The shape of the problem:

- `ContextChangedEvent` is two events glued together: an *observation*
  (`change_type` + `detail`) and a *command* (`reveal_*`).
- `ContextChangeType` mixes five different axes; two values are
  commands, one value is overloaded.
- `SessionContext` carries two distinct kinds of state (workbench
  focus and live selection) under one flat dataclass.

The simpler story:

- Split the bus into a **signal channel** (``ContextSignal``
  observations, fan-out) and a **lifecycle channel**
  (``LifecycleCommand`` imperatives — ``Reveal`` and ``Close`` are
  the two core commands; both local-only). Two separate methods on
  ``Session`` (``signal()`` / ``lifecycle()``); signal-then-lifecycle
  at the call site is the documented ordering contract (§4.4).
- Make signals **typed dataclasses**, not enum values, so libraries
  can declare their own without touching core (§7). Editors filter
  with plain `isinstance`; no framework identity machinery.
- Cross-session routing is a **class-level attribute**
  (`cross_session: ClassVar[bool] = False/True`) on each signal class
  (§6.2). The transport stamps the `subject` field on cross-session
  delivery — emit sites stay subject-free.
- Name signals after the **field that moved**, not the action that
  moved it. That gives an editor author a one-line subscription rule.
- Keep `SessionContext` flat. The signal vocabulary already encodes
  the workbench/selection split (§4.5).
- The vocabulary is open at exactly **one seam: the signal class**.
  Subjects (§6.4) and the bus topology stay sealed in core.

Mechanism unchanged; vocabulary tightened. The migration surface is
non-trivial in LOC but mechanical in shape — see §11 for the
enum→signal-class mapping that makes the rewrite reviewable.

---

## 11. Migration surface — enum → signal-class mapping

This section enumerates the concrete migration work. §5's "mechanically
nothing changes" is true at the architectural level but undersells the
LOC-level scope: every emit site of every enum value is touched, every
poll() filter is rewritten, and several editorial decisions per enum
value need to be made up front (not discovered during implementation).

The table below is the source of truth for those decisions. It is also
the verification of §7.5's claim that the core vocabulary covers every
existing emit site — that claim turns out to be off by two: the
LIBRARY_STATE_CHANGED split adds `LibraryCatalogChanged`, and
`GraphRemoved` stays as its own class (see notes), bringing the core
vocabulary to **9 signal classes + 2 lifecycle commands** (``Reveal``,
``Close``), not the 7 named in §7.5.

### 11.1 The mapping table

| Old enum value | New signal class(es) | Owning package | `cross_session` | Emit sites | Filter sites | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `SELECTION_CHANGED` | `SelectionMoved` | haywire-core | False | `graph_canvas/handlers/selection.py:78` (1) | `properties_editor.py:73`, `node_source_editor.py:56`, `library_component_editor.py:55` (3) | Per-session. Future peer-cursor library subscribes to `SelectionMoved` from peer subjects (Q1 open-vocabulary path) — `SelectionMoved` itself stays local-only. |
| `ACTIVE_GRAPH_CHANGED` | `ActiveGraphMoved` | haywire-core | False | `graph_editor.py:132,494`, `haystack_editor.py:366,481,584` (5) | `properties_editor.py:74`, `haystack_editor.py:85` (2) | Each session has its own active graph; multiple sessions may view different graphs simultaneously. |
| `EDITOR_FOCUSED` | (none — becomes ``Reveal`` lifecycle command) | haywire-core | N/A | `file_browser.py:316`, `haystack_editor.py:616,630,756,837` (5) | (none) | All emit sites carry `reveal_editor=...` (§3.2). Pure command, no signal. Replaced by `session.lifecycle(Reveal(editor=..., payload=...))`. |
| `WORKSPACE_CHANGED` | (deleted) | haywire-core | N/A | `tab_slot.py:115`, `icon_slot.py:116` (2) | (none in barn/) | Slot machinery calls `editor.on_focus()` directly instead (Q6A). |
| `DATA_MUTATED` | `GraphDataMutated` | haywire-core | True | `graph_editor.py:307,321,359,502`, `haystack_editor.py:928`, `haystack.py:169` (6 — all today already use `notify_cross_session_context_change` or `session_manager.broadcast`) | `properties_editor.py:75`, `haystack_editor.py:86` (2) | Class-level `cross_session=True` matches today's existing broadcast behavior exactly. |
| `LIBRARY_STATE_CHANGED` | **split:** `ActiveLibraryMoved` + `LibraryCatalogChanged` | haywire-core | `ActiveLibraryMoved`: False; `LibraryCatalogChanged`: True | `library_browser_editor.py:245` → `ActiveLibraryMoved`; `library_overview_editor.py:647` (called from enable/disable/install/uninstall handlers, ~4 sites) → `LibraryCatalogChanged` | `library_browser_editor.py:54`, `library_overview_editor.py:100` (2 — both today filter on the overloaded enum, so they widen to *both* new signals during migration; can be tightened post-migration if desired) | §3.4 overload resolved. **Latent-bug flag:** today's `LibraryCatalogChanged` emits are local-only; cross-session is the right behavior (if session A installs a library, session B's library browser must refresh) — behavior change, intentional. |
| `ACTIVE_COMPONENT_CHANGED` | `ActiveComponentMoved` | haywire-core | False | `library_overview_editor.py:604`, `library_component_editor.py:307`, `create_node_panel.py:66` (3) | `library_component_editor.py:54` (1) | Per-session inspection selection. |
| `FILE_SELECTED` | `ActiveFileMoved` | haywire-core | False | `file_browser.py:331,347`, `file_viewer.py:98`, `node_source_editor.py:381` (4) | (none) | All emit sites today carry `reveal_editor=...` — they're commands. Under Q4A the reveal becomes `session.lifecycle(Reveal(...))`; the state mutation gets `ActiveFileMoved` for vocabulary completeness (Q5C — every workbench field gets a signal, even if no current subscriber). |
| `WORKBENCH_THEME_CHANGED` | `ThemeMoved` | haywire-core | False | `shell.py:112` (1) | `code_editor.py:108`, `node_source_editor.py:57`, `library_component_editor.py:56` (3) | Per-session preference. **Audit flag:** confirm no other emit sites exist that today reach the bus by side-channel — grep clean as of writing. |
| `GRAPH_REMOVED` | **split:** `GraphRemoved` (signal, payload-less) + ``Close(payload=entry_id)`` (lifecycle command) | haywire-core | `GraphRemoved`: True; `Close`: N/A (local-only) | `haystack_editor.py:354` (1 emit site, now emits both) | `shell.py:_close_payload` routes the Close fan-out to every TabSlot's `close_tabs_for_payload`. | **Lifecycle split.** Routing of "close my tabs" lives on the lifecycle channel; cross-session "the underlying graph is gone" lives on the signal channel as a payload-less observation. Removes the §6.3 inline-payload exception entirely. **Latent-bug flag:** today's emit is local-only; peer sessions can keep showing tabs for a removed graph. The new model has each session emit its own ``Close`` in response to ``GraphRemoved`` (or via direct authoring, as today's haystack_editor does for its own session) — behavior change, intentional. |

**Total emit sites touched:** ~30 across 11 files.
**Total filter sites rewritten:** 8 across 6 editors (`event.change_type` reads), plus `shell.py:588` orchestrator branch.
**Total core vocabulary:** 9 signal classes + 2 lifecycle commands
(``Reveal``, ``Close``).

### 11.2 Editorial decisions logged

Decisions made during the audit that the table compresses into single
cells; recorded here so reviewers can challenge them without re-deriving
the rationale:

1. **`EDITOR_FOCUSED` produces no signal class.** Every emit carries
   `reveal_editor`. No subscriber today reads it as a state-change
   event. Becomes a pure ``Reveal`` lifecycle command.
2. **`FILE_SELECTED` produces `ActiveFileMoved` even though no current
   subscriber needs it.** Q5C wants every workbench field to have a
   signal so the vocabulary is uniform; future editors that follow
   `active_file` shouldn't have to introduce the signal class as part
   of their own work.
3. **`LIBRARY_STATE_CHANGED` splits into two classes, both in
   haywire-core.** The library *manager* lives in haywire-studio, but
   the *concept* of an installed library is core (it's a SessionContext
   field). Vocabulary cohesion beats package-of-emit-site as the home
   rule.
4. **`LibraryCatalogChanged` and `GraphRemoved` flip to
   `cross_session=True`** — both are latent-bug fixes, not pure
   refactors. Flagged in the table as intentional behavior changes.
5. **`GRAPH_REMOVED` splits across both channels.** The signal
   ``GraphRemoved`` is payload-less (cross-session observation
   only). Tab-close routing for the originating session is a
   separate ``Close(payload=entry_id)`` lifecycle command. This
   removes the §6.3 inline-payload exception that earlier drafts
   carried as a one-off — every core signal is now pointer-only.
6. **Filter sites that today match overloaded enum values widen to
   match all replacement signal classes during migration.** Tightening
   is a separate post-migration pass — the migration itself is
   mechanically `ContextChangeType.LIBRARY_STATE_CHANGED` →
   `(ActiveLibraryMoved, LibraryCatalogChanged)`.

### 11.3 Out-of-vocabulary flags

The audit also surfaced things the table doesn't cover but the
implementation PR will hit:

- **`reveal_editor` / `reveal_payload` / `reveal_label` fields on
  `ContextChangedEvent`** — appear on emit sites that *also* carry a
  `change_type`. Per §4.4, those split into two emits: a
  `session.signal(...)` for the state mutation, then a
  `session.lifecycle(Reveal(...))` for the reveal. Affected sites:
  `file_browser.py:329,345`, `library_browser_editor.py:242`
  (carries `LIBRARY_STATE_CHANGED` and a reveal — splits into
  `ActiveLibraryMoved` + ``Reveal``), `create_node_panel.py:64-70`
  (already cited in §8.2 — ACTIVE_COMPONENT_CHANGED + ``Reveal``).
- **Signal/lifecycle ordering** at the call site is the author's
  responsibility — see §4.4 "Ordering: signal before lifecycle" for
  the canonical contract. The migration preserves today's
  `_on_context_changed` ordering in `shell.py:591-595` (signal
  fan-out first, command second) by *making it the documented
  call-site convention* rather than a framework guarantee.
