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
    # No --yes. The command has exactly one mode — non-interactive — so a flag
    # meaning "don't prompt me" describes the only behaviour there is. It also
    # named the wrong thing: the run writes manifests, bumps, commits, tags and
    # pushes, which is "author a release", not "assume yes".
    #
    # The prompt-driven mode it used to switch on is gone with it. Walking a
    # seven-step git-mutating pipeline through input() duplicated every
    # judgement the Share editor makes, divergently, and the terminal is not
    # where anyone wants to answer eleven questions about dependency floors.
    parser.add_argument(
        "--bump",
        type=str,
        default=None,
        metavar="VERSION",
        help="Version to publish: patch|minor|major, or an explicit X.Y.Z. Every "
        "barn/* library is set to it (lockstep). Required unless --dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what a publish would do — preconditions, findings, and the "
        "version it would cut — and write nothing.",
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
        bump=args.bump,
        message=args.message,
        requires_haywire=args.requires_haywire,
        dry_run=args.dry_run,
    )
