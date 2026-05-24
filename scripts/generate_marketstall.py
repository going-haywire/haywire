"""Generate the official two-tier haywire feed (spec §11).

Output layout written under ``--out-dir``:

    <out-dir>/
    ├── marketplace.toml        # aggregator with one [[stalls]] per library
    └── stalls/
        ├── haybale-core.toml   # marketstall with exactly one [[haybales]]
        ├── haybale-studio.toml
        └── ...                 # one per publish_order entry

Reads [tool.haywire.release] (publish_order) and [tool.haywire.marketstall]
(source_url, docs_branch, defaults, feed_base_url) from the workspace
root pyproject, walks each publishable package's pyproject + __init__.py,
and emits the two-tier layout. Source = "pypi" for every entry. Deployed
by the publish CI workflow (T4) to GitHub Pages.

Used by:
  - .github/workflows/publish.yml (job 4 — deploy marketstall)
  - manual invocation: uv run python scripts/generate_marketstall.py
"""

from __future__ import annotations

import argparse
import ast
import sys
import tomllib  # type: ignore[import-not-found]  # stdlib 3.11+; mypy config pins 3.10
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LibraryMetadata:
    """Subset of @library(...) decorator fields we use in the marketstall.

    None means "not authored on the decorator" — caller should fall back
    to pyproject description or [tool.haywire.marketstall] defaults.
    """

    label: str | None
    description: str | None
    author: str | None
    tags: list[str] | None


