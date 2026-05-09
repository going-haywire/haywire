---
status: draft
doc_template: canonical-example
scope: Authoring type-pair adapters with @adapter, BaseAdapter / IAdapter, the convert / get_test_value / execute contract, chain assembly
see-also:
  - ../datatypes/datatype-canon.md
  - ../../architecture/execution/edges/edges-arch.md
  - ../../reference/glossary.md
---

# Adapter — Canonical Example

## 1. What it solves

An **adapter** converts a value from one datatype to another so that ports of incompatible types can be connected. When a user drags an edge from a `Temperature` outlet to a `STRING` inlet, the framework asks the adapter registry: "is there a chain from `Temperature` to `STRING`?" If yes, an adapter chain is attached to the edge and values are converted automatically as they flow through it.

You author an adapter when:

- You introduce a new datatype that should interoperate with existing types (e.g. `Temperature → FLOAT` so any FLOAT-consuming node can also accept a `Temperature`).
- Two existing types need a conversion that's not built in (e.g. `Color → STRING` for hex export, `STRING → Color` for hex parsing).
- You want to specialise the conversion priority when multiple paths exist.

Adapters operate on **unwrapped values** — they receive and return raw Python objects (`float`, `str`, an instance of your custom class), never `IType` wrappers. Subclassing inheritance does most of the work for you: a derived primitive is automatically connectable to its ancestor type without any adapter (e.g. `Temperature` outlet → `FLOAT` inlet just works). You only need an adapter when the conversion is *not* a simple inheritance walk.

## 2. How it fits

```text
Author declares                Library registers              Edge build
────────────────               ─────────────────              ──────────
@adapter(                      AdapterRegistry                When a user
    converts_from=Temp,         (BaseRegistry subclass)        connects two
    converts_to=FLOAT,                                          ports of
)                              Auto-populated by               different types,
class T2F(BaseAdapter):          @adapter decorator on          the EdgeWrapper
   def convert(self, v):         classes in adapter/            asks the registry
       return v                  folder.                        for a chain.
   def get_test_value(self):
       return 25.0                                              If a chain exists,
                                                                 it is attached
                                                                 to the edge and
                                                                 sample-tested
                                                                 before the link
                                                                 is finalised.
```

The registry handles **chain assembly** automatically. If you register `Temperature → FLOAT` and `FLOAT → STRING`, the framework can route `Temperature → STRING` through both — no explicit chain adapter needed.

The runtime mechanics — when chains are searched, how they are tested at edge-build time, when adapter chain rebuild happens after hot-reload — live in [architecture/execution/edges](../../architecture/execution/edges/edges-arch.md). This file documents the *authoring* surface only.

**Boundaries.** Datatype declaration (`@type`, `PrimitiveType`, `BaseType`, the `default` dict) lives in [components/datatypes](../datatypes/datatype-canon.md). The edge lifecycle (validation, sample-test, link/unlink/detach) lives in [architecture/execution/edges](../../architecture/execution/edges/edges-arch.md).

## 3. Important concepts

**The `@adapter` decorator.** Attaches `class_identity` (used by `BaseRegistry` for hot-reload), records `converts_from` and `converts_to`, and registers the adapter with `AdapterRegistry` automatically when its module is loaded.

| Parameter | Required | Purpose |
|---|---|---|
| `converts_from` | yes | Source `IType` class |
| `converts_to` | yes | Target `IType` class |
| `description` | no | Human-readable description |
| `label` | no | Display name (defaults to class name) |
| `priority` | no | Higher value wins when multiple adapters match the same pair |

**`BaseAdapter` is the class to subclass.** It implements the `IAdapter` interface (`packages/haywire-core/src/haywire/core/adapter/base.py`). You implement two methods:

| Method | Required | Purpose |
|---|---|---|
| `convert(self, value)` | yes | Transform a single unwrapped value. Receives the source type's unwrapped Python value, returns the target type's unwrapped Python value. |
| `get_test_value(self)` | yes | Return a sample input value of the source type. Used by the edge build pipeline to verify the chain works at connection time, not runtime. |

Optional overrides:

| Method | Default | Purpose |
|---|---|---|
| `get_test_repetitions()` | `1` | How many times to repeat the test (use higher values when conversion is non-deterministic and you want statistical confidence) |
| `test(value)` | calls `execute(value)` | Custom test harness if the default sample-test is insufficient |
| `execute(value)` | `convert(value)` then chains | Run the full adapter chain. You normally don't override this — `BaseAdapter` handles chaining automatically. |

**Adapter chains are assembled, not authored.** You write single-step adapters. The framework finds chains. If `Temperature → FLOAT` and `FLOAT → STRING` are both registered, then `Temperature → STRING` is connectable for free with the chain `[T2F, F2S]`. You don't write a `Temperature → STRING` adapter unless the chained conversion is unacceptable (lossy, expensive, semantically wrong).

**Inheritance and adapter selection.** A derived primitive (e.g. `Temperature(FLOAT)`) is automatically compatible with its ancestor — no adapter is needed for `Temperature → FLOAT` (passthrough). The framework only searches the adapter graph when no inheritance path exists, or when going *from* an ancestor *to* a descendant (which always requires an explicit adapter, since not every float is a valid Temperature).

**Sample testing at edge build.** When a user creates an edge between two compatible-via-chain ports, the `EdgeWrapper.test` step:

