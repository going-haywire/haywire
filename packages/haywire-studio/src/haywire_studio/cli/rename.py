"""``haywire rename`` — rename a project library, with the studio stopped."""

from __future__ import annotations

import argparse
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("rename", help="Rename a project library (run with studio stopped)")
    parser.add_argument("old_library", help="Current distribution name, e.g. hay-weather")
    parser.add_argument("new_name", help="New distribution name, taken verbatim, e.g. hay-forecast")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the rename. Without this flag, only a preflight report is printed.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="List every affected file and occurrence instead of counts.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts (for scripting).",
    )
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    from haywire_studio.packaging.rename import run_rename_cli

    return run_rename_cli(
        old_library=args.old_library,
        new_name=args.new_name,
        workspace_root=Path.cwd(),
        apply=args.apply,
        verbose=args.verbose,
        assume_yes=args.yes,
    )
