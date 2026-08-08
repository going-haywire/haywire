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
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from haywire.core.marketstall.requirement import haywire_core_requirement
from haywire.core.marketstall.types import Haybale
from haywire.core.publishing.manifest.decorator_ast import read_decorator


@dataclass(frozen=True)
class MarketstallConfig:
    """Repo-level config consumed by build_entry. Read from [tool.haywire.marketstall].

    ``feed_base_url`` (spec §11) is the deployed-feed root; the generator
    composes per-stall URLs as ``{feed_base_url}/stalls/{dist-name}.toml``.
    ``marketplace`` is the explicit allowlist of package names that appear in
    the official feed. Source (pypi vs git) is derived by lookup against the
    release config's pip_publish_order / git_publish_order.

    ``default_author`` is deliberately absent: authors now come from PEP 621
    ``[project] authors``, and a repo-wide default would attribute every
    library to the same name. An unauthored field is reported absent instead.
    A leftover key in a deployed pyproject is ignored, not an error.
    """

    source_url: str
    docs_branch: str
    default_tags: list[str]
    feed_base_url: str
    marketplace: list[str]


def read_marketstall_config(root_pyproject: Path) -> MarketstallConfig:
    data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    block = data["tool"]["haywire"]["marketstall"]
    return MarketstallConfig(
        source_url=block["source_url"],
        docs_branch=block.get("docs_branch", "main"),
        default_tags=list(block.get("default_tags", [])),
        feed_base_url=block.get("feed_base_url", "").rstrip("/"),
        marketplace=list(block.get("marketplace", [])),
    )


def build_entry(
    pyproject_path: Path,
    init_py: Path,
    config: MarketstallConfig,
    subdirectory: str,
    module_name: str,
    source: str = "pypi",
) -> dict[str, object]:
    """Build one [[packages]] dict for a package.

    `subdirectory` is the package directory relative to the repo root (e.g. "barn/haybale-foo").
    `module_name` is the importable module dir name (e.g. "haybale_foo") inside that subdirectory.
    `source` is "pypi" (default; install_spec is the bare dist name) or "git"
    (install_spec is a git+subdirectory VCS URL pointing into the monorepo).
    """
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject["project"]
    name = project["name"]
    version = project["version"]
    pyproject_description = project.get("description", "")
    pyproject_deps: list[str] = list(project.get("dependencies", []))
    pyproject_authors = [a.get("name", "") for a in project.get("authors", []) if a.get("name")]
    pyproject_keywords = list(project.get("keywords", []))

    # The same reader the share pipeline uses. Both producers now run
    # pyproject + decorator -> LibraryMetadata -> Haybale -> TOML, so a field
    # cannot come from one source here and another there.
    decorator = read_decorator(init_py)

    # Derived from the library's own floor, never authored beside it — see
    # haywire.core.marketstall.requirement. The wizard emits this same token
    # for the libraries it publishes, so both producers agree by construction
    # rather than by convention.
    require = haywire_core_requirement(pyproject_deps)
    # A path from the git root, not a URL: the consumer resolves it against
    # `origin` at `install_spec`'s ref — see haywire.core.marketstall.locate.
    # Trailing slash marks a directory.
    docs_path = f"{subdirectory}/{module_name}/"

    def _declared(path: str) -> str:
        """Prefix an author-declared, library-relative path with the package's
        own path from the repo root. Empty when undeclared."""
        return f"{subdirectory}/{path.lstrip('/')}" if path else ""

    if source == "git":
        install_spec = f"{name} @ git+{config.source_url}.git#subdirectory={subdirectory}"
    else:
        install_spec = name

    # PEP 621 metadata is the source for description/authors/tags. The decorator
    # stopped accepting those kwargs when the distribution plan landed, so the
    # old `decorator or pyproject` preference was both dead for migrated
    # libraries and backwards from the ADR's precedence for unmigrated ones.
    row = Haybale(
        name=name,
        label=decorator.label or name,
        version=version,
        description=pyproject_description,
        authors=pyproject_authors,
        tags=pyproject_keywords or list(config.default_tags),
        linked_libraries=decorator.linked_libraries,
        on_reload=decorator.on_reload,
        os=decorator.os,
        source=source,
        install_spec=install_spec,
        origin=config.source_url,
        docs_path=docs_path,
        examples_path=_declared(decorator.examples_path),
        tests_path=_declared(decorator.tests_path),
    )
    entry: dict[str, object] = row.to_dict()
    # Omitted rather than emitted empty when undeclared — an absent field means
    # "no requirement", which is exactly how the parser and the gate read it.
    # A bare "haywire-core" is NOT that case: it means the author declared the
    # dependency with no floor, and it is emitted.
    if require is not None:
        entry["require"] = require
    return entry


