"""``haywire init`` — scaffold a new haywire project."""

from __future__ import annotations

import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("init", help="Create a new haywire project")
    parser.add_argument(
        "name", nargs="?", help="Project name (leave out with --org-files to refresh the current one)"
    )
    parser.add_argument(
        "--distname",
        help=(
            "Override the scaffolded local library's pip distribution name. "
            "By default it is 'hay-<name>' (any leading hay-/haybale- on "
            "<name> is stripped first, so the result is never doubled) — "
            "this avoids colliding with installed haybale-* marketplace "
            "libraries. Pass --distname to bypass that automatism entirely "
            "and use an exact name instead."
        ),
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip running uv sync after scaffolding",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use editable local sources from this dev repo instead of PyPI",
    )
    parser.add_argument(
        "--org-files",
        action="store_true",
        help=(
            "Write a going-haywire library's repository files: the agent files from core, and the "
            "CI callers from going-haywire/.github when missing. With a name, into the new project's "
            "first commit; without one, refreshed in the project of the current folder"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the project structure that would be generated and create nothing",
    )
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    if args.name is None:
        if args.org_files:
            return _refresh_org_files()
        print("Error: name the project to create, or pass --org-files to refresh the current one.")
        return 1
    # Imported lazily: init pulls in the scaffolding templates, which no other
    # subcommand needs.
    from haywire_studio.init import (
        InvalidSlugError,
        _distmodule,
        _get_dev_repo_root,
        _resolve_distname,
        _validate_project_name,
        _validate_slug,
        init_project,
        render_scaffold_tree,
    )

    try:
        _validate_project_name(args.name)
        if args.distname is not None:
            _validate_slug(args.distname, "--distname")
    except InvalidSlugError as exc:
        print(f"Error: {exc}")
        return 1

    lib_name = _resolve_distname(args.name, args.distname)
    module_name = _distmodule(lib_name)

    print("The following project structure will be generated:\n")
    print(render_scaffold_tree(args.name, lib_name, module_name))
    if args.dry_run:
        print("Dry run — nothing was created. Re-run without --dry-run to scaffold it.")
        return 0

    dev_repo = _get_dev_repo_root() if args.dev else None
    init_project(
        args.name,
        auto_sync=not args.no_sync,
        dev_repo=dev_repo,
        distname=args.distname,
        org_files=args.org_files,
    )
    return 0


def _refresh_org_files() -> int:
    from pathlib import Path

    from haywire_studio.agents import write_org_files
    from haywire_studio.farmhand.bridge import find_project_root

    project = find_project_root(Path.cwd())
    if not (project / "pyproject.toml").is_file():
        print(f"Error: {project} is not a haywire project (no pyproject.toml).")
        return 1
    try:
        written = write_org_files(project)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1
    for path in written:
        print(f"  {path.relative_to(project)}")
    print("Org files written: review the diff and commit it on a branch.")
    return 0
