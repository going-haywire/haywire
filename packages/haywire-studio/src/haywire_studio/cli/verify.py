"""``haywire verify`` — check that every saved graph still resolves."""

from __future__ import annotations

import argparse
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("verify", help="Check that every saved graph's registry keys resolve")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="List every graph checked, not only the failing ones.",
    )
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    from haywire_studio.packaging.verify import run_verify_cli

    return run_verify_cli(workspace_root=Path.cwd(), verbose=args.verbose)
