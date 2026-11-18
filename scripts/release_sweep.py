#!/usr/bin/env python3
"""Report what a haywire release means for the libraries of the going-haywire organisation.

Three reports, all read-only (nothing is written on GitHub):

``names``
    The Author API names (``tests/api/names.py``) a release removes or newly
    deprecates against the previous release tag, and which ``haybale-*``
    repositories of the organisation import them. Also counts each library's
    imports of internal modules (``haywire.core``, ``haywire.ui``,
    ``haywire.barn``), which may change in any release. Run before the bump.
``reminders``
    The open ``after-core-release`` issues of the organisation, and whether
    ``--ref`` contains the commit on each one's ``Waits for:`` line. Run after
    the publish.
``floors``
    The dependency floors the organisation's libraries put on core's releasable
    packages (``[tool.haywire.release] pip_publish_order``): the ones above the
    latest release (the library waits) and, with ``--ref``, the ones that release
    newly satisfies (unblocked). Run before the release to see what waits, and
    after it to see what it frees.
``nightly``
    Each library's latest ``nightly`` run (its tests against core's ``master``):
    passed, failed, running, or why there is none (no workflow yet, the workflow
    disabled, no run yet). Run before the release: a failed run is a break the
    release would ship.

Usage::

    uv run python scripts/release_sweep.py names                    # HEAD against the last tag
    uv run python scripts/release_sweep.py names --ref v0.5.0 --previous v0.4.2
    uv run python scripts/release_sweep.py reminders --ref v0.5.0
    uv run python scripts/release_sweep.py reminders --json         # one object on stdout
    uv run python scripts/release_sweep.py floors                   # against the latest v* tag
    uv run python scripts/release_sweep.py floors --ref v0.5.4      # what v0.5.4 unblocks
    uv run python scripts/release_sweep.py nightly

Needs ``git`` and a logged-in ``gh``. Exit codes: 0 report printed, 2 a command
failed (the report could not be made; never read that as "nothing found").
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

OWNER = "going-haywire"
CORE_REPO = f"{OWNER}/haywire"
NAMES_PATH = "tests/api/names.py"
MODULES = {"COMPONENT": "haywire.api", "WORKBENCH": "haywire.api.workbench"}
INTERNAL_PREFIXES = ("haywire.core", "haywire.ui", "haywire.barn")
RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*([^;@]*)")
LOWER_BOUND = re.compile(r"^(>=|~=|==|>)\s*(\d+(?:\.\d+)*)")
WAITS_FOR = re.compile(rf"^Waits for: {re.escape(CORE_REPO)}@([0-9a-f]{{7,40}})", re.MULTILINE)
NIGHTLY_PATH = ".github/workflows/nightly.yml"


class CommandFailed(Exception):
    """A git or gh command failed; its message says which and why."""


@dataclass(frozen=True)
class NameChange:
    module: str
    name: str
    kind: str
    """``removed`` (a break for importers) or ``deprecated`` (a notice until it is removed)."""


@dataclass(frozen=True)
class Reminder:
    issue: str
    """``owner/repo#n``."""
    title: str
    url: str
    commit: str | None
    status: str
    """``released``, ``waiting``, ``unknown commit`` or ``no Waits for line``."""


@dataclass(frozen=True)
class Floor:
    library: str
    """``owner/repo``."""
    package: str
    """Distribution name of the core package."""
    requirement: str
    """The requirement as the library writes it."""
    bound: str
    """The lower bound of the requirement, ``0.5.4``."""
    status: str
    """``waiting`` (above the release) or ``unblocked`` (the release newly satisfies it)."""


@dataclass(frozen=True)
class Nightly:
    library: str
    """``owner/repo``."""
    status: str
    """``passed``, ``failed``, ``inconclusive``, ``running``, ``no workflow``, ``disabled`` or ``no run``."""
    detail: str
    """The run's conclusion or the workflow's state, as GitHub gives it; empty without either."""
    created: str | None
    """When the run started (ISO 8601), or ``None`` without a run."""
    url: str | None


