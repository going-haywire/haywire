---
name: trim-batch
description: Run one wave of the docstring-trimming campaign — claim the next pending modules from docs/trim-docs-manifest.md, fan out one subagent per module in its own git worktree, then verify and commit each result serially. Use when the user says "run a trim batch", "next trim wave", "continue trimming docstrings", or invokes /trim-batch.
argument-hint: "[wave size, default 4]"
disable-model-invocation: true
---

# Run one trim-docs wave

Execute ONE wave, then stop and report. Do not loop into the next wave
unless the user asks.

Wave size is `$ARGUMENTS` or 4 if unset. Never exceed 6 — beyond that,
failures get hard to attribute and rate limits start to bite.

## Why one agent per module

Each module is an independent unit of judgment. Isolating them means one
module's bad call cannot contaminate another's context, and a failure
parks exactly one row in the manifest instead of poisoning the wave.

Subagents CANNOT spawn subagents — the Agent tool is unavailable inside
one. So you are the only orchestrator: you fan out the module agents
yourself, and you serialize all git operations. Do not design around a
nested fan-out; it does not work.

## 1. Claim the wave

1. Read `docs/trim-docs-manifest.md`.
2. Confirm the working tree is clean (`git status --porcelain`). If it is
   not, stop and tell the user — a dirty tree makes the per-module
   verification meaningless.
3. Take the first N rows with status `pending`, in file order. The file is
   already sorted so the opus tier comes first.
4. If any row says `running`, a previous wave died. Tell the user and ask
   whether to reset those rows to `pending` before proceeding.
5. Set the claimed rows to `running` in the manifest.

## 2. One worktree per module

Parallel agents editing one checkout WILL corrupt each other. Give each
module its own worktree, branched from current HEAD:

    git worktree add -b trim/<slug> <scratchpad>/trim-wave/<slug> HEAD

`<slug>` is the module path with `/` replaced by `-`. Use your scratchpad
directory, not `/tmp`.

## 3. Fan out

Spawn one agent per module, all in the same message so they run in
parallel. Set `model` from the row's Model column (`opus` or `sonnet`).
Run them in the background.

Each agent's prompt must carry:
- its worktree path, stated as the working directory for the whole task,
  with an explicit instruction not to touch the main repo;
- the single module path it owns;
- the full task brief (below);
- an instruction NOT to commit, and not to run `git checkout`,
  `git stash`, or `git reset`.

### The brief to give each agent

> Bring the docstrings and comments under `<module>` in line with the
> project's docstring standard. Change NOTHING except docstrings and
> comments.
>
> Read first, in your worktree: `.claude/rules/python-docs.md` (the
> standard), `.claude/skills/trim-docs/examples.md` (calibration — these
> set target shape and length), `.claude/skills/trim-docs/SKILL.md` (the
> procedure).
>
> Build the worklist with
> `python .claude/skills/trim-docs/docstring_audit.py scan <module>`.
> Flags are HINTS. Many are false positives: domain acronyms (MCP, DI,
> TOML, PEP, DOM, URL) trip the ALL-CAPS check, and "no longer" is often
> present-tense contract about runtime state, not codebase history. Read
> every docstring in each file you touch — the scan also misses things.
>
> Keep every piece of CONTRACT: behavior, arguments, return values,
> exceptions, side effects, edge cases, units, valid ranges, threading and
> call-timing guarantees, and anything an implementer must honour. Delete
> history, design arguments, rejected alternatives, implementation
> narration, restatements of what a clear name already says, and
> descriptions of callers. A reason a specific LINE is non-obvious becomes
> a one- or two-line present-tense comment on that line.
>
> Never write a claim you have not confirmed by reading the code. Where a
> docstring contradicts the code, the CODE wins — fix the docstring and
> report it. A docstring still over the length guide after everything but
> contract is removed is DONE; do not cut contract to hit a number. Never
> cut a correct example.
>
> No renames, no reformatting (including swapping Unicode punctuation for
> ASCII), no moved code, no new docstrings on previously-undocumented
> code. Leave `# TODO`, `# noqa`, `# type: ignore`, `# pragma` and license
> headers alone.
>
> BEFORE you run the verification commands, do this explicitly: list every
> chunk of architectural reasoning you deleted, and for each one decide
> whether an ADR in `docs/adr/` already covers it. Whatever is left goes in
> `docs/docstring-cleanup-notes.md` — one entry per topic, naming the file
> and symbol, two or three sentences, no copied wording (git has it).
> Then state in your report either the entries you added, or "no notes
> entry needed" WITH the reason. Four of four models skipped this step in
> the benchmark, so treat it as a required checkpoint, not a footnote.
>
> Verify before finishing — all four must pass:
>
>     python .claude/skills/trim-docs/docstring_audit.py verify <module>
>     uv run pytest <targeted test path for this module> -q
>     uv run ruff check <module> && uv run ruff format --check <module>
>     uv run mypy <module>
>
> `verify` is the hard gate: it proves you changed only docstrings and
> comments. Establish the pytest/ruff/mypy baseline BEFORE editing so you
> can tell pre-existing failures from your own.
>
> Pick the SMALLEST test path that covers the module. Test-dir naming is
> inconsistent — both `tests/core/<name>/` and `tests/core/test_<name>/`
> exist, and for some modules BOTH do (`graph`, `node`). Check with
> `ls -d tests/core/<name> tests/core/test_<name> tests/<name> 2>/dev/null`
> and run every path that exists. Do NOT run the full suite or
> `-m "not browser and not perf"` — that costs five minutes and adds
> nothing. If no targeted path exists, say so and run the nearest parent.
>
> If a barn library module has no tests at all, say so plainly rather than
> reporting a pass you did not earn.
>
> Do not commit. Leave changes uncommitted in your worktree.
>
> Report: files changed and rough doc-lines removed; all four verification
> results stated plainly including any failure; sentences you kept because
> you could not tell whether they were contract; any docstring that
> contradicted the code; findings you deliberately left as false
> positives; notes entries you added.

## 4. Collect and land, one at a time

Wait for all agents. Then, per module, SERIALLY — never in parallel, they
share one git index:

1. Export the patch:
   `git -C <worktree> diff -- <module> > <scratchpad>/<slug>.patch`
   Include `docs/docstring-cleanup-notes.md` in the diff path if the agent
   wrote one.
2. `git apply --check` it against the main repo. On rejection, mark the
   row `failed`, note why, and move on — do not force it.
3. Apply it.
4. Re-run all four gates IN THE MAIN REPO. A worktree pass does not
   transfer: the agent may have had a different baseline.
5. If every gate passes, commit exactly this module:
   `docs: trim docstrings in <short module name>`
   and record the SHA in the manifest, status `done`.
6. If any gate fails, revert just this module
   (`git checkout -- <module>`), set the row to `failed`, and append a
   bullet to the manifest's Failure notes with the failing gate and the
   agent's explanation.

Verify the agent's claims rather than trusting the report. In the
benchmark every report was accurate on the gates, but the cheap failure
mode is a confident summary over a diff that lost contract.

## 5. Tear down and report

Remove the wave's worktrees (`git worktree remove --force`). Do NOT run
`git branch -D` — a repo hook blocks it; list the leftover `trim/*`
branches for the user to delete.

Report: one line per module (model, lines removed, gate results, commit
SHA or failure reason), then the manifest's remaining pending count split
by model tier.

## Spot-check

Read the actual diff for at least one module per wave — prefer an opus-tier
one, or any module whose agent reported a contradiction. The mechanical
gates cannot detect deleted contract; that check is yours, and skipping it
is how a wave silently degrades the docs it was meant to improve.
