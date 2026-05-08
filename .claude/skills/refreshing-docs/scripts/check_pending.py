"""Emit pending docs whose own tree-hash has changed since the pending date.

Walks .docmeta/META.md for "Review pending" sections and compares the recorded
doc-hash to the current HEAD tree-hash for that doc. Prints one path per line
for every pending doc whose content has changed since it was marked pending.

Skill workflow consumes this output: for each path, the coverage subagent
re-classifies the doc (it may now be R, N, or still P).

Exit code is always 0; empty stdout means no pending doc has changed.
"""

from __future__ import annotations

import sys

from meta import META_PATH, current_tree_hash, parse_pending


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
