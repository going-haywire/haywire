# Handoff: verify set_property-on-validated-settings through the REAL Claude Code → proxy chain

## Why this needs a new session

The investigation so far (see `.scratch/farmhand4claude-numeric-arg-stringified.md`
for the full history) root-caused a Claude Code MCP client bug: tool
arguments whose JSON Schema has no flat primitive `type` (Haywire's
`graph_editor_set_property`'s `value` field is exactly this — intentionally
untyped/polymorphic) can arrive at the proxy already stringified, e.g. a
request for `value: 8` shows up as `"8"`.

Every hop from the **proxy's own stdin onward** was tested directly (hand-fed
JSON-RPC over stdio to the real `dist/index.js`, and raw `curl` straight to
the studio's `/mcp/` HTTP endpoint) and is clean — a real JSON integer
round-trips correctly at every one of those layers. The only hop that
reproduces the bug is a **real Claude Code tool call**, through the actual
`farmhand` MCP server entry in `.mcp.json` (the `npx -y
@going-haywire/farmhand4claude@latest` proxy), from an actual Claude Code
session — not a hand-rolled script, not direct curl.

**This session's `mcp__farmhand__*` tools stopped responding partway through
testing** (studio was up, `farmhand_studio_status` intermittently reported
`unreachable`/`connected`, and `graph_editor_*`/`haystack_*` tools dropped out
of `ToolSearch` results entirely) — so continuing here would mean falling
back to direct curl again, which tests the wrong thing (bypasses Claude
Code's client, the one hop actually in question). Do this in a **fresh
session** where `/mcp` shows the `farmhand` server connected and
`mcp__farmhand__*` tools are actually invocable as real tool calls.

## What we're trying to isolate

The user's observation: **the issue shows up specifically when `set_property`
targets a setting that has a `validator=`** — not (as far as we know yet)
on unvalidated fields or ports. This handoff is to confirm or refute that
scoping with a real repro matrix, using the live studio + real Claude Code
tool calls (no curl).

Two things to determine:

1. **Does the string-corruption bug reproduce at all through a real tool
   call in this session** (sanity check — confirms `.mcp.json`/proxy/studio
   are wired correctly before drawing any conclusions)?
2. **Is validator-presence actually the deciding factor**, or is it
   incidental (e.g. every field looked at happened to have a validator, or
   the real factor is something else — field already holding the requested
   value, field type, first-write-vs-repeat-write, etc.)?

## Setup

```
S=.claude/skills/haywire-live-studio/scripts
$S/studioctl start
```

Then use the `haywire-live-studio` skill's tools directly (they should just
be present as `mcp__farmhand__*` in a fresh session — no need to hand-roll
curl/stdio sessions like earlier attempts in this investigation did).

Test node: `testing:node:SettingsNode`
(`barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py`) —
already has every field shape needed:

| field | category | validator? | notes |
|---|---|---|---|
| `even_int` | validator | `lambda v: isinstance(v, int) and v % 2 == 0` | the field from the original report |
| `clamped_positive` | validator | `lambda v: isinstance(v, (int, float)) and v > 0` | float-typed, validated |
| `validated_string` | validator | `lambda v: isinstance(v, str) and len(v) > 0` | string-typed, validated |
| `example_int` | type | none (min/max only, NOT enforced) | plain INT, no validator |
| `example_float` | type | none | plain FLOAT, no validator |
| `persistent_value` | stored | none | plain FLOAT, no validator |

## Test matrix — run each as a REAL tool call in this session

For each row: call `graph_editor_set_property` with the given `name`/`value`,
record whether it succeeds or raises `set_rejected`, then independently
verify with `graph_editor_inspect_node` (`get=["settings"]`, `data="all"`,
`by_name=[<field>]`) what the field's actual value ended up being. The
inspect call is the ground truth — it tells us whether the write really
landed regardless of what `set_property` claimed.

1. `even_int = 8` (even, validator present) — the ORIGINAL reported failure.
   Expect per the bug: `set_rejected`, even though 8 is a legal value.
2. `even_int = 7` (odd, validator present) — should genuinely reject
   regardless of any transport bug (real validator failure). Sanity check —
   if this ever unexpectedly *succeeds*, something else is very wrong.
3. `clamped_positive = 2.5` (valid, validator present, FLOAT not INT) —
   tests whether the bug is INT-specific or hits FLOAT too.
4. `validated_string = "hello world"` (valid, validator present, STRING) —
   tests whether the bug is numeric-specific or also corrupts strings (a
   string arriving as a string is not detectable by type alone — if this
   bugs out, look for a wrapping/escaping artifact instead, e.g. nested
   quotes).
5. `example_int = 42` (valid, NO validator, INT) — same value shape as test
   1 but no validator. If this succeeds cleanly, that's evidence for the
   user's hypothesis (validator presence is the trigger). If it ALSO fails,
   the validator isn't the real variable — look at the read-back value it
   produces (a plain field with no validator won't reject a wrong type, so
   the read-back will directly show what type actually arrived, e.g. `"42"`
   vs `42`).
6. `example_float = 3.5` (valid, NO validator, FLOAT) — same as 5 for float.
7. `even_int = 8` again, immediately after test 1's attempt (so the field
   already holds a stale/rejected state — check what `inspect_node` says it
   currently holds first) — tests the "no-op guard" theory from earlier in
   this investigation: `setting.__set__` has `if value == old: return`,
   which could make a *second* identical request look like a no-op success
   even if the underlying write is still corrupted, muddying the read from
   test 1 alone.

## What to report back

For each of the 7 cases: the exact tool-call result (success/`set_rejected`
+ full error text), AND the independent `inspect_node` read-back value +
its Python-relevant type signal (does it look like a string, e.g. would
`"value": "8"` vs `"value": 8` in the JSON response — the asymmetric-quoting
trick from the original investigation still applies at the JSON level: a
number renders unquoted, a string renders quoted).

Specifically answer:
- Does test 5 (no validator, same value/type as the broken test 1) succeed
  cleanly, or does it also silently store a wrong-typed value?
- Is the corruption present on ALL numeric argument writes regardless of
  validator (validator only makes it VISIBLE by rejecting the wrong type),
  or does validator-presence somehow change what Claude Code/the proxy
  sends?
- Does the string case (test 4) show any corruption at all, or is this
  purely a numeric (int/float) problem?

## Cleanup when done

Close the test graph and stop the studio if `studioctl` started it:

```
$S/studioctl stop
```

## Related files

- `.scratch/farmhand4claude-numeric-arg-stringified.md` — full investigation
  history, the proxy-side elimination tests, and the upstream tracking
  issues (`anthropics/claude-code#18260`,
  `modelcontextprotocol/typescript-sdk#1562`/`#1563`).
- `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`
  — `GraphEditorSetPropertyTool.run` (~L897) and `_read_property` (~L838) is
  where the read-back/verification logic lives, in case the matrix results
  point at a real Haywire-side bug in the post-condition check rather than
  (or in addition to) the Claude Code transport bug.