# --- pure parts -------------------------------------------------------------


def parse_names(source: str) -> dict[str, dict[str, set[str]]]:
    """Return ``{module: {"served": names, "deprecated": names}}`` from a ``names.py`` source.

    Reads the list literals only; the source is never executed.
    """
    lists: dict[str, list[str]] = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            target, value = node.target, node.value
        else:
            continue
        try:
            lists[target.id] = ast.literal_eval(value)
        except ValueError:
            continue
    result = {}
    for key, module in MODULES.items():
        deprecated = set(lists.get(f"{key}_DEPRECATED", []))
        result[module] = {"served": set(lists.get(key, [])) | deprecated, "deprecated": deprecated}
    return result


def api_changes(
    old: dict[str, dict[str, set[str]]], new: dict[str, dict[str, set[str]]]
) -> list[NameChange]:
    """Return the names *new* no longer serves, then the names it newly deprecates, per module."""
    changes = []
    for module in MODULES.values():
        before, after = old.get(module, {}), new.get(module, {})
        for name in sorted(before.get("served", set()) - after.get("served", set())):
            changes.append(NameChange(module, name, "removed"))
        for name in sorted(after.get("deprecated", set()) - before.get("deprecated", set())):
            changes.append(NameChange(module, name, "deprecated"))
    return changes


def imports_of(source: str) -> tuple[set[tuple[str, str]], int]:
    """Return the Author API ``(module, name)`` pairs a source imports, and its internal imports.

    Covers ``from haywire.api import X`` and ``import haywire.api as h`` followed
    by ``h.X``. The count is the import statements of ``haywire.core``,
    ``haywire.ui`` and ``haywire.barn``. A source that does not parse gives nothing.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set(), 0
    found: set[tuple[str, str]] = set()
    aliases: dict[str, str] = {}
    internal = 0
    api_modules = set(MODULES.values())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module in api_modules:
                found |= {(node.module, alias.name) for alias in node.names}
            elif node.module.startswith(INTERNAL_PREFIXES):
                internal += 1
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in api_modules and alias.asname:
                    aliases[alias.asname] = alias.name
                elif alias.name.startswith(INTERNAL_PREFIXES):
                    internal += 1
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases:
            found.add((aliases[node.value.id], node.attr))
    return found, internal


def version_key(version: str) -> tuple[int, ...]:
    """Return *version*'s numeric parts, ``"0.5.10"`` -> ``(0, 5, 10)``."""
    return tuple(int(part) for part in version.split("."))


def latest_release(tags: list[str]) -> str | None:
    """Return the highest ``vX.Y.Z`` tag of *tags*, or ``None``; other tags are ignored."""
    releases = [tag for tag in tags if RELEASE_TAG.match(tag)]
    return max(releases, key=lambda tag: version_key(tag[1:])) if releases else None


def lower_bound(requirement: str) -> tuple[str, str] | None:
    """Return ``(normalised name, lower bound)`` of a requirement string, or ``None`` without one.

    The bound is the highest of the ``>=``, ``>``, ``~=`` and ``==`` versions of its specifier;
    an extra, an environment marker or a URL does not count.
    """
    match = REQUIREMENT.match(requirement)
    if not match:
        return None
    bounds = [
        found.group(2) for part in match.group(2).split(",") if (found := LOWER_BOUND.match(part.strip()))
    ]
    if not bounds:
        return None
    return re.sub(r"[-_.]+", "-", match.group(1)).lower(), max(bounds, key=version_key)


def requirements_of(pyproject: str) -> list[str]:
    """Return every requirement string of a ``pyproject.toml`` source: dependencies and extras."""
    project = tomllib.loads(pyproject).get("project", {})
    found = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        found += extra
    return found


