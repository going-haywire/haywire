#!/usr/bin/env python3
"""T3 Code's slot (ADR 0090): check the user's T3 setup against the repository, and fix what it can.

``--check`` lists what the T3 setup lacks for the checkout ``--repo`` (default: the current
folder): the scripts of its ``t3.json`` among the ones T3 runs for this project, each with the
fields ``t3.json`` gives it (``async: false`` on *Worktree setup* among them, which T3's import
drops), and T3's worktree cleanup and branch naming. ``--fix`` backs up T3's settings file
beside it and adds or corrects only those scripts; the cleanup and branch naming stay with the
user, in T3's settings. ``--hook`` prints the check as the slot's session-start lines (see
``session.sh``).

T3's settings file (``$T3CODE_HOME/userdata/settings.json``) is internal and undocumented: a
file this script does not recognise is left untouched, and the user is pointed to the docs.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

DOCS = "https://github.com/going-haywire/haywire/blob/master/docs/collaboration/orchestrators/t3.md#setup"
IMPORT = "*Project settings → Actions → Import scripts → Import from t3.json*"
# Fields of a t3.json script that only label it: a difference there is not worth a fix.
LABELS = frozenset({"name", "icon"})


@dataclass
class Gap:
    """One thing the T3 setup lacks; ``fixable`` if ``--fix`` makes it right."""

    text: str
    fixable: bool


@dataclass
class Report:
    gaps: list[Gap]
    # The parsed settings and, when the scripts can be fixed, the list T3 runs them from.
    settings: dict | None = None
    scripts: list | None = None
    # Each change --fix makes to ``scripts``: (index or None to append, the script).
    changes: list[tuple[int | None, dict]] | None = None
    unreadable: str | None = None
    # Whether a gap already says what the t3.json scripts lack.
    scripts_named: bool = False


def t3_home() -> Path:
    return Path(os.environ.get("T3CODE_HOME") or Path.home() / ".t3")


def settings_path() -> Path:
    return t3_home() / "userdata" / "settings.json"


def main_folder(repo: Path) -> Path:
    """The main folder of the checkout ``repo``, which T3 has as the project, worktrees included."""
    try:
        common = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        return Path(common).parent.resolve()
    except (OSError, subprocess.SubprocessError):
        return repo.resolve()


def project_id(folder: Path) -> str | None:
    """T3's id for the project at ``folder``, from T3's state database; ``None`` if it cannot tell."""
    db = t3_home() / "userdata" / "statev2.sqlite"
    if not db.is_file():
        return None
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1) as con:
            rows = con.execute(
                "SELECT project_id, workspace_root FROM projection_projects WHERE deleted_at IS NULL"
            ).fetchall()
    except sqlite3.Error:
        return None
    for pid, root in rows:
        try:
            if Path(root).resolve() == folder:
                return str(pid)
        except (OSError, TypeError):
            continue
    return ""  # the database answered: no project has this folder


def load_t3_json(repo: Path) -> list[dict] | None:
    try:
        scripts = json.loads((repo / "t3.json").read_text(encoding="utf-8")).get("scripts")
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(scripts, list):
        return None
    return [
        s for s in scripts if isinstance(s, dict) and isinstance(s.get("command"), str) and s.get("name")
    ]


def find_entry(overrides: dict, wanted: list[dict], pid: str | None) -> tuple[str | None, str | None]:
    """The key of this project's entry in ``projectSettingsOverrides``, or ``(None, why)``."""
    if pid:
        entry = overrides.get(pid)
        imported = isinstance(entry, dict) and "defaultProjectScripts" in entry
        return (pid, None) if imported else (None, "not imported")
    if pid == "":
        return None, "no project"
    commands = {s["command"] for s in wanted}
    scored = []
    for key, entry in overrides.items():
        scripts = entry.get("defaultProjectScripts") if isinstance(entry, dict) else None
        if isinstance(scripts, list):
            hits = sum(1 for s in scripts if isinstance(s, dict) and s.get("command") in commands)
            if hits:
                scored.append((hits, key))
    scored.sort(reverse=True)
    if not scored:
        return None, "not imported"
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, "ambiguous"
    return scored[0][1], None


