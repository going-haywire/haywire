---
status: draft
doc_template: reference
scope: The principles a design change to the framework is held to — what the framework refuses, how machinery is shaped, and how user data survives a code change
see-also:
  - glossary.md
  - design-guide.md
---

# Design principles

These hold for every change to the framework and its libraries. A design that breaks one
needs a reason strong enough to write down in an ADR.

## The framework refuses only what breaks

The framework refuses a configuration only when it breaks or creates an unstable
condition: a crash, unbounded recursion, values that silently depend on order, edges that
silently go dead. Everything else is the library or node author's choice.

- **State a rule by the mechanism that breaks, not by a category.** "A widget can only
  write to a field that holds its own value", not "no widgets on control or callback
  pins". The error message names the same mechanism.
- **Defuse rather than refuse.** Make the breaking path harmless (a widget becomes
  read-only) and leave the configuration allowed.
- **A rule that guards a silent failure is a real rule.** A data node with no outlet never
  runs; refusing it stays.
- **No in-band sentinels.** Absence is modelled explicitly (`OPTIONAL`, holding absence),
  never as a reserved value.

Before adding a check, ask what breaks without it. If nothing does, leave it out.

## No special-case gates

Don't gate one node kind or one wire because the outcome is pointless (a reroute on a
stage, an inserted reroute on an annotation link). Gates like these end up in places
nobody finds later. Block only what breaks something: data loss, invisible edits, a
crash.

## Simple, general machinery

Prefer one predictable, general rule over special cases that polish one scenario, even at
a small cost in the user experience (an extra or empty undo step, for example). A rule per
field kind or per type is harder to maintain than the cost it saves.

## A code change yields a pristine node

When code changes under existing user data (hot reload, a new node version), the honest
result is the node as the new code defines it. Don't infer whether old values still
"fit" by inspecting values, validators or types: such inference misfires in ways nobody
planned for. Data carries over only by declared identity, the same key with the same
declared type, stated as one rule.
