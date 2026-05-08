"""Emit one JSON line per stale row in .docmeta/META.md.

Reads .docmeta/META.md, parses the per-doc sections and source tables, and
prints one newline-delimited JSON object for every (doc, source) pair whose
recorded tree-hash no longer matches `git rev-parse HEAD:<source>`.

Output schema:
    {"doc": "docs/x.md", "source": "barn/y.py",
     "recorded_hash": "abc...", "current_hash": "def..."}

If the source file has been removed from HEAD, "current_hash" is null — the
skill recognises this as a removal.

Exit code is always 0 unless META.md is missing; empty stdout means nothing is
stale.
"""

from __future__ import annotations

import json
import sys

from meta import META_PATH, current_tree_hash, parse_source_rows


def main() -> int:
    if not META_PATH.exists():
        print(f"error: {META_PATH} not found", file=sys.stderr)
        return 1
    text = META_PATH.read_text()
    for doc, source, recorded in parse_source_rows(text):
        current = current_tree_hash(source)
        if current is None or current != recorded:
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
