"""Report doc pages under docs/ that have no META section.

Walks docs/ for *.md files, compares the set against sections declared in
.docmeta/META.md. Prints one path per line for every doc page that is NOT
covered (neither a "Last reviewed" section nor a "No review needed" section).

Exit code is always 0; empty stdout means coverage is complete.

The skill workflow consumes this output: for each uncovered doc, an Explore
subagent reads it and proposes either --create (with sources) or --no-review.
The user approves before update_meta.py runs.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
META_PATH = REPO_ROOT / ".docmeta" / "META.md"
DOCS_ROOT = REPO_ROOT / "docs"

_SECTION_RE = re.compile(r"^##\s+(\S+\.md)\s*$", re.MULTILINE)


def covered_docs() -> set[str]:
    """Return repo-relative doc paths that already have a META section."""
    if not META_PATH.exists():
        return set()
    text = META_PATH.read_text()
    return {match.group(1) for match in _SECTION_RE.finditer(text)}


def all_docs() -> list[str]:
    """Return repo-relative paths of every .md under docs/, sorted."""
    return sorted(str(p.relative_to(REPO_ROOT)) for p in DOCS_ROOT.rglob("*.md"))


def main() -> int:
    covered = covered_docs()
    for doc in all_docs():
        if doc not in covered:
            print(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
