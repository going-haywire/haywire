# Classifier — three bands

Reference for the [refreshing-docs](SKILL.md) skill. Load this file when about to classify the first stale row in a run.

## Multi-doc rules — fact-check vs. enhancement

A single source change often produces stale rows across multiple docs. The action depends on whether the change is a **fact-check** or an **enhancement**:

- **Fact-check propagation.** A claim that was true is now false (R1a contradiction, R2 behavioural change, R3 removal of a referenced symbol). Every doc that made the falsified claim must be edited. Apply the band's action to *each* affected doc independently — the classifier walks the same diff per (doc, source) pair, and each pair gets its own outcome.

- **Enhancement (one-doc-only).** A new symbol is added that *could* be documented (R1b sibling addition, R4 new feature). Only the doc with the **deepest claim** about the parent surface should be considered for the enhancement; other docs that name the parent surface in passing do not need to grow. The classifier identifies the deepest-claim doc by source-row presence: if multiple docs track the same source, the doc whose claim is most concrete (signature, behavioural detail, enumerated list) takes the enhancement; weaker docs stay as-is, and their META rows just get a hash bump.

In practice: when a stale row implies "add this fact", check whether other docs also track the same source. If yes, only the deepest-claim doc gets the new sentence/list-item; the others' rows are bumped silently (Band A — hash-only, since their existing claims are still correct).

## Decision tree

For each stale row `(doc, source, recorded_hash, current_hash)`:

```
1. Compute the diff: git diff <recorded_hash>..HEAD -- <source>

2. Is the diff hash-only (whitespace, comments, formatting)?
   YES → BAND A. No doc edit; just bump the META hash.

3. Is the diff a clean rename (single old-name → new-name) AND
   the doc cites the old name verbatim?
   YES → BAND A. Replace the name in the doc; bump the META hash.

4. Is the diff a path move (file renamed, content unchanged) AND
   the doc has a markdown link to the old path?
   YES → BAND A. Update the link; bump the META hash.

5. Does the diff change a symbol the doc names AND a doc claim is
   now factually wrong (R1a) OR behavioural change against a doc
   claim (R2)?
   This is FACT-CHECK PROPAGATION (see Multi-doc rules above) —
   every doc whose claim is falsified gets its own edit.
   - Only this doc cites the affected source: BAND B.
   - Multiple docs cite it AND need the SAME edit (e.g. a rename
     that ripples): BAND B for each (still mechanical).
   - Multiple docs cite it AND need DIFFERENT edits: BAND C
     (editorial — different docs may need different framings).

6. Is the diff a removal of a symbol the doc references (R3)?
   Fact-check propagation: every doc that references the removed
   symbol must lose its reference.
   - Only this doc affected: BAND B (R3a).
   - Many docs affected, all citing the same removed surface:
     BAND C (R3b — editorial: the surface is gone, not just a
     reference; whether to remove sections, restructure, or
     consolidate is human judgment).

7. Is the diff a NEW symbol that the doc does not currently cite?
   This is ENHANCEMENT (see Multi-doc rules above) — only the
   deepest-claim doc considers adding it; weaker docs are
   hash-bumped silently.
   - This is the deepest-claim doc for the parent surface AND
     the new symbol is a sibling addition (see definition below)
     AND its absence would mislead a reader: BAND B (R1b).
   - This is NOT the deepest-claim doc, but other tracking docs
     are: BAND A (hash-only bump; the deepest doc handles the
     enhancement).
   - No doc has a deep claim, but the addition is sibling-shaped
     and a doc names the parent: BAND C (R4 — pick the right
     home is editorial).
   - Otherwise: BAND C (R4).

8. Is the diff a behavioural change with no signature change?
   - Doc makes a claim about the changed behaviour: BAND B (R2).
   - Doc makes no claim, but should: BAND C.
   - Doc makes no claim and the change is internal: BAND A
     (just bump the hash; nothing for the doc to track).

9. Anything else, or you are unsure: BAND C.
```