# Order of fields in every [[haybales]] entry. Taken from the runtime parsers'
# own definition rather than restated, so a field added to Haybale cannot be
# silently dropped from the emitted feed. Entries only ever carry the subset
# build_entry fills; emit_stall_toml skips the rest, including the cache-only
# tail (via/last_seen/stale) that a generated feed never contains.
_ENTRY_FIELD_ORDER: tuple[str, ...] = Haybale._TOML_FIELDS

_MARKETPLACE_HEADER = """\
# Official haywire marketplace — aggregator (spec §11)
# Generated by scripts/generate_marketstall.py on every release tag.
# Do not edit by hand — re-run the generator instead.
#
# Subscribers fetch this file from GitHub Pages:
#   https://going-haywire.github.io/haywire/marketplace.toml
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
      - [tool.haywire.release] pip_publish_order, git_publish_order
      - [tool.haywire.marketstall] marketplace (explicit allowlist), plus URL/defaults
      - each marketplace package's pyproject + __init__.py

    Validates:
      - Every marketplace entry appears in exactly one of pip_publish_order or
        git_publish_order (unknown name → ValueError).
      - No name may appear in both pip_publish_order and git_publish_order.

    Returns a :class:`GenerateResult` carrying:
      - ``marketplace_toml``: aggregator TOML with one ``[[stalls]]`` per entry
        in marketplace, URL = ``{feed_base_url}/stalls/{dist-name}.toml``.
      - ``stalls``: list of ``(dist-name, stall-toml)`` pairs in marketplace order.
    """
    from scripts.bump_version import locate_packages, read_release_config

    release = read_release_config(root_pyproject)
    config = read_marketstall_config(root_pyproject)
    root_dir = root_pyproject.parent

    base_url = (feed_base_url or config.feed_base_url).rstrip("/")
    if not base_url:
        raise ValueError(
            "feed_base_url is required: set [tool.haywire.marketstall].feed_base_url "
            "in pyproject.toml or pass --feed-base-url on the command line."
        )

    pip_set = set(release.pip_publish_order)
    git_set = set(release.git_publish_order)

    # Validate: no package in both lists.
    both = pip_set & git_set
    if both:
        raise ValueError(
            f"packages appear in both pip_publish_order and git_publish_order: {sorted(both)}. "
            "A package can only have one source."
        )

    # Validate: every marketplace entry must be in exactly one publish list.
    marketplace_set = set(config.marketplace)
    unknown = marketplace_set - pip_set - git_set
    if unknown:
        raise ValueError(
            f"marketplace entries not found in pip_publish_order or git_publish_order: "
            f"{sorted(unknown)}. "
            "Add them to the appropriate publish list or remove them from marketplace."
        )

    located = locate_packages(root_pyproject, release)

    stalls: list[tuple[str, str]] = []
    stall_urls: list[str] = []

    for pkg_name in config.marketplace:
        source = "pypi" if pkg_name in pip_set else "git"
        pyproject_path = located[pkg_name]
        pkg_dir = pyproject_path.parent
        module_path = _resolve_module_path(pyproject_path, pkg_dir)
        init_py = pkg_dir / module_path / "__init__.py"
        module_name = Path(module_path).name
        subdirectory = pkg_dir.relative_to(root_dir).as_posix()
        entry = build_entry(
            pyproject_path=pyproject_path,
            init_py=init_py,
            config=config,
            subdirectory=subdirectory,
            module_name=module_name,
            source=source,
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
