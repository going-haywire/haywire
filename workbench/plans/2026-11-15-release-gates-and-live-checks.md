# Release gates and live checks in the workflow: design and slices

Design pass for going-haywire/haywire#110, extended by the user on 2026-11-15 to bring
the Questionnaire (ADR 0083, `docs/reference/questionnaire.md`) into the documented
workflow. Settled with the user on 2026-11-15: every **(rec)** option below was chosen
(A1, A7, B1, B5 asked explicitly; the rest taken as proposed). Each slice's last task
marks its row in *Status*.

**Corrections by the user, 2026-11-15, after slices 1–2 were drafted** (they override the
tables below):

- **Live checks are rare and last.** They cost the user's time, so they confirm a change
  the agent is already confident in; they never find bugs. The agent first checks
  everything it can itself (tests, Farmhand tools, an empty error ledger), asks only
  for what needs a person, and asks before a second round. (Narrows B1, B2, B4.)
- **Release gates are reminders, not rules.** A labelled issue records a decision that
  affects the next release (most often a dependency floor to raise once a release
  contains a change). An agent proposes one and opens it only on the user's word, and an
  open `todo-pre-release` is listed before a release, not a stop. The convention moves
  from `sharing-libraries.md` §4.4 (*What has to be true before you publish*) to §7.1
  *Release reminders*. (Changes A3–A6, A8.)

## Problem

