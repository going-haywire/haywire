---
status: draft
doc_template: reference
scope: The rules Python code in this repository is written and reviewed by — what tools enforce, what review checks, and which rules also protect authors' libraries
see-also:
  - design-principles.md
  - component-naming.md
  - ../architecture/errors/errors-arch.md
---

# Coding standards

These rules hold for all Python in this repository: `packages/`, `barn/`, `tests/` and
`scripts/`. A review cites a rule by its ID ("breaks CS-E2"). The node templates that
`haywire init` and the New Node wizard copy into authors' libraries follow every rule.

## How to read a rule

Each rule has a stable ID, `CS-<area><n>`, and these lines:

- **Why**: what goes wrong without it.
- **Example**: ✗ the wrong form, ✓ the right one.
- **Enforced by**: the tool that checks it, or *review*. Review skips what a tool checks.
- **Scope**: *repo* is this repository's house style. *libraries too* means the rule
  protects a mechanism that also runs in an author's library (hot reload, annotations
  the framework reads, docstrings the studio displays), so a library that ignores it breaks.

Formatting, line length (109) and the lint rules in `[tool.ruff]` and `[tool.mypy]` of
the root `pyproject.toml` are part of this standard; the comments there say why each is
on. Run them as [Checks](../guides/development.md#checks) describes.

## Adding or changing a rule

A rule belongs here only when all three hold:

1. No tool can check it. A rule a tool can check is a line of config instead.
2. Breaking it has cost something in this repository: a bug, rework, a trap in
   `.insights/`, a review comment that keeps coming back. The proposal names that evidence.
3. It is specific to haywire, or the code disagrees with itself on it.

Changes go through a pull request the maintainer reads line by line, like any file that
steers agents. When a tool starts enforcing a rule, the rule shrinks to one line and its
**Enforced by** names the tool. A dropped rule keeps its ID as `CS-X9 · retired`, with one
line saying why, so old citations still resolve.

---

## D · Docstrings and comments

A docstring tells a caller what the code does and how to use it. A comment tells a
maintainer why a specific line is written the way it is. Everything else belongs
somewhere else.

### CS-D1 · Each kind of information has one place

| Information | Place |
|---|---|
| What it does, arguments, return value, exceptions, side effects, observable edge cases | Docstring |
| Usage example, when correct use isn't obvious from the signature | Docstring |
| What implementers of an overridable method or Protocol must guarantee | Docstring |
| Why a non-obvious line is written the way it is | Comment on that line |
| What changed and what it used to be | Commit message |
| Design reasoning and rejected alternatives | ADR in `docs/adr/`; a comment may point to it (`# See ADR 0017.`) |
| Meaning of domain terms | [Glossary](glossary.md) |
| Behavior of another class or function | That component's docstring; reference it instead of restating it |

**Why**: information in the wrong place goes stale where nobody looks for it.
**Enforced by**: review. **Scope**: repo.

### CS-D2 · A docstring states the contract, for a reader who sees only the signature

- Start with a one-line summary of what the code does or returns ("Return ...",
  "Reset ...", "A setting that ..."). It must make sense alone in an IDE tooltip.
- Describe behavior, not implementation.
- State edge cases as outcomes: "Returns ``None`` if the pin isn't promoted." Don't
  explain why the outcome is right.
- In user-facing API (settings, node base classes, anything a library author touches),
  use the words users see in the UI. Keep internal terms (bag, cell, tier, descriptor) to
  internal code.
- Refer to another component by name ("See ``DataField.accepts_absence``.") instead of
  describing what it does.
- Don't describe callers. Test: if the sentence would become false when some other code
  changes, it describes that code, not this one.
- Keep timing and threading guarantees that callers or implementers rely on: "Called once
  when the edge is built, so the result must not depend on the current value."

Before writing a sentence, check: can the caller act on it? Would it stay true if the
implementation were rewritten with the same behavior? Does it mention the past or a
rejected alternative? Only a yes, yes, no sentence goes in.

✗

```python
def _element_type(self) -> type[IType] | None:
    """The wrapped IType, read off the cell rather than declared here.

    ``type_cls``, NOT ``get_stored_type()``: the two deliberately disagree
    for a wrapper field. ``type_cls`` is what the field IS ... (five more lines)
    """
    wrapper = self.port.data.type_cls
```

✓

```python
def _element_type(self) -> type[IType] | None:
    """Return the element type of this row's wrapper field (``INT`` for ``OPTIONAL[INT]``), or ``None``."""
    # type_cls, not get_stored_type(): the stored type is already the element type.
    wrapper = self.port.data.type_cls
```

**Why**: callers read docstrings in tooltips and Component Docs; narration and rationale
there bury the contract and go stale with the implementation.
**Enforced by**: review. **Scope**: repo.

### CS-D3 · Arguments, return values and exceptions are documented when the type doesn't say it

- Document an argument or return value of a plain type (`str`, `int`, `float`, `bool`),
  `dict`, `list`, `tuple`, `Any`, a union or a callable: what the value represents, plus
  whichever apply: units, valid range, format, allowed values, what `None` means, where
  to get one.
- Skip the entry for a documented framework class, and when the name alone says
  everything (`label: str`; but `port_id: str` needs one if ids have a format).
- A precise name or type beats an explanation: `timeout_s: float` needs no "in seconds".
  Choose names and types so that fewer entries are needed.
- Document every exception a caller can reasonably handle, with the condition that
  raises it.
- Sections in this order: `Args:`, `Returns:`, `Raises:`, then the example. In a private
  helper, a phrase in the summary is enough.

```python
Args:
    iou_threshold: Minimum overlap between two boxes, from 0 to 1, for the
        lower-scoring box to be dropped.
    port: The port to connect.   # ✗ delete: framework type, clear name
```

**Why**: the entry carries what the signature can't; an entry that repeats it is noise.
**Enforced by**: review. **Scope**: repo.

### CS-D4 · Public classes, and public functions whose use isn't obvious, have an example

- Show each typical way to use it: the plain call, and every argument, context block or
  mode that changes the result, each with a short comment on its effect. Never cut a
  correct example to save space.
- Examples must be correct for the current code; take them from the tests and real call
  sites.
- In reST docstrings, the example follows the sections, introduced by `Example::` and
  indented. In displayed docstrings (CS-D5), use a fenced block.

**Why**: an example is the fastest way to use an API correctly, and a wrong one is worse
than none. **Enforced by**: review. **Scope**: repo.

### CS-D5 · Displayed docstrings are Markdown in the user's words; all others are reST

**Displayed docstrings** are the class docstrings of registered components (nodes,
types, widgets, skins, panels, and anything else the studio shows in Component Docs or
returns from `describe_component`). They are user documentation rendered as Markdown:

- single backticks for code: `OPTIONAL[INT]`;
- fenced code blocks with a language tag, not indented blocks;
- no reST: no double backticks, no `::`, no roles like `:class:`;
- the words users see in the UI, with internals left out.

**All other docstrings** (methods, functions, modules, non-component classes) use reST:
double backticks for code, and `::` followed by an indented block for examples.

**Why**: the studio renders a component's class docstring as Markdown; reST shows up as
literal markup in Component Docs and in what Farmhand returns.
**Enforced by**: review. **Scope**: libraries too.

### CS-D6 · A comment says why, in the present tense, on the line it explains

- Explain why, not what. If a better name or a small helper would make the code say it,
  change the code instead.
- Write about the code as it is now, on the line it explains, not in the docstring.
- Aim for one or two lines. A comment longer than four lines is usually design reasoning
  that belongs in an ADR.
- Leave markers (`# TODO`, `# noqa`, `# type: ignore`, `# pragma`, licence headers) as
  they are.

**Why**: a comment that narrates the code or its history drifts from it.
**Enforced by**: review. **Scope**: repo.

### CS-D7 · Docstrings and comments never carry history, argument or session reasoning

- No history: "used to", "previously", "no longer", "was changed to". Git keeps it.
- No arguments against alternatives: "NOT X", "deliberately", "rather than". Say what
  the code does. Where a maintainer could plausibly reintroduce a bug, one present-tense
  line is enough: `# type_cls, not get_stored_type(): the stored type is already the element type.`
- No reasoning from the work session that produced the code.
- No emphasis in ALL CAPS or bold. If a word needs emphasis to be understood, rewrite the
  sentence.

**Why**: these read as contract and aren't; they are where agent-written text drifts most.
**Enforced by**: review. **Scope**: repo.

### CS-D8 · Length follows the kind of code

Counting prose lines only (examples, section entries and blank lines don't count):

- Private helper: one line; up to about five with edge cases. No docstring is fine when
  the name says it all.
- Public function or method: summary plus up to about ten lines.
- Public class: summary, when to use it, an example, edge cases; rarely over 20 lines.
- Module: what it contains and when to use it; rarely over 25 lines.

These are guides, not limits: cut rationale, history and narration, never contract.
**Enforced by**: review. **Scope**: repo.

### CS-D9 · Docstring shape follows the Google convention

Summary on the first line, a blank line after it, sections as in CS-D3.
**Enforced by**: review (ruff `D2xx`/`D4xx`, Google convention, planned). **Scope**: repo.

---

## T · Typing

### CS-T1 · Annotations use the modern syntax

`list[str]`, `X | None`, `A | B`, `Self`, `def f[T](x: T) -> T`, and `Callable` from
`collections.abc`; never `List`, `Optional`, `Union` or a `TypeVar` for a plain generic.
**Enforced by**: ruff `UP`. **Scope**: repo.

### CS-T2 · Every module starts with `from __future__ import annotations`

Forward references then need no quotes: ✗ `-> "Graph"` ✓ `-> Graph`.
**Enforced by**: ruff `I002` and `UP037`. **Scope**: repo.

### CS-T3 · A type in an annotation the framework reads at runtime is imported at runtime

The framework resolves annotations with `get_type_hints` or `inspect.signature` on
settings classes, state classes, Farmhand tools and node worker methods. With CS-T2,
every annotation is a string resolved at that moment against the module's globals, so a
name imported only under `TYPE_CHECKING`, or a class defined inside a function (a test,
typically), raises there, far from the import.

✗

```python
if TYPE_CHECKING:
    from my_library.devices import Camera

class CameraState(AppState):
    camera: Camera | None = None   # get_type_hints(CameraState) raises NameError
```

✓ import `Camera` at module level. If that is a cycle, annotate with a type that resolves
at runtime (`SessionState.session` is annotated `weakref.ref` for this reason) rather
than hiding the import under `TYPE_CHECKING`.

**Why**: the failure is silent until the class is read, often at registration or in an
agent's tool call. **Enforced by**: review. **Scope**: libraries too.

### CS-T4 · Public functions and methods are fully annotated

Every parameter and the return value, `-> None` included. Private helpers and UI
callbacks may omit annotations; a signature is never half annotated.
**Why**: a half-typed signature looks checked and isn't; mypy skips the body of an
unannotated function.
**Enforced by**: mypy `check_untyped_defs` for the bodies, `disallow_incomplete_defs`
(planned) for half-annotated signatures; review for the public surface. **Scope**: repo.

### CS-T5 · Every escape hatch names its code and its reason

`# type: ignore[code]`, `# noqa: RULE` and `cast()` carry a reason on the same line or
the line above, unless the code says it (`import-untyped`). An escape hatch that no
longer suppresses anything is deleted.

✗ `value = cast(int, raw)` ✓ `value = cast(int, raw)  # the INT widget only ever stores int`

**Why**: an unexplained suppression is never removed, and a stale one hides the next real
error on that line.
**Enforced by**: mypy `ignore-without-code` and `warn_unused_ignores`; ruff `PGH004` and
`RUF100` (planned); review for the reason. **Scope**: repo.

### CS-T6 · `Any` only where the type is unknowable

At a real boundary: parsed JSON or TOML, a `**kwargs` passthrough, an untyped third-party
API. Not as a stand-in for a type nobody worked out.
**Why**: `Any` switches checking off for everything it touches, silently.
**Enforced by**: review, for new code. **Scope**: repo.

---

## E · Errors

How failures reach the error ledger, and the list of named boundaries, is
[errors-arch.md](../architecture/errors/errors-arch.md). These rules cover how ordinary
code raises and catches.

### CS-E1 · A rejection correct code can reach is a `Refusal`

Bad input, a stale id after another session's edit, a name collision: raise `Refusal`
(`haywire.core.errors`, and `haywire.api` for libraries). Anything only a bug can reach
raises any other exception. Never `ValueError` for an expected rejection.
**Why**: a `Refusal` goes back to the user or agent with its own message; anything else is
recorded as a failure in the ledger.
**Enforced by**: review. **Scope**: libraries too.

### CS-E2 · A broad `except` is a boundary or best-effort code that logs

`except Exception` appears only:

- at a named boundary, which calls `report_failure` (errors-arch §3 and §6), or
- in best-effort code (cleanup, teardown, an optional feature) that logs with
  `exc_info` and says on the line why a failure there is harmless.

Never a silent `pass`, `continue` or `return`.

✗

```python
try:
    watcher.stop()
except Exception:
    pass
```

✓

```python
try:
    watcher.stop()
except Exception:
    # Teardown: a watcher that fails to stop dies with the process.
    logger.debug("watcher stop failed", exc_info=True)
```

**Why**: a swallowed exception is the silent failure this codebase loses the most time to.
**Enforced by**: review (ruff `S110`/`S112`, planned). **Scope**: repo.

### CS-E3 · Catch the narrowest exception the code expects

✗ `except Exception` around a dict lookup ✓ `except KeyError`.
**Why**: a broad catch turns an unrelated bug into the expected fallback.
**Enforced by**: review. **Scope**: repo.

---

## I · Imports

### CS-I1 · Imports are sorted: standard library, third party, first party

**Enforced by**: ruff `I` with `known-first-party`. **Scope**: repo.

### CS-I2 · Dependencies point one way

`haybale-*` → `haywire-studio` → `haywire-core`; libraries import the framework through
the Author API (ADR 0084). **Enforced by**: ruff `TID251`. **Scope**: libraries too
(`haywire init` configures it).

### CS-I3 · No relative imports in a barn library

**Why**: hot reload resolves a library's modules through `sys.modules` and mis-resolves a
relative import mid-reload, silently. **Enforced by**: ruff `TID252` (barn/ only).
**Scope**: libraries too.

### CS-I4 · An import inside a function names its reason

Imports are at module level. A local import is allowed for one of three reasons, named
in a short comment:

- `# cycle: <module> imports this one`;
- a heavy or optional dependency (`torch`, `cv2`, a model hub), loaded only when used;
- `# reload:` a barn module that must be looked up fresh after a hot reload.

✗

```python
def load(self):
    from haywire.core.graph import BaseGraph
```

✓

```python
def load(self):
    from haywire.core.graph import BaseGraph  # cycle: graph imports node, node imports this
```

**Why**: an unexplained local import is the one the next reader tidies to the top and
turns into a cycle or a stale reference after reload. Tests follow
[tests/README.md](https://github.com/going-haywire/haywire/blob/master/tests/README.md).
**Enforced by**: review. **Scope**: repo.

---

## S · State and dependency injection

### CS-S1 · An app-scoped service comes from the injector

Services are provided by `HaywireModule` (`haywire.core.di.config`) and reach the objects
the injector builds through their constructors.
**Why**: a service reached any other way can't be replaced in a test or an embedding.
**Enforced by**: review. **Scope**: repo.

### CS-S2 · Objects the injector doesn't build read services through `haywire.core.di.context`

Nodes, ports, edges and other objects built from graph data or by authors' code call an
accessor such as `get_node_factory()`. Adding an accessor is an architecture decision
for the maintainer.
**Why**: these constructors are author-facing and rebuilt by hot reload, so they can't
take services as arguments; each accessor is process-wide state.
**Enforced by**: review. **Scope**: repo.

### CS-S3 · No other module-level mutable state

A module-level variable that changes after import is allowed only for a process-wide
fact, named by its kind and commented with why it is process-wide: an
[observable store](glossary.md) (error ledger, activity tracker), a strategy hook (a
module-level callable whose absence is a valid mode, such as the access resolver), or a
process switch (GC freeze, GIL switch). A new one is an architecture decision for the
maintainer.
**Why**: module state outlives sessions and survives or resets across hot reload in ways
tests don't show; see
[the DI context trap](https://github.com/going-haywire/haywire/blob/master/.insights/project_settings_registry_construction_side_effects.md).
**Enforced by**: review. **Scope**: repo.

### CS-S4 · Never `ContextVar` for app state

**Why**: a hot-reloaded module captures a different `ContextVar` instance than the rest of
the app, so lookups miss silently; see
[project_di_context.md](https://github.com/going-haywire/haywire/blob/master/.insights/project_di_context.md).
**Enforced by**: review. **Scope**: repo.

---

## L · Logging and output

### CS-L1 · Each module logs through `logging.getLogger(__name__)`

**Why**: the logger tree follows the package tree, so one setting silences or raises a
whole library. **Enforced by**: review. **Scope**: repo.

### CS-L2 · `print` only for a command-line tool's output to its user

Everything else logs. **Why**: an embedder of the library system or a test can't silence
a print. **Enforced by**: review (ruff `T20` with per-file ignores for CLI modules,
planned). **Scope**: repo.

### CS-L3 · Log levels mean the same everywhere

| Level | For |
|---|---|
| `DEBUG` | diagnostics a developer turns on |
| `INFO` | lifecycle a user would recognise: a library loaded, a graph saved |
| `WARNING` | degraded but working: a fallback taken, a setting ignored |
| `ERROR` | a failure; on a pathway the ledger covers, report it with `report_failure` instead of `logger.error` |

**Why**: a `logger.error` on a ledger pathway is a failure the Errors editor never shows
(errors-arch §6). **Enforced by**: review. **Scope**: repo.

---

## See also

- [Component naming](component-naming.md): names of nodes, types and other components.
- [Design principles](design-principles.md): what the framework refuses and how
  machinery is shaped.
- [Errors architecture](../architecture/errors/errors-arch.md): boundaries and the ledger.
- [tests/README.md](https://github.com/going-haywire/haywire/blob/master/tests/README.md):
  how tests are written.
- [.insights/INDEX.md](https://github.com/going-haywire/haywire/blob/master/.insights/INDEX.md):
  known traps, NiceGUI and async among them.
