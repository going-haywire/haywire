---
status: draft
doc_template: canonical-example
scope: Authoring Farmhand MCP tools — @farmhand decorator, Farmhand base class, FarmhandContext facade, FarmhandError contract, input schema derivation, resource vs tool distinction
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
studio_describe_component        what kind of node is this?          (class docstring)
  └─ graph_editor_query_graph    which node instances exist?         (topology)
      └─ inspect_node get=['summary']          how big / is it ok?
          └─ inspect_node data='info'          what fields exist?    (labels, descriptions)
              └─ inspect_node data='value'     what are they set to?
                  └─ inspect_node data='all' filter=['one_field']    what can I write?
                      └─ graph_editor_set_property                   write it
```

A row from `inspect_node` carries both handles the write tools need: flat `name` for `set_property`, and `accessor` for `promote_setting` (which addresses fields as `accessor` + `field`, not a flat name). `name` is stable across all three `data` levels, so it is also the key that joins a shallow row to its detailed counterpart.

Farmhand tools are **not** the same as MCP *resources*. Tools are actions the agent invokes with arguments and gets a structured result back (`list_tools` / `call_tool` in the MCP spec). Resources are addressable, read-only documents the agent fetches by URI (`list_resources` / `read_resource`) — the baked documentation tree (`farmhand://docs/...`) and per-library `OVERVIEW.md`/`QUICKREF.md` files (`farmhand://library/<id>/...`) are resources, not tools. If what you're exposing is "read this static text," prefer a resource; if it's "do something and return structured data," write a Farmhand tool.

## 2. How it fits

```text
Author declares                Library registers               MCP host serves
────────────────               ─────────────────                ───────────────
@farmhand(                     @library(...):                   list_tools()
    label='...',                 register_components(self):       → name, description,
    description='...',             self.add_folder_to_               inputSchema (derived
)                                     registry(                       from run()'s signature
class MyTool(Farmhand):                folder='farmhands',            or input_schema_override)
    async def run(self, ctx,           registry_cls=
        arg: str) -> dict:              FarmhandRegistry)          call_tool(name, args)
        ...                                                          → FarmhandContext() built,
                                  FarmhandRegistry                     MyTool().run(ctx, **args)
                                  (BaseRegistry subclass)              awaited, result JSON-
                                                                        encoded back to the agent
```

The MCP host (`haywire_studio.farmhand.host`) is the one place that talks the wire protocol. It builds a fresh `FarmhandContext` per call (carrying a progress-reporter callback wired to the MCP session), resolves your tool class from `FarmhandRegistry` by its derived name, and awaits `your_cls().run(ctx, **arguments)`. Everything below `run()` is plain Python — no async MCP SDK types leak into tool bodies.

**Boundaries.** The wire protocol, session tracking, and resource-serving mechanics (`list_resources`/`read_resource`, the docs bake pipeline) live in [architecture/studio](../../architecture/studio/studio-arch.md). This file documents the *authoring* surface only — what you write inside a `farmhands/` folder.

## 3. Important concepts

**The `@farmhand` decorator.** Stamps `class_identity` (a `FarmhandIdentity`, extending the same `BaseIdentity` every component kind shares) and derives `class_library` from the module hierarchy, same as `@node`/`@panel`/`@state`.

| Parameter | Required | Purpose |
|---|---|---|
| `label` | no | Human-readable display name. Defaults to `registry_id`. |
| `description` | no | Shown to the MCP client as the tool's description — this is the *only* text the agent sees before deciding whether/how to call the tool, since derived input schemas carry no per-parameter descriptions (see below). Write it to teach valid argument values, not just restate the label. |
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

**The `FarmhandError` contract.** Raise `FarmhandError(code, message, ids=None)` for any *expected* failure — bad arguments, not-found lookups, gate rejections. The host renders it as a structured MCP tool error (`[code] message (id=..., ...)`), never a raw stack trace. Reserve uncaught Python exceptions for genuine bugs; an agent can branch on `code` but not on exception-message text, so pick a stable, greppable code per failure class and reuse it everywhere that failure can occur.

