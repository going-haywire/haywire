---
status: draft
template: canonical-example
scope: Authoring IType subclasses (PrimitiveType / BaseType) and registering them with the type registry via @type
see-also:
  - ../../architecture/execution/edges/edges-arch.md
  - ../adapters/adapter-canon.md
  - ../../reference/glossary.md
---

# Datatype — Canonical Example

## 1. What it solves

A **datatype** in haywire is the *descriptor* of what kind of value flows through a port. It does **not** store data itself — that is the job of the matching `DataField`, selected by the framework based on the type category. As a node author, you define a type when you need to:

- Carry a value with a specific Python representation (`float`, `int`, `str`, `bool`, `bytes`)
- Carry a structured object with multiple attributes (a `Frame`, a `Color`, a `MeshData`)
- Carry a control or callback signal (`EXEC`, `CALLBACK`)

Once registered with `@type`, your datatype becomes available to every node in your library: `MyType.as_inlet('id')` and `MyType.as_outlet('id')` work in any `init()` method, the canvas renders ports in the type's colour, and the adapter system can route values to/from compatible types.

## 2. How it fits

```text
Type definition          Field selection            Worker sees
────────────────         ────────────────           ────────────
PrimitiveType[T]    →    PrimitiveField        →    T (unwrapped)
BaseType            →    BaseField             →    instance of your class
ArrayType[T]        →    ArrayField            →    list[T]
PooledType[T]       →    PooledField           →    dict[node_id, T]
```

You define the type. The framework instantiates the right field. The worker function sees the unwrapped value (for primitives) or the instance itself (for `BaseType`).

**Boundaries.** Three categories cover everything:

- **`PrimitiveType[T]`** — wraps a single Python built-in.
- **`BaseType`** — a structured object, declared as `@dataclass`.
- **`CompoundType[T]`** — a typed collection. The core library already provides `ArrayType` and `PooledType`; you almost never define new compound types.

Adapters live in [components/adapters](../adapters/adapter-canon.md); how the chain is built and tested at edge-link time lives in [architecture/execution/edges](../../architecture/execution/edges/edges-arch.md).

## 3. Important concepts

**The `@type` decorator.** Single decorator for every datatype, primitive or complex. It validates the `default` dict, attaches `class_identity` (a `DataTypeIdentity`), and derives `class_library` from the module path. `default` is the only required parameter.

**`default` dict.** Constructor kwargs for the default instance. For primitives: `{'value': <val>}` (or just the bare value, which the decorator auto-wraps). For `@dataclass` complex types: `{'attr1': v1, 'attr2': v2}` — keys must match the dataclass fields.

**`flow_type`.** One of `FlowType.DATA`, `FlowType.CONTROL`, `FlowType.CALLBACK`, or `FlowType.NONE`. `DATA` is the default and the common case. `CONTROL`/`CALLBACK` mark the type as a non-data signal — these get no widget and no meaningful default.

**Inheritance.** A derived type inherits its parent's full identity (`color`, `widget_key`, `flow_type`, …) and overrides only the parameters you pass to its `@type`. Derived types are **automatically compatible with ancestors** for connections — child→parent works as a passthrough; child→sibling-of-parent walks up to the parent's adapter; parent→child still requires an explicit adapter.

**Serialization.** Override `to_dict()` / `from_dict()` when your type has non-serializable attributes (numpy arrays, file handles). For simple `@dataclass` types, `dataclasses.asdict(self)` and `cls(**data)` work automatically — no override needed.

**Custom field for type coercion.** If incoming values may need casting (e.g. an int arriving where you want a guaranteed float), define a `PrimitiveField` subclass that overrides `set_value()` and assign it as `MyType.field_class = MyTypeField` *after* both classes exist. The built-in `FLOAT`/`INT`/`BOOL` types use this pattern.

