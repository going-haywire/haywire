"""Emit pending docs whose own tree-hash has changed since the pending date.

Walks .docmeta/META.md for sections containing "Review pending: <date> (doc-hash
`<hash>`)" and compares the recorded doc-hash to the current HEAD tree-hash for
that doc. Prints one path per line for every pending doc whose content has
changed since it was marked pending.

Skill workflow consumes this output: for each path, the coverage subagent
re-classifies the doc (it may now be R, N, or still P).

Exit code is always 0; empty stdout means no pending doc has changed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
META_PATH = REPO_ROOT / ".docmeta" / "META.md"

_SECTION_RE = re.compile(r"^##\s+(\S+\.md)\s*$", re.MULTILINE)
_PENDING_RE = re.compile(
    r"^Review pending:\s*[\d-]+\s*\(doc-hash\s+`([0-9a-f]{7,40})`\)\s*$",
    re.MULTILINE,
)


def current_tree_hash(path: str) -> str | None:
    """Return git rev-parse HEAD:<path> or None if the path is gone."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", f"HEAD:{path}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def parse_pending(text: str) -> list[tuple[str, str]]:
    """Yield (doc, recorded_doc_hash) for every 'Review pending' section."""
    rows: list[tuple[str, str]] = []
    sections = list(_SECTION_RE.finditer(text))
    for i, match in enumerate(sections):
        doc = match.group(1)
        start = match.end()
        end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        body = text[start:end]
        pending_match = _PENDING_RE.search(body)
        if pending_match is not None:
            rows.append((doc, pending_match.group(1)))
    return rows


def main() -> int:
    if not META_PATH.exists():
        return 0
    text = META_PATH.read_text()
    for doc, recorded in parse_pending(text):
        current = current_tree_hash(doc)
        if current is None or current != recorded:
            print(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
