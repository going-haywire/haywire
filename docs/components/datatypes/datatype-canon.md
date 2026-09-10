---
status: draft
doc_template: canonical-example
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

**`flow_type`.** One of `FlowType.DATA`, `FlowType.CONTROL`, `FlowType.CALLBACK`, or `FlowType.NONE`. The framework default is `NONE`; ordinary value-carrying datatypes set `DATA` explicitly (the common case). `CONTROL`/`CALLBACK` mark the type as a non-data signal — these get no widget and no meaningful default.

**Inheritance.** A derived type inherits its parent's full identity (`color`, `widget_key`, `flow_type`, …) and overrides only the parameters you pass to its `@type`. Derived types are **automatically compatible with ancestors** for connections — child→parent works as a passthrough; child→sibling-of-parent walks up to the parent's adapter; parent→child still requires an explicit adapter.

**Serialization.** Override `to_dict()` / `from_dict()` when your type has non-serializable attributes (numpy arrays, file handles). For simple `@dataclass` types, `dataclasses.asdict(self)` and `cls(**data)` work automatically — no override needed.

**Custom field for type coercion.** If incoming values may need casting (e.g. an int arriving where you want a guaranteed float), define a `PrimitiveField` subclass that overrides `set_value()` and assign it as `MyType.field_class = MyTypeField` *after* both classes exist. The built-in `FLOAT`/`INT`/`BOOL` types use this pattern.

**Widget binding.** Set `widget_key=` and `widget_config=` on the type when **every port** of this type should use the same widget. **Discouraged for general use** — the codebase's `@type` docstring marks `widget_key`/`widget_config` as `NOT RECOMMENDED`. Prefer per-port widget overrides via `as_inlet(widget_key=...)` unless you have a specific reason (e.g. a fixed `MathOperation` enum where a `SelectWidget` is the only sensible UI).

**`store_strategy`.** Enum (`StoreStrategy`) on `DataTypeIdentity` controlling when field values persist on save. Default is `NONE`. Older docs may refer to a `store_data: bool` parameter — that name is out of date; the current code uses `store_strategy: StoreStrategy`.

**`@adapter`-paired types.** If two types should interop, write an adapter in [components/adapters](../adapters/adapter-canon.md). The adapter system chains automatically: `INT → FLOAT` and `FLOAT → STRING` together yield `INT → STRING` for free, no explicit chain adapter needed.

### The four families

Every IType belongs to exactly one, and the choice is not cosmetic — other subsystems dispatch on it.

| Family | Holds | Storage | Parameterised |
|---|---|---|---|
| `PrimitiveType` | one unwrapped primitive | `PrimitiveField` | no |
| `BaseType` | a structured instance (the instance IS the data) | `BaseField` | no |
| `CompoundType` | **N** elements of one IType | `CompoundField` subclasses | `ArrayType[FLOAT]` |
| `WrapperType` | **exactly one** value of another IType, **or absence** | the element's field class, made absence-tolerant | `OPTIONAL[INT]` |

Two rules worth knowing before you add a type:

**A `PrimitiveType` cannot hold absence.** `PrimitiveType.__init__` treats `None` as "not supplied" at every step and raises if one survives the fallbacks, so `@type(default={'value': None})` on a primitive is a latent `TypeError` — `create_field()` never instantiates the type, but `create_default()` and `PrimitiveField.to_dict()` do. A type whose domain includes absence belongs in `WrapperType`.

**`CompoundType` means "container", and code acts on that.** `AdapterFactory` builds element-wise adapter chains for compounds, and `pin_render` gives them collection iconography. A type holding zero-or-one that inherited `CompoundType` for the parameterisation machinery would get both behaviours silently and wrongly. That is why `WrapperType` exists as a separate family rather than as a `CompoundType` subclass — see [ADR 0033](../../adr/0033-absence-is-a-type.md).

**Parameterised identity differs between the two.** A `CompoundType[T]` **shares** its parent's `class_identity`, so every `ArrayType[*]` reports one colour and one widget key and differs only in its element. A `WrapperType[T]` stamps a **per-parameterisation** identity instead: it keeps the wrapper's `registry_key` and `widget_key` (a graph must resolve back to the wrapper, and the wrapper's own widget renders the row) but takes the element's colour and declared widget properties — without which `OPTIONAL[VEC3F]` would reach `VecWidget` with no `vec_meta` and be unrenderable.

## 4. Live examples from the codebase

Source: [`barn/haybale-example/haybale_example/types/`](../../../barn/haybale-example/haybale_example/types/)

**Derived primitive type** — `Temperature` extends `FLOAT` with a custom widget binding. Inherits all FLOAT adapters automatically; a `Temperature` outlet connects to any `FLOAT` inlet with no extra adapter:

```python
--8<-- "barn/haybale-example/haybale_example/types/specs.py:6:33"
```

from: `Temperature` — registry_key: `haybale-example:type:Temperature`

**Derived type with widget and enum choices** — `MathOPSelector` extends `STRING` and pins a `SelectWidget` with a fixed option list at the type level:

```python
--8<-- "barn/haybale-example/haybale_example/types/math.py:22:37"
```

from: `MathOPSelector` — registry_key: `haybale-example:type:MathOPSelector`

**Compound type** — `MapsStringType` is a `CompoundType[T]` for string-keyed maps. Demonstrates the compound category: parameterisable (`MapsStringType[FLOAT]`), custom `field_class` assigned post-definition, no `value` property (compound types are descriptors, not instances):

```python
--8<-- "barn/haybale-example/haybale_example/types/maps_string_type.py:14:55"
```

from: `MapsStringType` — registry_key: `haybale-example:type:MapsStringType`

**Wrapper type** — `OPTIONAL` is the framework's only `WrapperType`. The whole type is a decorator plus a docstring: `__class_getitem__` on the family base derives the absence-tolerant `field_class`, stamps the merged identity, and refuses to wrap another wrapper:

```python
--8<-- "packages/haywire-core/src/haywire/barn/builtin/types/optional.py:8:18"
```

from: `OPTIONAL` — registry_key: `haywire-core:type:OPTIONAL`

What these examples exercise:

| Concept | Where it shows up |
|---|---|
| `@type` on a derived `PrimitiveType` (FLOAT subclass) | `Temperature` |
| Inherited widget binding from parent | `Temperature` inherits FLOAT's field |
| Per-type `widget_key` + `widget_config` | `Temperature`, `MathOPSelector` |
| `@type` on a derived STRING with enum choices | `MathOPSelector` |
| `default` as bare value (auto-wrapped to `{'value': ...}`) | `MathOPSelector` |
| `CompoundType[T]` for parameterisable collection types | `MapsStringType` |
| `field_class` assigned post-definition | `MapsStringType.field_class = MapsStringField` |
| `WrapperType[T]` for a value-or-absence type | `OPTIONAL` |
| `default={'value': None}` (legal only outside `PrimitiveType`) | `OPTIONAL` |
| `flow_type=FlowType.DATA` explicit | all four |

For everything ports-related (`as_config`, `on_change`, `on_connect`, port reconfiguration), see [guides/ports](../../guides/ports.md). For the worker function and node lifecycle, see [components/nodes](../nodes/node-canon.md).

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
