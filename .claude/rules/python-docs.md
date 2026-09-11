---
paths:
  - "**/*.py"
---

# Docstrings and comments

A docstring tells a caller what the code does and how to use it. A comment tells a maintainer why a specific line is written the way it is. Everything else belongs somewhere else.

## Where information goes

| Information | Place |
|---|---|
| What it does, arguments, return value, exceptions, side effects, observable edge cases | Docstring |
| Usage example, when correct use isn't obvious from the signature | Docstring |
| What implementers of an overridable method or Protocol must guarantee | Docstring |
| Why a non-obvious line is written the way it is | Comment on that line |
| What changed and what it used to be | Commit message |
| Design reasoning and rejected alternatives | ADR in `docs/adr/`; a comment may point to it (`# See ADR 0017.`) |
| Meaning of domain terms | Glossary |
| Behavior of another class or function | That component's docstring; reference it instead of restating it |

## Docstrings

- Start with a one-line summary of what the code does or returns ("Return ...", "Reset ...", "A setting that ..."). It must make sense alone in an IDE tooltip.
- Write for a reader who sees only the signature and the docstring. Describe behavior, not implementation.
- State edge cases as outcomes: "Returns ``None`` if the pin isn't promoted." Don't explain why the outcome is right.
- In user-facing API (settings, node base classes, anything a library-wrapper author touches), use the words users see in the UI. Keep internal terms (bag, cell, tier, descriptor) to internal code.
- Refer to another component by name ("See ``DataField.accepts_absence``.") instead of describing what it does.
- Don't describe callers ("every verb below goes through this", "the settings row passes `dense=False`"). Test: if the sentence would become false when some other code changes, it describes that code, not this one.
- Keep timing and threading guarantees that callers or implementers rely on: "Called once when the edge is built, so the result must not depend on the current value."

## Arguments, return values, and exceptions

Document an argument or return value when its type doesn't say what it means:

- Plain types (`str`, `int`, `float`, `bool`), `dict`, `list`, `tuple`, `Any`, unions, and callables: say what the value represents, plus whichever of these apply: units, valid range, format, allowed values, what `None` means, where to get one.
- A documented framework class explains itself, because its own docstring does that work. Skip the entry.
- Skip the entry when the name alone says everything. `label: str` needs none; `port_id: str` does if IDs have a format.
- A precise name or type beats an explanation. `timeout_s: float` needs no "in seconds", and a narrow type hint (`PortSpec` rather than `dict[Any, Any] | PortSpec`) needs no entry. Choose names and types so that fewer entries are needed.

Document every exception a caller can reasonably handle, each with the condition that raises it.

In reST docstrings, use Google-style sections in this order: `Args:`, `Returns:`, `Raises:`, then the example. In a private helper, a phrase in the summary is enough.

```python
Args:
    iou_threshold: Minimum overlap between two boxes, from 0 to 1, for the
        lower-scoring box to be dropped.
    port: The port to connect.   # delete: framework type, clear name
```

## Examples

- Give an example to public classes, and to public functions and methods whose use isn't obvious from a single call.
- Err on the extensive side. Show each typical way to use it: the plain call, and every argument, context block, or mode that changes the result, each with a short comment on its effect. Never cut a correct example to save space.
- Examples must be correct for the current code. Good sources are the tests and real call sites.
- In reST docstrings, put the example after the sections, introduced by `Example::` and indented. In displayed docstrings, use a fenced block.

## Markup

Docstrings use one of two markups, depending on whether the app displays them.

**Displayed docstrings** are the class docstrings of registered components (nodes, types, widgets, skins, panels, and anything else the app shows in Component Docs or returns from `describe_component`). They are user documentation rendered as Markdown:

- Use single backticks for code: `OPTIONAL[INT]`.
- Use fenced code blocks with a language tag (```` ```python ````), not indented blocks.
- Don't use reST: no double backticks, no `::`, no roles like `:class:`.
- Use the words users see in the UI, and leave out internals entirely.

**All other docstrings** (methods, functions, modules, non-component classes) use reST: double backticks for code, and `::` followed by an indented block for examples.

## Comments

- Explain why, not what. If a better name or a small helper would make the code say it, change the code instead.
- Write in the present tense about the code as it is now.
- Put the comment on the line it explains, not in the docstring.
- Aim for one or two lines. A comment longer than four lines is usually design reasoning that belongs in an ADR.

## Never write

- History: "used to", "previously", "no longer", "was changed to", "the old version". Git keeps the history.
- Arguments against alternatives: "NOT X", "deliberately", "rather than", "the honest reading". Say what the code does. When a maintainer could plausibly reintroduce a bug, one present-tense line is enough: `# type_cls, not get_stored_type(): the stored type is already the element type.`
- Reasoning from the current work session. Comments describe the code, not the conversation or investigation that produced it.
- Emphasis in ALL CAPS or bold. If a word needs emphasis to be understood, rewrite the sentence.

## Length

Counting prose lines only (examples, `Args:`/`Returns:`/`Raises:` entries, and blank lines don't count):

- Private helper: one line; up to about five with edge cases. No docstring is fine when the name says it all.
- Public function or method: summary plus up to about ten lines.
- Public class: summary, when to use it, an example, edge cases; rarely over 20 lines.
- Module: what the module contains and when to use it; rarely over 25 lines.

These are guides, not limits. A docstring that is all contract can be longer: cut rationale, history, and narration, never contract.

## Before writing a sentence, check

1. Can the caller act on it? If not, it doesn't go in the docstring.
2. Would it stay true if the implementation were rewritten with the same behavior? If not, it's a comment, or nothing.
3. Does it mention the past or a rejected alternative? Leave it out.

## Example

Not this:

```python
def _element_type(self) -> "type[IType] | None":
    """The wrapped IType, read off the cell rather than declared here.

    ``type_cls``, NOT ``get_stored_type()``: the two deliberately disagree
    for a wrapper field. ``type_cls`` is what the field IS ... (five more lines)
    """
    wrapper = self.port.data.type_cls
```

This:

```python
def _element_type(self) -> "type[IType] | None":
    """Return the element type of this row's wrapper field (``INT`` for ``OPTIONAL[INT]``), or ``None``."""
    # type_cls, not get_stored_type(): the stored type is already the element type.
    wrapper = self.port.data.type_cls
```
