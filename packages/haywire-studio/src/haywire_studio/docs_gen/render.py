from __future__ import annotations

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
