# trim-docs model benchmark — results

Target: `packages/haywire-core/src/haywire/core/marketstall/` (13 files + host_providers/, 2375 lines, 58 scan findings)
Baseline: dde749c5 — 287 tests pass, ruff clean, mypy clean.
Four isolated git worktrees, branches `bench/trim-*`.

## Mechanical gates — all four pass, independently verified

| | haiku | sonnet | opus-low | opus-high |
|---|---|---|---|---|
| code-identity `verify` | pass | pass | pass | pass |
| pytest (287) | pass | pass | pass | pass |
| ruff check + format | pass | pass | pass | pass |
| mypy | pass | pass | pass | pass |
| out-of-scope edits | none | none | none | none |
| files touched | 14 | 15 | 17 | 16 |
| insertions / deletions | 123 / 558 | 121 / 198 | 391 / 517 | 371 / 466 |
| residual findings | 28 | 46 | 31 | 32 |
| tokens | 127k | 167k | 182k | 189k |
| wall clock | 9m15s | 11m12s | 19m02s | 14m53s |

Every variant's self-report was accurate on the gates. The mechanical bar
does not separate them — judgment does.

Residual-finding counts are NOT a quality ranking: haiku's low 28 comes
from deleting content wholesale, sonnet's high 46 from deliberately
declining to cut contract. Reading it as "haiku cleared more" is the trap
the metric sets.

## The designated trap: framework_gate.py

The module docstring mixes deletable history with a hard safety invariant:
*"It must never be the sole guard, and a missing `require` must never block
anything."* `check_require`'s six-case list is pure contract that trips
three scan flags at once.

| variant | invariant kept? | six cases | Args: added |
|---|---|---|---|
| haiku | **LOST** | compressed to a parenthetical | no |
| sonnet | kept verbatim | flattened to prose | no |
| opus-low | **LOST** | kept as list | yes |
| opus-high | kept, as imperative | kept as list | yes |

Same model, different prompt, opposite outcome on the most important
sentence in the package. The terse prompt lost it; the full brief kept it.

## Docstrings audited AGAINST the code — the Opus-only class of finding

Neither haiku nor sonnet produced any. All verified by me in the live repo:

- `parsing.py:192` cites `_merge_cache` as justification. That identifier
  appears **exactly once in the entire repo** — in that comment. Dangling
  reference to a function that does not exist. (opus-low + opus-high)
- `subscribe.py` module docstring claimed "one pure function… no I/O";
  `subscribe()` reaches `_save_pasted_block` → `write_text`. (opus-low)
- `types.py::Subscription` claimed blocks are "un-blockable only by editing
  the file"; `helpers.remove_block_on_source()` exists at helpers.py:211.
  (opus-high)
- `_parse_haybale_entry` documented only `version` as required while the
  code also defaults `install_spec` to `name`. (opus-high)
- `url_resolution.py` "form 3" numbering contradicts itself. sonnet spotted
  it and left it; both Opus runs fixed it.

## Per-variant judgment

**haiku** — passes every gate cheapest and fastest. But it over-trims:
558 deletions vs sonnet's 198 on the same files. Deleted the worked
examples in `requirement.py` that the standard explicitly protects
("Never cut a correct example to save space"), lost the sole-guard
invariant, flattened the three-state token table. Left `**advisory**` bold
in place, which the standard bans. Report claimed "no false positives left
behind" and "no contradictions" — false confidence given what it cut.
*Usable only with a reviewer reading every diff, which is most of the work.*

**sonnet** — best cut discipline. Kept the invariant verbatim, kept the
examples, and **declined to trim four docstrings** still over the guide,
naming each and arguing every remaining line was contract. Explicitly
separated domain acronyms from real emphasis and argued "no longer" was
runtime state, not history. Found `gitlab.py`, which haiku missed. Fixed a
latent bug in the original (table said "two states", listed three).
Losses: the share-wizard "no-pin" rationale; and it swapped Unicode `→`
for ASCII `->` in refresh.py — gratuitous reformatting the brief forbids.

**opus-low (terse prompt)** — 17 files, most coverage, found two real
contradictions. But it **lost the sole-guard invariant**, and it ran
`pytest -m "not browser and not perf"` (~5 min, 4980 tests) instead of the
10-second targeted tier, then hit a pre-existing environmental failure
(`haybale-visiongraph` symlink absent in a worktree) it had to work around.
That is where its 19 minutes went. The terse prompt cost coverage of the
rules and wall-clock both.

**opus-high (full brief)** — best on every judgment axis. Kept the
invariant as an imperative ("Never use this gate as the sole guard"),
kept the six-case list as a list, added `Args:` entries the standard
requires and the original lacked, surfaced that `message` is empty unless
`ok` is False. Answered "what did you keep under uncertainty" with four
specific named sentences and reasoning. Listed five rename/retype
candidates without changing them. Ran `ruff format --check` unprompted,
citing CI.

## Gap common to all four

None added a `docs/docstring-cleanup-notes.md` entry, though SKILL.md
step 6 asks for one and framework_gate.py's deleted rationale warrants it.
If the notes entry matters, the skill needs to make it a gate, not a
closing instruction — four of four models skipped it.

## Answer to the question asked

Cheapest model that does this task *reasonably*: **Sonnet**.

- Haiku is cheapest but loses contract in ways only a full diff review
  catches — which costs more than the model saved.
- Sonnet passes the contract axis at ~1.3x haiku's tokens.
- Opus adds a different capability: auditing docstrings against the code.
  Four real defects on one package, none of which the task asked for.

Suggested split for the remaining ~40-60 batches:
- **Sonnet for the bulk**, with the full brief.
- **Opus for the public-API packages** (core/settings, core/node, ui/skin)
  where a false docstring is most expensive — budget it as a docs *audit*,
  not a trim.
- **Not haiku**, unless someone reviews every diff.

## Prompt effort mattered as much as model choice

The two Opus runs differ only in prompt. The terse one lost the safety
invariant and burned 4 extra minutes on the wrong test tier. Whatever
model you pick, send the full brief — it is the cheapest quality lever here.

## Caveat

n=1 per variant on one package. Directional, not statistically robust.
The trap file was chosen to be discriminating, so it overweights
contract-preservation relative to an average package in the long tail.
