#!/usr/bin/env bash
set -euo pipefail

# RALPH — Autonomous Claude Code agent loop
# Usage: .sandcastle/ralph.sh [iterations]
# Requires: docker, .sandcastle/.env with ANTHROPIC_API_KEY and GH_TOKEN

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_NAME="$(basename "$REPO_ROOT")"

# Load config
ITERATIONS="${1:-$(jq -r '.defaultIterations // 10' "$SCRIPT_DIR/config.json")}"

# Load env
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "ERROR: .sandcastle/.env not found. Copy .env.example and fill in your tokens."
  exit 1
fi
source "$SCRIPT_DIR/.env"

if [ -z "${ANTHROPIC_API_KEY:-}" ] || [ -z "${GH_TOKEN:-}" ]; then
  echo "ERROR: ANTHROPIC_API_KEY and GH_TOKEN must be set in .sandcastle/.env"
  exit 1
fi

IMAGE_NAME="ralph-haywire"
CONTAINER_NAME="ralph-haywire-runner"

# Get remote URL for cloning inside container (tries origin, then first available remote)
REMOTE_URL="$(cd "$REPO_ROOT" && git remote get-url origin 2>/dev/null || git remote get-url "$(git remote | head -1)" 2>/dev/null || echo "")"
BRANCH="$(cd "$REPO_ROOT" && git branch --show-current)"

if [ -z "$REMOTE_URL" ]; then
  echo "ERROR: No git remote found. RALPH needs a remote to clone from."
  exit 1
fi

# Convert SSH URL to HTTPS with token (Docker container has no SSH keys)
if [[ "$REMOTE_URL" == git@github.com:* ]]; then
  REPO_PATH="${REMOTE_URL#git@github.com:}"
  REPO_PATH="${REPO_PATH%.git}"
  REMOTE_URL="https://${GH_TOKEN}@github.com/${REPO_PATH}.git"
fi

echo "=== RALPH — Haywire Autonomous Agent ==="
echo "  Repo:       $REMOTE_URL"
echo "  Branch:     $BRANCH"
echo "  Iterations: $ITERATIONS"
echo ""

# Build Docker image
echo ">>> Building Docker image..."
docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"

# Clean up any previous container
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

# Start container
echo ">>> Starting container..."
docker run -d \
  --name "$CONTAINER_NAME" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -e GH_TOKEN="$GH_TOKEN" \
  "$IMAGE_NAME"

# Clone repo inside container
echo ">>> Cloning repo inside container..."
docker exec "$CONTAINER_NAME" bash -c "
  cd /home/agent/repos
  git clone --branch $BRANCH $REMOTE_URL $REPO_NAME
  cd $REPO_NAME
  git config user.name 'RALPH'
  git config user.email 'ralph@haywire.dev'
"

# Copy prompt into container
docker exec "$CONTAINER_NAME" bash -c "mkdir -p /home/agent/repos/$REPO_NAME/.sandcastle"
docker cp "$SCRIPT_DIR/prompt.md" "$CONTAINER_NAME:/home/agent/repos/$REPO_NAME/.sandcastle/prompt.md"

# Run the loop
echo ">>> Starting RALPH loop ($ITERATIONS iterations)..."
for i in $(seq 1 "$ITERATIONS"); do
  echo ""
  echo "=============================="
  echo "  RALPH iteration $i / $ITERATIONS"
  echo "=============================="

  # Fetch open issues
  ISSUES_JSON="$(docker exec -e GH_TOKEN="$GH_TOKEN" "$CONTAINER_NAME" bash -c "
    cd /home/agent/repos/$REPO_NAME
    gh auth login --with-token <<< \"\$GH_TOKEN\" 2>/dev/null || true
    gh issue list --state open --json number,title,body,comments --limit 20
  ")"

  # Get last 10 RALPH commits
  RALPH_COMMITS="$(docker exec "$CONTAINER_NAME" bash -c "
    cd /home/agent/repos/$REPO_NAME
    git log --all --grep='RALPH:' --format='%H %ai %s' -10 2>/dev/null || echo 'No RALPH commits yet.'
  ")"

  # Check if all issues are done
  ISSUE_COUNT="$(echo "$ISSUES_JSON" | jq 'length' 2>/dev/null || echo "0")"
  if [ "$ISSUE_COUNT" -eq 0 ]; then
    echo ">>> No open issues. RALPH is done."
    break
  fi

  # Write prompt file into container (avoids shell quoting issues)
  PROMPT_FILE="$(mktemp)"
  cat > "$PROMPT_FILE" <<PROMPT_EOF
# OPEN ISSUES
\`\`\`json
$ISSUES_JSON
\`\`\`

# RECENT RALPH COMMITS
\`\`\`
$RALPH_COMMITS
\`\`\`

$(cat "$SCRIPT_DIR/prompt.md")
PROMPT_EOF
  docker cp "$PROMPT_FILE" "$CONTAINER_NAME:/tmp/.ralph_prompt.md"
  rm -f "$PROMPT_FILE"
  docker exec -u root "$CONTAINER_NAME" chown agent:agent /tmp/.ralph_prompt.md

  # Run Claude Code
  docker exec -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    -e GH_TOKEN="$GH_TOKEN" \
    "$CONTAINER_NAME" bash -c "
    cd /home/agent/repos/$REPO_NAME
    claude --dangerously-skip-permissions --bare -p < /tmp/.ralph_prompt.md
  "

  # Push any commits
  docker exec -e GH_TOKEN="$GH_TOKEN" "$CONTAINER_NAME" bash -c "
    cd /home/agent/repos/$REPO_NAME
    git push 2>/dev/null || echo 'Nothing to push.'
  "

  echo ">>> Iteration $i complete."
done

echo ""
echo "=== RALPH finished ==="

# Cleanup
read -p "Remove container? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  docker rm -f "$CONTAINER_NAME"
  echo "Container removed."
else
  echo "Container '$CONTAINER_NAME' kept running. Stop with: docker rm -f $CONTAINER_NAME"
fi
