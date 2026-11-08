---
status: draft
doc_template: impl-spec
scope: Design proposal for making `haywire init` and `haywire share` safe for agents to run unattended — generated publish workflow, explicit first PyPI release, idempotent and machine-readable share, release-PR model, one agent playbook, and the `hay-*` naming problem
see-also:
  - ./share-pipeline-arch.md
  - ../../guides/sharing-libraries.md
  - ../../guides/publish-to-pypi.md
  - ../../guides/rename-library.md
  - ../../haybale/haybale-canon.md
  - ../../adr/0023-project-scoped-lockstep-sharing.md
---

# Agent-safe init and release — design

*Proposal, nothing implemented. Written for the project owner to decide on; effort is S (under a day), M (1–3 days), L (more).*

## 0. Premise and evidence

From now on an agent, possibly a weak one, runs `haywire init` and `haywire share`. Prose rules in a `CLAUDE.md` did not hold. The rule that holds is **the tool refuses**, and says what to do next in a form a cheap model cannot misread.

| # | Incident | Root cause (verified in code unless marked) | Fixed by |
|---|---|---|---|
| a | Single-package version bump in a feature PR | Instruction "bump X" was obeyed; nothing in CI or tooling objects to a version change outside a release PR | §3.6, order step 7 |
| b | `share` reported "denied", had run; retry made v0.0.2 then v0.0.3 | `check_tag_available` (`packages/haywire-core/src/haywire/core/publishing/pipeline/steps/version.py`) checks only the *target* tag. After a success, the tree is clean, on the default branch, and `v0.0.3` is free, so a second `--bump patch` passes every precondition | §3 |
| c | `init` told users `share --save` | Fixed in #18 (`init.py` now prints `share --bump patch`) | done |
| d | First PyPI release impossible via `share` | `_pypi_name_is_registered` (`packages/haywire-core/src/haywire/core/publishing/pipeline/steps/preconditions.py`) treats 404 as "no", and PyPI answers 404 for a pending publisher | §2 |
| e | `uv.lock` pollution | Symlinks not excluded; plain `uv run` re-locks. Mitigated: `--frozen` in all generated commands, excludes in the monorepo | keep; §5 playbook states `--frozen` |
| f | `init` makes `hay-*`; `share` refuses until a whole-project `rename` | `_RESERVED_LOCAL_PREFIX = "hay-"` (`packages/haywire-core/src/haywire/core/publishing/pipeline/steps/preconditions.py`); `init --distname` already exists (`packages/haywire-studio/src/haywire_studio/cli/init.py`) but nobody is told to use it | §6 |

**Design principles** used throughout:

1. *Retry-safe beats retry-proof.* We cannot stop an agent re-running a command (b: the harness itself lied about the outcome). Every command must be harmless to run twice.
2. *The tool is the state machine.* The playbook in `CLAUDE.md` is generated from, and checked against, the states the CLI itself reports. An agent never has to infer "what now".
3. *Humans own what only humans can do* (create the GitHub repo, register a PyPI pending publisher). The tool prints these as a checklist and stops.

## 1. Generated `publish.yml`

**Problem.** The workflow is hand-copied from the guide ([publish-to-pypi §4](../../guides/publish-to-pypi.md)); it is single-package, and the guide's first-release path builds from a branch, so a version can reach PyPI with no tag.

**Options.**
- (A) Keep a copy-paste guide. Rejected: an agent edits a placeholder wrong or skips it.
- (B) Generate it only when the author sets `distribute = "pypi"`. Needs a second command and a way to know when.
- (C) **`init` always writes it; a guard job makes it a green no-op unless `distribute = "pypi"`.** One path, no second command, nothing to forget.

**Recommendation: C.** Shape:

- Triggers: `push: tags: v*.*.*` and `workflow_dispatch`. The dispatch is for recovery only: the `guard` job refuses unless `github.ref_type == 'tag'` (re-run with `gh workflow run publish.yml --ref v0.0.2`). This closes the "upload from a branch, no tag" hole in the current guide §6.
- `guard` job: stdlib-only inline Python (`tomllib`, no install step) reads `[tool.haywire.marketstall] distribute` from the root `pyproject.toml`. Outputs `enabled` and a JSON matrix: one entry per `barn/*` library `{dist, dir, version}`. If not `pypi`: prints "distribute=git, nothing to publish" and every later job is skipped, so the run is green.
- `build` job (matrix, `needs: guard`, `if: enabled`): `uv sync --frozen`, assert the tag equals the library's committed version (same idea as the monorepo's `scripts/check_release_versions.py`, so a tag without a bump fails before any upload), `uv build --package <dist>`.
- `publish` job (matrix, `fail-fast: false`): `environment: pypi`, `permissions: id-token: write`, **skip if `<dist>==<version>` is already on PyPI** (the monorepo workflow already does this, `.github/workflows/publish.yml`), then `uv publish --trusted-publishing always`. Idempotent, so re-running the job after a partial failure is safe.
- A test gate is optional: run `pytest` only if a `tests/` directory exists.

