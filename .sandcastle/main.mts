/**
 * Sandcastle orchestration: works a feature's ticket queue, one ticket per
 * fresh agent context.
 *
 * Usage (from .sandcastle/):
 *   npm start -- <feature> [variant]
 *
 *   npm start -- graph-settings-tier            # Anthropic Claude (default)
 *   npm start -- graph-settings-tier qwen       # qwen3-coder:30b via host Ollama
 *
 * <feature> is the spec slug, resolved by convention:
 *   spec:    .scratch/issues/<feature>.md
 *   tickets: .scratch/<feature>/issues/*.md   (Status/Blocked-by conventions,
 *                                              see an existing ticket)
 *   branch:  agent/<feature>-<variant>
 *
 * One `run()` per ticket, so every ticket starts with a FRESH agent context.
 * State carries between runs only through the variant branch: each run
 * resumes from it, works the frontier ticket (selection logic in prompt.md),
 * commits, and exits. The loop ends when an iteration emits
 * <promise>COMPLETE</promise> (no frontier ticket left) or when the run
 * budget (ticket count + slack) is exhausted.
 *
 * Requires: Docker running; .sandcastle/.env with ANTHROPIC_API_KEY (claude
 * variant) or host Ollama serving the model (qwen variant); and the spec +
 * tickets + AGENTS.md COMMITTED on the branch you launch from — the sandbox
 * worktree is created from git, so untracked files do not exist inside it.
 * Both variants of one feature should launch from the SAME commit for a fair
 * comparison. See .sandcastle/README.md.
 *
 * Review gate: nothing is merged anywhere — work lands on the variant branch
 * for you to review/merge by hand.
 */
import { existsSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { run, pi } from "@ai-hero/sandcastle";
import { docker } from "@ai-hero/sandcastle/sandboxes/docker";

const VARIANTS = {
  claude: {
    // Override with PI_MODEL in .sandcastle/.env if pi rejects this id.
    model: process.env.PI_MODEL ?? "claude-opus-4-8",
    idleTimeoutSeconds: 1800,
  },
  qwen: {
    // Declared in the image's /home/agent/.pi/agent/models.json (Dockerfile),
    // pointing at the host's Ollama via host.docker.internal.
    model: "ollama/qwen3-coder:30b",
    // Local inference is slow — be generous before declaring the agent hung.
    idleTimeoutSeconds: 3600,
  },
} as const;

const usage = `usage: npm start -- <feature> [${Object.keys(VARIANTS).join(" | ")}]`;

const feature = process.argv[2];
if (!feature) {
  console.error(usage);
  process.exit(1);
}
const variantName = process.argv[3] ?? "claude";
const variant = VARIANTS[variantName as keyof typeof VARIANTS];
if (!variant) {
  console.error(`Unknown variant '${variantName}'.\n${usage}`);
  process.exit(1);
}

// Convention-derived paths. Relative to the repo root; validated on the HOST
// checkout as a fast sanity check — but the agent reads them from its git
// worktree, so they must also be COMMITTED on the current branch.
const repoRoot = resolve(process.cwd(), "..");
const specPath = `.scratch/issues/${feature}.md`;
const ticketsDir = `.scratch/${feature}/issues`;
const branch = `agent/${feature}-${variantName}`;

if (!existsSync(join(repoRoot, specPath))) {
  console.error(`Spec not found: ${specPath}\n${usage}`);
  process.exit(1);
}
const ticketCount = existsSync(join(repoRoot, ticketsDir))
  ? readdirSync(join(repoRoot, ticketsDir)).filter((f) => f.endsWith(".md")).length
  : 0;
if (ticketCount === 0) {
  console.error(`No tickets in ${ticketsDir} — run /to-tickets on the spec first.`);
  process.exit(1);
}

// One run per ticket + slack for iterations that close out unfinished
// ("## Progress") and resume.
const maxRuns = ticketCount + 3;

console.log(`feature: ${feature} (${ticketCount} tickets)`);
console.log(`variant: ${variantName} → ${variant.model}`);
console.log(`branch:  ${branch}`);

for (let i = 1; i <= maxRuns; i++) {
  console.log(`\n=== ${feature} [${variantName}]: run ${i}/${maxRuns} on ${branch} ===\n`);

  const result = await run({
    agent: pi(variant.model),
    sandbox: docker(),
    promptFile: ".sandcastle/prompt.md",
    promptArgs: { FEATURE: feature, SPEC_PATH: specPath, TICKETS_DIR: ticketsDir },
    branchStrategy: { type: "branch", branch },
    maxIterations: 1,
    // Repo env is created inside the sandbox before the agent starts.
    // Second command tops up Playwright browsers if the repo's pinned
    // version differs from the ones baked into the image.
    hooks: {
      sandbox: {
        onSandboxReady: [
          { command: "uv sync", timeoutMs: 900_000 },
          { command: "uv run playwright install chromium", timeoutMs: 600_000 },
        ],
      },
    },
    idleTimeoutSeconds: variant.idleTimeoutSeconds,
  });

  console.log(
    `run ${i}: ${result.commits.length} commit(s) on ${result.branch}` +
      (result.logFilePath ? ` — log: ${result.logFilePath}` : ""),
  );

  if (result.completionSignal) {
    console.log("\nAll tickets done (or blocked) — loop complete.");
    console.log(`Review the work on branch: ${branch}`);
    break;
  }
}
