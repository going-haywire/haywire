"""``haywire deps`` — dependency-manifest tooling."""

from __future__ import annotations

import argparse
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("deps", help="Dependency-manifest tooling")
    deps_subparsers = parser.add_subparsers(dest="deps_command")
    deps_subparsers.add_parser(
        "check",
        help="Report dependency-manifest drift for every barn/* library (CI-shaped, never writes)",
    )
    # Bare `haywire deps` is a usage error, not a default action — print the
    # subcommand's own help rather than the top-level parser's.
    parser.set_defaults(handler=_run, _parser=parser)


def _run(args: argparse.Namespace) -> int:
    from haywire_studio.packaging.deps import run_deps_check_cli

    if args.deps_command == "check":
        return run_deps_check_cli(Path.cwd())

    args._parser.print_help()
    return 2
