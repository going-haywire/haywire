"""Shared parsing primitives for .docmeta/META.md.

The META.md grammar is a flat list of `## <doc-path>` sections. Each section's
body is one of three shapes:

  Last reviewed: <date> (commit `<sha>`)
  | Source path | Tree-hash at review |
  |---|---|
  | <path> | <hash> |
  ...

  No review needed: <date>

  Review pending: <date> (doc-hash `<hash>`)

The four scripts in this skill all walk this structure, so the regexes and the
git helpers live here. If the META.md grammar evolves, this is the single file
to edit.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
META_PATH = REPO_ROOT / ".docmeta" / "META.md"
DOCS_ROOT = REPO_ROOT / "docs"

# Section heading: "## docs/foo/bar.md"
SECTION_RE = re.compile(r"^##\s+([\w./-]+\.md)\s*$", re.MULTILINE)

# Source-row inside a "Last reviewed" section: "| path | hash |"
ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([0-9a-f]{7,40})\s*\|\s*$", re.MULTILINE)

# Body marker for "Review pending: <date> (doc-hash `<hash>`)"
PENDING_RE = re.compile(
    r"^Review pending:\s*[\d-]+\s*\(doc-hash\s+`([0-9a-f]{7,40})`\)\s*$",
    re.MULTILINE,
)


def find_section(text: str, doc: str) -> tuple[int, int] | None:
    """Return (start, end) char offsets of the section for `doc`, or None."""
    sections = list(SECTION_RE.finditer(text))
    for i, match in enumerate(sections):
        if match.group(1) == doc:
            start = match.start()
            end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
            return start, end
    return None


def iter_sections(text: str) -> list[tuple[str, str]]:
    """Yield (doc, body) for every section in META.md."""
    sections = list(SECTION_RE.finditer(text))
    out: list[tuple[str, str]] = []
    for i, match in enumerate(sections):
        doc = match.group(1)
        start = match.end()
        end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        out.append((doc, text[start:end]))
    return out


def parse_source_rows(text: str) -> list[tuple[str, str, str]]:
    """Yield (doc, source, recorded_hash) for every source-table row."""
    rows: list[tuple[str, str, str]] = []
    for doc, body in iter_sections(text):
        for row_match in ROW_RE.finditer(body):
            source = row_match.group(1).strip()
            recorded = row_match.group(2).strip()
            if source.lower() in {"source path", "---"}:
                continue
            rows.append((doc, source, recorded))
    return rows


def parse_pending(text: str) -> list[tuple[str, str]]:
    """Yield (doc, recorded_doc_hash) for every 'Review pending' section."""
    rows: list[tuple[str, str]] = []
    for doc, body in iter_sections(text):
        match = PENDING_RE.search(body)
        if match is not None:
            rows.append((doc, match.group(1)))
    return rows


def covered_docs(text: str) -> set[str]:
    """Return doc paths that already have any META section."""
    return {match.group(1) for match in SECTION_RE.finditer(text)}


def current_tree_hash(path: str) -> str | None:
    """Return git rev-parse HEAD:<path>, or None if the path is not in HEAD."""
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


def head_tree_hash(source: str) -> str:
    """Return git rev-parse HEAD:<source>; raise if the path is not in HEAD."""
    result = subprocess.run(
        ["git", "rev-parse", f"HEAD:{source}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def head_short_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()