def floors_of(
    library: str, pyproject: str, packages: list[str], release: str, previous: str | None
) -> list[Floor]:
    """Return the floors of *pyproject* on *packages* that wait for, or are freed by, *release*.

    A floor above *release* waits. With *previous*, a floor above *previous* that *release* reaches
    is unblocked; without it, floors already satisfied are not reported.
    """
    wanted = {re.sub(r"[-_.]+", "-", name).lower() for name in packages}
    latest = version_key(release.removeprefix("v"))
    before = version_key(previous.removeprefix("v")) if previous else None
    found = []
    for requirement in requirements_of(pyproject):
        parsed = lower_bound(requirement)
        if not parsed or parsed[0] not in wanted:
            continue
        name, bound = parsed
        if version_key(bound) > latest:
            status = "waiting"
        elif before is not None and version_key(bound) > before:
            status = "unblocked"
        else:
            continue
        found.append(Floor(library, name, requirement.strip(), bound, status))
    return found


def nightly_of(library: str, workflows: list[dict], runs: list[dict]) -> Nightly:
    """Return *library*'s nightly result from ``gh workflow list`` and ``gh run list`` output.

    *runs* holds the latest run first. A ``failure``, ``timed_out`` or ``startup_failure``
    run failed; another unsuccessful conclusion (``cancelled``, ``skipped``) is
    ``inconclusive``. A disabled workflow reports ``disabled`` with its last run, if any.
    """
    workflow = next((w for w in workflows if w.get("path") == NIGHTLY_PATH), None)
    if workflow is None:
        return Nightly(library, "no workflow", "", None, None)
    run_ = runs[0] if runs else None
    created, url = (run_["createdAt"], run_["url"]) if run_ else (None, None)
    if workflow["state"] != "active":
        return Nightly(library, "disabled", workflow["state"], created, url)
    if run_ is None:
        return Nightly(library, "no run", "", None, None)
    if run_["status"] != "completed":
        return Nightly(library, "running", run_["status"], created, url)
    conclusion = run_["conclusion"]
    if conclusion == "success":
        status = "passed"
    elif conclusion in ("failure", "timed_out", "startup_failure"):
        status = "failed"
    else:
        status = "inconclusive"
    return Nightly(library, status, conclusion, created, url)


def waits_for(body: str) -> str | None:
    """Return the commit on an issue body's ``Waits for:`` line, or ``None``."""
    match = WAITS_FOR.search(body or "")
    return match.group(1) if match else None


# --- git and gh --------------------------------------------------------------


def run(*cmd: str, cwd: Path | None = None) -> str:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise CommandFailed(f"{cmd[0]} is not installed") from exc
    if proc.returncode != 0:
        raise CommandFailed(f"`{' '.join(cmd)}` failed: {proc.stderr.strip()}")
    return proc.stdout


def names_at(ref: str) -> dict[str, dict[str, set[str]]] | None:
    """Return the parsed name lists at *ref*, or ``None`` when *ref* has no ``names.py``."""
    try:
        return parse_names(run("git", "show", f"{ref}:{NAMES_PATH}"))
    except CommandFailed as exc:
        if "does not exist" in str(exc) or "exists on disk, but not in" in str(exc):
            return None
        raise


def previous_tag(ref: str) -> str:
    return run("git", "describe", "--tags", "--abbrev=0", "--match", "v*", f"{ref}^").strip()


def commit_status(sha: str, ref: str) -> str:
    if subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True).returncode:
        return "unknown commit"
    proc = subprocess.run(["git", "merge-base", "--is-ancestor", sha, ref], capture_output=True)
    return "released" if proc.returncode == 0 else "waiting"


def library_repos() -> list[str]:
    out = run("gh", "repo", "list", OWNER, "--limit", "200", "--json", "nameWithOwner,isArchived")
    return sorted(
        repo["nameWithOwner"]
        for repo in json.loads(out)
        if not repo["isArchived"] and repo["nameWithOwner"].split("/")[1].startswith("haybale-")
    )


def clone_repo(repo: str, workdir: Path) -> Path:
    """Shallow-clone *repo* into *workdir* and return the checkout."""
    dest = workdir / repo.replace("/", "__")
    run("git", "clone", "--quiet", "--depth", "1", f"https://github.com/{repo}.git", str(dest))
    return dest


