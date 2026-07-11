# Haywire ticket loop — {{FEATURE}}

You are one iteration of a loop. Your job: complete exactly **one** ticket of
this feature, close it out cleanly, and stop. The next iteration starts with a
fresh context and picks up the next ticket from the state you leave behind —
the ticket files and your commits are the only memory that survives you.

## Ground rules

- Read `CLAUDE.md` first and follow it: read files before editing, check
  `docs/` before reading source, read the relevant `.insights/` trap files
  before debugging, respect the ADRs.
- Read the spec in full: `{{SPEC_PATH}}`. Its Implementation Decisions are
  binding — do not relitigate them.
- Never modify the spec, other tickets' scope, or anything under `.sandcastle/`.
- Run `uv sync` if dependencies are not already installed.

## Select the frontier ticket

Tickets live in `{{TICKETS_DIR}}`, one file each, numbered in dependency
order. Read all of them, including their checkboxes and any `## Progress`
notes from previous iterations.

The frontier ticket is the **lowest-numbered** file whose `**Status:**` is
`ready-for-agent` and whose "Blocked by" tickets all have `**Status:** done`.

If no ticket qualifies — everything is done, or the only remaining tickets are
blocked — output `<promise>COMPLETE</promise>` and stop immediately. Do not
invent extra work.

## Work the ticket

- One ticket only. Do not start a second, even if you finish early.
- If a previous iteration left a `## Progress` note on this ticket, continue
  from where it stopped instead of starting over.
- Test at the seams the spec's Testing Decisions name — assert observable
  behaviour, never private internals.

## Validation gates

Before claiming anything done, all of these must pass with no new findings
(the mypy target list is in CLAUDE.md — use it verbatim):

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy <CLAUDE.md target list>
```

A gate failure you cannot fix this iteration means the ticket is NOT done —
close out honestly per below.

## Close out

- Check off only the acceptance boxes you actually **verified** — evidence,
  not intention. Boxes requiring a human (e.g. "verified in the running app")
  stay unchecked; they are the reviewer's gate, not yours.
- Ticket finished (all boxes except human-only ones): flip its `**Status:**`
  to `done`.
- Ticket unfinished: leave `**Status:** ready-for-agent` and append a
  `## Progress` section to the ticket file saying precisely what is done, what
  is not, and what blocked you.
- Commit everything — code, tests, and the updated ticket file — as
  `agent({{FEATURE}}): <NN> <summary>`, with key decisions and any blockers
  in the body. Commit even unfinished work (the branch is the handoff).
