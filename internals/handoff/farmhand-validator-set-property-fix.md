---
name: farmhand-validator-set-property-fix
description: Handoff — Farmhand tool parameters with no type annotation emit an empty JSON Schema, which Claude Code stringifies, silently corrupting untyped numeric settings
metadata:
  type: project
  status: landed
---

# Haywire fix: Farmhand tool parameters must not emit an empty JSON Schema

## Why

Claude Code stringifies any MCP tool argument whose parameter schema is empty
(`{}`). A number sent as `8` arrives as `"8"`; an object arrives as a JSON string.
Confirmed by controlled experiment on Claude Code 2.1.212 — see
[anthropics/claude-code#82652](https://github.com/anthropics/claude-code/issues/82652)
and the probe at
<https://gist.github.com/maybites/f86a427676402ad79d9186736b0f4cff>.

Any schema carrying type information is unaffected: inline `type`, `anyOf`,
`oneOf`, and `$ref` (to either) all round-trip correctly. **The trigger is
specifically the absence of a type declaration**, so the fix is to stop emitting
`{}` — not to coerce values anywhere.

This is an upstream defect, but it is not worth waiting on: emitting an explicit
"any type" schema is more correct anyway, and it is entirely within our control.

## Root cause in this repo

`GraphEditorSetPropertyTool.run` declares `value` with no annotation
(`barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py:867`):

```python
async def run(self, ctx: FarmhandContext, binding_id: str, node_id: str, name: str, value=None) -> dict:
```

Schemas are derived from the `run()` signature by `derive_input_schema`
(`packages/haywire-core/src/haywire/core/farmhand/schema.py:24`), which delegates
per-parameter to `_annotation_to_schema` (same file, line 46). That function
returns a bare `{}` in three cases:

| line | case | returns |
| --- | --- | --- |
| 48 | unannotated / `inspect.Parameter.empty` | `{}` |
| 60 | union with **more than one** non-`None` arm (e.g. `int \| str`) | `{}` |
| 66 | any unrecognised type | `{}` |

So `value` currently emits `{"default": null}` — no `type` keyword — which is
exactly the failing shape.

### The union branch matters more than it looks

Line 56–60 only unwraps `Optional[X]`. A genuinely polymorphic annotation such as
`value: int | str | bool` falls through to `{}` as well. **Annotating the
parameter is therefore not sufficient on its own** — without fixing the deriver,
the natural fix (adding a union annotation) still produces an empty schema and
still triggers the bug.

## Fix

Two options; the first is strongly preferred because it fixes every affected
Farmhand at once, and there are 49 `Farmhand` implementations in the repo.

### Option A — fix the deriver (recommended)

In `_annotation_to_schema`, replace the three `{}` returns with an explicit
"accepts any JSON type" schema, and give multi-arm unions a real `anyOf`:

```python
_ANY_TYPE = {
    "anyOf": [
        {"type": "string"}, {"type": "number"}, {"type": "integer"},
        {"type": "boolean"}, {"type": "object"}, {"type": "array"},
        {"type": "null"},
    ]
}

# line 56-60: multi-arm union -> anyOf of the arms, not {}
if origin in (typing.Union, types.UnionType):
    non_none = [a for a in args if a is not type(None)]
    if len(non_none) == 1:
        return _annotation_to_schema(non_none[0])
    return {"anyOf": [_annotation_to_schema(a) for a in non_none]}
```

…and return `_ANY_TYPE` (not `{}`) at lines 48 and 66.

This **preserves the existing contract.** The comment at line 66 —
*"unknown types: accept anything (schema evolution convention, spec §5)"* — stays
true; "accept anything" is simply stated explicitly instead of by omission.
Nothing becomes more restrictive.

Optionally also annotate `value` for clarity, but that is cosmetic once the
deriver is fixed.

### Option B — per-tool override (narrow)

`Farmhand.input_schema_override`
(`packages/haywire-core/src/haywire/core/farmhand/base.py:25`) short-circuits
derivation. Set it on `GraphEditorSetPropertyTool` with a hand-written schema.

Fixes only this tool; every other untyped or union-typed parameter stays broken.
Use only if a systemic change is out of scope right now.

## Blast radius (Option A)

`derive_input_schema` has 8 callers:

- `packages/haywire-core/src/haywire/core/farmhand/base.py` — `input_schema()`
- `packages/haywire-core/src/haywire/core/farmhand/__init__.py`
- `packages/haywire-studio/src/haywire_studio/docs_gen/extract.py` — **generated
  docs will change shape** for any parameter that previously rendered as `{}`;
  worth eyeballing the output.

Tests to update: `tests/core/test_farmhand/test_schema.py`, which includes
`test_float_and_unannotated` — it currently asserts the `{}` behavior and will
need to expect the explicit any-type schema instead.

Also worth auditing the other 48 `Farmhand` subclasses for unannotated or
multi-arm-union parameters; they are silently affected by the same defect.

## Severity: validator-less fields have silently stored strings

The original report surfaced on `even_int`, a field **with** a validator — the
validator rejected the string and the write was dropped. That is the *visible*
case. The silent case is worse.

`setting.validate()`
(`packages/haywire-core/src/haywire/core/settings/descriptor.py:344`) returns
`True` unconditionally when no validator is set:

```python
def validate(self, value: Any) -> bool:
    """Return True if *value* passes the validator (or if no validator is set)."""
    if self._validator is None:
        return True
    return bool(self._validator(value))
```

The declared type parameter (`setting[INT]`, `setting[FLOAT]`) is **not enforced
at write time**. So for a field with no validator, `__set__` (line 402) proceeds:

1. `validate("42")` → `True`
2. the no-op guard `if value == old` (line 414) does **not** catch it — `"42" == 42`
   is `False` in Python, so it is treated as a real change
3. `obj._cell_for(self).set_value("42")` — **the string is stored**

So the fields that *appeared* to work are the ones that were corrupted, and the
fields that *appeared* broken were protected by their validators. That inverts
the intuition the original investigation was working from.

### What to audit

Any numeric setting or config port written via `graph_editor_set_property`
**from an affected MCP client** and lacking a validator may now hold a string in
memory and in any graph saved since. Downstream arithmetic will either raise
`TypeError` or silently concatenate.

Scope is bounded — this only affects writes that went through the untyped `value`
parameter. UI edits, programmatic writes, and values loaded from disk are
unaffected, so exposure is limited to agent-driven edits.

Suggested check: scan saved `.haywire` graphs for settings whose stored JSON type
disagrees with the field's declared type (a quoted `"42"` where `setting[INT]` is
declared). Decide whether a one-off migration is warranted or whether re-writing
the affected fields by hand is enough.