def script_id(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "script"
    sid, n = base, 2
    while sid in taken:
        sid, n = f"{base}-{n}", n + 1
    return sid


UNCHECKED = (
    "could not check the t3.json scripts: T3's settings file is not as expected;"
    f" check them by hand ({DOCS})"
)
NOT_IMPORTED = (
    f"the t3.json scripts are not imported: import all three in {IMPORT}, *Haywire studio* optional"
    f" (not with `t3_project_update`, whose write T3 does not run, pingdotgg/t3code#14991), then set"
    f" `async: false` on *Worktree setup* again, which the import drops (pingdotgg/t3code#40325) ({DOCS})"
)


def check_scripts(settings: dict, repo: Path, report: Report) -> None:
    """Add a gap for each ``t3.json`` script T3 does not run as ``t3.json`` gives it."""
    wanted = load_t3_json(repo)
    if not wanted:
        return  # no t3.json: T3 has nothing to run for this repository
    report.scripts_named = True
    overrides = settings.get("projectSettingsOverrides", {})
    if settings.get("projectSettingsFolded") is not True or not isinstance(overrides, dict):
        report.gaps.append(Gap(UNCHECKED, False))
        return
    folder = main_folder(repo)
    key, why = find_entry(overrides, wanted, project_id(folder))
    if key is None:
        text = {
            "no project": f"the folder `{folder}` is not a T3 project: add it in T3, then import the t3.json"
            f" scripts in {IMPORT} ({DOCS})",
            "ambiguous": "could not tell which T3 project is this folder, so the t3.json scripts are not"
            f" checked; check them by hand ({DOCS})",
        }.get(why or "", NOT_IMPORTED)
        report.gaps.append(Gap(text, False))
        return
    scripts = overrides[key]["defaultProjectScripts"]
    if not isinstance(scripts, list) or not all(isinstance(s, dict) for s in scripts):
        report.gaps.append(Gap(UNCHECKED, False))
        return
    report.scripts, report.changes = scripts, []
    for want in wanted:
        at = next((i for i, s in enumerate(scripts) if s.get("command") == want["command"]), None)
        if at is None:
            at = next((i for i, s in enumerate(scripts) if s.get("name") == want["name"]), None)
        if at is None:
            taken = {str(s.get("id")) for s in scripts} | {str(s.get("id")) for _, s in report.changes}
            report.changes.append((None, {"id": script_id(want["name"], taken), **want}))
            report.gaps.append(Gap(f"the T3 project lacks the t3.json script *{want['name']}*", True))
            continue
        have = scripts[at]
        differ = [k for k, v in want.items() if k not in LABELS and have.get(k) != v]
        if not differ:
            continue
        report.changes.append((at, {**have, **{k: want[k] for k in differ}}))
        if differ == ["async"]:
            text = (
                f"*{want['name']}* lacks `async: {json.dumps(want['async'])}`, which T3's import drops"
                " (pingdotgg/t3code#40325)"
            )
        else:
            text = f"*{want['name']}* differs from t3.json in " + ", ".join(f"`{k}`" for k in differ)
        report.gaps.append(Gap(text, True))
    report.scripts_named = bool(report.changes)


def check_settings(settings: dict, report: Report) -> None:
    """Worktree cleanup and branch naming: set in T3's settings by hand (T3 may not take a file edit)."""
    cleanup = settings.get("storageCleanup", {})
    cleanup = cleanup if isinstance(cleanup, dict) else {}
    if cleanup.get("worktreeOnMerge", False) is not True:
        text = "merged worktrees are not deleted: *Settings → Worktrees → Cleanup → Delete merged worktrees*"
        report.gaps.append(Gap(text, False))
    if cleanup.get("worktreeKeepWhen", "uncommitted-changes") != "uncommitted-changes":
        text = (
            "worktrees with local changes are not kept by uncommitted changes: *Settings → Worktrees →"
            " Cleanup → Keep worktrees with local changes → Uncommitted changes*"
        )
        report.gaps.append(Gap(text, False))
    if settings.get("branchNamingMode", "static") != "semantic":
        report.gaps.append(
            Gap("branches are not named by kind: *Settings → Worktrees → Branch naming → semantic*", False)
        )


def check(repo: Path) -> Report:
    report = Report(gaps=[])
    path = settings_path()
    if not path.is_file():
        return report  # no T3 settings to check: say nothing
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        settings = None
    if not isinstance(settings, dict):
        report.unreadable = (
            f"could not read T3's settings file `{path}`, so the T3 setup is not checked;"
            f" the steps are in {DOCS}"
        )
        return report
    report.settings = settings
    check_scripts(settings, repo, report)
    check_settings(settings, report)
    return report


def fix(repo: Path) -> int:
    report = check(repo)
    path = settings_path()
    if report.unreadable:
        print(report.unreadable)
        return 1
    if report.settings is None:
        print(f"No T3 settings file at `{path}`: nothing to fix. The steps are in {DOCS}")
        return 1
    if report.changes:
        assert report.scripts is not None
        backup = path.with_name(f"{path.name}.{time.strftime('%Y%m%d-%H%M%S')}.bak")
        shutil.copy2(path, backup)
        for at, script in report.changes:
            if at is None:
                report.scripts.append(script)
            else:
                report.scripts[at] = script
        tmp = path.with_name(path.name + ".haywire-tmp")
        tmp.write_text(json.dumps(report.settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
        print(f"Backed up T3's settings to `{backup}`. Changed:")
        for gap in report.gaps:
            if gap.fixable:
                print(f"- fixed: {gap.text}")
    else:
        print("Nothing to fix in T3's settings file.")
    manual = [g for g in report.gaps if not g.fixable]
    if manual:
        print("Still to do by hand, in T3:")
        for gap in manual:
            print(f"- {gap.text}")
        print(f"The steps: {DOCS}")
    return 0


def hook(repo: Path, unfinished: int | None) -> None:
    """The slot's session-start lines: for the agent, and as ``user: `` lines for the developer."""
    report = check(repo)
    gaps = list(report.gaps)
    if unfinished is not None:
        cause = "" if report.scripts_named else f", most likely because {NOT_IMPORTED}"
        text = (
            f"the worktree setup did not finish within {unfinished} s{cause}; then run"
            " `python3 scripts/worktree_setup.py` in this worktree now"
        )
        gaps.insert(0, Gap(text, False))
    if report.unreadable:
        print(f"T3 setup: {report.unreadable}.")
        print(f"user: T3 setup: {report.unreadable}")
    if not gaps:
        return
    items = "; ".join(f"{g.text}{' [fix]' if g.fixable else ''}" for g in gaps)
    line = "T3 setup is incomplete; pass this list to the user in your first reply, before other work: "
    line += f"{items}."
    if any(g.fixable for g in gaps):
        line += (
            f" Offer to fix the items marked [fix] with `python3 {Path(__file__).resolve()} --fix`"
            " (it backs up T3's settings file and changes only those scripts), and run it only on the"
            " user's yes."
        )
    if any(not g.fixable for g in gaps):
        line += f" The other items the user sets in T3 by hand: {DOCS}"
    print(line)
    print("user: T3 setup is incomplete:")
    for gap in gaps:
        print(f"user: - {gap.text}{' (the agent can fix this)' if gap.fixable else ''}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="list what the T3 setup lacks")
    mode.add_argument("--fix", action="store_true", help="back up T3's settings and fix the t3.json scripts")
    mode.add_argument("--hook", action="store_true", help="print the check as session-start lines")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="the checkout (default: here)")
    parser.add_argument("--setup-unfinished", type=int, metavar="SECONDS", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.hook:
        hook(args.repo, args.setup_unfinished)
        return 0
    if args.fix:
        return fix(args.repo)
    report = check(args.repo)
    if report.unreadable:
        print(report.unreadable)
        return 1
    if not report.gaps:
        print(
            "The T3 setup is complete."
            if report.settings is not None
            else f"No T3 settings file at `{settings_path()}`."
        )
        return 0
    print("The T3 setup lacks:")
    for gap in report.gaps:
        print(f"- {gap.text}{' [fix: --fix]' if gap.fixable else ''}")
    print(f"The steps: {DOCS}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