**Default on ambiguity: C.** The skill is inside a git repo; the cost of bumping a borderline case to C is one extra human glance. The cost of misclassifying as B and editing wrongly is silent miseducation.

## Sibling addition (R1b)

A new symbol is a **sibling addition** to a documented one when **both** are members of the same parent **and** the parent surface is cited by the doc.

Concrete tests, in order of confidence:

1. **Same enum, same class, same dataclass** — clearest case. e.g. doc cites `NodeType.CONTROL` and `NodeType.DATA`; `NodeType.STATEMACHINE` is added → sibling addition.
2. **Same naming family** — e.g. doc cites `.as_inlet` and `.as_outlet`; `.as_event_inlet` is added on the same class → sibling addition.
3. **Same module's documented public surface** — case-by-case. If the new symbol is exported alongside cited ones AND its docstring/naming clearly mirrors the existing ones, treat as sibling addition. Otherwise bump to C.
4. **Cross-module addition** — never a sibling addition by default. Bump to C.

Does the absence "mislead"? Mislead means: a reader following the doc would reasonably believe the surface is complete (e.g. an enumerated list of node roles) and miss the new member. If the doc's framing is open-ended ("…among others", "for example"), the absence is not misleading and the addition is editorial — bump to C.

## Constrained edit shape (Band A and Band B)

Autonomous edits are limited to these shapes:

- **In-place text replacement of named symbols.** Find the old name in the doc, replace with the new name. Old and new must each be a single token; no surrounding prose changes.
- **Path replacement in markdown links.** Same rule as above for `[text](path)` links — replace the path, leave the link text.
- **Adding a single sentence or list item** to an existing section. The added text states the new fact and nothing else. No reordering of surrounding items, no rewording neighbors.
- **Removing a sentence or paragraph** whose subject is a removed symbol. If removing the sentence breaks paragraph cohesion, **bump to C** instead.

**Hard limits — bump to C if any of these are required:**

- Rewriting or paraphrasing surrounding prose.
- Restructuring (moving a section, changing heading levels, splitting a section).
- Editing example code in ways beyond a name swap (changing logic, inputs, outputs).
- Edits to multiple non-adjacent locations within a single doc page that aren't all the same name swap.

## Examples (Haywire-flavoured)

These are illustrative, not exhaustive.

| Diff | Band | Reason |
|---|---|---|
| `switch.py` reformatted by ruff | A | Hash-only |
| `switch.py`'s `hb_change` renamed to `hb_reconfigure`, doc cites `hb_change` | A | Clean rename, doc cites verbatim |
| `for_loop.py` moved to `nodes/control/for_loop.py`, doc has markdown link to old path | A | Path move, no content change |
| `node_type.py` adds `NodeType.STATEMACHINE`, node-canon enumerates roles as a closed list | B (R1b) | Sibling addition; absence misleads |
| `as_config` removed, only node-canon references it | B (R3a) | Single-doc removal |
| `as_config` removed, referenced in 4 canon pages and the glossary | C (R3b) | Systemic removal — editorial decisions about restructuring |
| `worker()` signature gains an optional `lifecycle: str` kwarg, doc says "Signature: `(self, context, *args, **kwargs)`" | C | Doc's framing already accommodates new kwargs; whether to call it out is editorial |
| `context.control_pin` returns the inlet's label instead of its ID; node-canon claims it returns the ID | B (R2) | Doc claim is wrong; correction is local |
| New module `event_router.py` added; no existing doc cites the parent module | C (R4) | New surface, no existing claim — editorial decision whether to document |

## Logging decisions

For each row, record in working memory (for the run summary):

- The row (doc, source, hashes).
- The band assigned.
- A one-line reason ("rename `hb_change` → `hb_reconfigure`", "removed reference to `as_config`", "new sibling `NodeType.STATEMACHINE`").
- The action taken (edit applied / pending human / hash-only bump).

Use this log to print the summary and to pass to `update_meta.py` for hash bumps.