1. **Release-gated work is forgotten.** Library work prepared before the core release it
   needs (haybale-stream#8/#9 waiting for #107; the five Author API issues waiting for
   #108) is tracked only by convention in one library's `CLAUDE.md`. Nothing in the
   monorepo's release flow looks at it, new libraries do not get the convention, and the
   human docs do not describe it.
2. **Live checks are free text.** The studio now has the Questionnaire: an agent posts
   *do this, expect that* Checks, the user answers them in ASIDE, the agent reads the
   Findings. But no workflow says when to run one, how, or where the result is recorded.
   Today a live check survives only as "live-checked" in a plan's Status row.

## Where things stand

| Place | Today |
|---|---|
| haybale-stream | `todo-pre-release` + `after-core-release` labels; *Release-gated issues* section in `CLAUDE.md` (haybale-stream#10). |
| protokol, comfyui, spandrel, visiongraph | `after-core-release` label only (created for the Author API issues); no `CLAUDE.md` section. |
| haywire (monorepo) | Neither label. `/haywire-release` ends at the tag push and CI handoff (Step 9). |
| `haywire init` | Generated `CLAUDE.md` = release playbook (`haywire_studio/playbook.py`); nothing on gated issues. |
| `haywire share` | Host-agnostic (GitHub, GitLab, local paths), git only, never calls `gh` or a host API. |
| `docs/guides/sharing-libraries.md` | Nothing on gated work. |
| `haywire-workflow` skill | Tests → commit → PR → ready; no live check step. |
| `haywire-live-studio` skill | studioctl + Farmhand tools; does not mention the Questionnaire. |
| PR template | Checklist has checks, docs, versions; no live check. |
| Open gated issues | stream#8, stream#11, spandrel#1, visiongraph#2, comfyui#1, protokol#3. |

## Decisions

### Part A: release gates (#110)

| # | Question | Options | Proposal |
|---|---|---|---|
| A1 | Labels: convention or enforced by `haywire share`? | (a) convention, checked by agents per `CLAUDE.md` and the skills; (b) `share` checks via the GitHub API; (c) `share` checks only when `gh` is present, warns otherwise | **(a) (rec).** `share` is host-agnostic and needs no token today; (b) adds GitHub coupling and a secret to every release, (c) gives a check that silently means different things on different machines. Revisit if a person releasing by hand ships a gated library. |
| A2 | Library-to-library dependencies | (a) not now; `after-core-release` covers anything released from the monorepo (lockstep, so "core" = any monorepo package); (b) a generic `after-dependency-release` label with the package named in the issue | **(a) (rec).** No case yet; the issue format below names the dependency explicitly, so (b) is a label addition later, not a redesign. |
| A3 | Label names, colours, who creates them | — | Names and colours as in haybale-stream: `todo-pre-release` `#D93F0B` "Must be closed before this library is released"; `after-core-release` `#FBCA04` "Can be done only once a haywire-core release contains the needed change". One home: a `RELEASE_GATE_LABELS` tuple in `playbook.py` that renders into the generated `CLAUDE.md` with the `gh label create … --force` lines (idempotent). The agent creates them on first need; the monorepo gets both now. |
| A4 | What the issue must say | — | A first line the sweep can read: `Waits for: going-haywire/haywire@<sha> (#<pr>)`. The sweep answers "is it released" with `git tag --contains <sha>` in the monorepo; no parsing of prose. |
| A5 | Offline / no `gh` | — | The agent says the check could not run and asks before releasing; never treats "could not check" as "nothing open". |
| A6 | Monorepo's own `todo-pre-release` | (a) yes, `/haywire-release` stops on open ones; (b) only libraries | **(a) (rec).** Same rule on both sides, one sentence in the skill. |
| A7 | Sweep driven by the Author API name list (issue comment) | (a) in the release skill now, by hand (diff `tests/api/names.py` between tags, `gh search code` per removed/deprecated name, draft one issue per hit library); (b) a script `scripts/release_sweep.py` that does the gated-issue sweep and the names diff and prints a report; the skill runs it; (c) later | **(b) (rec), as slice 3.** Deterministic and testable; the agent only drafts issues and comments, and posts them on the user's word (they appear under the user's name). |
| A8 | After the sweep, what is public | — | The agent reports a table (issue, waits for, released in, now unblocked yes/no) and offers one comment per unblocked issue ("unblocked by vX.Y.Z"). Posting is on the user's word. |

### Part B: live checks with the Questionnaire

| # | Question | Options | Proposal |
|---|---|---|---|
| B1 | When is a live check due? | (a) every change; (b) when the change has an effect tests cannot judge (UI, layout, interaction, theme, real devices, a library in the real studio), and the user can waive it; (c) only when the user asks | **(b) (rec).** The agent says in the PR which case applies. |
| B2 | When in the flow | — | After the checks pass and before the PR is marked ready; again for a fix that touches what failed. |
| B3 | Where the Checks come from | — | The acceptance points of the issue or plan, one `check` per behaviour (`do` / `expect`); for a fix, the reproduction of the bug as the first check. |
| B4 | The loop | — | `studioctl start` in the worktree → `haybale-studio_post_questionnaire` → tell the user → wait for their word → `haybale-studio_get_findings` → `haybale-studio_get_errors` with `since_seq = ledger_seq.posted` → fix each failed or blocked Check → re-post only those (plus a regression check if the fix was broad) → until none fail. Record the Findings before the next post: a post replaces them. |
| B5 | Where Findings are recorded | (a) the PR body, a *Live check* section: one row per Check (verdict, note, fixing commit), each round dated; (b) also the plan's Status row (link to the PR section); (c) a file under `workbench/` | **(a) + (b) (rec).** The PR is where the reviewer reads it; Findings on disk are local and replaced by the next post. |
| B6 | One home per piece | — | *When* and *where recorded*: `haywire-workflow` skill (agents) and CONTRIBUTING.md one line (people). *How to drive it*: `haywire-live-studio` skill. *Format*: `docs/reference/questionnaire.md` (unchanged). |
| B7 | Library repositories | — | The generated `CLAUDE.md` and the library guides get one line: a change a user sees is live-checked in the studio with a Questionnaire before release. A library session mostly runs from the monorepo (symlinked `barn/`), so the monorepo skills apply. |
| B8 | Release smoke | (a) `/haywire-release` posts a short smoke Questionnaire (studio boots, open and run a graph, Marketplace lists) before tagging; (b) not now | **(b) (rec)** for this pass; worth a slice once the per-PR loop has run a few times. |

## Edits

### Slice 1: live checks (docs and skills only)

1. `.claude/skills/haywire-workflow/SKILL.md`: new section *Live check*, after *Choosing
   and running tests*: when (B1), when in the flow (B2), where the Checks come from (B3),
   the loop as a pointer to `haywire-live-studio`, recording (B5). *Pushing and opening
   the PR*: the body's *Live check* section. *Finishing as the maintainer* step 2: the
   Findings table goes with the review request.
2. `.claude/skills/haywire-live-studio/SKILL.md`: *Live check with a Questionnaire*: the
   loop (B4), the traps (a post replaces the Findings; reading a submitted one closes it;
   no push, the user says when done; `ledger_seq.posted` for the errors), link to the
   format page. Add `haybale-studio_post_questionnaire` / `get_findings` to *When to use*
   and the description's triggers ("live check", "questionnaire", "ask the user to test").
3. `.github/pull_request_template.md`: checklist item *Live-checked in the studio, or not
   needed because …*; section *Live check* (Findings table). (Agent file: maintainer reads.)
4. `CONTRIBUTING.md` *Making the change*: one line on trying a visible change in the studio.
5. `docs/guides/development.md` *Run*: one line pointing agents' live checks at the
   Questionnaire reference.

### Slice 2: release gates (docs, skills, scaffold)

1. `docs/guides/sharing-libraries.md`: new §, *Work that waits for a release*: the two
   labels, the `Waits for:` line, when each is checked; human-facing home of the convention.
2. `packages/haywire-studio/src/haywire_studio/playbook.py`: `RELEASE_GATE_LABELS` and
   `render_release_gates()`; `init.py` `_generate_claude_md` adds the section (check before
   `share`, check at session start, create labels on first need, `Waits for:` line, offline
   rule A5). Test: the rendered section names both labels and the `gh label create` lines.
3. `.claude/skills/haywire-release/SKILL.md`: Step 2 gains the monorepo `todo-pre-release`
   check (A6); new Step 10, *Sweep gated work* (after the publish run succeeds): the
   report table and the comment offer (A8).
4. `docs/reference/publish_releases.md`: the sweep, one paragraph, linking the skill.
5. Monorepo labels: `gh label create` both, on the user's word.
6. External libraries (one stream at a time, each a PR in its repo, on the user's word):
   bring the *Release-gated issues* section of protokol, comfyui, spandrel, visiongraph to
   the generated text; add `todo-pre-release` where missing; add the `Waits for:` line to
   the six open issues.

### Slice 3: the sweep script (A7)

1. `scripts/release_sweep.py <new-tag> [--previous <tag>]`: open `after-core-release`
   issues across `going-haywire` with their `Waits for:` sha and whether `<new-tag>`
   contains it; then the diff of `tests/api/names.py` between the tags (removed and newly
   deprecated names) and, per name, the org repositories that import it
   (`gh search code`). Prints a report; `--json` for the skill. Writes nothing on GitHub.
2. Tests with a stand-in `gh` (as `tests/scripts/test_claude_hooks.py` does).
3. `/haywire-release` Step 10 runs it; the agent drafts one `after-core-release` issue per
   library hit that has none, and posts on the user's word.
4. `scripts/README.md` entry.

## Non-goals

- `haywire share` calling GitHub (A1).
- A label for library-to-library waits (A2).
- Posting issues or comments without the user's word.
- Changing the Questionnaire format or tools.

## Status

| Slice | State | Commit | Date | Deviations |
|---|---|---|---|---|
| 1 Live checks | done | 6dc3f5558 | 2026-11-15 | B7's line went into the generated `CLAUDE.md` (slice 2) and the author cycle of `sharing-libraries.md` §7. |
| 2 Release gates | done except step 5 (labels here: only when the user agrees to a first reminder) and the `Waits for:` lines (on the user's word) | #119; library PRs stream#12, protokol#4, comfyui#2, spandrel#2, visiongraph#3 | 2026-11-15 | Reworded as *release reminders* after the user's correction (top); the convention is `sharing-libraries.md` §7.1. Step 6: every library's `CLAUDE.md` gets the generated section verbatim (stream's hand-written *Release-gated issues* replaced); label descriptions in those repos still read as rules. The generated `CLAUDE.md` checks "released" with `gh api …/compare/v<pypi-version>...<sha>` (`behind`/`identical` = released), so a library needs no monorepo checkout; tried on stream#8's 840d29a21 (`ahead` of v0.4.2) and v0.4.1 (`behind`). The release skill's Step 10 uses `git merge-base --is-ancestor` until slice 3's script. `publish_releases.md` *Local phase* still says the skill runs the gate tests (it checks CI instead): stale before this change, left for a docs pass. |
| 3 Sweep script | proposed | | | |
