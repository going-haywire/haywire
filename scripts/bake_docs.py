"""Bake the full ``docs/`` tree to pure markdown for the haywire-core wheel.

Farmhand serves docs to the attached agent as MCP resources. Raw ``docs/`` is
unservable in three ways: ``--8<--`` snippet directives ship unexpanded,
relative ``.md`` cross-links don't resolve over MCP, and relative source-file
links (``../../../barn/...``) point at paths that don't exist in the wheel and
already 404 on the published site. This script fixes all three at build time:

1. **Snippet expansion** — every ``--8<-- "file:section"`` is expanded to the
   referenced source via ``pymdownx.snippets.SnippetPreprocessor`` (markdown →
   markdown, no HTML; ``mkdocs-material`` never enters the wheel).
2. **Cross-doc ``.md`` links** — rewritten to ``farmhand://docs/<path>`` URIs the
   agent passes straight to ``read_resource``.
3. **Source-file link targets** — rewritten to versioned GitHub blob/tree URLs
   ``https://github.com/going-haywire/haywire/blob/v{version}/<repo-path>``.

The result is written to a gitignored mirror under the haywire-core package dir
(``src/haywire/_baked_docs/``) that the wheel force-includes as ``haywire/docs``.

Run before ``uv build`` in the full workspace (barn packages installed so
snippet sources resolve):

    uv run python scripts/bake_docs.py [--version vX.Y.Z] [--out DIR]

``--version`` feeds the GitHub-URL rewrite; it defaults to the current
haywire-core version read from its pyproject.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Optional

import markdown
from pymdownx.snippets import SnippetExtension, SnippetPreprocessor

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"
DEFAULT_OUT = REPO_ROOT / "packages" / "haywire-core" / "src" / "haywire" / "_baked_docs"
CORE_PYPROJECT = REPO_ROOT / "packages" / "haywire-core" / "pyproject.toml"

GITHUB_BLOB_BASE = "https://github.com/going-haywire/haywire/blob"
GITHUB_TREE_BASE = "https://github.com/going-haywire/haywire/tree"

# A markdown inline link: [text](target) — target captured without surrounding
# angle brackets or a title. We only touch relative targets (Task 3 rules).
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")


def core_version() -> str:
    data = tomllib.loads(CORE_PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["version"]


def _normalise_version(version: str) -> str:
    """Accept ``0.0.26`` or ``v0.0.26``; always emit the ``v``-prefixed tag."""
    return version if version.startswith("v") else f"v{version}"


def build_snippet_preprocessor() -> SnippetPreprocessor:
    """A SnippetPreprocessor pinned to the resolved repo root.

    ``mkdocs.yml`` uses ``base_path: ['.']`` because MkDocs runs from the repo
    root. This script must not assume its cwd, so we pin an absolute path.
    ``check_paths=True`` makes a moved snippet source fail loudly
    (``SnippetMissingError``) instead of silently baking a dead directive.
    """
    md = markdown.Markdown(
        extensions=[
            SnippetExtension(
                base_path=[str(REPO_ROOT)],
                check_paths=True,
                dedent_subsections=True,
            )
        ]
    )
    for pp in md.preprocessors:
        if isinstance(pp, SnippetPreprocessor):
            return pp
    raise RuntimeError("SnippetPreprocessor not found on the Markdown instance")


def _rewrite_link_target(target: str, doc_path: Path, version_tag: str) -> str:
    """Rewrite one relative link target per the Task 3 rules.

    ``doc_path`` is the source doc's path relative to ``DOCS_ROOT`` (used to
    resolve relative ``.md`` links against the doc's own location). Absolute
    ``http(s)`` links and non-relative targets are returned untouched.
    """
    # External and already-rewritten links: leave alone.
    if target.startswith(("http://", "https://", "farmhand://", "#", "mailto:")):
        return target

    raw_target, _, anchor = target.partition("#")
    if not raw_target:
        # Pure in-page anchor (#section) — untouched.
        return target
    anchor = f"#{anchor}" if anchor else ""

    doc_dir = (DOCS_ROOT / doc_path).parent
    resolved = (doc_dir / raw_target).resolve()

    # Cross-doc .md link that resolves within docs/ → farmhand://docs/<rel>.
    if raw_target.endswith(".md"):
        try:
            rel = resolved.relative_to(DOCS_ROOT.resolve())
        except ValueError:
            print(f"  WARN: {doc_path}: .md link escapes docs/ — left as-is: {target}")
            return target
        return f"farmhand://docs/{rel.as_posix()}{anchor}"

    # Source-file / directory link into the repo → versioned GitHub URL.
    try:
        rel = resolved.relative_to(REPO_ROOT.resolve())
    except ValueError:
        print(f"  WARN: {doc_path}: link target not under repo root — left as-is: {target}")
        return target

    if not resolved.exists():
        print(f"  WARN: {doc_path}: link target does not exist — left as-is: {target}")
        return target

    base = GITHUB_TREE_BASE if resolved.is_dir() else GITHUB_BLOB_BASE
    return f"{base}/{version_tag}/{rel.as_posix()}{anchor}"


def rewrite_links(text: str, doc_path: Path, version_tag: str) -> str:
    def _sub(m: re.Match[str]) -> str:
        link_text, target = m.group(1), m.group(2)
        return f"[{link_text}]({_rewrite_link_target(target, doc_path, version_tag)})"

    return _LINK_RE.sub(_sub, text)


def bake_file(src: Path, preprocessor: SnippetPreprocessor, doc_path: Path, version_tag: str) -> str:
    lines = src.read_text(encoding="utf-8").splitlines()
    expanded = preprocessor.run(list(lines))
    text = "\n".join(expanded)
    if not text.endswith("\n"):
        text += "\n"
    return rewrite_links(text, doc_path, version_tag)


def bake(out_dir: Path, version: str) -> int:
    version_tag = _normalise_version(version)
    preprocessor = build_snippet_preprocessor()

    # Idempotent: clear and rewrite the whole mirror.
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    md_files = sorted(DOCS_ROOT.rglob("*.md"))
    for src in md_files:
        rel = src.relative_to(DOCS_ROOT)
        baked = bake_file(src, preprocessor, rel, version_tag)
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(baked, encoding="utf-8")

    print(f"Baked {len(md_files)} docs → {out_dir} (version {version_tag})")
    return len(md_files)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        default=None,
        help="Version tag for GitHub URLs (e.g. v0.0.26). Defaults to haywire-core's pyproject version.",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help=f"Output directory for the baked mirror (default: {DEFAULT_OUT}).",
    )
    args = parser.parse_args(argv)

    version = args.version or core_version()
    bake(Path(args.out), version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
