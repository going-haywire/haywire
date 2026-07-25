"""Runtime access to the full baked ``docs/`` tree shipped inside haywire-core.

At build time ``scripts/bake_docs.py`` bakes every ``docs/*.md`` to pure
markdown (snippets expanded, links rewritten) and the wheel force-includes the
result at ``haywire/docs/`` (see haywire-core ``pyproject.toml``). In a dev /
editable checkout that packaged directory does not exist, so ``docs_root``
prefers the locally baked ``_baked_docs/`` (present after running the bake
script), and only falls back to the raw monorepo ``docs/`` when nothing has been
baked — see ``docs_root`` for the full resolution order.

Farmhand serves these files as version-matched authoring resources, one MCP
resource per file (``farmhand://docs/<relative-path>``) plus a generated
``_manifest`` index. See ``haywire_studio.farmhand.host``.
"""

from __future__ import annotations

import re
from pathlib import Path

import haywire

# Marker file used to recognise a valid docs root in the dev fallback. The
# node canon is a stable, always-present entry point into the tree.
_MARKER = Path("components") / "nodes" / "node-canon.md"


def docs_root() -> Path:
    """Return the root of the docs tree.

    Resolution order:

    1. The packaged ``haywire/docs/`` — present in a built wheel (the docs
       force-included from ``_baked_docs``). Fully baked.
    2. The dev-checkout ``_baked_docs/`` next to the package — present after a
       local ``scripts/bake_docs.py`` run in an editable install. Also baked, so
       a from-source studio serves the agent the same expanded/rewritten content
       an installed release would, not raw ``--8<--`` directives and dead links.
    3. The monorepo ``docs/`` — the raw source tree. Last resort for a fresh
       checkout that hasn't been baked yet.
    """
    pkg_dir = Path(haywire.__file__).resolve().parent
    for baked in (pkg_dir / "docs", pkg_dir / "_baked_docs"):
        if (baked / _MARKER).is_file():
            return baked
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docs"
        if (candidate / _MARKER).is_file():
            return candidate
    raise FileNotFoundError(
        "Docs tree not found: none of the packaged haywire/docs, the baked "
        "_baked_docs (run scripts/bake_docs.py), or a monorepo docs/ directory "
        "(with components/nodes/node-canon.md) exists."
    )


def list_docs() -> list[str]:
    """Every doc file, as POSIX paths relative to the docs root, sorted."""
    root = docs_root()
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*.md"))


def read_doc(rel_path: str) -> str:
    """Read one doc by its docs-root-relative path (e.g. ``guides/ports.md``).

    Rejects paths that escape the docs root (``..`` traversal, absolute paths).
    """
    root = docs_root()
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        raise FileNotFoundError(f"Doc path escapes the docs root: {rel_path!r}") from None
    if not target.is_file():
        raise FileNotFoundError(f"No doc at {rel_path!r}")
    return target.read_text(encoding="utf-8")


_H1_RE = re.compile(r"^#\s+(.*\S)\s*$")


def _first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        m = _H1_RE.match(line)
        if m:
            return m.group(1)
    return fallback


def doc_manifest() -> list[dict[str, str]]:
    """Index of the tree: one entry per file with its path and title.

    ``title`` is the file's first ``# H1`` heading, falling back to the file
    stem. Used to build the ``farmhand://docs/_manifest`` resource so the agent
    can see the whole corpus without reading every file.
    """
    root = docs_root()
    entries: list[dict[str, str]] = []
    for rel in list_docs():
        text = (root / rel).read_text(encoding="utf-8")
        entries.append({"path": rel, "title": _first_heading(text, Path(rel).stem)})
    return entries
