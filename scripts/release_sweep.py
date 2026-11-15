#!/usr/bin/env python3
"""Report what a haywire release means for the libraries of the going-haywire organisation.

Two reports, both read-only (nothing is written on GitHub):

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

Usage::

    uv run python scripts/release_sweep.py names                    # HEAD against the last tag
    uv run python scripts/release_sweep.py names --ref v0.5.0 --previous v0.4.2
    uv run python scripts/release_sweep.py reminders --ref v0.5.0
    uv run python scripts/release_sweep.py reminders --json         # one object on stdout

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
from dataclasses import asdict, dataclass
from pathlib import Path

OWNER = "going-haywire"
CORE_REPO = f"{OWNER}/haywire"
NAMES_PATH = "tests/api/names.py"
MODULES = {"COMPONENT": "haywire.api", "WORKBENCH": "haywire.api.workbench"}
INTERNAL_PREFIXES = ("haywire.core", "haywire.ui", "haywire.barn")
WAITS_FOR = re.compile(rf"^Waits for: {re.escape(CORE_REPO)}@([0-9a-f]{{7,40}})", re.MULTILINE)


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


def scan_repo(repo: str, workdir: Path) -> tuple[set[tuple[str, str]], int]:
    """Shallow-clone *repo* into *workdir* and return ``imports_of`` summed over its Python files."""
    dest = workdir / repo.replace("/", "__")
    run("git", "clone", "--quiet", "--depth", "1", f"https://github.com/{repo}.git", str(dest))
    found: set[tuple[str, str]] = set()
    internal = 0
    for path in dest.rglob("*.py"):
        if ".git" in path.parts:
            continue
        names, count = imports_of(path.read_text(errors="replace"))
        found |= names
        internal += count
    return found, internal


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
    args = parser.parse_args(argv)

    try:
        if args.report == "names":
            report = names_report(args.ref, args.previous)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print_names(report)
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