Worth considering independently of this bug: whether `validate()` should enforce
the declared type when no explicit validator is supplied. That would have
converted this from silent corruption into a visible rejection. It is a
behavioral change with its own blast radius, so it belongs in its own decision,
not bundled into this fix.

## Verification

1. Unit: `derive_input_schema` on a function with an unannotated parameter yields
   a schema containing `anyOf`, and no property is ever `{}`.
2. End-to-end: from a Claude Code session, call `graph_editor_set_property` with
   a plain integer against an int-typed field and confirm the write lands
   (previously it was silently rejected by the field validator, since the value
   arrived as `str`).

Note the original symptom was a *silent* validator rejection reported as
`[set_rejected] ... requested '8', value is still 8` — the asymmetric quoting
(`'8'` vs `8`) is the diagnostic signature of the value arriving as a string.

## Caveat

Only the `anyOf` form has been verified against Claude Code. The alternative
JSON Schema spelling for "any type" — a type array,
`{"type": ["string","number",...]}` — was **not** tested and may behave
differently. Prefer `anyOf` unless someone re-runs the probe.

## Landed

Option A implemented as specified:

- `packages/haywire-core/src/haywire/core/farmhand/schema.py` —
  `_ANY_TYPE` added; the three `{}` returns in `_annotation_to_schema`
  replaced (unannotated, unknown type); multi-arm unions now return
  `{"anyOf": [...]}` of their arms instead of `{}`.
- `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`
  — `GraphEditorSetPropertyTool.run`'s `value` param annotated `Any`
  (cosmetic, per the doc).
- `tests/core/test_farmhand/test_schema.py` — `test_float_and_unannotated`
  updated to expect `anyOf` (plus an explicit assert it is not `{}`); new
  `test_multi_arm_union_yields_anyof_not_empty` and
  `test_unknown_type_yields_anyof_not_empty`.

Verification:

- ruff + mypy clean on all touched files.
- `tests/core/test_farmhand/` (23/23), and
  `tests/farmhand/test_graph_editor_tools.py` +
  `tests/core/test_undo/test_set_property_action.py` (38/38) pass.
- Full pre-commit gate (`-m "not browser and not perf"`): 3265 passed, 1
  pre-existing unrelated failure (`test_doc_source_keys_exist`, confirmed
  via `git stash` to fail identically on master before this change).
- Live verification against a running studio via the real MCP path: the
  served `graph_editor_set_property` schema now shows `anyOf` for `value`
  (not `{}`); wrote `42` to `testing:node:SettingsNode.example_int` (INT,
  no validator — the silent-corruption case) and `8` to `even_int` (INT,
  validated — the original visible-failure case) via
  `graph_editor_set_property`; both succeeded with no `set_rejected`, and
  read-back confirmed real JSON integers (`42`, `8`), not quoted strings.

Not done, left for follow-up (all explicitly out of scope per this doc):

- Audit of the other 48 `Farmhand` subclasses for unannotated/multi-arm-union
  parameters.
- Whether `setting.validate()` should enforce the declared type when no
  explicit validator is supplied.
- Migration/audit of already-saved `.haywire` graphs for values corrupted
  to strings before this fix landed.
- Eyeballing `haywire docs --all` / generated-docs output for shape changes
  on previously-`{}` parameters.
