from __future__ import annotations

import re

from haywire_studio.docs_gen.model import ComponentRecord, LibraryDoc

_KIND_ORDER = [
    "node",
    "type",
    "adapter",
    "widget",
    "setting",
    "farmhand",
    "state",
    "panel",
    "editor",
    "skin",
    "theme",
]

_MARKER_RE = re.compile(
    r"<!-- marketstall:share-url:start -->.*?<!-- marketstall:share-url:end -->",
    re.DOTALL,
)
_PLACEHOLDER = (
    "<!-- marketstall:share-url:start -->\n"
    "*Subscribe URL not yet published — run `haywire share --save`.*\n"
    "<!-- marketstall:share-url:end -->"
)


def doc_filename(registry_key: str) -> str:
    return registry_key.replace(":", ".") + ".md"


def _visible(doc: LibraryDoc) -> list[ComponentRecord]:
    return [c for c in doc.components if not c.hidden]


def render_quickref(doc: LibraryDoc) -> str:
    """Agent steering index: registry_key — label — description, grouped by kind."""
    lines = [f"# {doc.library_id} — component index (v{doc.version})", ""]
    by_kind: dict[str, list[ComponentRecord]] = {}
    for c in _visible(doc):
        by_kind.setdefault(c.kind, []).append(c)
    for kind in _KIND_ORDER:
        recs = by_kind.get(kind)
        if not recs:
            continue
        lines.append(f"## {kind}")
        for c in sorted(recs, key=lambda r: r.registry_key):
            tags = f"  _tags: {', '.join(c.search_tags)}_" if c.search_tags else ""
            dep = "  **DEPRECATED**" if c.deprecation else ""
            lines.append(f"- `{c.registry_key}` — {c.label} — {c.description}{tags}{dep}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_overview(doc: LibraryDoc) -> str:
    """Human catalog: labels + intent, nodes grouped by menu category."""
    lines = [f"# {doc.label}", "", doc.description, ""]
    nodes = [c for c in _visible(doc) if c.kind == "node"]
    if nodes:
        lines.append("## Nodes")
        by_cat: dict[str, list[ComponentRecord]] = {}
        for n in nodes:
            cat = (n.menu.split("/")[0] if n.menu else "misc").title()
            by_cat.setdefault(cat, []).append(n)
        for cat in sorted(by_cat):
            lines.append(f"### {cat}")
            for n in sorted(by_cat[cat], key=lambda r: r.label):
                lines.append(f"- **{n.label}** — {n.description}")
            lines.append("")
    for kind in ("type", "widget", "adapter", "setting", "farmhand"):
        recs = [c for c in _visible(doc) if c.kind == kind]
        if not recs:
            continue
        lines.append(f"## {kind.title()}s")
        for c in sorted(recs, key=lambda r: r.label):
            lines.append(f"- **{c.label}** — {c.description}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_component(rec: ComponentRecord) -> str:
    """Deep doc for one component: ports/settings tables, kind-specific details, docstring."""
    lines = [f"# {rec.label}", "", f"`{rec.registry_key}` · kind: {rec.kind}", ""]
    if rec.description:
        lines += [rec.description, ""]
    if rec.deprecation:
        lines += [f"> **Deprecated:** {rec.deprecation}", ""]
    if rec.kind == "node" and rec.ports:
        lines += [
            "## Ports",
            "",
            "| id | direction | type | description |",
            "|---|---|---|---|",
        ]
        for p in rec.ports:
            lines.append(f"| {p.id} | {p.direction} | {p.data_type or ''} | {p.description} |")
        lines.append("")
    documented_settings = [s for s in rec.settings if s.bag != "props"]
    if rec.kind == "node" and documented_settings:
        lines += [
            "## Settings",
            "",
            "| name | bag | default | description |",
            "|---|---|---|---|",
        ]
        for s in documented_settings:
            lines.append(f"| {s.name} | {s.bag} | {s.default!r} | {s.description} |")
        lines.append("")
    if rec.extra:
        lines += ["## Details", ""]
        for k, v in rec.extra.items():
            if v not in (None, "", [], {}):
                lines.append(f"- **{k}**: `{v}`")
        lines.append("")
    if rec.docstring:
        lines += ["## Notes", "", rec.docstring, ""]
    return "\n".join(lines).rstrip() + "\n"


def coverage_report(doc: LibraryDoc) -> list[str]:
    """One line per gap the author should fill. Never fabricates content."""
    report: list[str] = []
    for c in doc.components:
        gaps = []
        if not c.description:
            gaps.append("no description")
        if not c.docstring:
            gaps.append("no docstring")
        if c.kind == "node" and not c.ports:
            gaps.append("no ports (instantiation may have failed)")
        if gaps:
            report.append(f"{c.registry_key}: {', '.join(gaps)}")
    return report


def _catalog_body(doc: LibraryDoc) -> str:
    """The README catalog is the OVERVIEW catalog (labels), minus its H1 title."""
    body = render_overview(doc)
    return body.split("\n", 1)[1].lstrip("\n") if "\n" in body else body


def render_readme(doc: LibraryDoc, notes: str, existing_readme: str | None) -> str:
    """README with NOTES prefix and preserved marker block.

    The block between `<!-- marketstall:share-url:start -->` and
    `<!-- marketstall:share-url:end -->` is owned by `haywire share --save`
    and must be preserved verbatim. If no existing README or no marker found,
    insert a placeholder marker.
    """
    marker = _PLACEHOLDER
    if existing_readme:
        found = _MARKER_RE.search(existing_readme)
        if found:
            marker = found.group(0)
    parts = [f"# {doc.label}", ""]
    if notes.strip():
        parts += [notes.strip(), ""]
    parts += [marker, "", _catalog_body(doc)]
    return "\n".join(parts).rstrip() + "\n"