1. Calls `adapter.get_test_value()` for the first adapter in the chain.
2. Pipes that value through every adapter in the chain.
3. If any adapter raises, the edge is rejected with a clear error.
4. Only after the chain succeeds is the edge `link`ed.

This catches type errors at *connection* time, not at first execution — so users see "this edge cannot be made" in the UI rather than a crashed flow.

**Hot-reload.** `AdapterRegistry` extends `BaseRegistry`. When an adapter file changes:

1. The old class is unregistered.
2. The new class is registered under the same `(converts_from, converts_to)` key.
3. Every existing edge using the old chain rebuilds its chain from the new adapter classes.
4. Sample-testing runs again on each edge; edges where the chain now fails are unlinked (but not detached — the framework keeps the edge record for re-linking when the chain works again).

The pipeline is documented in [architecture/hot-reload](../../architecture/hot-reload/hot-reload-arch.md) and the rebuild logic in [architecture/execution/edges](../../architecture/execution/edges/edges-arch.md).

**Imports** (verified against codebase 2026-05):

```python
from haywire.core.adapter.base import BaseAdapter, IAdapter, adapter
from haywire.core.adapter.registry import AdapterRegistry
```

## 4. Live examples from the codebase

Source: [`barn/haybale-testing/haybale_testing/adapters/test_adapters.py`](../../../barn/haybale-testing/haybale_testing/adapters/test_adapters.py)

Three single-step adapters that form a chain: `TEST_BOOL → TEST_INT → TEST_FLOAT → TEST_STRING`. The framework assembles multi-hop chains automatically — no explicit `TEST_BOOL → TEST_STRING` adapter is needed.

**Bool → Int:**

```python
--8<-- "barn/haybale-testing/haybale_testing/adapters/test_adapters.py:bool_to_int_adapter"
```

**Int → Float:**

```python
--8<-- "barn/haybale-testing/haybale_testing/adapters/test_adapters.py:int_to_float_adapter"
```

**Float → String:**

```python
--8<-- "barn/haybale-testing/haybale_testing/adapters/test_adapters.py:float_to_string_adapter"
```

**Compound type adapter** — `MapsStringType → ArrayType` from [`barn/haybale-example/haybale_example/adapters/compound_adapters.py`](../../../barn/haybale-example/haybale_example/adapters/compound_adapters.py). Demonstrates a cross-category conversion with `get_test_value()` delegating to the chain and `get_test_repetitions()` set above 1:

```python
--8<-- "barn/haybale-example/haybale_example/adapters/compound_adapters.py:maps_string_array_adapter"
```

What these examples exercise:

| Concept | Where |
|---|---|
| `@adapter(converts_from=, converts_to=)` decorator | every class |
| `convert()` operating on unwrapped values | every class |
| `get_test_value()` returning a sample of the source type | every class |
| `get_test_repetitions()` above 1 | `MapsStringArrayAdapter` |
| Automatic chain assembly (`BOOL → INT → FLOAT → STRING`) | the three test adapters together |
| Cross-category conversion (compound → array) | `MapsStringArrayAdapter` |
| `get_test_value()` delegating to `self._chain` | `MapsStringArrayAdapter` |

**Chain implications** for the test adapters:

| Connection | Resolved chain | Why |
|---|---|---|
| `TEST_BOOL → TEST_INT` | `[BoolToIntAdapter]` | direct |
| `TEST_INT → TEST_FLOAT` | `[IntToFloatAdapter]` | direct |
| `TEST_FLOAT → TEST_STRING` | `[FloatToStringAdapter]` | direct |
| `TEST_BOOL → TEST_STRING` | `[BoolToInt, IntToFloat, FloatToString]` | auto-chained |
| `TEST_STRING → TEST_BOOL` | rejected | no reverse adapters registered |

For datatype declaration (the `Color` and `Temperature` classes themselves), see [components/datatypes](../datatypes/datatype-canon.md). For the edge build pipeline that consumes these adapters at connection time, see [architecture/execution/edges](../../architecture/execution/edges/edges-arch.md).

---

## Quick reference

### Authoring checklist

- [ ] `@adapter(converts_from=Source, converts_to=Target)` decorator
- [ ] Inherit from `BaseAdapter`
- [ ] Implement `convert(self, value)` — operates on **unwrapped** Python values
- [ ] Implement `get_test_value(self)` — return a sample of the source type
- [ ] Override `get_test_repetitions()` if the conversion is non-deterministic
- [ ] Set `priority=` if multiple adapters could match the same pair

### Imports

```python
from haywire.core.adapter.base import BaseAdapter, adapter
```

### Default vs. override surface

| Always implement | Sometimes override | Never override |
|---|---|---|
| `convert(value)` | `get_test_repetitions()` | `execute()` (chain runner) |
| `get_test_value()` | `test(value)` | `_get_registry_keys()` |

### Common pitfalls

| Pitfall | Why it matters |
|---|---|
| Wrapping the return value in an `IType` (e.g. `return FLOAT(value)`) | `convert()` returns unwrapped values; the framework wraps them |
| `convert()` raising on bad input rather than returning a sensible fallback | Sample-testing rejects the chain; user can't make the edge |
| Writing a `SourceWide → SourceNarrow` adapter without thinking through ambiguity | The framework will use it for *every* `Wide → Narrow` connection — make sure that's safe |
| Forgetting `get_test_value()` | Edge build will fail — the chain can't be sample-tested |