**Multiple libraries, pending publishers.** Verified: the monorepo docs say "repeat for every package" ([publish_releases.md](../../reference/publish_releases.md)). Each distribution name gets its **own** pending publisher, all with identical fields (owner, repo, `publish.yml`, `pypi`). Inferred from PyPI's documented model, not tested here: the OIDC claims identify repo + workflow + environment, not the matrix leg, so one environment serves all legs. **Unverified:** whether PyPI caps pending publishers per account; check before promising projects with many libraries.

**Change.** New `render_publish_workflow()` in `haywire_studio/init.py` (template tested by parsing the YAML and running the guard script against fixture pyprojects); update the `CLAUDE.md` text that says "init creates no `publish.yml`" and the `init` console output; docs: publish-to-pypi §4 becomes "already there, here is how it works". Existing projects: a `haywire init --refresh-workflow` is out of scope; document a one-time copy. **Effort: M.**

## 2. First release to PyPI: `share --first-release`

**Problem.** `distribute = "pypi"` + unregistered name fails preflight (d), and the guide's workaround is a manual untagged branch dispatch that a later `share` then contradicts (no `v0.0.1` tag, though the README's "frozen" URL expects one).

**Options.**
- (A) Manual `workflow_dispatch` (today). Two steps, untagged, an agent must know to do it and when to stop doing it.
- (B) **Explicit `share --first-release`.**
- (C) Infer: treat 404 as "first release". Rejected: a typo'd name, a deleted project and a flaky proxy all look like 404. The tool would tag and push for a name nobody registered.

**Recommendation: B.**

- Without the flag, on 404 under `distribute = "pypi"`: the precondition fails with kind `first_release_required` and prints exactly the human checklist, **derived from the git remote** (host, `owner/repo` parsed from `origin`):

  ```text
  STOP: human needed. Register a pending publisher on PyPI, for EACH name below:
    https://pypi.org/manage/account/publishing/
      PyPI project name : haybale-my-lib        (exactly this, copy it)
      Owner             : maybites
      Repository        : my-repo
      Workflow name     : publish.yml
      Environment name  : pypi
  Also: GitHub repo → Settings → Environments → create `pypi`.
  Then run:  uv run --frozen haywire share --first-release
  ```
