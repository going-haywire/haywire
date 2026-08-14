"""Registry-key rewriting inside saved graphs.

Name-based and fully recursive. Measured across the repo's 8 graphs there are
13,242 ``registry_key`` + 2,893 ``widget_key`` + 8 ``chain_adapter_keys``
values, and they sit at many different depths — inside every port of every
node, not at a handful of fixed paths. Graph-groups will nest whole graphs
inside nodes, so depth is unbounded by design.

Matching by field name is safe *for these fields specifically* because the
key grammar is unambiguous: all 16,143 real values match
``<dist>:<kind>[:<sub>]:<Name>``. A value starting ``<old-dist>:`` in one of
these fields is certainly a registry key, never a coincidence. The same is
NOT true of a bare ``name`` field, which is why ``library.name``,
``library.module_name``, ``library.folder_path``, and ``identity.module``
each keep a position-scoped rule instead of a blind substring replace — a
blind replace would also touch user prose that happens to mention the old
name, or a DIFFERENT library whose name merely contains this one as a
substring (``haybale-testing`` inside ``haybale-testing-extras``).

All four are write-only telemetry — ``graph/base.py``'s loader reads only
``library.name`` and ``library.version`` on load, never these — so this
module rewrites them purely for hygiene: a graph opened for a quick look
should not show a stale path or module name. ``library.folder_path`` gets
the narrowest treatment of the four: it is an absolute filesystem path, so
only its own ``.../<old_dist>/<old_module>`` tail is rewritten (workspace
root untouched), and if that exact tail isn't present — the path was
captured on a different machine, or the library directory was moved by
something other than this rename — it is reported as drift instead of
guessing at a rewrite that might point at nothing on disk.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .discovery import find_graph_files
from .model import FileChange, Occurrence

#: Fields whose value is a single registry key.
KEY_FIELDS = frozenset({"registry_key", "widget_key"})

#: Fields whose value is a list of registry keys.
LIST_KEY_FIELDS = frozenset({"chain_adapter_keys"})

#: ``<dist>:<kind>:<Name>`` with an optional extra kind segment (themes use
#: ``<dist>:theme:<type>:<Name>``). Verified against all 16,143 real values.
_KEY_GRAMMAR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9_]+){2,3}$")


def is_registry_key(value: str) -> bool:
    """True if *value* is shaped like a registry key."""
    return bool(_KEY_GRAMMAR.match(value))


def _rewrite(value: object, old: str, new: str) -> tuple[object, int]:
    """Rewrite one key value if it belongs to *old*. Colon-scoped, so
    ``haybale-foo`` never matches ``haybale-foobar``, and grammar-guarded, so
    prose parked in a key field is left alone."""
    if not isinstance(value, str):
        return value, 0
    if not value.startswith(old + ":") or not is_registry_key(value):
        return value, 0
    return new + value[len(old) :], 1


def _rewrite_module(value: object, old_module: str, new_module: str) -> tuple[object, int]:
    """Rewrite a dotted-module-shaped value (``identity.module``): exact
    match, or ``<old_module>.<rest>`` for a submodule. Never a bare
    substring match — ``haybale_testing_extras`` must not match
    ``haybale_testing``."""
    if not isinstance(value, str):
        return value, 0
    if value == old_module:
        return new_module, 1
    if value.startswith(old_module + "."):
        return new_module + value[len(old_module) :], 1
    return value, 0


def _rewrite_folder_path(
    value: object, old_dist: str, old_module: str, new_dist: str, new_module: str
) -> tuple[object, int]:
    """Rewrite ``library.folder_path``'s ``.../<old_dist>/<old_module>``
    tail. The workspace-root prefix is preserved untouched — only the two
    path segments that are actually this library's own name are rewritten,
    never a blind substring replace across the whole path."""
    if not isinstance(value, str):
        return value, 0
    suffix = f"/{old_dist}/{old_module}"
    if value.endswith(suffix):
        return value[: -len(suffix)] + f"/{new_dist}/{new_module}", 1
    return value, 0


def _walk(
    node: object,
    old: str,
    new: str,
    needles: tuple[str, ...],
    leftovers: list[str],
    trail: str = "",
    in_library: bool = False,
    in_identity: bool = False,
    old_module: str | None = None,
    new_module: str | None = None,
) -> int:
    """Recurse the whole tree once: rewrite key fields where they appear,
    and record a drift hit for every OTHER string containing a needle.

    A single pass, not two, is required for correctness: a field the walker
    rewrites (``registry_key``, ``widget_key``, ``chain_adapter_keys``, the
    position-scoped ``library.name``/``library.module_name``/
    ``library.folder_path``/``identity.module``) legitimately contains
    ``old`` both before and after rewriting is decided — scanning either
    snapshot in isolation, without knowing which fields the walker claims,
    cannot tell "a field the walker is about to fix" apart from "a field
    nothing touches". Only a walk that makes both decisions together gets
    this right, including the case where *new* itself contains *old* as a
    substring (e.g. renaming ``haybale-testing`` to ``haybale-testing2``,
    where the rewritten value still contains the old needle).

    Module-name rewriting (``old_module``/``new_module``) is optional: a
    caller that doesn't supply it gets the old behaviour unchanged
    (distribution-name rewriting only, module-shaped fields left as drift).
    """
    count = 0

    if isinstance(node, dict):
        for key, value in node.items():
            child_trail = f"{trail}.{key}" if trail else key
            if key in KEY_FIELDS:
                node[key], hit = _rewrite(value, old, new)
                count += hit
                # _rewrite declines a value that isn't a matching registry
                # key (lookalike prefix, or a grammar-guard miss) — that's
                # exactly the case the drift report exists to surface.
                if not hit and isinstance(value, str) and any(needle in value for needle in needles):
                    leftovers.append(child_trail)
            elif key in LIST_KEY_FIELDS and isinstance(value, list):
                for i, item in enumerate(value):
                    value[i], hit = _rewrite(item, old, new)
                    count += hit
                    if not hit and isinstance(item, str) and any(needle in item for needle in needles):
                        leftovers.append(f"{child_trail}[{i}]")
            elif key == "name" and in_library and value == old:
                # Position-scoped: only the library block's own name. A bare
                # `name` anywhere else is a graph/port/user value.
                node[key] = new
                count += 1
            elif key == "module_name" and in_library and old_module is not None and new_module is not None:
                node[key], hit = _rewrite_module(value, old_module, new_module)
                count += hit
                if not hit and isinstance(value, str) and any(needle in value for needle in needles):
                    leftovers.append(child_trail)
            elif key == "folder_path" and in_library and old_module is not None and new_module is not None:
                node[key], hit = _rewrite_folder_path(value, old, old_module, new, new_module)
                count += hit
                if not hit and isinstance(value, str) and any(needle in value for needle in needles):
                    leftovers.append(child_trail)
            elif key == "module" and in_identity and old_module is not None and new_module is not None:
                node[key], hit = _rewrite_module(value, old_module, new_module)
                count += hit
                if not hit and isinstance(value, str) and any(needle in value for needle in needles):
                    leftovers.append(child_trail)
            elif isinstance(value, str):
                if any(needle in value for needle in needles):
                    leftovers.append(child_trail)
            else:
                count += _walk(
                    value,
                    old,
                    new,
                    needles,
                    leftovers,
                    child_trail,
                    in_library=(key == "library"),
                    in_identity=(key == "identity"),
                    old_module=old_module,
                    new_module=new_module,
                )

    elif isinstance(node, list):
        for i, item in enumerate(node):
            item_trail = f"{trail}[{i}]"
            if isinstance(item, str):
                if any(needle in item for needle in needles):
                    leftovers.append(item_trail)
            else:
                count += _walk(
                    item,
                    old,
                    new,
                    needles,
                    leftovers,
                    item_trail,
                    in_library=in_library,
                    in_identity=in_identity,
                    old_module=old_module,
                    new_module=new_module,
                )

    return count


def patch_graph_tree(
    data: dict,
    old: str,
    new: str,
    *,
    old_module: str | None = None,
    new_module: str | None = None,
) -> tuple[int, list[str]]:
    """Rewrite every registry key in *data* in place.

    *old*/*new* are distribution names (hyphenated) — always rewritten.
    *old_module*/*new_module* are the underscore-form module names. When
    BOTH are supplied, ``library.module_name``, ``library.folder_path``,
    and ``identity.module`` are also rewritten (position-scoped, never a
    blind substring match — see the module docstring). Supplying only
    ``old_module`` (or neither) leaves those fields unrewritten and reports
    them as drift instead — the widened-reporting-only behaviour this
    function has always had for callers that don't have a module rename in
    hand yet (e.g. a plan-time drift preview before ``new_module`` is
    known).

    Returns ``(replacements, leftover_paths)``.
    """
    needles = (old,) if old_module is None or old_module == old else (old, old_module)
    leftovers: list[str] = []
    rewrite_module = old_module if new_module is not None else None
    count = _walk(data, old, new, needles, leftovers, old_module=rewrite_module, new_module=new_module)
    return count, leftovers


def plan_graphs(
    root: Path,
    old: str,
    new: str,
    *,
    old_module: str | None = None,
    new_module: str | None = None,
) -> tuple[list[FileChange], list[Occurrence]]:
    """Compute graph changes without writing anything."""
    changes: list[FileChange] = []
    drift: list[Occurrence] = []

    for path in find_graph_files(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        count, leftovers = patch_graph_tree(data, old, new, old_module=old_module, new_module=new_module)
        if count:
            changes.append(FileChange(path=path, kind="graph", count=count))
        drift += [Occurrence(path=path, line=0, text=p) for p in leftovers]

    return changes, drift


def apply_graphs(
    changes: list[FileChange],
    old: str,
    new: str,
    *,
    old_module: str | None = None,
    new_module: str | None = None,
) -> None:
    """Rewrite each planned graph on disk. No backups — a clean tree is the
    precondition, so ``git checkout .`` is the rollback."""
    for change in changes:
        data = json.loads(change.path.read_text(encoding="utf-8"))
        patch_graph_tree(data, old, new, old_module=old_module, new_module=new_module)
        change.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
