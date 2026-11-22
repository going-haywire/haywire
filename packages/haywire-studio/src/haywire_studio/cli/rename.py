"""``haywire rename`` — rename a project library, or components by a key map, with the studio stopped."""

from __future__ import annotations

import argparse
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "rename",
        help="Rename a project library, or components by a key map (run with studio stopped)",
        usage="haywire rename (OLD_LIBRARY NEW_NAME | --map FILE) [--dry-run] [--verbose]",
    )
    parser.add_argument("old_library", nargs="?", help="Current distribution name, e.g. hay-weather")
    parser.add_argument(
        "new_name", nargs="?", help="New distribution name, taken verbatim, e.g. hay-forecast"
    )
    parser.add_argument(
        "--map",
        type=Path,
        metavar="FILE",
        help="Rename components instead: rewrite the keys a TOML key map lists in every saved graph.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the preflight report and change nothing.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="List every affected file and occurrence instead of counts.",
    )
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    from haywire_studio.packaging.rename import run_key_map_cli, run_rename_cli

    if args.map is not None:
        if args.old_library is not None:
            print("haywire rename: give either --map FILE or OLD_LIBRARY NEW_NAME, not both.")
            return 2
        return run_key_map_cli(
            map_path=args.map,
            workspace_root=Path.cwd(),
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    if args.old_library is None or args.new_name is None:
        print("haywire rename: give OLD_LIBRARY NEW_NAME, or --map FILE.")
        return 2
    return run_rename_cli(
        old_library=args.old_library,
        new_name=args.new_name,
        workspace_root=Path.cwd(),
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
