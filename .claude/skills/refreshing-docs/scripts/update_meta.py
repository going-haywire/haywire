"""Rewrite a row or section in .docmeta/META.md.

Modes:

    update_meta.py <doc_path> <source_path>
        Bump the recorded hash for a single (doc, source) row to HEAD.
        Also bumps the doc's "Last reviewed" header. Idempotent: if the
        recorded hash already matches HEAD, only the header is touched.

    update_meta.py --create <doc_path> <source_path> [<source_path> ...]
        Append a new section for <doc_path> with one row per source path,
        each at HEAD's tree-hash. Errors if the section already exists,
        unless --replace-pending is passed and the existing section is
        a "Review pending" placeholder.

    update_meta.py --no-review <doc_path>
        Append a "No review needed" section for <doc_path>. Used for docs
        with no source-code dependencies. Same --replace-pending behaviour
        as --create.

    update_meta.py --pending <doc_path>
        Append (or refresh) a "Review pending" section for <doc_path>.
        Records the doc's own tree-hash so check_pending can detect when
        the doc itself has changed and may now be ready for re-classification.
        Idempotent on an existing pending section.

All paths are repo-relative. Source paths must exist at HEAD.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date

from meta import META_PATH, find_section, head_short_sha, head_tree_hash


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


def render_no_review_section(doc: str) -> str:
    today = date.today().isoformat()
    return "\n".join([f"## {doc}", "", f"No review needed: {today}", ""])


def render_pending_section(doc: str, doc_hash: str) -> str:
    today = date.today().isoformat()
    return "\n".join([f"## {doc}", "", f"Review pending: {today} (doc-hash `{doc_hash}`)", ""])


def update_row(text: str, doc: str, source: str, new_hash: str) -> str:
    """Update the hash for one row. Bumps the doc's Last-reviewed header."""
    section = find_section(text, doc)
    if section is None:
        raise SystemExit(f"error: no section for {doc} in META.md (use --create first)")
    start, end = section
    body = text[start:end]

    row_re = re.compile(
        rf"^\|\s*{re.escape(source)}\s*\|\s*[0-9a-f]{{7,40}}\s*\|\s*$",
        re.MULTILINE,
    )
    new_row = f"| {source} | {new_hash} |"
    new_body, n = row_re.subn(new_row, body, count=1)
    if n == 0:
        raise SystemExit(f"error: no row for source `{source}` under {doc}")

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


def _existing_section_kind(text: str, doc: str) -> str | None:
    """Return 'pending', 'no-review', 'tracked', or None for the doc's section."""
    section = find_section(text, doc)
    if section is None:
        return None
    body = text[section[0] : section[1]]
    if "Review pending:" in body:
        return "pending"
    if "No review needed:" in body:
        return "no-review"
    if "Last reviewed:" in body:
        return "tracked"
    return "unknown"


def _replace_section(text: str, doc: str, new_section: str) -> str:
    section = find_section(text, doc)
    assert section is not None
    start, end = section
    return text[:start] + new_section + "\n" + text[end:]


def _append_section(text: str, new_section: str) -> str:
    sep = "\n" if text.endswith("\n") else "\n\n"
    return text + sep + new_section + "\n"


def create_section(text: str, doc: str, sources: list[str], replace_pending: bool) -> str:
    kind = _existing_section_kind(text, doc)
    if kind is not None:
        if kind == "pending" and replace_pending:
            new_section = render_section(doc, [(src, head_tree_hash(src)) for src in sources])
            return _replace_section(text, doc, new_section)
        raise SystemExit(
            f"error: section for {doc} already exists ({kind}); "
            f"{'pass --replace-pending to overwrite a pending section, ' if kind == 'pending' else ''}"
            "drop --create to update rows"
        )
    new_section = render_section(doc, [(src, head_tree_hash(src)) for src in sources])
    return _append_section(text, new_section)


def create_no_review_section(text: str, doc: str, replace_pending: bool) -> str:
    kind = _existing_section_kind(text, doc)
    if kind is not None:
        if kind == "pending" and replace_pending:
            return _replace_section(text, doc, render_no_review_section(doc))
        raise SystemExit(
            f"error: section for {doc} already exists ({kind})"
            + (" — pass --replace-pending to overwrite a pending section" if kind == "pending" else "")
        )
    return _append_section(text, render_no_review_section(doc))


def upsert_pending_section(text: str, doc: str) -> str:
    """Create OR refresh a pending section. Idempotent on the doc."""
    new_section = render_pending_section(doc, head_tree_hash(doc))
    kind = _existing_section_kind(text, doc)
    if kind is None:
        return _append_section(text, new_section)
    if kind != "pending":
        raise SystemExit(
            f"error: section for {doc} exists ({kind}); "
            "use --create or --no-review to change its state, not --pending"
        )
    return _replace_section(text, doc, new_section)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--create", action="store_true", help="create a new tracked section with sources")
    mode.add_argument("--no-review", action="store_true", help="create a 'No review needed' section")
    mode.add_argument("--pending", action="store_true", help="create or refresh a 'Review pending' section")
    parser.add_argument(
        "--replace-pending",
        action="store_true",
        help="when used with --create or --no-review, overwrite an existing pending section",
    )
    parser.add_argument("doc")
    parser.add_argument("sources", nargs="*")
    args = parser.parse_args()

    if not META_PATH.exists():
        META_PATH.parent.mkdir(parents=True, exist_ok=True)
        META_PATH.write_text(
            "# Documentation Freshness Ledger\n\n"
            "Tracks tree-hashes of source files cited by each doc page. "
            "The [refreshing-docs](../.claude/skills/refreshing-docs/SKILL.md) "
            "skill compares these against HEAD and edits stale docs.\n\n"
        )

    if args.replace_pending and not (args.create or args.no_review):
        raise SystemExit("error: --replace-pending only applies with --create or --no-review")

    text = META_PATH.read_text()

    if args.no_review:
        if args.sources:
            raise SystemExit("error: --no-review takes no source paths")
        new_text = create_no_review_section(text, args.doc, args.replace_pending)
    elif args.pending:
        if args.sources:
            raise SystemExit("error: --pending takes no source paths")
        new_text = upsert_pending_section(text, args.doc)
    elif args.create:
        if not args.sources:
            raise SystemExit("error: --create requires at least one source path")
        new_text = create_section(text, args.doc, args.sources, args.replace_pending)
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
