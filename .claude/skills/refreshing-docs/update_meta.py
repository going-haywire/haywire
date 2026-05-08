"""Rewrite a row in .docmeta/META.md with the current HEAD tree-hash.

Modes:

    update_meta.py <doc_path> <source_path>
        Bump the recorded hash for a single (doc, source) row to HEAD.
        Also bumps the doc's "Last reviewed" header. Idempotent: if the
        recorded hash already matches HEAD, only the header is touched.

    update_meta.py --create <doc_path> <source_path> [<source_path> ...]
        Append a new section for <doc_path> with one row per source path,
        each at HEAD's tree-hash. Errors if the section already exists.

    update_meta.py --no-review <doc_path>
        Append a "No review needed" section for <doc_path>. Used for docs
        with no source-code dependencies (glossary, design guide, perspective
        landing pages). The freshness check skips these. Errors if the
        section already exists.

    update_meta.py --pending <doc_path>
        Append (or refresh) a "Review pending" section for <doc_path>. Used
        for placeholder / stub / incomplete docs that don't yet have enough
        content to classify. Records the doc's own tree-hash so check_pending
        can detect when the doc itself has changed and may now be ready for
        re-classification. Idempotent: running on an existing pending section
        just refreshes the date and doc-hash.

All paths are repo-relative. Source paths must exist at HEAD.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
META_PATH = REPO_ROOT / ".docmeta" / "META.md"


def head_tree_hash(source: str) -> str:
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


_SECTION_RE = re.compile(r"^##\s+(\S+\.md)\s*$", re.MULTILINE)


def find_section(text: str, doc: str) -> tuple[int, int] | None:
    """Return (start, end) char offsets of the section for `doc`, or None."""
    sections = list(_SECTION_RE.finditer(text))
    for i, match in enumerate(sections):
        if match.group(1) == doc:
            start = match.start()
            end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
            return start, end
    return None


def render_section(doc: str, sources_with_hashes: list[tuple[str, str]]) -> str:
    today = date.today().isoformat()
    sha = head_short_sha()
    lines = [
        f"## {doc}",
        "",
        f"Last reviewed: {today} (commit `{sha}`)",
        "",
        "| Source path | Tree-hash at review |",
        "|---|---|",
    ]
    for src, h in sources_with_hashes:
        lines.append(f"| {src} | {h} |")
    lines.append("")
    return "\n".join(lines)


def update_row(text: str, doc: str, source: str, new_hash: str) -> str:
    """Update the hash for one row. Bumps the doc's Last-reviewed header."""
    section = find_section(text, doc)
    if section is None:
        raise SystemExit(f"error: no section for {doc} in META.md (use --create first)")
    start, end = section
    body = text[start:end]

    # Bump the row's hash.
    row_re = re.compile(
        rf"^\|\s*{re.escape(source)}\s*\|\s*[0-9a-f]{{7,40}}\s*\|\s*$",
        re.MULTILINE,
    )
    new_row = f"| {source} | {new_hash} |"
    new_body, n = row_re.subn(new_row, body, count=1)
    if n == 0:
        raise SystemExit(f"error: no row for source `{source}` under {doc}")

    # Bump the Last-reviewed line.
    today = date.today().isoformat()
    sha = head_short_sha()
    new_body = re.sub(
        r"^Last reviewed:.*$",
        f"Last reviewed: {today} (commit `{sha}`)",
        new_body,
        count=1,
        flags=re.MULTILINE,
    )

    return text[:start] + new_body + text[end:]


def create_section(text: str, doc: str, sources: list[str]) -> str:
    if find_section(text, doc) is not None:
        raise SystemExit(f"error: section for {doc} already exists; drop --create to update rows")
    sources_with_hashes = [(src, head_tree_hash(src)) for src in sources]
    new_section = render_section(doc, sources_with_hashes)
    # Append at end with a separator newline.
    sep = "\n" if text.endswith("\n") else "\n\n"
    return text + sep + new_section + "\n"


def render_no_review_section(doc: str) -> str:
    today = date.today().isoformat()
    return "\n".join([f"## {doc}", "", f"No review needed: {today}", ""])


def create_no_review_section(text: str, doc: str) -> str:
    if find_section(text, doc) is not None:
        raise SystemExit(f"error: section for {doc} already exists")
    new_section = render_no_review_section(doc)
    sep = "\n" if text.endswith("\n") else "\n\n"
    return text + sep + new_section + "\n"


def render_pending_section(doc: str, doc_hash: str) -> str:
    today = date.today().isoformat()
    return "\n".join([f"## {doc}", "", f"Review pending: {today} (doc-hash `{doc_hash}`)", ""])


def upsert_pending_section(text: str, doc: str) -> str:
    """Create OR refresh a pending section. Idempotent on the doc."""
    doc_hash = head_tree_hash(doc)
    new_section = render_pending_section(doc, doc_hash)
    section = find_section(text, doc)
    if section is None:
        sep = "\n" if text.endswith("\n") else "\n\n"
        return text + sep + new_section + "\n"
    # Section exists — must be a pending section to be refreshed.
    start, end = section
    body = text[start:end]
    if "Review pending:" not in body:
        raise SystemExit(
            f"error: section for {doc} exists but is not 'Review pending'; "
            "use --create or --no-review to change its state"
        )
    return text[:start] + new_section + "\n" + text[end:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--create", action="store_true", help="create a new section with sources")
    mode.add_argument(
        "--no-review",
        action="store_true",
        help="create a 'No review needed' section (no sources)",
    )
    mode.add_argument(
        "--pending",
        action="store_true",
        help="create or refresh a 'Review pending' section (no sources)",
    )
    parser.add_argument("doc")
    parser.add_argument("sources", nargs="*")
    args = parser.parse_args()

    if not META_PATH.exists():
        # Bootstrap: create an empty META so the first --create / --no-review has somewhere to write.
        META_PATH.parent.mkdir(parents=True, exist_ok=True)
        META_PATH.write_text(
            "# Documentation Freshness Ledger\n\n"
            "Tracks tree-hashes of source files cited by each doc page. "
            "The [refreshing-docs](../.claude/skills/refreshing-docs/SKILL.md) "
            "skill compares these against HEAD and edits stale docs.\n\n"
        )

    text = META_PATH.read_text()

    if args.no_review:
        if args.sources:
            raise SystemExit("error: --no-review takes no source paths")
        new_text = create_no_review_section(text, args.doc)
    elif args.pending:
        if args.sources:
            raise SystemExit("error: --pending takes no source paths")
        new_text = upsert_pending_section(text, args.doc)
    elif args.create:
        if not args.sources:
            raise SystemExit("error: --create requires at least one source path")
        new_text = create_section(text, args.doc, args.sources)
    else:
        if len(args.sources) != 1:
            raise SystemExit("error: update mode takes exactly one source (use --create for many)")
        source = args.sources[0]
        new_hash = head_tree_hash(source)
        new_text = update_row(text, args.doc, source, new_hash)

    META_PATH.write_text(new_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
