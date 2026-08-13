---
status: draft
doc_template: canonical-example
scope: Authoring Farmhand MCP tools — @farmhand decorator, Farmhand base class, FarmhandContext facade, FarmhandError contract, input schema derivation, resource vs tool distinction, agent-facing output conventions (row shape, truncation, next-step hints)
see-also:
  - ../../architecture/studio/studio-arch.md
  - ../../reference/glossary.md
---

# Farmhand — Canonical Example

## 1. What it solves

A **Farmhand** is one MCP tool exposed by a running Haywire studio to an attached AI agent (Claude Desktop, Claude Code, or any MCP client). Where a node runs inside a graph and a panel renders inside the studio UI, a Farmhand tool runs on behalf of an external agent that wants to *drive* the studio — list what's installed, inspect a component, mutate an open graph, query the error ledger.

You author a Farmhand tool when a library wants to expose one of its capabilities to an agent as a callable action. Examples already shipping: `studio_list_components` (catalog search), `studio_describe_component` (identity + docstring lookup), `graph_editor_add_node` / `graph_editor_connect` (graph mutation), `graph_editor_inspect_node` (one node's live values + health), `haystack_open_graph` (session management), `marketplace_get_library_docs` (doc retrieval).

**Pair every mutation with a way to read what it changed.** An agent that can write but not read has to guess names and cannot verify outcomes. The graph-editor tools are deliberately layered by breadth, and share one addressing vocabulary so a read result feeds straight back into a write:

| Tool | Scope | Answers |
|---|---|---|
| `studio_describe_component` | a component **class** | "what is this kind of node for?" (identity, docstring) |
| `graph_editor_query_graph` | a whole **graph** | "what nodes and edges exist, and how are they wired?" (topology, no values) |
| `graph_editor_inspect_node` | one **node instance** | "what is on this node, what is it set to, and is it healthy?" — at three depths (see `data=` below) |
| `graph_editor_set_property` | one **field** | writes a port value or settings field by the same flat `name` `inspect_node` reports |

The intended path narrows at every step, so an agent never pays for detail it did not ask for:

```text
studio_describe_component      what kind of node is this?        (class docstring)
  └─ graph_editor_query_graph  which node instances exist?       (topology)
      └─ inspect_node get=['summary']                is it ok, and which bags are big?
          └─ inspect_node get=['settings'] by_bag=['depth']      what fields does it have?
              └─ ... data='value'                               what are they set to?
                  └─ ... data='all' by_name=['threshold']        what can I write?
                      └─ graph_editor_set_property               write it
```

A row from `inspect_node` carries both handles the write tools need: flat `name` for `set_property`, and `accessor` for `promote_setting` (which addresses fields as `accessor` + `field`, not a flat name). `name` is stable across all three `data` levels, so it is also the key that joins a shallow row to its detailed counterpart.

Farmhand tools are **not** the same as MCP *resources*. Tools are actions the agent invokes with arguments and gets a structured result back (`list_tools` / `call_tool` in the MCP spec). Resources are addressable, read-only documents the agent fetches by URI (`list_resources` / `read_resource`) — the baked documentation tree (`farmhand://docs/...`) and per-library `OVERVIEW.md`/`QUICKREF.md` files (`farmhand://library/<id>/...`) are resources, not tools. If what you're exposing is "read this static text," prefer a resource; if it's "do something and return structured data," write a Farmhand tool.

## 2. How it fits

```text
Author declares                Library registers               MCP host serves
────────────────               ─────────────────                ───────────────
@farmhand(                     @library(...):                   list_tools()
    label='...',                 register_components(self):       → name, description
    description='...',             self.add_folder_to_               (from instructions=),
    instructions='...',              registry(                       inputSchema (derived
)                                     folder='farmhands',              from run()'s signature
class MyTool(Farmhand):                registry_cls=                  or input_schema_override)
    async def run(self, ctx,           FarmhandRegistry)
        arg: str) -> dict:                                       call_tool(name, args)
        ...                       FarmhandRegistry                  → FarmhandContext() built,
                                  (BaseRegistry subclass)              MyTool().run(ctx, **args)
                                                                        awaited, result JSON-
                                                                        encoded back to the agent
```

The MCP host (`haywire_studio.farmhand.host`) is the one place that talks the wire protocol. It builds a fresh `FarmhandContext` per call (carrying a progress-reporter callback wired to the MCP session), resolves your tool class from `FarmhandRegistry` by its derived name, and awaits `your_cls().run(ctx, **arguments)`. Everything below `run()` is plain Python — no async MCP SDK types leak into tool bodies.

**Boundaries.** The wire protocol, session tracking, and resource-serving mechanics (`list_resources`/`read_resource`, the docs bake pipeline) live in [architecture/studio](../../architecture/studio/studio-arch.md). This file documents the *authoring* surface only — what you write inside a `farmhands/` folder.

## 3. Important concepts

**The `@farmhand` decorator.** Stamps `class_identity` (a `FarmhandIdentity`, extending the same `BaseIdentity` every component kind shares) and derives `class_library` from the module hierarchy, same as `@node`/`@panel`/`@state`.

| Parameter | Required | Purpose |
|---|---|---|
| `label` | no | Human-readable display name. Defaults to `registry_id`. |
| `description` | no | Short human-facing blurb — shown in generated docs and the `studio_list_components` catalog. Not sent to MCP clients. |
| `instructions` | **yes** | Sent to the MCP client as the tool's description — this is the *only* text the agent sees before deciding whether/how to call the tool, since derived input schemas carry no per-parameter descriptions (see below). Write it for an LLM: what the tool does, when to use it, valid argument values, gotchas — not just a restated label. Omitting it raises `TypeError` at class-definition time. |
| `registry_id` | no | Unique id within the library. Defaults to the class name. The MCP-visible tool name is `{lib_id}_{registry_id}` — pass a snake_case id (e.g. `registry_id="save_graph"` → `mylib_save_graph`). |
| `annotations` | no | A `ToolAnnotations` instance: `read_only_hint`, `destructive_hint`, `idempotent_hint`, `open_world_hint` — MCP consent hints surfaced to the client/user before a mutating call. Defaults to all-`False`. |
| `hidden` | no | Exclude from author-facing selection UIs (inherited from `BaseIdentity`; unrelated to MCP visibility — a hidden Farmhand is still callable). |
| `deprecation_warning` | no | Advisory message shown wherever this tool is listed. |

**`Farmhand` is the class to subclass.** Implement exactly one method:

```python
async def run(self, ctx: FarmhandContext, *args, **kwargs) -> dict:
```

`run` must be `async` — the decorator raises `TypeError` at class-definition time otherwise (the MCP SDK thread-offloads sync functions, which breaks the shared NiceGUI loop's affinity). Declare your real parameters after `ctx`; `self` and `ctx` are excluded from the derived input schema automatically.

**Input schema derivation.** By default, `Farmhand.input_schema()` introspects `run()`'s signature — type hints become JSON Schema types (`str`→`string`, `int`→`integer`, `float`→`number`, `bool`→`boolean`, `dict`→`object`, `list[T]`→`array` of `T`, `Optional[X]`/`X | None`→schema of `X` with presence handled by `required`), and parameters without a default become `required`. This covers most tools with zero extra code.

It does **not** produce `enum` constraints, per-parameter descriptions, or any JSON Schema keyword outside that primitive mapping — unknown/unmapped annotations degrade to `{}` (accept-anything). When your tool needs an `enum` (e.g. a `kind` argument limited to a fixed set of valid strings) or other schema-level constraints hints can't express, set `input_schema_override` to a hand-written schema dict; it replaces the derived one entirely.

```python
class MyFilterTool(Farmhand):
    input_schema_override = {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["fast", "thorough"]},
        },
        "required": [],
    }

    async def run(self, ctx: FarmhandContext, mode: str = "fast") -> dict:
        ...
```

**`FarmhandContext` — the facade every `run()` receives.** Never reach around it for ambient DI, session, or signal-bus access; it is the enforcement point for cross-cutting concerns (thread affinity, undo fencing, cross-session broadcast).

| Method | Purpose |
|---|---|
| `ctx.registry(RegistryCls)` | Resolve a framework singleton (any `BaseRegistry` subclass — `NodeRegistry`, `LibraryRegistry`, etc.) from the global injector. |
| `ctx.state(StateCls)` | Resolve an `AppState` instance (e.g. a library's own `AppState` subclass) from the DI container. |
| `ctx.broadcast(signal)` | Emit a cross-session signal so open browser UIs update. Caller-owned — call it explicitly after any mutation an open editor should reflect (mirrors the editor's own mutate-then-broadcast convention; see `StudioDismissErrorsTool` below). |
| `await ctx.offload(fn, *args, **kwargs)` | Run blocking work off the shared NiceGUI loop (`asyncio.to_thread` under the hood) — use for CPU-bound or blocking-I/O work; tool handlers otherwise share the app's single event loop. |
| `await ctx.progress(message)` | Stream a progress line to the MCP client. No-op if the call wasn't made through a session that supports it — safe to call unconditionally. |
| `ctx.fence(editor)` | Open the undo fence for this tool call, so the whole call collapses into one undo gesture in the studio UI. Use for any tool that mutates a graph through an editor. |
| `ctx.workspace_root()` | The studio's workspace root `Path`. |

**The `FarmhandError` contract.** Raise `FarmhandError(code, message, ids=None, help=None)` for any *expected* failure — bad arguments, not-found lookups, gate rejections. The host renders it as a structured MCP tool error (`[code] message (id=..., ...)`, plus a `help: ...` line when a hint is supplied), never a raw stack trace. Reserve uncaught Python exceptions for genuine bugs; an agent can branch on `code` but not on exception-message text, so pick a stable, greppable code per failure class and reuse it everywhere that failure can occur.

**Supply `help=` whenever the fix is knowable at the throw site.** It is the one command that resolves the failure. An agent that gets a hint self-corrects in one turn; without one it guesses at the tool surface. Name a concrete tool call and carry forward the ids you already hold — a not-found lookup almost always knows which list tool would have shown the valid values. Put the hint in `help=`, not trailing prose in `message`, so it stays machine-separable. Omit it when there is no honest next step: a genuine operation failure (`save_failed`) should not invent one.

```python
raise FarmhandError(
    "graph_not_found",
    f"No open graph '{binding_id}'.",
    ids={"binding_id": binding_id},
    help="Run haystack_list_graphs to see open graphs, or haystack_open_graph to open one.",
)
```

**Folder convention and registration.** Farmhand tools go in the library's `farmhands/` folder; register it with `FarmhandRegistry` in `register_components()`, alongside the same-shaped calls for `nodes/`, `panels/`, `state/`, etc:

```python
from haywire.core.farmhand import FarmhandRegistry

def register_components(self):
    base = Path(__file__).parent
    self.add_folder_to_registry(
        folder_path=str(base / "farmhands"),
        registry_cls=FarmhandRegistry,
    )
```

**The `'haybale-studio'` registry-key prefix is reserved.** `barn/haybale-studio`'s baseline tools (`studio_status`, `studio_list_components`, ...) own it; the reservation is enforced by distribution-name uniqueness at discovery, not by `FarmhandRegistry` itself. Don't register a second library under that distribution name.

## 4. Agent-facing output

Everything above is about making a tool *work*. This section is about making it *usable by an agent* — a different discipline, with its own failure modes, and the one most easily skipped because a tool that ignores all of it still passes its tests.

Two costs drive every rule here:

- **Every field costs tokens multiplied by row count.** A field nobody reads is not free; it is paid on every call, by every agent, forever.
- **Every missing hint costs a round trip.** The expensive failure is rarely a slightly longer response — it is the extra call the agent makes because your response did not tell it what to do next.

An agent has no peripheral vision. It cannot skim, scroll back, or notice that a list looked short. Whatever your response does not say, it does not know.

### 4.1 Return the least that lets the agent act

**Default to the smallest useful row; put the rest behind `detail=true`.** Return the 3-4 fields a caller needs to *decide what to do next* — an identifier, a label, a status — and gate prose, URLs, and provenance behind `detail`. Never `asdict()` a domain dataclass straight into a row: it ships whatever the class happens to hold, including fields that are empty for every row. Measured on a real 5-row `marketplace_list_available`, `asdict()` emitted 21 fields per row of which 41% of all values were empty, and 8 fields were empty on *every* row; trimming to four cut the payload 77%. When `detail=true` does return the full record, still drop empty values and runtime-only internals — an absent value says nothing worth a token.

**Make the caller drill down: separate WHICH from HOW MUCH.** A tool whose full response is expensive should force the caller to choose, on each independent axis, rather than defaulting to everything. `graph_editor_inspect_node` is the reference implementation, with three orthogonal parameters:

| Axis | Parameter | Effect |
|---|---|---|
| Breadth — *which* sections | `get: list[str]` (**required, non-empty**) | `summary`, `node_id`, `ports`, `settings`, `props`, `state` |
| Depth — *how much* per row | `data: str` (default `"info"`) | `info` (identity only) → `value` (+ current value) → `all` (+ writable schema) |
| Selection — *which* rows | `by_name` / `by_bag` / `by_category` / `by_dir` (each default `[]`) | ANDed across axes, ORed within one |

The payoff is concrete: on a real 29-field, 5-bag node, an unfiltered `info` dump is ~4800 chars while `by_bag=["depth"]` at `data="all"` is ~950 — the agent pays for the slice it asked for. Design notes worth copying:

- **Default to the cheap end.** `data="info"` means an agent that ignores the parameter still gets the orientation payload, not the expensive one. Make the *expensive* behaviour the thing that must be requested.
- **Keep one join key across depths.** Every row carries `name` at every level, so an `info` row and its `all` counterpart are trivially correlated — and that same `name` is what the write tool takes. Non-identity metadata (`label`, `description`, `category`) appears **only** at `info`; repeating a description on 29 deep rows is pure waste once the agent has read it.
- **Group by the author's own structure, outermost-first.** Ports come back as `inlets`/`outlets`/`configs`; settings nest `{bag: {category: [rows]}}` at `info` and `{bag: [rows]}` deeper. Bag is the **outer** key because it is the code-declared identity (and the handle `promote_setting` takes), while `category` is a free-text display label an author may reuse across bags — a flat category map silently merges rows from different bags. Grouping also removes a redundant per-row key.
- **One filter parameter per namespace.** Names and bag accessors are code-declared identifiers, a category is free text, and a direction is a closed enum. A single combined `filter` could not tell the `depth` bag from a `"Depth"` category, which makes the miss report untrustworthy. Splitting them makes each value's namespace explicit, so `unmatched` can be **keyed by the filter that missed** (`{"by_bag": ["colour"]}`) — and lets the one closed-enum axis (`by_dir`) be validated by the client instead of the tool body. Flat per-axis arrays beat a combined `filter: [{by, values}]` list here: same expressiveness, fewer tokens per call, and every axis stays independently enum-checkable at the protocol boundary.
- **A section-specific axis still reports its miss.** `by_dir` (`inlet`/`outlet`/`config`) narrows the `ports` section only. Ports carry no bag or category, so `by_bag`/`by_category` exclude them outright — combining either with `by_dir` returns no ports and reports `by_dir` under `unmatched`. That is deliberate: it is the one place a sibling-axis exclusion IS surfaced, because mixing a settings axis with a ports axis is a caller confusion, not a legitimate narrowing.
- **Surface the constraint that actually bites.** At `data="all"` a field carrying a validator reports `validator: {name, doc}`. `min`/`max` are UI hints and are **not** enforced, so a payload that returns those and stays silent about the validator shows the agent the decorative constraint and hides the real one. The predicate is an opaque `Callable[[Any], bool]` — only its presence, `__name__` and first docstring line are recoverable, and a lambda honestly reports `<lambda>`. The agent cannot pre-check a value; the signal exists to shift it from "this write will land" to "verify this write", which is what `set_property`'s read-back already assumes.
- **Report filter misses, but only real ones.** `unmatched` is present only when non-empty, and a value excluded by a *sibling* axis is not a miss — otherwise a legitimate narrowing call reports phantom typos. Silently omitting a miss would make a typo indistinguishable from "that field does not exist", the worst possible signal just before a write.
- **Put the cost preview in the summary.** `get=["summary"]` returns per-bag `setting_counts` (`{"color": 17, "depth": 6, …}`), not just a total — a bare "29 settings in 5 bags" leaves the caller with an all-or-nothing choice, while per-bag counts let it pick a `by_bag` and fetch one slice.
- **Don't show an agent what the user cannot see.** A field whose `effective_ui_state` is `HIDDEN` is absent from the properties panel entirely (ADR 0020), so returning it in full puts the agent in a different reality from the human sharing the graph. Collapse it to `{name, ui_state: "hidden"}` — **collapse, not omit**: the gate is state, not structure, so an agent that flips the controlling flag must still be able to find the field. Naming it in `by_name` expands it in full.
- **The host validates `input_schema_override` before `run()` executes** — an empty `get` or a misspelled `enum` value is rejected at the protocol boundary (`Input validation error: [] should be non-empty`), so the tool body never sees it. Keep the in-body guards for non-MCP callers, but write tests against the schema error, not the `FarmhandError`.
- `summary` is emitted **unconditionally** (the canon rule above) *and* is selectable, so `get=["summary"]` is a legitimate cheap survey — the same ergonomic as `count_only=true` on `studio_list_components`.

Prefer these axes over a pile of `include_*` booleans: booleans multiply combinatorially and each one has to be discovered separately, whereas one enum per axis is self-describing in the derived schema.

### 4.2 Never hide that something was withheld

A truncated response that does not announce itself is the worst output a tool can produce: the agent proceeds confidently on partial data. Truncating is fine. Truncating silently is not.

**Pagination convention.** Any tool returning a list should accept `limit`/`offset` and call the shared helpers so every list tool paginates identically:

```python
from haywire.core.farmhand import truncation_note
from ._helpers import page  # barn/haybale-studio's local pagination slice helper

rows, total = page(rows, limit, offset)
return {
    "summary": f"{total} match.{truncation_note(len(rows), total, offset)}",
    "items": rows,
    "total": total,
}
```

`truncation_note` returns `''` when the page already covers the whole collection, and a suffix like `' (showing 1-50 of 200 — pass limit/offset for more)'` otherwise — append it to `summary` so a client that only reads the summary string still learns the result was truncated.

**Large single payloads truncate too.** Pagination covers lists; a tool returning one *big* value (a source file, a README) needs the same guarantee, because an uncapped read silently dominates the caller's context. Cap by default, report the full size, and offer the escape hatch:

- Return the natural unit — lines for source (`studio_read_component_source`, `total_lines`, absolute line numbers preserved so a windowed read stays quotable), characters for prose (`marketplace_get_library_docs`, `total_chars`).
- Say it was truncated in `summary`, and add a `help` key naming the exact follow-up call (`offset=<end>` for the next window, or `full=true`).
- Accept `full=true` to bypass the cap. Never omit a large field entirely — a preview plus the total beats forcing a second blind call.

**Every result should carry a `summary` string.** The host injects a fallback (`f"{name}: ok"`) if a returned dict omits one, but an explicit, information-dense summary is the first (and sometimes only) thing a token-conscious agent reads — write one deliberately rather than relying on the fallback.

### 4.3 Say what to do next

**Put a `help` key on list and mutation results, not just on errors.** `FarmhandError(help=)` covers the failure path; the success path needs the same courtesy — the asymmetry is the bug. After a list, name the drill-down (`studio_describe_component registry_key=<key>`); after a mutation, name what makes the change useful (`haystack_create_graph` → add a node, then save — it is unsaved until you do). Carry forward ids you already hold so the hint is a runnable command rather than a template, and prefer a concrete value over a placeholder when you know it: `studio_list_components count_only=true` names its own biggest bucket. Omit `help` on detail views — they are self-contained, and a hint there is noise. Omit it on an empty page too, except to say how to create the first item.

The error-path half of this rule lives with the `FarmhandError` contract in §3 — same principle, applied where the agent needs it most.

### 4.4 Be honest about what you know

**Resist inventing causality the framework does not record.** A tempting addition to `inspect_node` was a `disabled_reason` explaining *why* a field is `DISABLED`. `effective_ui_state` composes a severity-max over three independent sources and discards which one won, so any such field would be a guess — and a plausible-but-wrong reason is worse for an agent than no reason at all. Report the state; leave the cause to whoever declared it.

The general form: an agent cannot tell a confident guess from a fact. When the framework does not record something, say nothing rather than infer it. This is why `unmatched` reports only real filter misses (a phantom typo report is worse than none), why a `HIDDEN` field is collapsed rather than omitted (absence would read as "does not exist"), and why a dropped value gets an explicit `value_omitted` marker instead of a repr that looks like data.

**Serializing values that cross the wire.** The host emits every result *twice*: as a JSON text block (for text-only clients) and as MCP `structuredContent` (a real JSON object, so a structure-aware client skips the string parse). Both halves come from the same `json.dumps(result, default=str)` pass, so they can never disagree — and `default=str` means a non-serializable value does not crash, it silently degrades to an object repr (`"<MeshData object at 0x...>"`), which is useless to an agent and unbounded in size. When a tool returns *values* rather than metadata:

- Check serializability instead of trusting the fallback. `haywire.core.types.utils.is_cattrs_serializable(value)` is the codebase's existing predicate for exactly this.
- Emit an explicit marker for what you dropped (`inspect_node` uses `value_omitted: "<type>"`) so the agent learns the value exists but is not retrievable, rather than reading a repr as if it were data.
- Most Haywire value types are already JSON-native: `Vec2i`/`Vec3f`/… are `list` subclasses and `Color`/`Icon` are `str`, so settings values round-trip losslessly with no conversion layer. Arbitrary port `BaseType`s (mesh, frame) do not.
- A `widget_config` may hold a **live zero-arg callable** at `properties["options"]` (the documented dynamic-dropdown mechanism — see [setting-canon](../settings/setting-canon.md)). Resolve it the way the widget does (`options()`), inside a `try/except` so one failing probe can't fail the whole call, and never pass it through unresolved.

### 4.5 Where these rules come from

This section adapts [AXI](https://axi.md) (Agent eXperience Interface), a set of ergonomic standards written for **CLI tools** that agents drive through shell execution. The reasoning transfers; several of the mechanics do not, because MCP is a typed protocol with its own conventions rather than a byte stream on stdout.

What we took, and what changed in translation:

| AXI | Here |
|---|---|
| §2 minimal default schemas, `--fields` to widen | §4.1, as `detail=true` — same idea, named for the schema convention the derived `inputSchema` already exposes |
| §3 truncate long content, show total, offer `--full` | §4.2, as `full=true` + `total_lines`/`total_chars` |
| §4 pre-computed aggregates, definitive totals | §4.2, as `total` + `truncation_note()` |
| §9 contextual disclosure — suggest next steps | §4.3, as the `help` key |
| §6 structured errors with an actionable suggestion | §3 `FarmhandError(code, message, ids, help)` |
| §1 emit TOON on stdout | **Not adopted.** MCP negotiates its own typing: the client owns the parse, and the protocol already carries a real object in `structuredContent`. Emitting TOON inside `content[].text` would hand every client a format it has no contract for. Measured on a real payload, TOON saved ~40% on uniform tabular rows but was *larger* than JSON on nested count maps, and has no representation for the multi-line source strings some tools return. Schema trimming (§4.1) delivered ~12× more on the same payload with no new dependency — do that first, and revisit the format question only against an already-trimmed baseline. |
| §6 exit codes 0/1/2, errors to stdout | **N/A.** MCP has `isError`; there is no exit code and no stdout. |
| §7 session hooks, §10 `--help` and bin path | **N/A.** `list_tools` and the `instructions=` field do this job — which is why `instructions=` is worth writing carefully (§3). |
| §8 no-args shows live content | Closest equivalent is `studio_status`, not a per-tool behaviour. |

The measurements above are from a reproducible analysis of payload size and structure. See the internal documentation for the detailed script and results.

If you are extending a *different* agent-facing surface — a CLI, for instance — read AXI directly; more of it applies there than here.

## 5. Live examples from the codebase

**Minimal read-only tool** — no arguments beyond a single required string, `read_only_hint` annotation:

```python
--8<-- "barn/haybale-testing/haybale_testing/farmhands/echo_tool.py:6:19"
```

from: `EchoTool` — registry_key: `haybale-testing:farmhand:echo`

**The `FarmhandError` contract** — a tool that always fails, to exercise the structured-error path in tests:

```python
--8<-- "barn/haybale-testing/haybale_testing/farmhands/fail_tool.py:6:19"
```

from: `FailTool` — registry_key: `haybale-testing:farmhand:fail`

**Pagination + filtering** — `ctx.registry()`, the `page()`/`truncation_note()` convention, and an `include_*` opt-out pattern for rows excluded by default:

```python
--8<-- "barn/haybale-studio/haybale_studio/farmhands/catalog.py:31:86"
```

from: `StudioListLibrariesTool` — registry_key: `haybale-studio:farmhand:list_libraries`

**Mutually-exclusive arguments, idempotent delete, and `ctx.broadcast`** — validates exactly one of two optional arguments is set before doing anything, and notifies open studio UIs after a mutation:

```python
--8<-- "barn/haybale-studio/haybale_studio/farmhands/errors.py:57:109"
```

from: `StudioDismissErrorsTool` — registry_key: `haybale-studio:farmhand:dismiss_errors`

What these examples exercise:

| Concept | Where |
|---|---|
| `@farmhand(label=, description=, instructions=, registry_id=, annotations=)` | every example |
| `ToolAnnotations(read_only_hint=True)` for a non-mutating tool | `EchoTool`, `StudioListLibrariesTool` |
| `ToolAnnotations(destructive_hint=True, idempotent_hint=True)` | `StudioDismissErrorsTool` |
| Raising `FarmhandError(code, message, ids=)` | `FailTool`, `StudioDismissErrorsTool` |
| `limit`/`offset` + `page()` + `truncation_note()` | `StudioListLibrariesTool` |
| `ctx.registry(RegistryCls)` | `StudioListLibrariesTool` |
| An `include_*` default-off opt-out param | `StudioListLibrariesTool` (`include_system`) |
| Validating mutually exclusive arguments before acting | `StudioDismissErrorsTool` |
| `ctx.broadcast(signal)` after a mutation | `StudioDismissErrorsTool` |
| Idempotent handling of an absent target | `StudioDismissErrorsTool` |

For the MCP wire protocol, session tracking, and how resources (`farmhand://docs/...`, `farmhand://library/...`) differ from tools, see [architecture/studio](../../architecture/studio/studio-arch.md).

---

## Quick reference

### Authoring checklist

Mechanics (§3):

- [ ] `@farmhand(label=, description=, instructions=, registry_id=, annotations=)` decorator
- [ ] Inherit from `Farmhand`
- [ ] Implement `async def run(self, ctx: FarmhandContext, ...) -> dict` — must be `async`
- [ ] Write `instructions=` to teach valid arguments — it's the only text the agent sees before calling; keep `description=` short and human-facing
- [ ] Set `input_schema_override` if you need an `enum` or other schema constraint the derived schema can't express
- [ ] Raise `FarmhandError(code, message, ids=)` for expected failures, not bare exceptions
- [ ] Pass `help=` on any failure whose fix is knowable at the throw site
- [ ] For mutations open editors should reflect: `ctx.broadcast(signal)` after the mutation
- [ ] Place file in `farmhands/` folder; register via `FarmhandRegistry` in `register_components`

Agent-facing output (§4) — a tool passes its tests without any of these:

- [ ] Default rows to 3-4 fields; gate prose/URLs/provenance behind `detail=true` (§4.1)
- [ ] For list results: `limit`/`offset` params + `page()` + `truncation_note()` in `summary` (§4.2)
- [ ] For one large payload (source, docs): cap by default, report the total, accept `full=true` (§4.2)
- [ ] Every returned dict should include an explicit `summary` string (§4.2)
- [ ] Add a `help` key to list and mutation results naming the natural next call (§4.3)
- [ ] Report only what the framework actually records — no inferred causes (§4.4)

### Imports

```python
from haywire.core.farmhand import (
    Farmhand, FarmhandContext, FarmhandError, ToolAnnotations,
    farmhand, truncation_note, FarmhandRegistry,
)
```

### `FarmhandContext` method reference

| Method | Purpose |
|---|---|
| `ctx.registry(Cls)` | Resolve a registry singleton |
| `ctx.state(Cls)` | Resolve an `AppState` instance |
| `ctx.broadcast(signal)` | Cross-session UI refresh |
| `await ctx.offload(fn, *a, **kw)` | Run blocking work off the shared loop |
| `await ctx.progress(msg)` | Stream a progress line to the client |
| `ctx.fence(editor)` | Open one undo fence for the whole call |
| `ctx.workspace_root()` | Studio's workspace root `Path` |

### Common pitfalls

| Pitfall | Why it matters |
|---|---|
| `def run(...)` without `async` | `TypeError` at decoration time — the MCP SDK thread-offloads sync functions, breaking loop affinity |
| Omitting `instructions=` | `TypeError` at decoration time — required, no fallback to `description` |
| Writing `instructions=` as a restated `label` | Agent gets no signal on when to call the tool or how to shape arguments — write it as usage guidance, not a title |
| Assuming type hints alone can express an `enum` | Derived schemas only map primitive types; use `input_schema_override` |
| Raising a bare `ValueError`/`KeyError` for an expected failure | Agent sees an unstructured error instead of a stable `code` it can branch on |
| Returning a list without `limit`/`offset` | No way for a caller to scope a large result — the exact problem `studio_list_components` had before it grew filters |
| Slicing a list by hand instead of `page()` + `truncation_note()` | Silently drops the rest with no signal — `marketplace_list_available` and `studio_get_errors` both shipped this way, reporting a bare `total` a caller had no way to act on |
| Returning a whole file or document uncapped | One call can swamp the caller's context, and nothing tells it whether it got a preview or everything — cap, report `total_lines`/`total_chars`, offer `full=true` |
| Putting the recovery hint in `message` prose instead of `help=` | The agent has to regex it out of the sentence; `help=` is a separate line it can act on directly |
| `asdict()`-ing a domain dataclass into a list row | Ships every field the class happens to hold — `marketplace_list_available` emitted 21 fields/row with 41% of values empty and 8 fields empty on *every* row. Pick fields explicitly; gate the rest behind `detail=true` |
| A successful list or mutation with no `help` | The error path tells the agent what to do next but the success path leaves it guessing — the asymmetry is the bug |
| Mutating state without `ctx.broadcast(...)` | Open studio editors silently go stale until their next unrelated refresh |
| Writing a tool when a static resource would do | Resources (`farmhand://...`) are cheaper for the client and don't need argument handling — reserve tools for actions |
| Returning a value without checking it serializes | `json.dumps(..., default=str)` turns a mesh/frame into an unbounded object repr instead of failing — check with `is_cattrs_serializable` and emit an explicit omission marker |
| Passing a `widget_config` through verbatim | `properties["options"]` may be a live callable (dynamic dropdowns). Resolve it like the widget does; a plain port can't hold one (ADR 0018) but a **promoted** port can |
| Trusting a mutating tool's success when the write path is silent | `setting.__set__` drops a validator-rejected write and returns normally, so the action "succeeds". Verify by reading the value back (`graph_editor_set_property` raises `set_rejected`) |
| Walking `type(node)._settings_bags` without filtering | `props` (framework position/size/muted/skin, 13 fields) sits in there beside author bags — include it deliberately or exclude it deliberately, never accidentally |