**Widget binding.** Set `widget_key=` and `widget_config=` on the type when **every port** of this type should use the same widget. **Discouraged for general use** — the codebase's `@type` docstring marks `widget_key`/`widget_config` as `NOT RECOMMENDED`. Prefer per-port widget overrides via `as_inlet(widget_key=...)` unless you have a specific reason (e.g. a fixed `MathOperation` enum where a `SelectWidget` is the only sensible UI).

**`store_strategy`.** Enum (`StoreStrategy`) on `DataTypeIdentity` controlling when field values persist on save. Default is `NONE`. Older docs may refer to a `store_data: bool` parameter — that name is out of date; the current code uses `store_strategy: StoreStrategy`.

**`@adapter`-paired types.** If two types should interop, write an adapter in [components/adapters](../adapters/adapter-canon.md). The adapter system chains automatically: `INT → FLOAT` and `FLOAT → STRING` together yield `INT → STRING` for free, no explicit chain adapter needed.

## 4. One comprehensive example

A worked example that exercises every concept above: a `Color` complex type with one derived primitive variant, a custom field for coercion, an adapter, and node usage.

```python
# my_library/types/color.py

from dataclasses import dataclass
from haywire.core.types.base import BaseType, PrimitiveType
from haywire.core.types.decorator import type
from haywire.core.data.fields import PrimitiveField
from haywire.core.data.enums import FlowType


# ── A complex type ─────────────────────────────────────────────────────

@type(
    label='Color',
    description='RGBA color, channels in 0.0 – 1.0',
    color='#e91e63',
    flow_type=FlowType.DATA,
    default={'r': 0.0, 'g': 0.0, 'b': 0.0, 'a': 1.0},
)
@dataclass
class Color(BaseType):
    """RGBA color. Default to_dict / from_dict via dataclasses.asdict work
    out of the box because every attribute is JSON-serializable."""
    r: float = 0.0
    g: float = 0.0
    b: float = 0.0
    a: float = 1.0

    def to_hex(self) -> str:
        return '#{:02x}{:02x}{:02x}'.format(
            int(self.r * 255), int(self.g * 255), int(self.b * 255)
        )

    @classmethod
    def from_hex(cls, hex_str: str) -> 'Color':
        h = hex_str.lstrip('#')
        return cls(
            r=int(h[0:2], 16) / 255.0,
            g=int(h[2:4], 16) / 255.0,
            b=int(h[4:6], 16) / 255.0,
        )


# ── A primitive variant with type coercion ─────────────────────────────

@type(
    label='Alpha',
    description='Single-channel opacity in 0.0 – 1.0',
    color='#9e9e9e',
    default={'value': 1.0},  # overrides parent's default
)
class Alpha(PrimitiveType[float]):
    """Specialisation of FLOAT (would inherit from FLOAT in real code).
    Inherits FLOAT's adapters automatically: an Alpha outlet can connect
    to a FLOAT inlet with no additional adapter."""
    pass


class AlphaField(PrimitiveField):
    """Guarantees stored value is a Python float and clamped to 0..1."""
    def set_value(self, value, source_id=None):
        v = float(value)
        return super().set_value(max(0.0, min(1.0, v)), source_id)

# Assign AFTER both classes exist
Alpha.field_class = AlphaField


# ── An adapter (full coverage lives in components/adapters) ────────────
# Adapters belong in components/adapters/adapter-canon.md. Shown briefly
# here only to make the round-trip example complete.

from haywire.core.adapter.base import BaseAdapter, adapter
from haybale_core.types.specs import STRING

@adapter(
    description='Convert Color to hex string',
    converts_from=Color,
    converts_to=STRING,
)
class ColorToStringAdapter(BaseAdapter):
    def convert(self, value: Color) -> str:
        return value.to_hex()

    def get_test_value(self) -> Color:
        return Color(r=1.0, g=0.5, b=0.0)


# ── Using the type in a node ───────────────────────────────────────────

from haywire.core.node.base import BaseNode
from haywire.core.node.decorator import node
from haywire.core.execution.execution_context import ExecutionContext
from haybale_core.types.specs import FLOAT

@node(label='Mix Colors', menu='color/operations')
class MixColorsNode(BaseNode):
    def init(self):
        # Complex type with a non-default initial value
        self.add(Color.as_inlet('color_a', label='Color A',
                                default={'r': 1.0, 'g': 0.0, 'b': 0.0, 'a': 1.0}))
        self.add(Color.as_inlet('color_b', label='Color B',
                                default={'r': 0.0, 'g': 0.0, 'b': 1.0, 'a': 1.0}))
        # Primitive — bare value is auto-wrapped to {'value': 0.5}
        self.add(FLOAT.as_inlet('mix', label='Mix Factor', default=0.5))
        # Variant — its custom field clamps the value at field-set time
        self.add(Alpha.as_inlet('opacity', default=1.0))
        self.add(Color.as_outlet('result', label='Result'))

    def worker(self, context: ExecutionContext,
               color_a: Color, color_b: Color,
               mix: float = 0.5, opacity: float = 1.0):
        t = max(0.0, min(1.0, mix))
        result = Color(
            r=color_a.r * (1 - t) + color_b.r * t,
            g=color_a.g * (1 - t) + color_b.g * t,
            b=color_a.b * (1 - t) + color_b.b * t,
            a=opacity,  # already clamped by AlphaField
        )
        self.out('result', result)
```

