"""``haywire init`` — scaffold a new haywire project."""

from __future__ import annotations

import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("init", help="Create a new haywire project")
    parser.add_argument("name", help="Project name")
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
        "-y",
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt and scaffold immediately",
    )
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
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

    if not args.yes:
        print("The following project structure will be generated:\n")
        print(render_scaffold_tree(args.name, lib_name, module_name))
        reply = input("ok? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted.")
            return 1

    dev_repo = _get_dev_repo_root() if args.dev else None
    init_project(
        args.name,
        auto_sync=not args.no_sync,
        dev_repo=dev_repo,
        distname=args.distname,
    )
    return 0
