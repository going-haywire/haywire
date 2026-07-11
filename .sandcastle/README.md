# Sandcastle agent loop

Autonomous ticket-working loop for this repo, built on
[sandcastle](https://github.com/mattpocock/sandcastle) driving the
[Pi coding agent](https://pi.dev/) inside a Docker sandbox. It picks tickets
off a local markdown tracker, implements them one per fresh agent context, and
commits everything to a review branch — **nothing is ever merged
automatically**.

The loop is feature-agnostic: you launch it with a **spec slug**, and all
paths derive by convention:

| | Convention |
| --- | --- |
| spec | `.scratch/issues/<feature>.md` |
| tickets | `.scratch/<feature>/issues/*.md` |
| branch | `agent/<feature>-<variant>` |

(Specs come out of `/to-spec`, tickets out of `/to-tickets` — both already
write this layout.)

## Host prerequisites

The Python toolchain is **not** needed on the host for agent runs — it lives
inside the sandbox image. You need:

| Dependency | Why | Notes |
| --- | --- | --- |
| Node.js ≥ 20 | runs the orchestrator (`npm start` → `tsx main.mts`) | |
| Docker | the sandbox | Docker Desktop on macOS; daemon must be running; multi-GB image |
| Anthropic API key | `claude` variant | in `.sandcastle/.env`, never committed |
| [Ollama](https://ollama.com) | `qwen` variant only | on the **host**, with the model pulled — see below |

## One-time setup per machine

```sh
cd .sandcastle
npm install                              # sandcastle 0.12.x (pinned via lockfile)
cp .env.example .env                     # then fill in ANTHROPIC_API_KEY
npx sandcastle docker build-image        # builds sandcastle:haywire-repo
```

Rebuild the image only when the `Dockerfile` changes.

**Before the first run:** the spec, tickets, `AGENTS.md`, and this
`.sandcastle/` config must be **committed to git**. Sandcastle creates the
agent's worktree from a git branch — untracked host files do not exist inside
the sandbox, so an uncommitted ticket tracker means the agent finds no work.

## Running

```sh
cd .sandcastle
npm start -- <feature>            # Anthropic Claude via API (default variant)
npm start -- <feature> qwen       # qwen3-coder:30b via the host's Ollama

# e.g.
npm start -- graph-settings-tier
npm start -- graph-settings-tier qwen
```

The run budget is derived from the ticket count (+ slack), and the loop
refuses to start if the spec or tickets are missing on the host.

Each variant works the **same tickets on its own branch**, so you can run both
and diff the two implementations:

| Variant | Model | Branch |
| --- | --- | --- |
| `claude` | `claude-opus-4-8` (override: `PI_MODEL` in `.env`) | `agent/<feature>-claude` |
| `qwen` | `ollama/qwen3-coder:30b` | `agent/<feature>-qwen` |

Both branches are created from your current HEAD at first run (launch both
variants from the **same commit** for a fair comparison); subsequent runs of
a variant reuse its branch, stacking one commit per ticket. To compare:

```sh
git diff <base>..agent/<feature>-claude
git diff <base>..agent/<feature>-qwen
git range-diff <base> agent/<feature>-claude agent/<feature>-qwen
```

Review each branch per commit (one commit ≈ one ticket), do the human-only
acceptance boxes the agent deliberately leaves unchecked ("verified in the
running app"), and merge the winner by hand.

## How it works

- `main.mts` loops `run()` up to ticket-count + 3 times. **One run = one
  ticket = one fresh agent context**; state carries between runs only through
  the variant branch (the sandbox worktree is recreated from it each run).
- `prompt.md` holds the frontier discipline: read all tickets, pick the
  lowest-numbered one whose `**Status:**` is `ready-for-agent` and whose
  blockers are `done`, work exactly that one, run the CLAUDE.md quality gates,
  check off only *verified* acceptance boxes, flip the status (or leave a
  `## Progress` note if unfinished), commit code + ticket file together.
- The loop stops when a run emits `<promise>COMPLETE</promise>` (no frontier
  ticket left) or the run budget is exhausted.
- Project rules reach the agent via the repo-root `AGENTS.md` (Pi reads
  `AGENTS.md`, not `CLAUDE.md` — it's a pointer).
- `uv sync` + a Playwright browser top-up run inside the sandbox before the
  agent starts (`onSandboxReady` hooks); browsers are pre-baked in the image.

## The qwen variant (host Ollama)

The 30B model runs on the **host**, not in the container. The image bakes a
Pi provider config (`/home/agent/.pi/agent/models.json`, written by the
`Dockerfile`) pointing at `host.docker.internal:11434`.

Host-side setup:

```sh
ollama pull qwen3-coder:30b
OLLAMA_CONTEXT_LENGTH=65536 ollama serve     # context size is make-or-break
```

- **Context length matters.** Ollama's default context is far too small for
  agentic coding; the provider config declares 65536, and the host must match
  (`OLLAMA_CONTEXT_LENGTH`, or a Modelfile with `num_ctx`). If you change one,
  change the other and rebuild the image.
- Expect slower iterations (the `qwen` variant uses a longer idle timeout) and
  calibrate expectations — a 30B local model may handle architecture-heavy
  tickets noticeably worse than the API model; comparing the two branches is
  the point of the experiment.

## Adding a new feature to the queue

Nothing to configure: produce the spec with `/to-spec` and the tickets with
`/to-tickets` (they write the conventional layout), commit them, then
`npm start -- <feature>`. `prompt.md` is a generic template — the spec path,
tickets dir, and feature name are substituted per run via sandcastle's
`promptArgs`.

## Troubleshooting

- **Agent finds no tickets / empty worktree** — tickets aren't committed on
  the branch the run started from (see one-time setup).
- **Pi rejects the model id** (`claude` variant) — set `PI_MODEL` in `.env`
  (try the `anthropic/…`-prefixed form).
- **`qwen` variant can't reach Ollama** — is `ollama serve` running on the
  host? `host.docker.internal` requires Docker Desktop (on plain Linux Docker,
  add `--add-host=host.docker.internal:host-gateway` or switch the baseUrl in
  the Dockerfile to the docker bridge IP) .
- **Run seems hung** — local models stream slowly; the idle timeout resets on
  any output. Check the log file path printed after each run.
- **Image drift** — after any `Dockerfile` edit:
  `npx sandcastle docker build-image`.
