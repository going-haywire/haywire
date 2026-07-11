# Sandbox image for sandcastle agent runs against the haywire monorepo.
# Built by `npx @ai-hero/sandcastle docker build-image` (or plain `docker build`).
#
# Contains: Python 3.12 + uv (the repo's toolchain), Node 22 + the Pi coding
# agent CLI, and Playwright's chromium + system libs (needed by the
# tests/ui/harness suite, exercised by the panel ticket). The repo itself is
# bind-mounted by sandcastle at runtime; `uv sync` runs there via a hook.

FROM python:3.12-bookworm

# --- System deps -------------------------------------------------------------
RUN apt-get update && apt-get install -y \
  git \
  curl \
  jq \
  && rm -rf /var/lib/apt/lists/*

# --- Node 22 (required by the Pi CLI) ---------------------------------------
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
  && apt-get install -y nodejs \
  && rm -rf /var/lib/apt/lists/*

# --- Pi coding agent ---------------------------------------------------------
# Auth is ANTHROPIC_API_KEY from the environment (sandcastle passes it through
# from .sandcastle/.env).
RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent

# --- Playwright chromium + system libs (for tests/ui/harness) ----------------
# Baked into the image so agent runs don't re-download browsers. The pip
# playwright here only provisions the image; the repo's own (uv-managed)
# playwright is used at test time and finds the browsers via
# PLAYWRIGHT_BROWSERS_PATH. If versions drift, the onSandboxReady hook's
# `uv run playwright install chromium` tops up the cache.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN pip install --no-cache-dir playwright \
  && playwright install --with-deps chromium \
  && chmod -R a+rX /ms-playwright

# --- Non-root user -----------------------------------------------------------
# Agent CLIs are happier non-root, and host-mounted worktree files stay
# reasonably owned on Linux hosts.
RUN useradd -m -s /bin/bash agent
USER agent

# uv for the agent user
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/agent/.local/bin:$PATH"

# --- Pi custom providers (Ollama on the HOST) --------------------------------
# Registers qwen3-coder:30b served by the host's Ollama, reachable from the
# container as host.docker.internal (Docker Desktop). Selected from main.mts
# as "ollama/qwen3-coder:30b". contextWindow must not exceed the host's
# OLLAMA_CONTEXT_LENGTH (see .sandcastle/README.md). Harmless for the
# Anthropic variant — built-in providers are unaffected.
RUN mkdir -p /home/agent/.pi/agent && cat > /home/agent/.pi/agent/models.json <<'EOF'
{
  "providers": {
    "ollama": {
      "baseUrl": "http://host.docker.internal:11434/v1",
      "api": "openai-completions",
      "apiKey": "ollama",
      "compat": {
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": false
      },
      "models": [
        {
          "id": "qwen3-coder:30b",
          "name": "Qwen3 Coder 30B (host Ollama)",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 65536,
          "maxTokens": 16384,
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
        }
      ]
    }
  }
}
EOF

WORKDIR /home/agent
