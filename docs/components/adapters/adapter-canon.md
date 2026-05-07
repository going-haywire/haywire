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

## 4. One comprehensive example

A `Color` datatype (RGBA dataclass, defined in [datatype-canon §4](../datatypes/datatype-canon.md#4-one-comprehensive-example)) that needs three pieces of interop: convert *to* a hex string for export, convert *from* a hex string for import, and a `Temperature → Color` adapter that maps temperature values to a heat-map colour. Together they exercise inheritance-based chaining (`Color → STRING` works directly through `ColorToStringAdapter`; `STRING → Color` directly; chained conversions through `FLOAT → STRING` aren't needed because `Color` already knows hex), plus an explicit cross-domain adapter (`Temperature → Color`).

```python
# my_lib/adapters/color_adapters.py

from haywire.core.adapter.base import BaseAdapter
from haywire.core.adapter.decorator import adapter   # exported from .base too
from haybale_core.types.specs import STRING

from ..types.color import Color
from ..types.temperature import Temperature   # @type-decorated PrimitiveType[float]

# ── 1. Color → STRING (hex export) ─────────────────────────────────────

@adapter(
    description='Convert Color to hex string (#rrggbb)',
    converts_from=Color,
    converts_to=STRING,
    priority=10,
)
class ColorToStringAdapter(BaseAdapter):
    """Outlet of type Color can connect to inlet of type STRING."""

    def convert(self, value: Color) -> str:
        # Color.to_hex() defined on the datatype (see datatype-canon §4)
        return value.to_hex()

    def get_test_value(self) -> Color:
        # Sample for edge sample-testing. Pick a value that exercises every
        # branch of convert(); here all four channels are non-default.
        return Color(r=1.0, g=0.5, b=0.0, a=0.8)

# ── 2. STRING → Color (hex import) ─────────────────────────────────────

@adapter(
    description='Convert hex string (#rrggbb) to Color',
    converts_from=STRING,
    converts_to=Color,
    priority=10,
)
class StringToColorAdapter(BaseAdapter):
    """Inverse of ColorToStringAdapter. Together they make Color and STRING
    fully interchangeable on edges (in both directions)."""

    def convert(self, value: str) -> Color:
        # Color.from_hex() defined on the datatype (see datatype-canon §4)
        return Color.from_hex(value)

    def get_test_value(self) -> str:
        return '#ff8000'

# ── 3. Temperature → Color (cross-domain conversion) ───────────────────

@adapter(
    description='Map temperature to a blue–red gradient colour',
    converts_from=Temperature,
    converts_to=Color,
)
class TemperatureToColorAdapter(BaseAdapter):
    """A non-trivial conversion — clearly not an inheritance passthrough.
    Maps Celsius temperatures linearly into a 0..255 hue range. Demonstrates:
      - convert() containing real domain logic
      - get_test_value() picking a representative input
      - get_test_repetitions() = 3 because we want to exercise the
        clipping branches (cold, hot, mid) in the connection-time test.
    """

    COLD = 0.0   # °C → fully blue
    HOT  = 100.0 # °C → fully red

    def convert(self, value: float) -> Color:
        # Temperature is a PrimitiveType[float]; convert receives the
        # unwrapped float, not a Temperature instance.
        t = max(self.COLD, min(self.HOT, value))
        # Linear interpolation in RGB
        ratio = (t - self.COLD) / (self.HOT - self.COLD)
        r = ratio
        b = 1.0 - ratio
        return Color(r=r, g=0.0, b=b, a=1.0)

    def get_test_value(self) -> float:
        # Mid-range sample exercises the interpolation branch
        return 50.0

    def get_test_repetitions(self) -> int:
        # The test harness will pick three sample values across the range
        # for connection-time testing (not strictly necessary here since
        # convert() is deterministic, shown for completeness).
        return 3
```

What this example exercises:

| Concept | Where |
|---|---|
| `@adapter(converts_from=, converts_to=)` decorator | every adapter class |
| Source and target as `IType` *classes*, not instances | `converts_from=Color`, `converts_from=Temperature` |
| `priority=` to disambiguate when multiple adapters match | `ColorToStringAdapter`, `StringToColorAdapter` |
| `convert()` operating on unwrapped values | every class |
| `get_test_value()` returning a sample of the source type | every class |
| `get_test_repetitions()` for non-trivial conversions | `TemperatureToColorAdapter` |
| Two adapters forming a bidirectional pair | Color↔STRING (export and import) |
| Cross-domain conversion (not just type widening) | `Temperature → Color` |
| Convert on a derived primitive's unwrapped float | `TemperatureToColorAdapter.convert(self, value: float)` |

**Chain implications.** With these three adapters registered:

| Connection | Resolved chain | Why |
|---|---|---|
| `Color outlet → STRING inlet` | `[ColorToStringAdapter]` | direct |
| `STRING outlet → Color inlet` | `[StringToColorAdapter]` | direct |
| `Temperature outlet → FLOAT inlet` | `[]` (passthrough) | Temperature inherits FLOAT |
| `Temperature outlet → Color inlet` | `[TemperatureToColorAdapter]` | direct |
| `Temperature outlet → STRING inlet` | `[TemperatureToColorAdapter, ColorToStringAdapter]` | chained |
| `FLOAT outlet → Color inlet` | rejected | no adapter — not every float is a valid Temperature |

The last row is intentional — `FLOAT → Color` is *not* automatic just because we have `Temperature → Color`. Going from an ancestor (`FLOAT`) to a descendant (`Temperature`) always requires an explicit adapter, because the framework can't safely assume every float is a valid temperature.

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