```python
raise FarmhandError(
    "graph_not_found", f"No open graph '{binding_id}'.", ids={"binding_id": binding_id}
)
```

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

**Every result should carry a `summary` string.** The host injects a fallback (`f"{name}: ok"`) if a returned dict omits one, but an explicit, information-dense summary is the first (and sometimes only) thing a token-conscious agent reads — write one deliberately rather than relying on the fallback.

**Make the caller drill down: separate WHICH from HOW MUCH.** A tool whose full response is expensive should force the caller to choose, on each independent axis, rather than defaulting to everything. `graph_editor_inspect_node` is the reference implementation, with three orthogonal parameters:

| Axis | Parameter | Effect |
|---|---|---|
| Breadth — *which* sections | `get: list[str]` (**required, non-empty**) | `summary`, `node_id`, `ports`, `settings`, `props`, `state` |
| Depth — *how much* per row | `data: str` (default `"info"`) | `info` (identity only) → `value` (+ current value) → `all` (+ writable schema) |
| Selection — *which* rows | `filter: list[str]` (default `[]` = all) | exact row names, one namespace across sections |

The payoff is concrete: on a 29-field node, an unfiltered `data="all"` settings dump is ~4900 chars, while `filter=["one_field"]` at the same depth is ~130 — the agent pays for what it asked for. Design notes worth copying:

- **Default to the cheap end.** `data="info"` means an agent that ignores the parameter still gets the orientation payload, not the expensive one. Make the *expensive* behaviour the thing that must be requested.
- **Keep one join key across depths.** Every row carries `name` at every level, so an `info` row and its `all` counterpart are trivially correlated — and that same `name` is what the write tool takes. Non-identity metadata (`label`, `description`, `category`) appears **only** at `info`; repeating a description on 29 deep rows is pure waste once the agent has read it.
- **Group by the author's own structure.** Ports come back as `inlets`/`outlets`/`configs` (how they are declared and how an agent wiring an edge thinks) and `info`-depth settings are grouped by their `category` — the same clustering the properties panel uses. Grouping also removes a redundant per-row key.
- **Report filter misses.** A name matching nothing comes back under `unmatched`, present only when non-empty. Silently omitting it would make a typo indistinguishable from "that field does not exist" — the worst possible signal just before a write.
- **The host validates `input_schema_override` before `run()` executes** — an empty `get` or a misspelled `enum` value is rejected at the protocol boundary (`Input validation error: [] should be non-empty`), so the tool body never sees it. Keep the in-body guards for non-MCP callers, but write tests against the schema error, not the `FarmhandError`.
- `summary` is emitted **unconditionally** (the canon rule above) *and* is selectable, so `get=["summary"]` is a legitimate cheap survey — the same ergonomic as `count_only=true` on `studio_list_components`.

Prefer these axes over a pile of `include_*` booleans: booleans multiply combinatorially and each one has to be discovered separately, whereas one enum per axis is self-describing in the derived schema.

**Serializing values that cross the wire.** The host JSON-encodes results with `json.dumps(result, default=str)`, so a non-serializable value does not crash — it silently degrades to an object repr (`"<MeshData object at 0x...>"`), which is useless to an agent and unbounded in size. When a tool returns *values* rather than metadata:

- Check serializability instead of trusting the fallback. `haywire.core.types.utils.is_cattrs_serializable(value)` is the codebase's existing predicate for exactly this.
- Emit an explicit marker for what you dropped (`inspect_node` uses `value_omitted: "<type>"`) so the agent learns the value exists but is not retrievable, rather than reading a repr as if it were data.
- Most Haywire value types are already JSON-native: `Vec2i`/`Vec3f`/… are `list` subclasses and `Color`/`Icon` are `str`, so settings values round-trip losslessly with no conversion layer. Arbitrary port `BaseType`s (mesh, frame) do not.
- A `widget_config` may hold a **live zero-arg callable** at `properties["options"]` (the documented dynamic-dropdown mechanism — see [setting-canon](../settings/setting-canon.md)). Resolve it the way the widget does (`options()`), inside a `try/except` so one failing probe can't fail the whole call, and never pass it through unresolved.

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

