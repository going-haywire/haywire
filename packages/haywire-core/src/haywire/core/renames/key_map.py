"""Key maps: TOML lists of component registry keys, before and after a rename.

A key map is a TOML document of ``[[rename]]`` entries::

    [[rename]]
    old = "haybale-core:type:ArrayType"
    new = "haybale-core:type:ARRAY"
    old_module = "haybale_core.types.array_type"   # optional, with new_module
    new_module = "haybale_core.types.array"

One entry per parameterized family covers every parameterization: ``ArrayType[INT]``
saves its family's key with a nested ``element_type`` recipe.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass

from .graph_keys import is_registry_key

_ENTRY_FIELDS = frozenset({"old", "new", "old_module", "new_module"})


@dataclass(frozen=True)
class KeyRename:
    """One entry of a key map: a component's registry key, before and after.

    *old_module*/*new_module* are dotted module paths, set together when the
    component's module moved; ``None`` leaves a saved ``module`` as it is.
    """

    old: str
    new: str
    old_module: str | None = None
    new_module: str | None = None

    @property
    def old_name(self) -> str:
        """The class name the old key ends in."""
        return self.old.rsplit(":", 1)[1]

    @property
    def new_name(self) -> str:
        """The class name the new key ends in."""
        return self.new.rsplit(":", 1)[1]


@dataclass(frozen=True)
class KeyMapProblem:
    """Why a key map, or one of its entries, cannot be used, and how to fix it."""

    message: str
    remedy: str = ""


def _kind(key: str) -> str:
    """The kind segments of *key*: ``node`` for ``lib:node:X``, ``theme:t`` for ``lib:theme:t:X``."""
    return ":".join(key.split(":")[1:-1])


def parse_key_map(text: str, source: str) -> tuple[list[KeyRename], list[KeyMapProblem]]:
    """Parse and validate one key map document.

    Every problem is reported, not only the first: invalid TOML, no ``[[rename]]``
    entries, an unknown field, a value that isn't a registry key, an entry that
    changes nothing or changes the kind, only one of the two module fields, and
    the problems :func:`check_renames` finds across entries.

    Args:
        text: The TOML document.
        source: Where *text* came from, named in each problem's message.

    Returns:
        ``(renames, problems)``; *renames* is empty when there are problems.
    """
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return [], [KeyMapProblem(message=f"Key map {source} is not valid TOML: {exc}")]

    entries = document.get("rename")
    if not isinstance(entries, list) or not entries:
        return [], [
            KeyMapProblem(
                message=f"Key map {source} has no [[rename]] entries.",
                remedy='[[rename]]\nold = "<dist>:<kind>:<Name>"\nnew = "<dist>:<kind>:<Name>"',
            )
        ]

    problems: list[KeyMapProblem] = []
    renames: list[KeyRename] = []
    for number, entry in enumerate(entries, start=1):
        where = f"[[rename]] #{number}"
        if not isinstance(entry, dict):
            problems.append(KeyMapProblem(message=f"{where} is not a table."))
            continue
        unknown = sorted(set(entry) - _ENTRY_FIELDS)
        if unknown:
            problems.append(
                KeyMapProblem(
                    message=f"{where} has unknown field(s): {', '.join(unknown)}.",
                    remedy="Allowed: old, new, old_module, new_module.",
                )
            )
            continue
        old, new = entry.get("old"), entry.get("new")
        bad = [
            f"{name} = {value!r}"
            for name, value in (("old", old), ("new", new))
            if not isinstance(value, str) or not is_registry_key(value)
        ]
        if bad:
            problems.append(
                KeyMapProblem(
                    message=f"{where}: not a registry key: {'; '.join(bad)}.",
                    remedy='Write the whole key, e.g. "haybale-core:node:BeginPlayNode".',
                )
            )
            continue
        assert isinstance(old, str) and isinstance(new, str)
        if old == new:
            problems.append(KeyMapProblem(message=f"{where}: old and new are both {old!r}."))
            continue
        if _kind(old) != _kind(new):
            problems.append(KeyMapProblem(message=f"{where}: {old!r} → {new!r} changes the kind."))
            continue
        old_module, new_module = entry.get("old_module"), entry.get("new_module")
        if (old_module is None) != (new_module is None):
            problems.append(
                KeyMapProblem(message=f"{where}: set both old_module and new_module, or neither.")
            )
            continue
        if old_module is not None and not (isinstance(old_module, str) and isinstance(new_module, str)):
            problems.append(KeyMapProblem(message=f"{where}: old_module and new_module must be strings."))
            continue
        renames.append(KeyRename(old=old, new=new, old_module=old_module, new_module=new_module))

    problems += check_renames(renames)
    return ([] if problems else renames), problems


def check_renames(renames: list[KeyRename]) -> list[KeyMapProblem]:
    """Find what makes *renames* unusable as one map: the same ``old`` twice, and chains.

    A chain is an entry whose ``new`` is another entry's ``old``; one pass rewrites
    each key once, so it would not be followed.
    """
    problems: list[KeyMapProblem] = []
    olds = [rename.old for rename in renames]
    for old in sorted({old for old in olds if olds.count(old) > 1}):
        problems.append(KeyMapProblem(message=f"{old!r} is renamed more than once."))
    for rename in renames:
        if rename.new in olds:
            problems.append(
                KeyMapProblem(
                    message=f"Chain: {rename.old!r} → {rename.new!r}, which is renamed again.",
                    remedy="Map each old key straight to its final key.",
                )
            )
    return problems
