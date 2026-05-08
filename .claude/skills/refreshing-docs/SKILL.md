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

## Workflow

The skill runs in two phases. Phase 1 ensures every doc page has a META section (so nothing is silently untracked); Phase 2 detects and repairs drift in tracked docs.

### Phase 1 — Coverage

Three section states track every doc page:

- **`Last reviewed: <date>` + source table** — actively tracked; freshness check applies (Phase 2).
- **`No review needed: <date>`** — permanent exemption; doc has no source-code dependencies AND is complete.
- **`Review pending: <date> (doc-hash <hash>)`** — placeholder/stub doc; re-checked each run when the doc itself changes.

```
1a. Run check_coverage.py
        → list of doc paths that have NO META section
1b. Run check_pending.py
        → list of pending docs whose own tree-hash has changed
          (these need re-classification)

2. For each doc from 1a OR 1b:
       a. Dispatch Explore subagent with the prompt in coverage_classifier.md.
          Subagent reads the doc and returns:
            verdict: R (review-needed), N (no-review-needed), or P (pending)
            sources: list of repo-relative paths (R only)
       b. Verify proposed source paths exist at HEAD.
       c. Sanity-check against calibration rules in coverage_classifier.md
          (subagent has known biases — over-citing by name-presence,
           missing files where claims are most concrete).
       d. Show the user the proposal: verdict + reasoning + sources.
       e. On approval:
            R → update_meta.py --create <doc> <sources...>
            N → update_meta.py --no-review <doc>
            P → update_meta.py --pending <doc>
       f. For 1b re-classifications: if the section already exists as
          P and the verdict is still P, --pending refreshes the date
          and doc-hash idempotently. If the verdict has changed (P→R
          or P→N), the existing pending section must be removed first
          before the new --create or --no-review runs.
       g. On rejection or edit: adjust per user instruction, then run.
```

Coverage decisions are editorial — the user owns the call. Never auto-create META sections without approval; an empty or wrong section is worse than no section.

### Phase 2 — Staleness

```
1. Run check_freshness.py
       → JSON list of stale rows: { doc, source, recorded_hash, current_hash }
2. For each stale row:
       a. git diff <recorded_hash>..HEAD -- <source>
       b. Read the cited doc page.
       c. Classify the change (see classifier.md).
       d. Band A → apply mechanical edit, log it.
       e. Band B → apply edit per the constrained shape rules, log it.
       f. Band C → record "pending human review" in the run log; no edit.
3. Run update_meta.py for every row whose doc is now in sync (Bands A, B,
   and any C rows the user resolves before exit).
4. Print summary: coverage gaps resolved, counts per band, doc pages
   edited, pending C rows.
5. If anything was edited, stage the changes and propose a commit message
   ("docs: refresh from META staleness check") — let the user commit.
```

## The three bands (summary)

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

## Quick-start

Read this file (you're here). Then load whichever phase reference is relevant:

- [coverage_classifier.md](coverage_classifier.md) — for Phase 1 (subagent prompt + calibration rules for R/N classification).
- [classifier.md](classifier.md) — for Phase 2 (three-band drift decision tree).

The four scripts are short — read them once before first use:

- [check_coverage.py](check_coverage.py) — lists uncovered doc pages.
- [check_pending.py](check_pending.py) — lists pending docs whose content has changed.
- [check_freshness.py](check_freshness.py) — emits stale source rows.
- [update_meta.py](update_meta.py) — rewrites META (--create / --no-review / --pending / row update).

### 1. Coverage check (Phase 1)

```bash
uv run python .claude/skills/refreshing-docs/check_coverage.py
uv run python .claude/skills/refreshing-docs/check_pending.py
```

`check_coverage` prints docs with no META section at all. `check_pending` prints docs marked "Review pending" whose own content has changed since the pending mark — these need re-classification (the placeholder may now have real content). Empty output from both means coverage is complete — skip to step 2.

For each doc from either output, follow the workflow in [coverage_classifier.md](coverage_classifier.md): dispatch a subagent with the prompt template, verify proposed paths exist, sanity-check against the calibration rules, show the user the proposal, and on approval run:

```bash
# R verdict (review-needed):
uv run python .claude/skills/refreshing-docs/update_meta.py --create <doc> <sources...>

# N verdict (no-review-needed):
uv run python .claude/skills/refreshing-docs/update_meta.py --no-review <doc>

# P verdict (pending):
uv run python .claude/skills/refreshing-docs/update_meta.py --pending <doc>
```

If there are many docs (>5), do them sequentially with the user — batch approval is risky for editorial calls.

For pending docs that are STILL pending after re-classification, `--pending` is idempotent: it just refreshes the date and doc-hash. For pending docs whose verdict has changed (P→R or P→N), the existing pending section must be removed first; this is a manual step (edit `.docmeta/META.md` to remove the section) before `--create` or `--no-review` runs.

### 2. Staleness check (Phase 2)

```bash
uv run python .claude/skills/refreshing-docs/check_freshness.py
```

Emits one JSON object per line on stdout (newline-delimited JSON, easy to iterate). Empty output means nothing is stale — done.

Each row looks like:

```json
{"doc": "docs/components/nodes/node-canon.md", "source": "barn/haybale-core/haybale_core/nodes/switch.py", "recorded_hash": "abc123...", "current_hash": "def456..."}
```

### 3. Classify and act, row by row

For each row:

```bash
git diff <recorded_hash>..HEAD -- <source>
```

Then read the doc page and apply the [classifier rules](classifier.md). Take the band's action.

When you make an edit, **note it in a run log** you keep in working memory — at the end you'll print a summary and the META updates depend on which docs are now in sync.

### 4. Update META

After all edits, for every row whose doc is now in sync (i.e. the doc was edited to reflect the new source state, OR the source change was hash-only and didn't need a doc edit):

```bash
uv run python .claude/skills/refreshing-docs/update_meta.py <doc_path> <source_path>
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

## Maintaining the META file

When a new doc is created that cites barn or framework sources, add a section to `.docmeta/META.md` describing it. The format is:

```markdown
## <relative-doc-path>

Last reviewed: YYYY-MM-DD (commit `<short-sha>`)

| Source path | Tree-hash at review |
|---|---|
| <path> | <full-tree-hash> |
| <path> | <full-tree-hash> |
```

Tree-hashes are obtained via `git rev-parse HEAD:<path>`. The skill's `update_meta.py` does this for you on refresh, but the **initial entry** for a brand-new doc page is added manually (or, if the new doc is part of the same session that ran the skill, by an extra invocation: `update_meta.py --create <doc> <source> [<source> ...]`).
