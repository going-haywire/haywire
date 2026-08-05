"""``haywire share`` — publish the whole project."""

from __future__ import annotations

import argparse
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "share",
        help="Publish this project: bump every barn library, regenerate docs, "
        "rebuild marketstall.toml, commit, tag, and push",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive full run using flag-supplied answers. Requires --bump.",
    )
    parser.add_argument(
        "--bump",
        type=str,
        default=None,
        metavar="VERSION",
        help="Version to publish: patch|minor|major, or an explicit X.Y.Z. Every "
        "barn/* library is set to it (lockstep).",
    )
    parser.add_argument(
        "--message",
        type=str,
        default=None,
        help="Commit message. Defaults to 'chore: share v<version>'.",
    )
    parser.add_argument(
        "--requires-haywire",
        type=str,
        default=None,
        metavar="SPECIFIER",
        help="PEP 440 specifier for the framework this project needs "
        "(e.g. '>=0.0.31', '~=0.0.31'). Written to every barn library's "
        "haywire-core floor AND to the marketstall entry. Omitted: the "
        "declared floor is kept unchanged.",
    )
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    from haywire_studio.packaging.share_cli import run_share_cli

    return run_share_cli(
        repo_root=Path.cwd(),
        yes=args.yes,
        bump=args.bump,
        message=args.message,
        requires_haywire=args.requires_haywire,
    )
