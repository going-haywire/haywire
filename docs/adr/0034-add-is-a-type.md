---
name: add-is-a-type
description: A pin that grows a new port declares what it accepts through its IType (bare ADD, or ADD[T], a new type family), so an unconvertible edge is refused by the adapter layer instead of by node code
status: accepted
see-also: ADR-0017, ADR-0033
level: architectural
---

# A growing pin declares what it accepts

**Context.** A node can declare a pin that grows: connecting to it replaces it
with a real port, which is how a node offers a variable number of inputs. What
that new port's type should be is the open question. Adopting the type at the
other end covers one case; a node that wants every grown slot to be a `STRING`,
converting whatever arrives, needs to say so — and a pin with no type has no
way to.

The constraint that shapes the answer is that **the adapter layer already knows
how to refuse.** `AdapterFactory.create_chain` resolves a conversion between two
types or reports that none exists, and edge construction acts on that. A growing
pin that participates in that resolution gets filtering for free; one that opts
out of it has to reimplement the same judgement in node code, against a
connection the framework has already accepted.

**Decision.** What a growing pin accepts is a property of its **type**. A pin
says so by being parameterized:

- **bare `ADD`** — undecided. `_is_any` is `True`, so `create_chain` returns a
  pass-through: it connects to anything and adopts the other end's type.
- **`ADD[T]`** — decided. `_is_any` is `False`. Its field reports `T` from
  `get_stored_type()`, so the adapter layer sees an ordinary `T` sink, resolves
  a real conversion chain, and refuses anything that cannot reach `T`.

`INT -> ADD[STRING]` therefore grows a `STRING` port with a conversion on the
edge, and `ArrayType[BOOL] -> ADD[STRING]` grows nothing at all.

## The refusal is structural, not coded

`build()` runs before `link()` at both call sites (`GraphValidation`,
`BaseGraph.add_edge_wrapper`). A failed chain sets `is_built = False`, which
makes `is_functional()` false, which makes `link()` return at its guard — and
`on_connect` fires from inside `_add_link`, past that guard.

So an unconvertible connection never reaches the node's handler. `ADD[T]` needs
no resolvability check of its own: **the type declaration is the filter**.

This ordering is also why a filter written in `on_connect` cannot stand in for
one written in the type. A pin flagged `_is_any` has already had a pass-through
edge built for it by the time the handler runs, so a handler that declines to
retype leaves that edge linked and carrying an unconverted value into a pin of
another type — silently. `_is_any = False` removes the short-circuit that makes
this reachable.

## `ADD` is its own family

`ADD` joins `PrimitiveType` / `BaseType` / `CompoundType` / `WrapperType` as a
fifth family, subclassing `BaseType` and carrying its own `__class_getitem__`.

**Not a `CompoundType`**, for the two reasons ADR-0033 gives for `OPTIONAL`,
which apply here unchanged. `AdapterFactory` would treat `ADD[STRING]` as a
container and build an element-wise chain — so `INT -> ADD[STRING]` would land
in "scalar ↔ compound mismatch" and be refused, killing the feature outright.
`pin_render` would give it collection iconography, overriding the `+` glyph that
tells the user the pin grows. A compound also shares its parent's
`class_identity`, so `ADD[STRING]` could not take STRING's colour.

