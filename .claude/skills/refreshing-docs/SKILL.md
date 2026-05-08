---
name: refreshing-docs
description: >
  Two-phase documentation refresh for the Haywire repo. Phase 1 (coverage): finds doc pages with no META section in .docmeta/META.md AND pending docs whose content has changed; dispatches a subagent to propose review-needed (R), no-review-needed (N), or pending (P) classification with source paths, and on user approval registers them. Phase 2 (staleness): compares recorded tree-hashes against HEAD, classifies drift into three bands (with multi-doc fact-check vs. enhancement rules), auto-applies mechanical edits (renames, moves, sibling additions), and bumps editorial cases to the user. Use after implementation steps that touched files cited by docs, when the user asks "are the docs up to date", "refresh the docs", "update docs after this change", or as the documentation-update step at the end of a feature branch.
---

# Refreshing docs

Keep `docs/` in sync with the source files it cites. The freshness ledger lives at [.docmeta/META.md](../../../.docmeta/META.md). This skill reads it, finds rows whose recorded tree-hash no longer matches HEAD, classifies each change, and edits docs autonomously when the change is mechanical or sibling-shaped — bumping anything editorial to the user.

## When to invoke

- After an implementation step that touched code cited by docs.
- At the end of a feature branch, before merging — the doc-update step.
- When the user asks: "refresh docs", "are the docs stale", "update docs after this change".
- Do **not** invoke for trivial code edits that obviously don't touch documented surfaces (formatting-only, internal helper renames in private modules) — the META check will catch real drift on the next intentional run.

## How the two phases relate

Phase 1 (Coverage) ensures every doc page has a META section so nothing is silently untracked. Three section states are possible per doc:

- **`Last reviewed: <date>` + source table** — actively tracked; freshness check applies (Phase 2).
- **`No review needed: <date>`** — permanent exemption; doc has no source-code dependencies AND is complete.
- **`Review pending: <date> (doc-hash <hash>)`** — placeholder/stub doc; re-checked each run when the doc itself changes.

Phase 2 (Staleness) detects and repairs drift in tracked docs by comparing recorded tree-hashes against HEAD, classifying each diff into one of three bands, and either auto-editing (Bands A/B) or flagging for human review (Band C).

The supporting files:

- [coverage_classifier.md](coverage_classifier.md) — Phase 1 subagent prompt + calibration rules for R/N/P.
- [classifier.md](classifier.md) — Phase 2 three-band drift decision tree.
- [scripts/check_coverage.py](scripts/check_coverage.py) — lists uncovered doc pages.
- [scripts/check_pending.py](scripts/check_pending.py) — lists pending docs whose content has changed.
- [scripts/check_freshness.py](scripts/check_freshness.py) — emits stale source rows.
- [scripts/update_meta.py](scripts/update_meta.py) — rewrites META (`--create` / `--no-review` / `--pending` / row update).
- [scripts/meta.py](scripts/meta.py) — shared parsing primitives (the META.md grammar lives here; edit this when the grammar evolves).

## The three bands (Phase 2 summary)

Full decision tree in [classifier.md](classifier.md). At a glance:

| Band | What | Action |
|---|---|---|
| **A** | Hash-only changes; clean renames the doc cites verbatim; file moves with no content change | Auto-edit |
| **B** | Doc claim is now wrong (R1a/R2); doc references something removed (R3a, single-doc); sibling addition that would mislead by absence (R1b) | Auto-edit, constrained shape only |
| **C** | Removal rippling across many docs (R3b); new feature with no existing doc claim (R4); behavioural change with no current doc claim that arguably needs one; anything ambiguous | Human review; skill flags and stops on this row |

**Constrained edit shape for Band A and B** — autonomous edits are limited to:

- In-place replacement of named symbols (renames, path changes).
- Adding a single sentence or list item to an existing section.
- Removing a sentence or paragraph that names a removed symbol.
- **No rewriting**, **no paraphrasing surrounding prose**, **no restructuring**, **no changing example code logic**. If the edit needs any of these, bump to C.

**Default on ambiguity: C.** The classifier should err on the side of human review. We are inside git; the cost of a false-C is one extra glance from a human, the cost of a false-B is a wrong edit committed silently.

## Procedure

### 1. Coverage check (Phase 1)

```bash
uv run python .claude/skills/refreshing-docs/scripts/check_coverage.py
uv run python .claude/skills/refreshing-docs/scripts/check_pending.py
```

`check_coverage` prints docs with no META section at all. `check_pending` prints docs marked "Review pending" whose own content has changed since the pending mark — these need re-classification. Empty output from both means coverage is complete; skip to step 2.

