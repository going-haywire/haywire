"""``haywire volumes`` — the volumes on this machine and where each one lives.

Volumes are stored in ``~/.haywire/volumes.toml`` (see :mod:`haywire.core.volumes`).
``set``, ``remove`` and ``reset`` take a volume key, or its name part when exactly
one volume has that name. ``remove`` deletes only user volumes; ``reset`` sets a
library's volume back to its suggested location. Folders are made absolute against
the current directory and are never created. ``list`` works without a workspace root: the project volume then
shows no location, because the CLI entry never sets one.

Named ``volumescmd`` to match the other ``*cmd`` modules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from haywire.core.volumes import (
    PROJECT_KEY,
    VOLUME_KEY_RE,
    get_volume_store,
    list_volumes,
    user_volume_key,
    volume_name,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("volumes", help="List, add, change or delete volumes")
    actions = parser.add_subparsers(dest="volumes_command", required=True)

    show = actions.add_parser("list", help="Show every volume and where it points")
    show.set_defaults(handler=_list)

    add = actions.add_parser("add", help="Add a volume (key user:volume:<name>)")
    add.add_argument("name", help="Volume name (lowercase letters, digits, '_' and '-')")
    add.add_argument("folder", help="Folder the volume points at (made absolute; not created)")
    add.add_argument("--label", default="", help="Label shown for the volume (default: the name)")
    add.add_argument("--description", default="", help="Description shown for the volume")
    add.set_defaults(handler=_add)

    change = actions.add_parser("set", help="Change a volume's location, label or description")
    change.add_argument("volume", help="Volume key, or its name when unique")
    change.add_argument("--location", help="Folder the volume points at (made absolute; not created)")
    change.add_argument("--label", help="Label shown for the volume")
    change.add_argument("--description", help="Description shown for the volume")
    change.set_defaults(handler=_set)

    drop = actions.add_parser("remove", help="Delete a volume you added (key user:volume:<name>)")
    drop.add_argument("volume", help="Volume key, or its name when unique")
    drop.set_defaults(handler=_remove)

    reset = actions.add_parser("reset", help="Set a library's volume back to its suggested location")
    reset.add_argument("volume", help="Volume key, or its name when unique")
    reset.set_defaults(handler=_reset)


def _list(args: argparse.Namespace) -> int:
    for status in list_volumes():
        location = str(status.location) if status.location is not None else "-"
        line = f"{status.key}  {status.label}  {location}"
        if status.location is not None and not status.exists:
            line += "  (missing)"
        print(line)
    return 0


def _folder(text: str) -> Path:
    folder = Path(text).expanduser()
    return folder if folder.is_absolute() else Path.cwd() / folder


def _error(message: object) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _key(text: str) -> str:
    """Return the key *text* names: itself if it is a key, else the one volume with that name.

    Raises:
        ValueError: If no volume, or more than one, has that name.
    """
    if text == PROJECT_KEY or VOLUME_KEY_RE.match(text):
        return text
    matches = [s.key for s in list_volumes() if volume_name(s.key) == text]
    if not matches:
        raise ValueError(f"There is no volume {text!r}")
    if len(matches) > 1:
        raise ValueError(f"{text!r} names several volumes; use one of: {', '.join(matches)}")
    return matches[0]


def _add(args: argparse.Namespace) -> int:
    folder = _folder(args.folder)
    try:
        key = user_volume_key(args.name)
        get_volume_store().add(
            key, label=args.label or args.name, description=args.description, location=folder
        )
    except (ValueError, OSError) as exc:
        return _error(exc)
    print(f"{key} -> {folder}")
    return 0


def _set(args: argparse.Namespace) -> int:
    if args.location is None and args.label is None and args.description is None:
        return _error("nothing to change: give --location, --label or --description")
    location = _folder(args.location) if args.location is not None else None
    try:
        key = _key(args.volume)
        get_volume_store().update(key, label=args.label, description=args.description, location=location)
    except (ValueError, OSError) as exc:
        return _error(exc)
    print(f"updated {key}")
    return 0


def _remove(args: argparse.Namespace) -> int:
    try:
        key = _key(args.volume)
        removed = get_volume_store().remove(key)
    except (ValueError, OSError) as exc:
        return _error(exc)
    if not removed:
        return _error(f"There is no volume {key!r}")
    print(f"removed {key}")
    return 0


def _reset(args: argparse.Namespace) -> int:
    try:
        key = _key(args.volume)
        location = get_volume_store().reset(key)
    except (ValueError, OSError) as exc:
        return _error(exc)
    print(f"{key} -> {location}")
    return 0