- With the flag: preconditions skip the 404 check, **but require 404 for every library** (if any name exists the flag is refused: "name exists on PyPI: drop `--first-release` if it is yours, rename if not"; this also stops a typo that lands on one of the owner's other projects). Then the normal pipeline runs: docs, marketstall, commit, tag, push. The tag push triggers §1's workflow, which creates the project. Version: default is the *current* declared version (no bump, so `0.0.1` is really released); if its tag exists, the tool refuses with `NEXT: add --bump patch`. `--first-release` and `--bump` compose.
- Scope: GitHub only (PyPI also supports GitLab publishers, with different fields). On another host: `STOP: human needed`, link to the PyPI docs.

**Safe failure of a typo.** Inferred from PyPI's trusted-publishing model, not exercised here: the OIDC token exchange looks the publisher up by the project name in the upload. A mismatch between the name on the PyPI form and `[project].name` is a 403 *before* any file is stored, so no version number is burned (a version is only burned by a successful upload). Recovery, all idempotent: correct the PyPI form → re-run the failed job on the tag. If the typo is in the local name: the tag already points at the wrong commit and tags are never moved, so fix the name, commit, and `share --first-release --bump patch` (hence the composability above). Nothing is deleted or force-pushed in any recovery path.

**Cannot be checked:** PyPI has no API to ask "is a pending publisher registered". The flag *is* the assertion; the 403 above is the safety net, and the failure is visible in CI, not silent.

**Change.** New precondition kind and a flag in `share.py`/`share_cli.py`; `read_distribute`-adjacent helper `github_owner_repo(remote_url)` (reuse the host parsing in `publishing/url.py`); `_unregistered_pypi_names` gains a `first_release` mode; tests in `tests/share_pipeline` with a stubbed `_pypi_name_is_registered`. **Effort: M.**

## 3. Agent-proof `share`

Today (verified, `packages/haywire-studio/src/haywire_studio/packaging/share_cli.py`): exit codes are only 0 and 1, output is prose, no state query, no idempotency, no lock. The Share editor drives the same `SharePipeline`, so everything below goes into the pipeline, not only the CLI.

### 3.1 Idempotency

Refuse, with exit code `10 ALREADY_RELEASED`, when either holds:
- `HEAD` is the share commit: message matches `chore: share v<ver>` and tag `v<ver>` exists on `HEAD` (local or `origin`); or
- the latest `v*` tag is an ancestor of `HEAD` and nothing under `barn/` or the root `pyproject.toml` changed since it ("nothing to release since v0.0.2").

Message: `ALREADY RELEASED v0.0.2 at <sha>. Nothing to do. Do not run share again.` This alone would have prevented incident (b). Escape hatch: none; a real new release needs a real commit.

### 3.2 Lock and marker

`.git/haywire-share.json` (inside `.git`, so it never dirties the tree): `{version, tag, phase, started}`, with `phase` advanced through `writing → committed → tagged → pushed` and deleted on success or on a clean rollback. At start, a present marker means an interrupted run: refuse with `STOP: human needed` unless the phase is `committed|tagged`, where the single safe continuation is `haywire share --resume` (push the existing commit and tag; nothing else). Today the equivalent information exists only as `PushError.manual_command` printed once and lost.

### 3.3 `--status`: the one read-only oracle

`haywire share --status [--json]` computes the state (§5) and prints the single next step. Never writes. An agent's rule becomes "before any release action, and after any ambiguous tool result, run `--status`". That also answers the classifier problem in (b) without trusting the harness's report.

### 3.4 Refusals carry the next step

Extend `PreconditionFailure` (has `message, remedy, fix_id, doc_url` today) with `next_command: str | None` and `human_only: bool`. Every refusal prints a final line, exactly one of:
```text
NEXT: git switch main
STOP: human needed — <one sentence>
```
Messages for steps with no safe single command (e.g. dirty tree: the agent must decide what to commit) say `NEXT: commit or discard your changes, then run: haywire share --status`.

### 3.5 `--json` and exit codes

`--json` writes one JSON object to stdout (all prose to stderr): `{schema:1, state, ok, exit_code, version, tag, next:{command}|null, stop:{reason, checklist[]}|null, failure:{kind, message}|null}`. Stable exit codes, documented and pinned by a contract test:

| Code | Meaning | Agent action |
|---|---|---|
| 0 | Released | done |
| 10 | Already released | done, do not retry |
| 20 | Refused, fixable | run `next.command` |
| 30 | `STOP: human needed` | hand `stop.checklist` to the owner, wait |
| 40 | Failed, tree reverted | read `failure`, then `--status`; never loop |
| 50 | Failed after commit (partial) | `share --resume` once, else STOP |
| 64 | Usage error | fix the command |

### 3.6 Human-only steps, declared once

A code-level registry `HUMAN_ONLY_STEPS` (id, title, where, fields, `check()` or `None`): create the GitHub repository (checkable: `git ls-remote origin`), register the PyPI pending publisher (not checkable), create the GitHub `pypi` environment (checkable only if `gh` is authenticated). `init` prints the relevant ones as a checklist at the end; `share` prints them on `STOP`. The generated `CLAUDE.md` says: "when output contains `STOP`, paste it to the owner verbatim and wait; never attempt these steps". Same registry feeds the docs, so text cannot drift.

**Adjacent, outside `share` (incident a):** a CI job in the monorepo and in generated projects that fails a PR changing any `version` field unless the PR is a release PR (`chore: release` / `chore: share`). Cheap, catches the exact failure. Effort S.

**Effort for §3: M** (idempotency, marker, status: M; json/codes/registry: M; can be two PRs).

## 4. Release-PR model vs local commit+tag+push

**Today** (verified): `share` commits on the default branch, tags, and pushes both. The monorepo is *not* the model it is sometimes called: `/haywire-release` bumps in a release PR, but the **tag is pushed by the user** (a local hook blocks tag pushes), and CI publishes on the tag; CI does not tag. release-please is the only CI-tags-on-merge example.

**Release-PR model.** `share --pr`: branch `release/v<ver>`, same commit (bump, docs, marketstall), push, open a PR. On merge, one workflow job tags the merge commit and publishes in the same run. (A tag pushed with the default `GITHUB_TOKEN` does not trigger other workflows, a documented GitHub behaviour, so tag + publish must live in one workflow, or use a token that can trigger.)

| Aspect | Local commit+tag+push (today) | Release PR |
|---|---|---|
| Permission classifier | The agent runs `git push` of a tag and of the default branch: the actions the classifier treats as public surface; incident (b) was this | Agent pushes a branch and opens a PR (still public, but reviewable and reversible). Merge is a separate, gateable act |
| Branch protection | `share` fails on any protected default branch (it pushes to it) | Works with protection |
| Retry | Guarded by §3 idempotency | Natural: re-running finds the open PR or the existing tag |
| Rollback | Before push: revert tree. After push: tag is permanent, only a new version fixes it | Before merge: close the PR, nothing happened. After merge: same as today |
| Human gate | None; the agent can publish unseen | Built in: the owner merges. Good for weak agents, a speed bump for a solo author |
| Squash merge | n/a | The tag goes on the merge commit; `install_spec` pins the tag not a SHA, so this is fine. The marketstall content does not depend on the SHA |
| Effort | done | **L**: PR-opening step (needs `gh`/API auth), tag-on-merge job, Share editor flow variant, docs, tests; marketstall URLs reference a tag that only exists after merge (short window) |

**Recommendation.** Do §3 first (it makes today's model retry-safe and benefits both). Then add `share --pr` as an **opt-in** mode, structured by making the pipeline's last step a pluggable "land" step (push vs open-PR). Make `--pr` the mode the generated agent playbook uses once it exists. Do not remove the direct mode: solo authors with an unprotected repo should keep one command.

## 5. One agent playbook, as a state machine

The tool computes `state` (`share --status --json`). `init` writes the playbook into `CLAUDE.md` (and `AGENTS.md` keeps pointing at it) **generated from the same state table**, with a unit test that every state in code has a row in the template and vice versa.

| State | Detected when | Exact command | Expected output | Next |
|---|---|---|---|---|
| NO_PROJECT | no `pyproject.toml` | `haywire init <name> --distname haybale-<final> -y` (ask the owner for the final name and for git vs PyPI first; **never accept the `hay-` default if the project will be shared**) | `Project '<name>' created` + human checklist | NO_REMOTE |
| NO_REMOTE | no `origin` | `STOP`: owner creates the GitHub repo and gives the URL; then `git remote add origin <url> && git push -u origin <default>` | push succeeds | DIRTY or READY |
| DIRTY_TREE | `git status --porcelain` non-empty | `git checkout uv.lock` if only that changed, else commit the work | clean | `--status` again |
| WRONG_BRANCH | not on default | `git switch <default>` | on default | `--status` |
| NEEDS_FIRST_RELEASE | `pypi` + 404 | `STOP`: hand the PyPI checklist to the owner; after they confirm: `share --first-release` | tag pushed, CI starts | RELEASED |
| READY | all preconditions pass | `uv run --frozen haywire share --bump patch` (minor/major only if the owner said so) | `RESULT: released v<ver>`, exit 0 | RELEASED |
| RELEASED | HEAD is a tagged share commit | none | `ALREADY RELEASED`, exit 10 | DONE |
| INTERRUPTED | marker present | `share --resume` once; if it fails: `STOP` | `RESULT: pushed`, exit 0 | RELEASED |
| UNKNOWN / exit 40, 50 | anything else | `STOP`: paste full output to the owner | - | - |

Standing rules, in the first three lines of the playbook: always `uv run --frozen`; run `--status` before acting and after any unclear tool result; never run `share` twice for the same change; never tag, push tags, force-push, or edit versions/`marketstall.toml`; `STOP` means stop.

**Cheap-model dry-run test (describe, not build).** A script under `scripts/` plus a test directory:
1. Scratch project in a temp dir via `haywire init`, with a *local bare git repo* as `origin` (a filesystem remote skips the host check, per the sharing guide) and a stubbed PyPI lookup (env var).
2. Run a small model (Haiku class) headless with only the generated `CLAUDE.md` and a restricted tool set, on prompts like "create project X and release it", "release this", "release again", with the harness playing the owner when the agent reaches a `STOP`.
3. Fault injections: dirty tree; wrong branch; name 404 under `pypi`; a stale marker; and **retry bait** (the harness replaces a successful `share` result with "permission denied" to reproduce incident (b)).
4. Assert on repository state, not transcripts: exactly one new tag, versions unchanged on `ALREADY_RELEASED`, no tag push or force push attempted, no hand edit of version fields, every `STOP` surfaced to the owner. Five runs each; any failure fails. Run on demand first, nightly later; not a PR gate (cost, flakiness).

**Effort: M** (template + sync test: S; harness: M).

## 6. `hay-*` libraries published via git

### 6.1 What was verified in code

- **Build:** every key is `reg_key(identity.name, kind, id)` = `<name>:<kind>:<Class>` (`packages/haywire-core/src/haywire/core/library/utils.py`), called from ~15 decorators (node, type, widget, skin, theme, state, setting, panel, editor, adapter, farmhand, wire). `identity.name` is the `name` in `haybale.toml`, i.e. the distribution name.
- **Parse:** by `split(":")` in at least 10 production sites, not one parser: `split_reg_key` (maxsplit 2), `get_kind_from_key`, `get_registry_id_from_key`, macro source/registry, `field_list_widget.py:72`, `node/factory.py:291`, docs `extract.py`, `di/config.py:835,879`, and two **strict 3-way unpacks** (`farmhand/base.py:34`, `farmhand/host.py:197`) that raise on any 4th segment.
- **Stored:** in saved graphs (`registry_key`, `widget_key`, `chain_adapter_keys`, `node_data.library.{name,module_name,folder_path}`, `node_data.identity.module`, per the [rename guide](../../guides/rename-library.md)); the rename tool recognises keys with `_KEY_GRAMMAR` (`packages/haywire-studio/src/haywire_studio/packaging/rename/graphs.py`), whose first segment allows only `[A-Za-z0-9._-]` (no `/`, no `@`). The marketplace uninstall check text-searches `"<library_id>:<kind>:<Class>"`. Roughly 88 non-test files reference a library id (a grep count, not an audit of each).
- **Loader does not refuse duplicates.** It dedupes by `identity.name` with priority core > pip > folder and **silently skips** the later one with an INFO log (`packages/haywire-core/src/haywire/core/library/registry.py`). The brief assumed a clear error; there is none today.
- **Feeds:** `identity_matches` (`barn/haybale-marketplace/haybale_marketplace/identity.py`): same name, both git: equal only if same canonical `origin`; otherwise a conflict. So a collision is detected when subscribing, not when loading. `write_barn_origins` re-records `origin` on every publish, so a fork's first publish records the fork.
- **The `hay-` check** is a string-prefix test only (`packages/haywire-core/src/haywire/core/publishing/pipeline/steps/preconditions.py`).
- **Inferred, not tested:** two distributions that ship the same top-level module (`hay_mylib`) cannot coexist in one environment, whatever the registry keys look like.

### 6.2 Options

**(i) Downgrade the `hay-` failure to a warning for `distribute = "git"`.** Removes the friction in (f). But `hay-` exists because every user's *own* local library is `hay-<project>` ([canon §5](../../haybale/haybale-canon.md)). A published `hay-weather` collides, by key and by module, with any consumer's local `hay-weather`, and the loader then **silently shadows** one of them (verified above): graphs resolve to the wrong library with no error. The reservation is what prevents that. **Not recommended.**

**(ii-a) Origin-qualified keys** (`maybites/hay_mylib:node:Resize`). Breaks: the ≥10 `split(":")` sites and the two strict unpacks; `_KEY_GRAMMAR`; every saved graph, settings store and feed (a migration for all of them); and a fork or repo move **changes every key**, orphaning graphs, the opposite of stability. It also does not fix the module-name collision. **Not recommended.**

**(ii-b) Stable library id decoupled from the distribution name** (an immutable `id` in `haybale.toml`, keys built from it). Fork and repo move are unaffected (the id travels in the manifest; a fork shares the lineage, which is the right default), and `rename` would stop rewriting graphs. But: same migration scope as (ii-a), a feed schema change (`id` next to `name`), and the module-name collision remains, so authors would still have to pick unique module names. **Effort: XL. Defer** until collisions are actually observed.

**(iii) Recommended: remove the cause, keep the rule.** The pain in (f) is renaming a project *with graphs*. At `init` time there are none, and `init --distname haybale-<final>` already scaffolds the right name (verified). So:
- the agent playbook (§5) makes the final name a required input to `init` for any project that will be shared;
- `init` without `--distname` prints one extra line: "`hay-*` is local-only; to share this project use `--distname haybale-<name>` now (renaming later rewrites every graph)";
- the `hay-` precondition message points at the same advice, and `NEXT:` carries the exact `haywire rename` command it already prints.
- Hardening, independent of this decision (S): make the loader's silent skip a **WARNING** that names both sources, so a shadowed library is visible. That is the "clear error" the brief assumed; it is a behaviour change to confirm (an error could break startups that rely on the skip, e.g. the core-over-pip priority).

**Effort: S** for (iii) and the warning; (ii) not scheduled.

## 7. Recommended order of work (small PRs)

1. **Share idempotency + marker + `--status`** (§3.1-3.3). Directly prevents incident (b). M.
2. **Exit codes, `--json`, `NEXT/STOP` fields** (§3.4-3.5). M.
3. **Human-only registry; checklist in `init` and `share`** (§3.6). S.
4. **Generated `publish.yml`** (§1) + CLAUDE.md/`init` text fixes. M.
5. **`share --first-release`** (§2). M. Needs 1, 2, 4.
6. **Playbook generated from the state table** + sync test, `--distname` hint, loader shadowing warning (§5, §6). S-M.
7. **Version-change guard job** for feature PRs (incident a). S.
8. **Cheap-model dry-run harness** (§5). M.
9. **`share --pr`** (§4). L, opt-in; decide after 1-6 have been used.
10. Not scheduled: stable library id (§6 ii-b).

Each PR touches code, the relevant guide, and the contract tests; none changes a version number.

## 8. Open questions

1. **Release PR (§4):** make `--pr` the default for agent-driven projects once it exists, or keep direct publish as default everywhere?
2. **Exit code 10:** is "already released" a success (agents treat as done, my proposal) or a refusal?
3. **First release scope (§2):** GitHub-only with `STOP` elsewhere acceptable?
4. **`publish.yml` dispatch:** OK to accept dispatch only on tags (no branch builds)?
5. **`hay-` (§6):** agree to keep the failure and fix at `init` time; and may the loader's duplicate skip become a warning?
6. **Bump authority:** may the agent choose only `patch`, with minor/major requiring the owner's word?
7. **Marker location:** `.git/haywire-share.json` acceptable, or prefer a tracked file?
8. **PyPI pending-publisher limit per account** (unverified): worth checking before we promise multi-library projects?

## 9. Follow-up: review the monorepo release flow

Once this design has landed, the next design doc should review the **haywire monorepo's own release flow**. Out of scope here, but it should not be forgotten, for these reasons:

- **Incident (a) happened in the monorepo**, not in a generated project. This doc covers it only with the version-guard job (§7, step 7).
- **It is a second implementation of the same job.** `scripts/bump_version.py` and `/haywire-release` bump; the release PR is merged by hand; the user pushes the tag (a local hook blocks tag pushes); `publish.yml` then publishes, skipping versions already on PyPI. This is the flow §4 compares the release-PR model against, and CI does not tag.
- **It has the same agent risks as `share`:** `/haywire-release` is written as a walkthrough for a human; nothing reports the release state; retrying after a half-finished run relies on the agent's judgement; the `uv.lock` pollution (incident e) happened here.

Checks for that review:
1. Make `/haywire-release` retry-safe: if `vX.Y.Z` is already merged or tagged, stop with "already released".
2. CI guard: fail any PR that changes a `version` field unless it is a `chore: release` PR.
3. A `--status` equivalent (bumped, merged, tagged, on PyPI) so an agent need not infer the state.
4. Share code with `share` or stay separate? Project-scoped lockstep (ADR-0023) and `[tool.haywire.release]` lockstep are close; `publish.yml` generation (§1) and the idempotent-skip step may be shareable.
5. Which steps stay human-only? The tag push is deliberately human today; a release-PR model could move it to CI. That is a policy decision (open question 1).

**Order:** after share PRs 1-3 (idempotency, `--status`, exit codes), so the review reuses their state definitions. The version-guard job is independent and can land earlier. Same structure as this doc: problem, options, recommendation, effort.
