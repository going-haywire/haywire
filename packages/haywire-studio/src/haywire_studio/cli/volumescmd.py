"""``haywire volumes`` — define where named volumes live on this machine.

Volumes are stored in ``~/.haywire/volumes.toml`` (see :mod:`haywire.core.volumes`).
``list`` works without a workspace root: the ``project`` volume then shows as
undefined, because the CLI entry never sets one.

Named ``volumescmd`` to match the other ``*cmd`` modules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from haywire.core.volumes import get_volume_store, list_volumes


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("volumes", help="List, define or remove named volume locations")
    actions = parser.add_subparsers(dest="volumes_command", required=True)

    show = actions.add_parser("list", help="Show every volume and where it points")
    show.set_defaults(handler=_list)

    define = actions.add_parser("set", help="Point a volume at a folder")
    define.add_argument("name", help="Volume name (lowercase letters, digits, '_' and '-')")
    define.add_argument("folder", help="Folder the volume points at (made absolute; not created)")
    define.set_defaults(handler=_set)

    drop = actions.add_parser("remove", help="Forget a volume's configured location")
    drop.add_argument("name", help="Volume name")
    drop.set_defaults(handler=_remove)


def _list(args: argparse.Namespace) -> int:
    for status in list_volumes():
        location = str(status.location) if status.location is not None else "-"
        line = f"{status.name}  {status.source}  {location}"
        if status.location is not None and not status.exists:
            line += "  (missing)"
        print(line)
    return 0


def _set(args: argparse.Namespace) -> int:
    folder = Path(args.folder).expanduser()
    if not folder.is_absolute():
        folder = Path.cwd() / folder
    try:
        get_volume_store().set(args.name, folder)
    except (ValueError, TypeError, OSError) as exc:
        # ValueError also covers the TOML parser's decode errors on a malformed file.
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"{args.name} -> {folder}")
    return 0


def _remove(args: argparse.Namespace) -> int:
    try:
        removed = get_volume_store().remove(args.name)
    except (ValueError, TypeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not removed:
        print(f"error: no configured volume named {args.name!r}", file=sys.stderr)
        return 1
    print(f"removed {args.name}")
    return 0