def extract_library_metadata(init_py: Path) -> LibraryMetadata:
    """Parse an __init__.py for an @library(...) decorator and lift label/description/author/tags.

    Returns all-None if the file doesn't exist or has no @library decorator.
    Framework packages without a Library class (e.g., haywire-core, haywire-studio)
    have no decorator and are expected to fall through to pyproject + config defaults.
    """
    if not init_py.is_file():
        return LibraryMetadata(label=None, description=None, author=None, tags=None)
    tree = ast.parse(init_py.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if not (isinstance(func, ast.Name) and func.id == "library"):
                continue
            kwargs = {kw.arg: kw.value for kw in dec.keywords if kw.arg is not None}
            return LibraryMetadata(
                label=_as_str(kwargs.get("label")),
                description=_as_str(kwargs.get("description")),
                author=_as_str(kwargs.get("author")),
                tags=_as_str_list(kwargs.get("tags")),
            )
    return LibraryMetadata(label=None, description=None, author=None, tags=None)


def _as_str(node: ast.expr | None) -> str | None:
    """Return the string literal value of an AST node, or None for any non-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _as_str_list(node: ast.expr | None) -> list[str] | None:
    """Return a list of string literals from an AST list, or None for any non-list-of-strings."""
    if not isinstance(node, ast.List):
        return None
    out: list[str] = []
    for elt in node.elts:
        s = _as_str(elt)
        if s is None:
            return None
        out.append(s)
    return out


@dataclass(frozen=True)
class MarketstallConfig:
    """Repo-level config consumed by build_entry. Read from [tool.haywire.marketstall].

    ``feed_base_url`` (spec §11) is the deployed-feed root; the generator
    composes per-stall URLs as ``{feed_base_url}/stalls/{dist-name}.toml``.
    """

    source_url: str
    docs_branch: str
    default_author: str
    default_tags: list[str]
    feed_base_url: str


def read_marketstall_config(root_pyproject: Path) -> MarketstallConfig:
    data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    block = data["tool"]["haywire"]["marketstall"]
    return MarketstallConfig(
        source_url=block["source_url"],
        docs_branch=block.get("docs_branch", "main"),
        default_author=block.get("default_author", ""),
        default_tags=list(block.get("default_tags", [])),
        feed_base_url=block.get("feed_base_url", "").rstrip("/"),
    )


def build_entry(
    pyproject_path: Path,
    init_py: Path,
    config: MarketstallConfig,
    subdirectory: str,
    module_name: str,
) -> dict[str, object]:
    """Build one [[packages]] dict for a package.

    `subdirectory` is the package directory relative to the repo root (e.g. "barn/haybale-foo").
    `module_name` is the importable module dir name (e.g. "haybale_foo") inside that subdirectory.
    """
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject["project"]
    name = project["name"]
    version = project["version"]
    pyproject_description = project.get("description", "")
    pyproject_deps: list[str] = list(project.get("dependencies", []))

    meta = extract_library_metadata(init_py)

    sibling_haybale = _filter_haybale_siblings(pyproject_deps)
    docs_url = (
        f"https://raw.githubusercontent.com/{_strip_github_prefix(config.source_url)}/"
        f"{config.docs_branch}/{subdirectory}/{module_name}/"
    )

    return {
        "name": name,
        "label": meta.label or name,
        "min_version": version,
        "description": meta.description or pyproject_description,
        "author": meta.author or config.default_author,
        "source": "pypi",
        "install_spec": name,
        "tags": meta.tags if meta.tags is not None else list(config.default_tags),
        "dependencies": sibling_haybale,
        "source_url": config.source_url,
        "docs_url": docs_url,
    }


def _filter_haybale_siblings(deps: list[str]) -> list[str]:
    """Return the bare haybale-* distribution names from a list of PEP 508 dep strings.

    Marketstall `dependencies` is sibling haybale-* only (per spec §7) — framework
    haywire-* packages and external deps are excluded.
    """
    out: list[str] = []
    for dep in deps:
        # Strip any version/marker suffix: "haybale-foo~=0.0.1" → "haybale-foo".
        name = (
            dep.split("~")[0].split(">")[0].split("<")[0].split("=")[0].split(";")[0].split("[")[0].strip()
        )
        if name.startswith("haybale-"):
            out.append(name)
    return out


def _strip_github_prefix(url: str) -> str:
    """Turn 'https://github.com/user/repo' into 'user/repo'. Used to build raw URLs."""
    return url.rstrip("/").removeprefix("https://github.com/")


# Order of fields in every [[haybales]] entry. Matches the new spec vocabulary
# (Haybale._TOML_FIELDS) used by the runtime parsers.
_ENTRY_FIELD_ORDER: tuple[str, ...] = (
    "name",
    "label",
    "min_version",
    "description",
    "author",
    "source",
    "install_spec",
    "tags",
    "dependencies",
    "source_url",
    "docs_url",
)

_MARKETPLACE_HEADER = """\
# Official haywire marketplace — aggregator (spec §11)
# Generated by scripts/generate_marketstall.py on every release tag.
# Do not edit by hand — re-run the generator instead.
#
# Subscribers fetch this file from GitHub Pages:
#   https://maybites.github.io/haywire/marketplace.toml
#
# Per-library marketstalls live under stalls/<dist-name>.toml; a consumer who
# wants only one library can subscribe to that stall URL directly.
"""

_STALL_HEADER = """\
# Marketstall for {name} (auto-generated; spec §2)
# Source of truth: the package's pyproject.toml in the haywire monorepo.
# Re-generated on every release tag by scripts/generate_marketstall.py.
"""


def emit_stall_toml(entry: dict[str, object]) -> str:
    """Emit a marketstall TOML with one ``[[haybales]]`` section for ``entry``.

    Field order follows the runtime ``Haybale._TOML_FIELDS`` definition.
    """
    parts: list[str] = [_STALL_HEADER.format(name=entry.get("name", ""))]
    parts.append("")
    parts.append("[[haybales]]")
    for field in _ENTRY_FIELD_ORDER:
        if field not in entry:
            continue
        parts.append(f"{field} = {_format_value(entry[field])}")
    parts.append("")
    return "\n".join(parts)


def emit_marketplace_toml(stall_urls: list[str]) -> str:
    """Emit the aggregator marketplace TOML referencing one ``[[stalls]]`` per URL."""
    parts: list[str] = [_MARKETPLACE_HEADER]
    for url in stall_urls:
        parts.append("")
        parts.append("[[stalls]]")
        parts.append(f"url = {_format_string(url)}")
        parts.append("ignores = []")
        parts.append("doubles = []")
        parts.append("blocked = []")
    parts.append("")
    return "\n".join(parts)


def _format_value(value: object) -> str:
    if isinstance(value, str):
        return _format_string(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[" + ", ".join(_format_value(v) for v in value) + "]"
    raise TypeError(f"unsupported marketstall value type: {type(value).__name__}")


def _format_string(value: str) -> str:
    """Format a string as a TOML basic string.

    Escapes backslash, double quote, and the control characters TOML basic
    strings forbid (newline, carriage return, tab). Other control characters
    are rare in practice and would fail TOML parsing — we accept that and
    don't pre-validate.
    """
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


@dataclass(frozen=True)
class GenerateResult:
    """Output of :func:`generate` — one marketplace + one stall per library."""

    marketplace_toml: str
    stalls: list[tuple[str, str]]  # [(dist-name, stall-toml), ...] in publish order


def generate(root_pyproject: Path, *, feed_base_url: str | None = None) -> GenerateResult:
    """Build the two-tier official feed (spec §11) for the workspace.

    Reads:
      - [tool.haywire.release] publish_order (consumed via bump_version)
      - [tool.haywire.marketstall] (defaults; ``feed_base_url`` may also be
        passed as a CLI override via the keyword argument)
      - each publishable package's pyproject + __init__.py

    Returns a :class:`GenerateResult` carrying:
      - ``marketplace_toml``: aggregator TOML with one ``[[stalls]]`` per
        library, URL = ``{feed_base_url}/stalls/{dist-name}.toml``.
      - ``stalls``: list of ``(dist-name, stall-toml)`` pairs, one per library
        in publish order. Each stall contains exactly one ``[[haybales]]``.
    """
    # Reuse bump_version's package-location logic — same workspace-globs scan.
    from scripts.bump_version import locate_packages, read_release_config

    release = read_release_config(root_pyproject)
    located = locate_packages(root_pyproject, release)
    config = read_marketstall_config(root_pyproject)
    root_dir = root_pyproject.parent

    base_url = (feed_base_url or config.feed_base_url).rstrip("/")
    if not base_url:
        raise ValueError(
            "feed_base_url is required: set [tool.haywire.marketstall].feed_base_url "
            "in pyproject.toml or pass --feed-base-url on the command line."
        )

    stalls: list[tuple[str, str]] = []
    stall_urls: list[str] = []
    for pkg_name in release.publish_order:
        pyproject_path = located[pkg_name]
        pkg_dir = pyproject_path.parent
        module_path = _resolve_module_path(pyproject_path, pkg_dir)
        init_py = pkg_dir / module_path / "__init__.py"
        # For docs_url we want the module dir name without the src/ prefix:
        module_name = Path(module_path).name
        subdirectory = pkg_dir.relative_to(root_dir).as_posix()
        entry = build_entry(
            pyproject_path=pyproject_path,
            init_py=init_py,
            config=config,
            subdirectory=subdirectory,
            module_name=module_name,
        )
        dist_name = str(entry["name"])
        stalls.append((dist_name, emit_stall_toml(entry)))
        stall_urls.append(f"{base_url}/stalls/{dist_name}.toml")

    return GenerateResult(
        marketplace_toml=emit_marketplace_toml(stall_urls),
        stalls=stalls,
    )


def _resolve_module_path(pyproject_path: Path, pkg_dir: Path) -> str:
    """Find the module path relative to pkg_dir.

    Priority:
      1. [tool.hatch.build.targets.wheel].packages — first entry. This is the
         authoritative source hatchling uses to find the module at build time,
         and it correctly handles both flat (`haybale_foo`) and src-layout
         (`src/haywire`) packages.
      2. [project.entry-points."haywire.libraries"] — first value before `:`.
         Returned as a bare name (no `src/` prefix) — only useful for flat
         layouts.
      3. The package directory name with hyphens converted to underscores.

    Returns a path string (may contain `/` for src-layouts).
    """
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    hatch_packages = (
        data.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("packages", [])
    )
    if hatch_packages:
        return hatch_packages[0]
    entry_points = data.get("project", {}).get("entry-points", {}).get("haywire.libraries", {})
    if entry_points:
        first_target = next(iter(entry_points.values()))
        return first_target.split(":")[0]
    return pkg_dir.name.replace("-", "_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_marketstall",
        description="Generate the official two-tier haywire feed (spec §11).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to the workspace root pyproject.toml (default: ./pyproject.toml).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory. Will contain marketplace.toml and stalls/<dist>.toml.",
    )
    parser.add_argument(
        "--feed-base-url",
        default=None,
        help=(
            "Override [tool.haywire.marketstall].feed_base_url — the deployed-feed "
            "root used to build per-stall subscription URLs."
        ),
    )
    args = parser.parse_args(argv)

    result = generate(args.root, feed_base_url=args.feed_base_url)

    out_dir: Path = args.out_dir
    stalls_dir = out_dir / "stalls"
    stalls_dir.mkdir(parents=True, exist_ok=True)

    marketplace_path = out_dir / "marketplace.toml"
    marketplace_path.write_text(result.marketplace_toml, encoding="utf-8")
    print(f"Wrote {marketplace_path}", file=sys.stderr)

    for dist_name, stall_body in result.stalls:
        stall_path = stalls_dir / f"{dist_name}.toml"
        stall_path.write_text(stall_body, encoding="utf-8")
        print(f"Wrote {stall_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    # When run as `python scripts/generate_marketstall.py`, the script's own
    # directory (not the repo root) is on sys.path, so `from scripts.bump_version
    # import ...` inside generate() fails. Prepend the repo root so the import
    # resolves. The `python -m scripts.generate_marketstall` form already works
    # because -m puts CWD on sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    sys.exit(main())