def scan_repo(repo: str, workdir: Path) -> tuple[set[tuple[str, str]], int]:
    """Clone *repo* and return ``imports_of`` summed over its Python files."""
    dest = clone_repo(repo, workdir)
    found: set[tuple[str, str]] = set()
    internal = 0
    for path in dest.rglob("*.py"):
        if ".git" in path.parts:
            continue
        names, count = imports_of(path.read_text(errors="replace"))
        found |= names
        internal += count
    return found, internal


def release_tags() -> list[str]:
    return run("git", "tag", "--list", "v*").split()


def publish_order() -> list[str]:
    """Return core's ``pip_publish_order`` from the ``pyproject.toml`` beside this script's repository."""
    root = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text())
    return root["tool"]["haywire"]["release"]["pip_publish_order"]


def open_reminders(ref: str) -> list[Reminder]:
    out = run(
        "gh", "search", "issues", "--owner", OWNER, "--label", "after-core-release", "--state", "open",
        "--limit", "200", "--json", "repository,number,title,url,body",
    )  # fmt: skip
    reminders = []
    for issue in json.loads(out):
        sha = waits_for(issue.get("body", ""))
        reminders.append(
            Reminder(
                issue=f"{issue['repository']['nameWithOwner']}#{issue['number']}",
                title=issue["title"],
                url=issue["url"],
                commit=sha,
                status=commit_status(sha, ref) if sha else "no Waits for line",
            )
        )
    return sorted(reminders, key=lambda r: r.issue)


# --- reports -----------------------------------------------------------------


def names_report(ref: str, previous: str | None) -> dict:
    previous = previous or previous_tag(ref)
    old, new = names_at(previous), names_at(ref)
    report: dict = {"ref": ref, "previous": previous, "changes": [], "importers": {}, "internal": {}}
    if new is None:
        report["note"] = f"{ref} has no {NAMES_PATH}"
        return report
    if old is None:
        report["note"] = f"{previous} has no {NAMES_PATH}: no earlier Author API to compare with"
    changes = api_changes(old or {}, new) if old else []
    report["changes"] = [asdict(change) for change in changes]
    with tempfile.TemporaryDirectory(prefix="release-sweep-") as tmp:
        for repo in library_repos():
            found, internal = scan_repo(repo, Path(tmp))
            report["internal"][repo] = internal
            hits = [f"{c.module}.{c.name}" for c in changes if (c.module, c.name) in found]
            if hits:
                report["importers"][repo] = hits
    return report


def floors_report(ref: str | None) -> dict:
    """Return the floors of every organisation library on core's packages against *ref*.

    *ref* defaults to the latest ``v*`` tag; with an explicit one, the report also lists the floors
    it freed relative to the tag before it.
    """
    tags = release_tags()
    release = ref or latest_release(tags)
    if release is None:
        raise CommandFailed("no v* release tag found (git fetch --tags)")
    previous = None
    if ref:
        earlier = [t for t in tags if RELEASE_TAG.match(t) and version_key(t[1:]) < version_key(release[1:])]
        previous = latest_release(earlier)
    packages = publish_order()
    floors: list[Floor] = []
    with tempfile.TemporaryDirectory(prefix="release-sweep-") as tmp:
        for repo in library_repos():
            checkout = clone_repo(repo, Path(tmp))
            for pyproject in sorted(checkout.glob("barn/*/pyproject.toml")):
                floors += floors_of(repo, pyproject.read_text(), packages, release, previous)
    return {"release": release, "previous": previous, "floors": [asdict(f) for f in floors]}


def nightly_results() -> list[Nightly]:
    """Return the latest nightly result of every organisation library."""
    results = []
    for repo in library_repos():
        workflows = json.loads(
            run("gh", "workflow", "list", "--repo", repo, "--all", "--json", "path,state")
        )
        runs = []
        if any(w.get("path") == NIGHTLY_PATH for w in workflows):
            runs = json.loads(
                run(
                    "gh",
                    "run",
                    "list",
                    "--repo",
                    repo,
                    "--workflow",
                    Path(NIGHTLY_PATH).name,
                    "--limit",
                    "1",
                    "--json",
                    "status,conclusion,createdAt,url",
                )  # fmt: skip
            )
        results.append(nightly_of(repo, workflows, runs))
    return results


