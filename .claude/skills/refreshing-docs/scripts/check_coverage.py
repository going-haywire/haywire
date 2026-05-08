"""Report doc pages under docs/ that have no META section.

Walks docs/ for *.md files, compares against sections declared in
.docmeta/META.md, and prints one path per line for every doc page that is NOT
covered (no "Last reviewed", "No review needed", or "Review pending" section).

Exit code is always 0; empty stdout means coverage is complete.
"""

from __future__ import annotations

import sys

from meta import DOCS_ROOT, META_PATH, REPO_ROOT, covered_docs


def all_docs() -> list[str]:
    return sorted(str(p.relative_to(REPO_ROOT)) for p in DOCS_ROOT.rglob("*.md"))


def main() -> int:
    text = META_PATH.read_text() if META_PATH.exists() else ""
    covered = covered_docs(text)
    for doc in all_docs():
        if doc not in covered:
            print(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