**Not a `WrapperType`**, though it is the closest fit: ADR-0033 invites members,
and `ADD` passes both of its dispatch-site tests. The bar is how much is
actually shared, and little is. `ADD` reuses the parameterization cache idiom
and `_wrapped_identity` — and the latter is a module-level function any type can
call without inheriting. It needs its own `field_class` (`WrapperType` derives
an absence-tolerant one from the element, which is `OPTIONAL`'s concern, not the
family's), its own serialization, and none of the absence semantics.

Against that, inheriting would grant `ADD` two behaviours that are wrong for it:
`promotion.py` promotes a wrapper-typed setting to a port of its element type,
and `descriptor.py` routes wrapper-typed settings down a wrapper path. `ADD` is
never a setting — a growing pin has no meaning in a settings bag — so both would
have to be fenced with `ADD`-shaped exceptions inside `OPTIONAL`'s code. That is
the bargain ADR-0033 refused when it declined to make `OPTIONAL` a
`CompoundType`: *every other dispatch site is right by default instead of by
exception.* Standing alone, `ADD` reaches neither site.

## Two forms, one type

The mode is selected by parameterization, not by a magic element value. Bare
`ADD` and `ADD[T]` are different runtime classes — `__class_getitem__` generates
a subclass — so `_is_any` is an ordinary class attribute stamped on the
parameterization alongside `element_type_cls`, not a value computed per
lookup on a hot path.

## Considered and rejected

- **`ADD[ANY]` as the spelling for the undecided form**, which would make
  `ADD[T]` a single uniform rule. The rule is not uniform: "`ADD[T]` grows a
  port of type `T`" is false at exactly one value of `T`, where it must instead
  grow a port of the *other end's* type. That is a second algorithm sharing a
  spelling, and it forces `_is_any` to become a value derived per lookup.
  Parameterized-or-not is a boundary the type system already draws.
- **A `grows=True` flag on the port spec.** Growth is a port property, so this
  is the smaller change — but a plain `STRING` pin with a flag cannot express
  "accept anything convertible to STRING" differently from a plain `STRING`
  pin, because that is what a `STRING` pin already does. It buys slot-growth
  and loses the declaration, which is the part that carries information.
- **A typeless placeholder plus a filter in `on_connect`.** The shipped
  predecessor, `ANY`. Ordering defeats it: the pass-through edge exists before
  the handler runs, so declining to retype is not the same as refusing the
  connection. See *The refusal is structural* above.
- **Primitives inheriting from the placeholder**, to make placeholder-to-`INT`
  adapter-free. Inheritance runs the wrong way: `issubclass(source, sink)` is
  the child-to-parent passthrough, so it licenses `INT -> placeholder` (already
  free) and not the reverse. It would also make `_is_any` inherit to every
  primitive, and route every primitive's identity through the placeholder's in
  the `@type` decorator, silently taking its colour and `store_strategy=NEVER`.
- **Keeping a separate undecided type alongside `ADD[T]`.** Two spellings for
  one pin idiom: both grow, both are consumed on connect, both render a `+`.
  Bare `ADD` covers it exactly, so the second name carries no behaviour.

## Consequences

- **`ADD` is the only growing pin.** Its predecessor `ANY` is removed rather
  than aliased, so graphs saved against that registry key do not load. Accepted,
  as with any breaking type change: there is no library-level migration hook
  (ADR-0033 names that gap).
- **`_is_any` means "is a bare `ADD`"** — read on the `create_chain` hot path,
  and by nodes deciding whether the other end has a type to adopt.
- **`serialize_element_type` recurses for `ADD`**, so `ADD[STRING]` round-trips
  as ADD's registry key plus a `STRING` element recipe. The guard also skips an
  element that is the class itself, which is how `BaseType` marks a leaf.
- **`ADD` cannot be a config port.** A config has no pin, so it never connects
  and could never resolve.
- **`ADD[ADD[T]]` raises.** A growing pin has nothing to grow another with.
- **The pin takes its element's colour and keeps ADD's glyph**, via
  `_wrapped_identity`. Ports are built from the parameterized class's identity
  (`as_inlet` merges `asdict(type_cls.class_identity)`), so no `_configure_port`
  override is needed — unlike `PooledType`/`ArrayType`, which rewrite
  `port.color` because a compound shares its parent's identity.

  The glyph half required `_resolve_pin_icon` to read the icon from the port
  rather than from `stored_type`, which for `ADD[STRING]` is `STRING`. Colour
  already travelled through the port; the icon was the one appearance field
  re-read from the type at render time, so a parameterization could not keep
  its own. Reading both from the port also makes a per-port `icon_in=` override
  reach the glyph, as `color=` already did.
