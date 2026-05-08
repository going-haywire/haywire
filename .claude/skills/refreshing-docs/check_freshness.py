"""Emit one JSON line per stale row in .docmeta/META.md.

Reads .docmeta/META.md, parses the per-doc sections and source tables, and
prints one newline-delimited JSON object for every (doc, source) pair whose
recorded tree-hash no longer matches `git rev-parse HEAD:<source>`.

Output schema:
    {"doc": "docs/x.md", "source": "barn/y.py",
     "recorded_hash": "abc...", "current_hash": "def..."}

Exit code is always 0; empty stdout means nothing is stale.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
META_PATH = REPO_ROOT / ".docmeta" / "META.md"

# Matches "## docs/foo/bar.md" headings — the doc-page sections.
_SECTION_RE = re.compile(r"^##\s+(\S+\.md)\s*$", re.MULTILINE)
# Matches table rows: | path | hash |
_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([0-9a-f]{7,40})\s*\|\s*$", re.MULTILINE)


def current_tree_hash(source: str) -> str | None:
    """Return git rev-parse HEAD:<source> or None if the path is gone."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", f"HEAD:{source}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def parse_meta(text: str) -> list[tuple[str, str, str]]:
    """Yield (doc, source, recorded_hash) tuples from META.md."""
    rows: list[tuple[str, str, str]] = []
    sections = list(_SECTION_RE.finditer(text))
    for i, match in enumerate(sections):
        doc = match.group(1)
        start = match.end()
        end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        body = text[start:end]
        for row_match in _ROW_RE.finditer(body):
            source = row_match.group(1).strip()
            recorded = row_match.group(2).strip()
            # Skip the header separator row that gets matched if its second
            # column happens to be all hex (it won't, but be defensive).
            if source.lower() in {"source path", "---"}:
                continue
            rows.append((doc, source, recorded))
    return rows


def main() -> int:
    if not META_PATH.exists():
        print(f"error: {META_PATH} not found", file=sys.stderr)
        return 1
    text = META_PATH.read_text()
    for doc, source, recorded in parse_meta(text):
        current = current_tree_hash(source)
        if current is None:
            # Source file is gone — emit as stale with current_hash=null so the
            # skill recognises it as a removal.
            print(
                json.dumps(
                    {
                        "doc": doc,
                        "source": source,
                        "recorded_hash": recorded,
                        "current_hash": None,
                    }
                )
            )
            continue
        if current != recorded:
            print(
                json.dumps(
                    {
                        "doc": doc,
                        "source": source,
                        "recorded_hash": recorded,
                        "current_hash": current,
                    }
                )
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
