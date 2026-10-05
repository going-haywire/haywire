---
name: refuse-only-what-breaks
description: The framework refuses a configuration only where a mechanism breaks, and states the rule by that mechanism, not by a category of type or wire; it defuses the breaking path where it can
status: accepted
see-also: ADR-0003, ADR-0034, ADR-0042, ADR-0044
level: architectural
---

# Refuse only what breaks

**Context.** Several rules refused configurations by category: `@type` refused a widget on any control or callback type, `ArrayType` refused control and callback elements, and nothing refused a value type without a wire type, whose pins then silently matched nothing. Two bare `ADD` slots linked and did nothing. Rules by category hide what they guard and block what works.

**Decision.** The framework refuses a configuration only where something breaks — a crash, unbounded recursion, a value that depends on write order, an edge that can never work — and states the rule by that mechanism. Where the breaking path can be made harmless, it is defused instead of refused. Applied in edge-kinds step 5.2:

- A widget may sit on any type. It writes only to a field that can hold an own value (`DataField.accepts_own_value()`); on a pooled field or an `ADD` slot it refuses the edit and shows the model again, as it already did on a linked inlet.
- Arrays of control and callback elements are allowed: each combination runs end to end under test. `PooledType` refuses a control element: the pool reads every linked outlet, so a source that never fired adds its empty payload, which reads as a fired one. It refuses an outlet, because a pool holds no own value to write.
- `@type` refuses a value type with no wire type, unless it is a container or wrapper (which takes its element's) or a bare `ADD` (the wildcard): its pins could never link.
- Two bare `ADD` slots do not link: the edge has no wire type to take.
- Pins on a `VISUAL` wire never make a node invalid, except on a reroute: they never take part in execution.
- How many edges a port takes follows the same principle; see ADR 0044.

**Alternatives.** *Keep category rules and add exceptions* — each exception is another category, and the rule still does not say what it protects. *Refuse nothing and document* — a pin that can never link, or a widget that crashes on first edit, fails silently or late.

**Consequences.** A rule's error message names the mechanism and the fix. A configuration nobody anticipated is allowed until something breaks, and the test that finds the break names the rule to add.
