"""``haywire init`` — scaffold a new haywire project."""

from __future__ import annotations

import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("init", help="Create a new haywire project")
    parser.add_argument("name", help="Project name")
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
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    # Imported lazily: init pulls in the scaffolding templates, which no other
    # subcommand needs.
    from haywire_studio.init import _get_dev_repo_root, init_project

    dev_repo = _get_dev_repo_root() if args.dev else None
    init_project(args.name, auto_sync=not args.no_sync, dev_repo=dev_repo)
    return 0
