"""
Generate a marketplace.toml snippet for sharing a haybale library.

Reads metadata from the library's pyproject.toml and detects the git
remote URL to produce a ready-to-paste TOML block.
"""

from dataclasses import dataclass
from pathlib import Path

import toml

from haywire.core.library.dep_detect import find_module_dir
from haywire.core.marketstall import Haybale
from haywire_studio.packaging.share.barn import barn_library_dirs
from haywire_studio.packaging.share.manifest.deps import _read_library_dependencies, _read_library_label
from haywire_studio.packaging.share.manifest.reader import read_manifest
from haywire_studio.packaging.share.readme import _update_repo_readmes
from haywire_studio.packaging.share.url import (
    _derive_url,
    _find_git_root,
    _get_current_ref,
    _get_remote_url,
    _ssh_to_https,
)


def _build_entry_for_library(lib_dir: Path, *, tag: str | None = None) -> dict | None:
    """Build a marketplace entry for one library directory.

    Returns the entry dict (TOML-serializable), or None if `lib_dir` lacks a
    pyproject.toml. Used by both `haywire share` (single library, stdout) and
    `haywire share --save` (every barn library, aggregated to file).

    When `tag` is given (the full SharePipeline always supplies it — the
    version is resolved and tag-collision-checked in step 3, well before this
    runs in step 5), every ref-bearing URL pins to that tag: install_spec,
    docs_url, examples_url, and tests_url all resolve to the exact commit a
    consumer will get, not whatever the branch currently holds. When `tag` is
    None (standalone `write_marketstall()` calls outside the pipeline, or a
    repo with no tags yet), falls back to the previous branch/ref-less
    behavior unchanged.
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

    git_root = _find_git_root(lib_dir)
    remote_url = _get_remote_url(git_root) if git_root else None

    subdirectory: Path | str
    if remote_url:
        assert git_root is not None
        https_url = _ssh_to_https(remote_url)
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
    label = _read_library_label(module_dir, label_fallback) if module_dir else label_fallback
    dependencies = _read_library_dependencies(module_dir) if module_dir else []

    # The branch a raw-content URL points at MUST be the repo's actual current
    # branch, not a hardcoded guess — this repo's default is "master", and a
    # hardcoded "main" 404s on raw.githubusercontent.com even though the file
    # exists on the real branch. No fallback: a guessed branch name nobody
    # verified exists silently emits a URL that may 404 forever, whereas
    # `None` (detached HEAD, git unavailable) propagates to an empty URL below
    # — an honest "couldn't determine this" beats a plausible-looking wrong
    # answer. `SharePipeline.check_preconditions` is the layer that turns an
    # undeterminable/wrong branch into an actual failure before publish; this
    # module has no such gate, so it degrades instead of guessing.
    #
    # `ref` is what every raw-content URL below resolves against. A supplied
    # tag always wins — it names the exact commit a consumer's install_spec
    # will resolve to, so the doc/example/test URLs must point at the same
    # commit or they contradict install_spec about which state of the library
    # "publishing" refers to. With no tag (standalone write_marketstall(), or
    # a repo with no release yet) this falls back to the current branch, same
    # as before this parameter existed.
    ref = tag or (_get_current_ref(git_root) if git_root else None)

    docs_url = ""
    if remote_url and module_dir and ref:
        assert git_root is not None
        module_rel = module_dir.relative_to(git_root)
        if "github.com" in https_url:
            raw_base = https_url.replace("github.com", "raw.githubusercontent.com")
            docs_url = f"{raw_base}/{ref}/{module_rel}/"
        elif "gitlab.com" in https_url:
            docs_url = f"{https_url}/-/raw/{ref}/{module_rel}/"

    # read_manifest() above already validated [tool.haywire].os via
    # _read_os_field; re-running it here would just re-validate the same
    # already-checked value. Read it directly off the validated `data`.
    os_decl: list[str] = data.get("tool", {}).get("haywire", {}).get("os") or []

    def _folder_url(folder_name: str) -> str:
        """Raw git URL for <lib>/<folder>/ when it holds >=1 .haywire graph."""
        if not (remote_url and git_root and ref):
            return ""
        folder = lib_dir / folder_name
        if not folder.is_dir() or not any(folder.rglob("*.haywire")):
            return ""
        rel = lib_dir.relative_to(git_root)
        if "github.com" in https_url:
            raw_base = https_url.replace("github.com", "raw.githubusercontent.com")
            return f"{raw_base}/{ref}/{rel}/{folder_name}/"
        if "gitlab.com" in https_url:
            return f"{https_url}/-/raw/{ref}/{rel}/{folder_name}/"
        return ""

    examples_url = _folder_url("examples")
    tests_url = _folder_url("tests")

    return Haybale(
        name=name,
        label=label,
        min_version=version,
        description=description,
        author=author,
        source="git",
        install_spec=install_spec,
        tags=tags,
        os=os_decl,
        dependencies=dependencies,
        source_url=https_url if remote_url else "",
        docs_url=docs_url,
        examples_url=examples_url,
        tests_url=tests_url,
    ).to_dict()


class NoBarnError(RuntimeError):
    """Raised when `share --save` is invoked on a repo with no `barn/` directory."""


@dataclass(frozen=True)
class MarketstallWriteResult:
    """Output of :func:`write_marketstall`.

    ``readmes`` lists only the READMEs actually rewritten (they had the marker
    pair AND the URL changed), so a caller staging ``written`` never stages a
    file it didn't touch.
    """

    out_path: Path
    share_url: str | None
    warning: str | None
    readmes: list[Path]

    @property
    def written(self) -> list[Path]:
        return [self.out_path, *self.readmes]


def build_marketstall_entries(repo_root: Path, *, tag: str | None = None) -> list[dict]:
    """Build a marketstall entry for every ``barn/*`` library, sorted by directory.

    The feed's contract is "every haybale this repo offers", so it is always
    rebuilt from disk in full — a partial rebuild silently deletes the entries
    of libraries that weren't part of this run.

    ``tag``, when given, pins every entry's ref-bearing URLs (install_spec,
    docs_url, examples_url, tests_url) to that tag instead of the current
    branch — see :func:`_build_entry_for_library`.

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


def write_marketstall(
    repo_root: Path,
    *,
    update_readme: bool = True,
    tag: str | None = None,
) -> MarketstallWriteResult:
    """Rebuild ``<repo_root>/marketstall.toml`` from every ``barn/*`` library.

    Deliberately does NOT run the dependency-drift gate: drift is the share
    pipeline's step 2, where the user makes a Union/Replace decision, and a
    second gate here would re-ask a settled question. Prints nothing — callers
    own their own output.

    ``tag``, when given, pins every entry's ref-bearing URLs to that tag
    rather than the current branch. The share pipeline always supplies it
    (the version is resolved and reserved in step 3, before this runs in
    step 5); direct/standalone callers that don't have a tag yet get the
    previous branch-based behavior unchanged.
    """
    entries = build_marketstall_entries(repo_root, tag=tag)

    out_path = repo_root / "marketstall.toml"
    out_path.write_text(_MARKETSTALL_HEADER + toml.dumps({"haybales": entries}))

    url_result = _derive_url(repo_root, out_path)
    readmes: list[Path] = []
    if url_result.share_url is not None and update_readme:
        readmes = _update_repo_readmes(repo_root, url_result.share_url)

    return MarketstallWriteResult(
        out_path=out_path,
        share_url=url_result.share_url,
        warning=url_result.warning,
        readmes=readmes,
    )