What this example exercises:

| Concept | Where it shows up |
|---|---|
| `@type` on `BaseType` with `@dataclass` | `Color` |
| `@type` on `PrimitiveType[T]` | `Alpha` |
| Custom `field_class` for type coercion | `AlphaField`, assigned post-definition |
| Inheritance compatibility | `Alpha` (a FLOAT-like) auto-compatible with FLOAT |
| `default` as constructor kwargs (complex) | `Color`'s `default={'r': …, 'g': …, …}` |
| `default` auto-wrap (primitive) | `Alpha`'s `default={'value': 1.0}`; node-side `default=0.5` |
| `flow_type=FlowType.DATA` | implicit on both |
| Adapter pairing (full coverage in [components/adapters](../adapters/adapter-canon.md)) | `ColorToStringAdapter` |
| `as_inlet` / `as_outlet` | inside `MixColorsNode.init()` |
| Default `to_dict` / `from_dict` (no override needed) | `Color`'s simple dataclass |

For everything ports-related (`as_config`, `on_change`, `on_connect`, port reconfiguration), see [components/ports](../ports/port-canon.md). For the worker function and node lifecycle, see [components/nodes](../nodes/node-canon.md).

---

## `@type` parameter reference

| Parameter | Type | Required | Default | Notes |
|---|---|---|---|---|
| `default` | `dict` | yes | — | Constructor kwargs. Primitives: `{'value': v}` or bare `v`. Complex: `{attr: v, ...}`. |
| `label` | `str` | no | class name | Display name in UI. |
| `description` | `str` | no | docstring | Tooltip / description. |
| `color` | `str` | no | `#757575` | Hex colour for pins on the canvas. |
| `icon` | `str` | no | `None` | Pin icon (applies to all pin variants unless overridden). |
| `icon_in` / `icon_out` | `str` | no | `None` | Inlet- / outlet-specific icon override. |
| `icon_in_multi` / `icon_out_multi` | `str` | no | `None` | Multi-connection icon overrides. |
| `flow_type` | `FlowType` | no | `NONE` | `DATA`, `CONTROL`, `CALLBACK`, `NONE`. |
| `widget_key` | `str` | no | `None` | **NOT RECOMMENDED at type level** — prefer per-port `as_inlet(widget_key=...)`. |
| `widget_config` | `dict` | no | `{}` | **NOT RECOMMENDED at type level** — see above. |
| `store_strategy` | `StoreStrategy` | no | `NONE` | When to persist field values on save. (Older docs called this `store_data: bool` — out of date.) |
| `help_url` | `str` | no | `''` | External documentation link. |
| `registry_id` | `str` | no | class name | Unique ID within the library. |
| `deprecation_warning` | `str` | no | `None` | Emitted when the type is used. |