def print_floors(report: dict) -> None:
    release = report["release"]
    floors = report["floors"]
    print(f"Dependency floors on core against {release}:")
    for status, title in (("waiting", "Waiting for a release above"), ("unblocked", "Unblocked by")):
        rows = [f for f in floors if f["status"] == status]
        if status == "unblocked" and not report["previous"]:
            continue
        print(f"\n{title} {release}:")
        if not rows:
            print("  none")
        for f in rows:
            print(f"  {f['library']:<34} {f['requirement']}")


def print_nightly(results: list[Nightly]) -> None:
    print("Latest nightly run of each library (its tests against core's master):")
    if not results:
        print("  no library found")
    for r in results:
        status = f"{r.status} ({r.detail})" if r.detail and r.status != "passed" else r.status
        when = r.created[:10] if r.created else ""
        print(f"  {r.library:<34} {status:<28} {when:<10} {r.url or ''}".rstrip())


def print_names(report: dict) -> None:
    print(f"Author API: {report['ref']} against {report['previous']}")
    if note := report.get("note"):
        print(f"  {note}")
    changes = report["changes"]
    if not changes and not report.get("note"):
        print("  no name removed or newly deprecated")
    for change in changes:
        print(f"  {change['kind']:<10} {change['module']}.{change['name']}")
    if report["importers"]:
        print("\nLibraries importing a changed name:")
        for repo, hits in report["importers"].items():
            print(f"  {repo}: {', '.join(hits)}")
    elif changes:
        print("\nNo library imports a changed name.")
    if report["internal"]:
        print("\nImports of internal modules (haywire.core / ui / barn), which may change in any release:")
        for repo, count in report["internal"].items():
            print(f"  {repo}: {count}")


def print_reminders(ref: str, reminders: list[Reminder]) -> None:
    print(f"Open after-core-release reminders against {ref}:")
    if not reminders:
        print("  none")
    for r in reminders:
        commit = r.commit[:9] if r.commit else "-"
        print(f"  {r.status:<18} {r.issue:<28} waits for {commit}  {r.url}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="report", required=True)
    names = sub.add_parser(
        "names", help="Author API names a release removes or deprecates, and their importers"
    )
    names.add_argument("--ref", default="HEAD", help="the release, or HEAD before the bump (default)")
    names.add_argument(
        "--previous", help="the release to compare with (default: the last v* tag before --ref)"
    )
    names.add_argument("--json", action="store_true")
    reminders = sub.add_parser(
        "reminders", help="open after-core-release reminders and whether --ref contains them"
    )
    reminders.add_argument("--ref", default="HEAD", help="the release tag (default: HEAD)")
    reminders.add_argument("--json", action="store_true")
    floors = sub.add_parser(
        "floors", help="dependency floors of the libraries above (waiting) or freed by a release"
    )
    floors.add_argument("--ref", help="the release tag (default: the latest v* tag, nothing freed)")
    floors.add_argument("--json", action="store_true")
    nightly = sub.add_parser("nightly", help="each library's latest nightly run against core's master")
    nightly.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.report == "names":
            report = names_report(args.ref, args.previous)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print_names(report)
        elif args.report == "floors":
            report = floors_report(args.ref)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print_floors(report)
        elif args.report == "nightly":
            results = nightly_results()
            if args.json:
                print(json.dumps({"nightly": [asdict(r) for r in results]}, indent=2))
            else:
                print_nightly(results)
        else:
            found = open_reminders(args.ref)
            if args.json:
                print(json.dumps({"ref": args.ref, "reminders": [asdict(r) for r in found]}, indent=2))
            else:
                print_reminders(args.ref, found)
    except CommandFailed as exc:
        print(f"release_sweep: {exc}. The report could not be made.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