**The `'studio'` library-id prefix is reserved.** `barn/haybale-studio`'s baseline tools (`studio_status`, `studio_list_components`, ...) own the `studio` library id; the reservation is enforced by library-id uniqueness at discovery, not by `FarmhandRegistry` itself. Don't register a second library under the `studio` id.

## 4. Live examples from the codebase

**Minimal read-only tool** — no arguments beyond a single required string, `read_only_hint` annotation:

```python
--8<-- "barn/haybale-testing/haybale_testing/farmhands/echo_tool.py:echo_tool"
```

**The `FarmhandError` contract** — a tool that always fails, to exercise the structured-error path in tests:

```python
--8<-- "barn/haybale-testing/haybale_testing/farmhands/fail_tool.py:fail_tool"
```

**Pagination + filtering** — `ctx.registry()`, the `page()`/`truncation_note()` convention, and an `include_*` opt-out pattern for rows excluded by default:

```python
--8<-- "barn/haybale-studio/haybale_studio/farmhands/catalog.py:list_libraries_tool"
```

**Mutually-exclusive arguments, idempotent delete, and `ctx.broadcast`** — validates exactly one of two optional arguments is set before doing anything, and notifies open studio UIs after a mutation:

```python
--8<-- "barn/haybale-studio/haybale_studio/farmhands/errors.py:dismiss_errors_tool"
```

What these examples exercise:

| Concept | Where |
|---|---|
| `@farmhand(label=, description=, registry_id=, annotations=)` | every example |
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

- [ ] `@farmhand(label=, description=, registry_id=, annotations=)` decorator
- [ ] Inherit from `Farmhand`
- [ ] Implement `async def run(self, ctx: FarmhandContext, ...) -> dict` — must be `async`
- [ ] Write `description=` to teach valid arguments — it's the only text the agent sees before calling
- [ ] Set `input_schema_override` if you need an `enum` or other schema constraint the derived schema can't express
- [ ] Raise `FarmhandError(code, message, ids=)` for expected failures, not bare exceptions
- [ ] For list results: `limit`/`offset` params + `page()` + `truncation_note()` in `summary`
- [ ] Every returned dict should include an explicit `summary` string
- [ ] For mutations open editors should reflect: `ctx.broadcast(signal)` after the mutation
- [ ] Place file in `farmhands/` folder; register via `FarmhandRegistry` in `register_components`

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
| Assuming type hints alone can express an `enum` | Derived schemas only map primitive types; use `input_schema_override` |
| Raising a bare `ValueError`/`KeyError` for an expected failure | Agent sees an unstructured error instead of a stable `code` it can branch on |
| Returning a list without `limit`/`offset` | No way for a caller to scope a large result — the exact problem `studio_list_components` had before it grew filters |
| Mutating state without `ctx.broadcast(...)` | Open studio editors silently go stale until their next unrelated refresh |
| Writing a tool when a static resource would do | Resources (`farmhand://...`) are cheaper for the client and don't need argument handling — reserve tools for actions |
| Returning a value without checking it serializes | `json.dumps(..., default=str)` turns a mesh/frame into an unbounded object repr instead of failing — check with `is_cattrs_serializable` and emit an explicit omission marker |
| Passing a `widget_config` through verbatim | `properties["options"]` may be a live callable (dynamic dropdowns). Resolve it like the widget does; a plain port can't hold one (ADR 0018) but a **promoted** port can |
| Trusting a mutating tool's success when the write path is silent | `setting.__set__` drops a validator-rejected write and returns normally, so the action "succeeds". Verify by reading the value back (`graph_editor_set_property` raises `set_rejected`) |
| Walking `type(node)._settings_bags` without filtering | `props` (framework position/size/muted/skin, 13 fields) sits in there beside author bags — include it deliberately or exclude it deliberately, never accidentally |
