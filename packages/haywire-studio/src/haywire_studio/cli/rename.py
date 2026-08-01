"""``haywire rename`` — rename a project library, with the studio stopped."""

from __future__ import annotations

import argparse
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("rename", help="Rename a project library (run with studio stopped)")
    parser.add_argument("old_library", help="Current library dir, e.g. haybale-foo")
    parser.add_argument("new_name", help="New name (without the haybale- prefix)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the rename. Without this flag, only a dry-run preview is printed.",
    )
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    from haywire_studio.packaging.rename import run_rename_cli

    return run_rename_cli(
        old_library=args.old_library,
        new_name=args.new_name,
        workspace_root=Path.cwd(),
        apply=args.apply,
    )