For each doc from either output, follow the workflow in [coverage_classifier.md](coverage_classifier.md): dispatch a subagent with the prompt template, verify proposed paths exist, sanity-check against the calibration rules, show the user the proposal, and on approval run:

```bash
# R verdict (review-needed):
uv run python .claude/skills/refreshing-docs/scripts/update_meta.py --create <doc> <sources...>

# N verdict (no-review-needed):
uv run python .claude/skills/refreshing-docs/scripts/update_meta.py --no-review <doc>

# P verdict (pending):
uv run python .claude/skills/refreshing-docs/scripts/update_meta.py --pending <doc>
```

Coverage decisions are editorial — the user owns the call. Never auto-create META sections without approval; an empty or wrong section is worse than no section. If there are many docs (>5), do them sequentially with the user — batch approval is risky for editorial calls.

**Re-classifying a pending doc.** When `check_pending` surfaces a doc and the new verdict is:

- Still **P** — `--pending` is idempotent; rerun it to refresh date and doc-hash.
- **R** — pass `--replace-pending` to overwrite the pending section in one step:
  ```bash
  uv run python .claude/skills/refreshing-docs/scripts/update_meta.py --create --replace-pending <doc> <sources...>
  ```
- **N** — same flag with `--no-review`:
  ```bash
  uv run python .claude/skills/refreshing-docs/scripts/update_meta.py --no-review --replace-pending <doc>
  ```

Without `--replace-pending`, `--create` and `--no-review` refuse to overwrite an existing section — that's the safety default for cases where you'd otherwise be silently clobbering a tracked or no-review entry.

### 2. Staleness check (Phase 2)

```bash
uv run python .claude/skills/refreshing-docs/scripts/check_freshness.py
```

Emits one JSON object per line on stdout (newline-delimited JSON). Empty output means nothing is stale — done.

Each row looks like:

```json
{"doc": "docs/components/nodes/node-canon.md", "source": "barn/haybale-core/haybale_core/nodes/switch.py", "recorded_hash": "abc123...", "current_hash": "def456..."}
```

`current_hash` is `null` if the source file was removed from HEAD — the classifier treats this as a removal (R3).

### 3. Classify and act, row by row

For each row:

```bash
git diff <recorded_hash>..HEAD -- <source>
```

Then read the doc page and apply the [classifier rules](classifier.md). Take the band's action.

When you make an edit, **note it in a run log** you keep in working memory — at the end you'll print a summary, and the META updates depend on which docs are now in sync.

### 4. Update META

After all edits, for every row whose doc is now in sync (i.e. the doc was edited to reflect the new source state, OR the source change was hash-only and didn't need a doc edit):

```bash
uv run python .claude/skills/refreshing-docs/scripts/update_meta.py <doc_path> <source_path>
```

This rewrites the matching row in `.docmeta/META.md` with the current tree-hash and bumps the doc's "Last reviewed" header.

For Band C rows that the user did not resolve in this session, **leave the META row untouched** — the doc is still stale; the next run should pick it up again.

### 5. Summary

Print to the user:

```
Refreshing-docs run summary

  Coverage (Phase 1):
    - Created 3 META sections (2 R, 1 N).
    - Skipped 1 — user declined the proposed sources.

  Staleness (Phase 2):
    Auto-edited (Band A): N rows
      - docs/X.md        ← rename: foo → bar
      - docs/Y.md        ← path: a/b.py → a/c.py

    Auto-edited (Band B): M rows
      - docs/Z.md        ← removed reference to deleted `as_config`
      - docs/Q.md        ← added line for new NodeType.LOOPBACK sibling

    Pending human review (Band C): K rows
      - docs/R.md        ← new feature in foo.py; doc may need new section
      - docs/S.md        ← behavioural change in bar.py; doc claims need rechecking

Run `git diff docs/ .docmeta/` to review autonomous changes.
```

Stage changes (`git add docs/ .docmeta/META.md`) and propose a commit message — but do not commit unless the user confirms.

## What this skill is NOT

- Not a doc generator — it does not write new docs from scratch.
- Not a code-style checker — diffs that are pure formatting are Band A and skipped.
- Not a CI gate — it's a human-invoked refresh step. (CI integration is a later question; the manual flow stands alone.)
- Not generic — paths, conventions, and the META schema are Haywire-specific. Don't try to use this elsewhere without porting.

## Bootstrapping a new doc page manually

The skill's `update_meta.py --create` is the normal path. For reference, the section format is:

```markdown
## <relative-doc-path>

Last reviewed: YYYY-MM-DD (commit `<short-sha>`)

| Source path | Tree-hash at review |
|---|---|
| <path> | <full-tree-hash> |
```

Tree-hashes come from `git rev-parse HEAD:<path>`. Use this only when bootstrapping or recovering — the script does it correctly every time.
