"""Component registry-key renames: key maps, the maps a release bundles, and the graph rewrite.

Each release that renames components ships its key maps here, one TOML file per
distribution under ``<release>/``. Graph pre-hydration applies them to every file
saved before that release (format v6 for 0.6); ``haywire rename --map`` applies a
map to the graph files on disk.
"""

from __future__ import annotations

import functools
from importlib import resources

from .graph_keys import (
    KEY_FIELDS,
    LIST_KEY_FIELDS,
    TABLE_KEY_FIELDS,
    KeyMapRewriter,
    is_registry_key,
    patch_graph_keys,
    patch_graph_tree,
    rewrite_graph_keys,
)
from .key_map import KeyMapProblem, KeyRename, check_renames, parse_key_map

__all__ = [
    "KEY_FIELDS",
    "LIST_KEY_FIELDS",
    "TABLE_KEY_FIELDS",
    "KeyMapProblem",
    "KeyMapRewriter",
    "KeyRename",
    "bundled_renames",
    "check_renames",
    "is_registry_key",
    "load_bundled_key_maps",
    "parse_key_map",
    "patch_graph_keys",
    "patch_graph_tree",
    "rewrite_graph_keys",
]


def load_bundled_key_maps(release: str) -> tuple[list[KeyRename], list[KeyMapProblem]]:
    """Parse every key map bundled for *release* as one map.

    Returns:
        ``(renames, problems)``, as :func:`parse_key_map` does; the problems include
        an ``old`` key renamed in two files and a chain across files.
    """
    folder = resources.files(__name__).joinpath(release)
    renames: list[KeyRename] = []
    problems: list[KeyMapProblem] = []
    for entry in sorted(folder.iterdir(), key=lambda item: item.name):
        if not entry.name.endswith(".toml"):
            continue
        found, wrong = parse_key_map(entry.read_text(encoding="utf-8"), f"{release}/{entry.name}")
        renames += found
        problems += wrong
    problems += check_renames(renames)
    return ([] if problems else renames), problems


# Package data, fixed for the life of the process: parsed once.
@functools.cache
def bundled_renames(release: str) -> tuple[KeyRename, ...]:
    """The renames bundled for *release*.

    Raises:
        RuntimeError: A bundled map is malformed, which only a bug in this package can cause.
    """
    renames, problems = load_bundled_key_maps(release)
    if problems:
        raise RuntimeError(
            f"Bundled key maps for {release} are malformed: " + "; ".join(p.message for p in problems)
        )
    return tuple(renames)
