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

When you read [context.py](../../packages/haywire-core/src/haywire/ui/context.py)
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
([file_browser.py:316](../../barn/haybale-studio/haybale_studio/editors/file_browser.py#L316),
[haystack_editor.py:620](../../barn/haybale-studio/haybale_studio/editors/haystack_editor.py#L620),
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
([library_browser_editor.py:245](../../barn/haybale-studio/haybale_studio/editors/library_browser_editor.py#L245))
fires `LIBRARY_STATE_CHANGED` for **two different things**: "user
clicked a library row" (selection) and "library was installed/enabled"
(data mutation). Subscribers can't tell them apart and have to redraw
on both. This is exactly the conflation that `DATA_MUTATED` vs.
`SELECTION_CHANGED` keeps separate elsewhere.

### 3.5 The reveal payload tunnels through an event

`reveal_editor` / `reveal_payload` / `reveal_label` are **imperative
commands**, not observations. The shell handles them in
`_on_context_changed` *before* the per-slot poll loop
([shell.py:592-596](../../packages/haywire-core/src/haywire/ui/app/shell.py#L592-L596)).
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

- **`ContextSignal`** — *observations*: "the world looks different
  now; if you depend on X, redraw". Fan-out, idempotent, anyone
  may emit, anyone may subscribe.
- **`RevealRequest`** — *commands*: "please bring editor *E* with
  payload *P* to the front". Point-to-point, the shell is the only
  consumer.

Today both ride one struct (`ContextChangedEvent`) on one bus. Two
structs on two channels would let `RevealRequest` lose its "what kind
of change is this?" pretence — it has no change type, it's a command.
And it would let `ContextSignal` shrink to its minimum.

### 4.2 Re-cut the enum along a single axis: **what moved in `SessionContext`**

If the only purpose of the enum is to let editors filter, name the
values after the *field that moved*, not after the action that caused
the move. That gives a developer a one-to-one mapping:

| Editor field of interest | Subscribes to signal |
| --- | --- |
| `active_graph` / `active_graph_path` | `ACTIVE_GRAPH` |
| `active_file` | `ACTIVE_FILE` |
| `active_library` | `ACTIVE_LIBRARY` |
| `active_component` | `ACTIVE_COMPONENT` |
| `active_node` / `active_edge` / selection sets | `SELECTION` |
| graph data (nodes, edges, props) | `GRAPH_DATA` |
| theme tokens | `THEME` |

Six signals. Naming them "what's authoritative now" rather than
"what action just happened" makes them composable without overlap.
You can subscribe to any subset and never wonder whether
`LIBRARY_STATE_CHANGED` includes a selection click.

`GRAPH_REMOVED` collapses into `ACTIVE_GRAPH` plus a side-effect that
the shell already runs (`_handle_graph_removed` only needs the entry
id, which can hang off the signal payload). `WORKSPACE_CHANGED` and
`EDITOR_FOCUSED` either disappear entirely or move to the other
channel — see below.

### 4.3 Re-home the orphans

| Today | Proposed home |
| --- | --- |
| `EDITOR_FOCUSED` | becomes a `RevealRequest`, no signal |
| `WORKSPACE_CHANGED` | drop; `BaseEditor.on_focus` already fires |
| `LIBRARY_STATE_CHANGED` | split: selection = `ACTIVE_LIBRARY`, install/enable = a new `LIBRARY_CATALOG` signal (or fold into `GRAPH_DATA`'s broader sibling — see §4.5) |

### 4.4 Shrink `ContextChangedEvent` to its actual payload

```python
@dataclass(frozen=True)
class ContextSignal:
    field: ContextField        # which group of state moved
    detail: Optional[Any] = None  # narrow disambiguator (entry_id for removals, etc.)
```

That's it. Drop:

- `reveal_editor` / `reveal_payload` / `reveal_label` — they belong on
  `RevealRequest`, not `ContextSignal`

The shell's orchestrator splits cleanly:

```text
session.signal(ContextSignal(...))    →  fan out to slots
session.reveal(RevealRequest(...))    →  switch tab in target slot
```

Both can be batched if needed (a graph open is "set active_graph,
then reveal the GraphEditor for that payload").

### 4.5 Naming `SessionContext`

The dataclass is doing two jobs (§2.1). One option: keep a single
`SessionContext` but expose two grouped sub-objects so the split is
obvious:

```python
@dataclass
class SessionContext:
    workbench: WorkbenchState   # active_graph, active_file, active_library, ...
    selection: SelectionState   # active_node, active_edge, selected_nodes, ...
    app: IProjectState
    session: Session
    metadata: dict[str, Any]
```

The signal field then maps 1:1 to a sub-object (`ContextField.SELECTION`
moves things on `selection`, `ContextField.ACTIVE_GRAPH` moves things on
`workbench`). A new editor author can read the dataclass top-down and
*see* the two roles.

A weaker version of the same idea: keep the flat dataclass but rename
the existing fields with consistent prefixes (`focus_graph`,
`focus_file`, `focus_node`, ... vs `selected_nodes`). Today the prefix
soup (`active_*`, `selected_*`, `interaction_*`, `context_menu_*`) hides
the structure.

### 4.6 The story you tell a new editor author

After the rework, the developer-facing pitch fits in a paragraph:

> **An editor is a function of `SessionContext`. When the workbench
> moves (different graph, different file) or the selection moves
> (different node/edge), the shell sends a `ContextSignal` so you can
> redraw. Subscribe to the signals whose fields you read; ignore the
> rest. If you want to bring another editor to the front (e.g. you
> just opened a file), send a `RevealRequest` — that's a separate
> action, not a kind of change.**

Compare to today's pitch, which has to explain a 14-value enum where
most values overlap, three values are unused, two values are commands
masquerading as observations, and one value (`LIBRARY_STATE_CHANGED`)
means two different things depending on emit site.

---

## 5. What stays exactly the same

This is *not* an architectural rewrite, it's a renaming-and-pruning
exercise dressed up as a model. Specifically:

- The poll/draw cycle on `BaseEditor` is unchanged.
- The slot orchestration in `AppShell._on_context_changed` is unchanged
  in shape — it just dispatches `ContextSignal` to slots and
  `RevealRequest` to the reveal helper.
- Cross-session broadcast (`Session.notify_cross_session_context_change`
  → `SessionManager.broadcast`) is unchanged. It only ever needed to
  carry *signals*, not commands; this is already true today (no caller
  cross-broadcasts a reveal).
- `BaseEditor.on_focus` already exists and already does the
  "wrapper just became active" job that `WORKSPACE_CHANGED` was trying
  to express.
- All the emit sites stay where they are — they just emit smaller,
  more honestly-named structs.

Mechanically nothing changes. The mental model is what gets simpler.

---

## 6. Multi-actor signals

The §4 model implicitly assumes one authoritative state per session.
Haywire's collaboration story already breaks that assumption — multiple
sessions share one `BaseGraph`, edits propagate via
`notify_cross_session_context_change` → `SessionManager.broadcast` —
and plausible future directions (peer cursors, follow-mode, presence
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
    SELF: ClassVar["Subject"]      # this session
    BROADCAST: ClassVar["Subject"] # all sessions, including self

    @classmethod
    def peer(cls, session_id: str) -> "Subject": ...
```

`subject` defaults to `Subject.SELF` so existing emit sites and
subscribers don't have to think about it. A peer-aware editor opts in
explicitly:

```python
class PeerCursorEditor(BaseEditor):
    def poll(self, context, signal):
        # Only react to peer selection signals; ignore my own.
        return signal.is_a(SelectionMoved) and signal.is_from_peer()
```

(`is_a` and `is_from_peer` are predicates on `ContextSignal` itself —
see §7.4 for the full set.)

### 6.2 Why this works

1. **Existing editors keep working.** Without an explicit subject filter
   they implicitly mean "self" — which is what they already mean today.
   No subscriber accidentally renders a peer's selection as their own.
2. **Cross-session fan-out becomes a property of the signal**, not a
   separate transport method. Today there are two parallel APIs
   (`notify_context_changed` and `notify_cross_session_context_change`);
   tomorrow the signal's `subject` decides routing:
   - `Subject.SELF` → local fan-out (current `notify_context_changed`)
   - `Subject.peer(id)` → delivered to that one peer
   - `Subject.BROADCAST` → all sessions including self (current
     `notify_cross_session_context_change` semantics)
3. **`SessionContext` doesn't grow a `peer_selections` dict.** Peers
   expose their own context through the `SessionManager`; the signal's
   subject identifies whose, and editors traverse to peer state when
   they care.

### 6.3 Inline state vs. pointer

A peer-cursor signal could carry the new selection inline
(`SelectionMoved(subject=peer:abc, selection_id="node-7")`) or just
say "go look" (`SelectionMoved(subject=peer:abc)`).

The codebase already prefers **pointer**: today's `DATA_MUTATED`
broadcast carries no graph data — receivers re-read the shared
`BaseGraph`. Following that precedent, peer signals just mark a peer's
state dirty; editors that care fetch from `session_manager.get(peer_id).context`.

Inline payloads are tempting for performance but couple the wire
format to the sender's data model and break the moment a library
adds new fields to its peer-visible state. Pointer is more flexible
and matches the existing pattern.

### 6.4 What stays sealed

`Subject` is one of the few places where closing the vocabulary is
correct. Peers are sessions, sessions are managed by core, and a
library has no business inventing new subject kinds. `field` opens up
(see §7); `subject` does not.

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

@dataclass(frozen=True)
class ActiveGraphMoved(ContextSignal):
    pass

@dataclass(frozen=True)
class SelectionMoved(ContextSignal):
    selection_id: Optional[str] = None  # node/edge id, optional disambiguator

@dataclass(frozen=True)
class GraphDataMutated(ContextSignal):
    pass

# A library declares its own:
@dataclass(frozen=True)
class ActiveBreakpointMoved(ContextSignal):
    breakpoint_id: str
```

Editors filter by class:

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
where A reloads without B. This is narrow — and arguably any library
that subscribes to another library's signals already has a dependency
relationship that could be made explicit (B reloads when A does). The
framework handles this case via the `is_a` predicate in §7.4 — no
author-declared identity key needed.

### 7.4 Filter ergonomics: `is_a` / `is_local` / `is_from_peer`

Plain `isinstance` works, but reads heavily once you compose it with
the subject filter from §6:

```python
return (isinstance(signal, SelectionMoved)
     or isinstance(signal, ActiveGraphMoved)
     or isinstance(signal, GraphDataMutated)) and signal.subject == Subject.SELF
```

The base `ContextSignal` can expose three small predicates that read
as the question the subscriber is asking:

```python
def _qualified_name(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


class ContextSignal:
    subject: Subject = Subject.SELF

    def is_a(self, signal_type: type["ContextSignal"]) -> bool:
        """True if this signal is of the given type.

        Compares by qualified name (module + qualname) rather than class
        identity, so the predicate survives hot-reload of the
        signal-declaring library even when the subscriber wasn't
        reloaded in the same pass (the §7.3 cross-library edge case).
        """
        return _qualified_name(type(self)) == _qualified_name(signal_type)

    def is_local(self) -> bool:
        """True if this signal describes *this* session's state."""
        return self.subject == Subject.SELF

    def is_from_peer(self) -> bool:
        """True if this signal describes a peer session's state."""
        return self.subject not in (Subject.SELF, Subject.BROADCAST)
```

Filter sites read as the question they're asking:

```python
# Properties: redraw on local selection / graph / data changes.
def poll(self, context, signal):
    return ((signal.is_a(SelectionMoved)
          or signal.is_a(ActiveGraphMoved)
          or signal.is_a(GraphDataMutated))
         and signal.is_local())

# PeerCursor: only peers' selections.
def poll(self, context, signal):
    return signal.is_a(SelectionMoved) and signal.is_from_peer()
```

A few design choices worth being explicit about:

- **`is_a` does single-level matching, not subclass matching.** The
  signal hierarchy in §7 is flat by convention — each signal names a
  distinct concern, and "subscribe to all subclasses of X" isn't a
  pattern the design uses. Comparing qualified names instead of walking
  the MRO matches that intent and removes a class of accidents (a
  refactor that introduces an intermediate base class wouldn't silently
  widen every subscription).
- **The class itself is the identity.** `__module__` + `__qualname__`
  are stable across hot-reload by construction, so the framework
  derives signal identity from the class declaration directly. Library
  authors declare nothing beyond the dataclass.
- **Type-checker support.** `is_a` is annotated `signal_type: type[ContextSignal]`,
  so passing a string or non-class (`signal.is_a("SelectionMoved")`)
  is flagged by mypy / pyright. No runtime guard needed.
- **`isinstance` still works** within a library — but `is_a` is the
  recommended idiom across the codebase for consistency, and is
  required for cross-library subscriptions.

Naming: `is_a` follows the Smalltalk/Ruby tradition (`is_a?`,
`kind_of?`) and reads as English. `is_instance` was considered but
collides visually with the stdlib `isinstance` builtin without being
the same thing — boring-and-distinct beats clever-and-similar.

> **Footnote on `__main__`.** Python sets `cls.__module__ == "__main__"`
> when a module is run directly (`python some_signals.py`) instead of
> imported. A class defined in such a module has qualified name
> `"__main__.ClassName"` rather than `"package.module.ClassName"`, and
> won't compare equal to the same class imported normally. This only
> affects ad-hoc script invocation — Haywire's plugin discovery always
> imports modules, never executes them as `__main__`, so the trap
> doesn't bite real sessions. Worth knowing if a developer is
> debugging signal classes with a `if __name__ == "__main__":` block.

### 7.5 What core declares vs. what libraries declare

Core declares the signal vocabulary for state core owns:
`ActiveGraphMoved`, `SelectionMoved`, `GraphDataMutated`, `ActiveFileMoved`,
`ActiveLibraryMoved`, `ActiveComponentMoved`, `ThemeMoved`. That's the
full vocabulary needed to retire today's 14-value enum — the
core-declared set covers every existing emit site.

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

From [context_menu.py](../../packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py):

1. User right-clicks. `SessionContextMenuProvider._open_menu` sets
   `context.context_menu_trigger = "canvas" | "node" | "edge" | "selection"`.
2. Builds a `Popup`, queries `PanelRegistry` for panels matching the
   trigger scope, draws them.
3. Stuffs callbacks and intermediate state into `context.metadata`:
   `on_emit_event`, `edge_state`, `pending_connection`,
   `context_menu_screen_pos`, `edge_reconnect_end`.
4. On close: clears `context_menu_trigger`, drains the metadata keys.

Panels themselves use the bus too —
[create_node_panel.py:64-70](../../barn/haybale-core/haybale_core/panels/context_menu/create_node_panel.py#L64-L70)
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
context.session.reveal(RevealRequest(LibraryComponentEditor, ...))
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
> another editor, it sends a reveal request. The popup's open/close
> is the popup's own lifecycle — not a signal anyone subscribes to.

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
follow-on once §6 / §7 land — see open question §9.5.

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

3. **Should `RevealRequest` carry a "create if missing" flag, or is
   that always-on?** Today the shell decides: TabSlot auto-creates on
   miss, IconSlot just switches. The behaviour is fine; the question is
   whether the request type should make it explicit.

4. **Does the current `notify_cross_session_context_change` survive as
   a separate API, or is it absorbed into the subject-routed signal
   bus** (§6.2)? Mechanically the second is cleaner — one method, the
   `subject` field decides routing. The migration risk is that today's
   call sites are all `BROADCAST` semantics; widening the API to
   include `Subject.peer(id)` is purely additive.

5. **Is `ContextMenuScope` an instance of a more general "popup
   scope" pattern?** §8.5 notes that several other popups in the
   codebase (Save-As, rename dialog, remove-confirm) carry similar
   ephemeral state in closures and locals. After the bus split makes
   popup state stop hiding inside `metadata`, the pattern becomes
   visible. Worth a separate design pass once §6 / §7 are real — the
   shape is roughly *"typed scope object passed alongside
   `SessionContext` to popup children"*, and a shared base might be
   warranted, or the popups might stay independent and just follow a
   convention. Don't decide now.

---

## 10. TL;DR

- `ContextChangedEvent` is two events glued together: an *observation*
  (`change_type` + `detail`) and a *command* (`reveal_*`).
- `ContextChangeType` mixes five different axes; two values are
  commands, one value is overloaded.
- `SessionContext` carries two distinct kinds of state (workbench
  focus and live selection) under one flat dataclass.

A simpler story:

- Split the bus into **`ContextSignal`** (observations, fan-out) and
  **`RevealRequest`** (commands, point-to-point).
- Make signals **typed classes**, not enum values, so libraries can
  declare their own without touching core (§7).
- Every signal carries a **`subject`** so peer-cursor / collaboration
  features have a place to land without breaking existing subscribers
  (§6).
- Name signals after the **field that moved**, not the action that
  moved it. That gives an editor author a one-line subscription rule.
- Group the dataclass into **`workbench` + `selection`** so the two
  state lifetimes are visible in the type.

Mechanism unchanged; vocabulary tightened, and made open at exactly
the two seams (signal type and subject scope) where library authors
need room to extend.
