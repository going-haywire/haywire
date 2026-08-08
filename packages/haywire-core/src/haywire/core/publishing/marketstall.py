"""
Generate a marketplace.toml snippet for sharing a haybale library.

Reads metadata from the library's pyproject.toml and detects the git
remote URL to produce a ready-to-paste TOML block.
"""

from dataclasses import dataclass
from pathlib import Path

import toml

from haywire.core.library.dep_detect import find_module_dir
from haywire.core.publishing.manifest.os_field import _DECLARABLE_OS_VALUES
from haywire.core.marketstall import Haybale
from haywire.core.marketstall.host_providers import ssh_to_https
from haywire.core.marketstall.requirement import haywire_core_requirement
from haywire.core.publishing.barn import barn_library_dirs
from haywire.core.publishing.manifest.decorator_ast import DecoratorFields, read_decorator
from haywire.core.publishing.manifest.reader import read_manifest
from haywire.core.publishing.readme import _update_repo_readmes
from haywire.core.publishing.url import (
    _derive_url,
    _find_git_root,
    _get_remote_url,
)


def _build_entry_for_library(lib_dir: Path, *, tag: str | None = None) -> dict | None:
    """Build a marketplace entry for one library directory.

    Returns the entry dict (TOML-serializable), or None if `lib_dir` lacks a
    pyproject.toml. Used by both `haywire share` (single library, stdout) and
    `haywire share --save` (every barn library, aggregated to file).

    When `tag` is given (the full SharePipeline always supplies it — the
    version is resolved and tag-collision-checked in step 3, well before this
    runs in step 5), ``install_spec`` pins to that tag, naming the exact commit
    a consumer will get. It is the entry's ONLY ref: ``docs_path``,
    ``examples_path`` and ``tests_path`` are repo-relative and resolved against
    it by the consumer, so no two fields can disagree about which commit was
    published. When `tag` is None (standalone `write_marketstall()` calls, or a
    repo with no tags yet), install_spec floats to the branch as before.

    The framework requirement is DERIVED from this library's own
    ``haywire-core`` floor, not passed in: the pyproject is the truth and
    ``require`` is its projection, so a standalone call and a full pipeline run
    emit the same value and neither can publish a stale one. Per-library, so a
    library whose floor genuinely differs is reported honestly instead of being
    flattened to one project-wide string.
    """
    pyproject_path = lib_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    data = read_manifest(lib_dir)
    project = data.get("project", {})

    name = project.get("name", lib_dir.name)
    version = project.get("version", "0.0.0")
    description = project.get("description", "")
    tags = project.get("keywords", [])

    authors = project.get("authors", [])
    author = authors[0].get("name", "") if authors else ""

    # Derived, never passed in: the library's own floor IS the requirement, and
    # the entry is its projection. None (undeclared) omits the key entirely;
    # the bare name (declared, no floor) is emitted, because those two states
    # are different answers and the field is shaped to tell them apart.
    require = haywire_core_requirement([str(entry) for entry in project.get("dependencies", []) or []])

    git_root = _find_git_root(lib_dir)
    remote_url = _get_remote_url(git_root) if git_root else None

    subdirectory: Path | str
    if remote_url:
        assert git_root is not None
        https_url = ssh_to_https(remote_url)
        https_url = https_url.removesuffix(".git")
        subdirectory = lib_dir.relative_to(git_root)
        if tag:
            install_spec = f"{name} @ git+{https_url}.git@{tag}#subdirectory={subdirectory}"
        else:
            install_spec = f"{name} @ git+{https_url}.git#subdirectory={subdirectory}"
    else:
        https_url = ""
        subdirectory = (
            lib_dir.relative_to(Path.cwd()) if lib_dir.is_relative_to(Path.cwd()) else lib_dir.name
        )
        install_spec = f"{name} @ git+https://<REPO_URL>.git#subdirectory={subdirectory}"

    module_dir = find_module_dir(lib_dir)
    label_fallback = name.removeprefix("haybale-").replace("-", " ").replace("_", " ").title()

    # One read of the decorator source, for every field the row takes from it.
    # Source rather than an imported class: `haywire share` runs against a
    # checkout, where nothing is installed, so cls.class_identity is unreachable.
    decorator = read_decorator(module_dir / "__init__.py") if module_dir else DecoratorFields()

    label = decorator.label or label_fallback
    dependencies = decorator.linked_libraries

    # No ref is read here any more. It used to be needed because this function
    # baked raw-content URLs, and getting the branch wrong ("main" against a
    # repo whose default is "master") emitted URLs that 404'd forever. Rows now
    # carry repo-relative paths, and the ref lives in install_spec alone — so
    # the two can no longer disagree, and there is nothing left to guess.

    # `os` is a decorator kwarg; the decorator source is the only read. The
    # [tool.haywire].os fallback went with the migration — but strip_os and its
    # precondition still read that key, because they REPAIR a library that
    # declares it, and third-party libraries have not migrated.
    #
    # Validation, not workaround: an unknown platform string is dropped rather
    # than published. (The regex reader this replaced also mangled underscores.)
    os_decl: list[str] = [v for v in decorator.os if v in _DECLARABLE_OS_VALUES]

    # Paths are relative to the git root and resolved by the consumer against
    # `origin` at `install_spec`'s ref — see haywire.core.marketstall.locate.
    # Trailing slash marks a directory.
    docs_path = ""
    if git_root and module_dir:
        docs_path = f"{module_dir.relative_to(git_root)}/"

    def _declared_path(declared: str) -> str:
        """Prefix an author-declared, library-relative path with the lib's own
        path from the git root. Empty when undeclared."""
        if not declared or not git_root:
            return ""
        rel = lib_dir.relative_to(git_root)
        return f"{rel}/{declared.lstrip('/')}"

    return Haybale(
        name=name,
        label=label,
        version=version,
        require=require or "",
        description=description,
        authors=[author] if author else [],
        source="git",
        install_spec=install_spec,
        tags=tags,
        os=os_decl,
        linked_libraries=dependencies,
        origin=https_url if remote_url else "",
        docs_path=docs_path,
        examples_path=_declared_path(decorator.examples_path),
        tests_path=_declared_path(decorator.tests_path),
    ).to_dict()


