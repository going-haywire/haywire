---
name: link-ceiling
description: A port's link count is a ceiling the framework derives from the port's role and its field's storage; a port can only narrow it (single_link); allow_multiple_links is gone
status: accepted
see-also: ADR-0003, ADR-0042, ADR-0043
level: architectural
---

# The link ceiling

**Context.** `DataPort.allow_multiple_links` was one flag with two writers: `__post_init__` overwrote it by flow (later by wire role), and a container's `_configure_port` overwrote it again (`PooledType` set it, `ArrayType` set an outlet's). A port saved it whenever it was true, so a derived value came back as if declared. A port author's own value survived only on callback ports.

**Decision.** The framework derives a **link ceiling** from two facts about the port, read on every call of `DataPort.takes_many_links`:

| | Outlet | Inlet |
|---|---|---|
| value wire (`DEPENDENT`, `IMMEDIATE`) | many | one, many when the field `keeps_value_per_source()` |
| `SEQUENCE` | one — the VM keeps one transition per outlet | many |
| `VISUAL` | many | many |
| bare `ADD` slot | many | one |

A container's role is its element's, so `ArrayType[T]`, `OPTIONAL[T]` and `ADD[T]` behave as `T`; `PooledType[T]` lifts its inlet because its field keeps one value per source. A port can only narrow the ceiling, with `single_link=True`, saved only when set. Nothing else writes a link count: `_configure_port` keeps colour and refusals, and mirrors, reroute ports and grown slots start at the ceiling.

**Alternatives.** *Wire types declare per-direction defaults (`outlet_links`, `inlet_links`) and a port overrides them within the limits* — two concepts where one suffices; no wire type in tree needs a ceiling below the mechanism's, and a ClassVar can be added later without breaking anything. *One bool resolved at construction* — its derived value is saved as if declared, and a container's later write skips the limits. *Let a type narrow through `_configure_port`* — reintroduces a second writer.

**Consequences.** A saved `allow_multiple_links` key is ignored on load and dropped at the next save. A callback outlet fans out without declaring anything. Narrowing a port does not narrow the card that mirrors it in a Group.