class NoBarnError(RuntimeError):
    """Raised when `share --save` is invoked on a repo with no `barn/` directory."""


@dataclass(frozen=True)
class MarketstallWriteResult:
    """Output of :func:`write_marketstall`.

    ``readmes`` lists only the READMEs actually rewritten (they had the marker
    pair AND the URL changed), so a caller staging ``written`` never stages a
    file it didn't touch. ``tagged_url`` mirrors ``share_url`` pinned to the
    ``tag`` passed in (None when no tag was given or derivation failed).
    ``pypi_url`` is the project's deployed PyPI feed, read from
    ``[tool.haywire.marketstall].pypi_marketplace_url`` (None when unset).
    """

    out_path: Path
    share_url: str | None
    warning: str | None
    readmes: list[Path]
    tagged_url: str | None = None
    pypi_url: str | None = None

    @property
    def written(self) -> list[Path]:
        return [self.out_path, *self.readmes]


def build_marketstall_entries(repo_root: Path, *, tag: str | None = None) -> list[dict]:
    """Build a marketstall entry for every ``barn/*`` library, sorted by directory.

    The feed's contract is "every haybale this repo offers", so it is always
    rebuilt from disk in full — a partial rebuild silently deletes the entries
    of libraries that weren't part of this run.

    ``tag``, when given, pins every entry's ``install_spec`` — the entry's only
    ref — to that tag instead of the current branch. See
    :func:`_build_entry_for_library`.

    Each entry's framework requirement is derived from that library's own
    ``haywire-core`` floor — see :func:`_build_entry_for_library`.

    Raises :class:`NoBarnError` when ``<repo_root>/barn`` does not exist.
    """
    barn = repo_root / "barn"
    if not barn.is_dir():
        raise NoBarnError(f"no barn/ directory at {repo_root}")

    entries: list[dict] = []
    for lib_dir in barn_library_dirs(repo_root):
        entry = _build_entry_for_library(lib_dir, tag=tag)
        if entry is not None:
            entries.append(entry)
    return entries


_MARKETSTALL_HEADER = (
    "# marketstall.toml — share this file's raw URL so others can subscribe to your library feed\n"
    "# Run: haywire share   to update this file\n\n"
)


def read_pypi_marketplace_url(repo_root: Path) -> str | None:
    """Read ``[tool.haywire.marketstall].pypi_marketplace_url`` from the repo pyproject.

    The deployed feed of a project that also publishes to PyPI — typically a
    GitHub Pages URL written by a release workflow. Project-scoped rather than
    per-run: the value is the same on every publish, so it is authored once in
    ``pyproject.toml`` instead of retyped as a flag (an omitted flag would
    silently drop the link from the README, which is rewritten wholesale).

    Lenient by the same reasoning as :func:`read_manifest_lenient` — this is a
    read-to-report caller. A missing file, malformed TOML, an absent block, or
    a non-string value all mean "no PyPI feed to advertise", which is the
    correct answer for every project that does not publish one. It must never
    fail a publish over an optional link.
    """
    try:
        data = toml.loads((repo_root / "pyproject.toml").read_text())
    except (OSError, toml.TomlDecodeError):
        return None
    block = data.get("tool", {}).get("haywire", {}).get("marketstall", {})
    if not isinstance(block, dict):
        return None
    value = block.get("pypi_marketplace_url")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def write_marketstall(
    repo_root: Path,
    *,
    update_readme: bool = True,
    tag: str | None = None,
) -> MarketstallWriteResult:
    """Rebuild ``<repo_root>/marketstall.toml`` from every ``barn/*`` library.

    Deliberately does NOT run the dependency detect step: that is the pipeline's
    own step, where the author resolves what they choose to resolve, and a
    second gate here would re-ask a settled question. Prints nothing — callers
    own their own output.

    ``tag``, when given, pins every entry's ``install_spec`` to that tag
    rather than the current branch. The share pipeline always supplies it
    (the version is resolved and reserved in step 3, before this runs in
    step 5); direct/standalone callers that don't have a tag yet get the
    previous branch-based behavior unchanged.

    Every entry's ``require`` is derived from that library's pyproject floor at
    write time, so a standalone call emits the same value the pipeline would.
    """
    entries = build_marketstall_entries(repo_root, tag=tag)

    out_path = repo_root / "marketstall.toml"
    out_path.write_text(_MARKETSTALL_HEADER + toml.dumps({"haybales": entries}))

    url_result = _derive_url(repo_root, out_path, tag=tag)
    pypi_url = read_pypi_marketplace_url(repo_root)
    readmes: list[Path] = []
    if url_result.share_url is not None and update_readme:
        readmes = _update_repo_readmes(
            repo_root,
            url_result.share_url,
            tagged_url=url_result.tagged_url,
            pypi_url=pypi_url,
        )

    return MarketstallWriteResult(
        out_path=out_path,
        share_url=url_result.share_url,
        warning=url_result.warning,
        readmes=readmes,
        tagged_url=url_result.tagged_url,
        pypi_url=pypi_url,
    )
