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

``KeyMapRewriter`` drives the same walk for ``haywire rename --map``: exact
whole-key matches from a key map instead of a distribution prefix.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .discovery import find_graph_files
from .model import FileChange, KeyRename, Occurrence

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


@dataclass(frozen=True)
class _Rules:
    """What one walk rewrites, and which untouched strings it reports as drift.

    *rewrite_key* rewrites one value of a key field and returns ``(value, hits)``.
    *mentions* says whether a string the walk leaves alone still names something
    being renamed. *rewrite_copies* rewrites a dict's descriptive copies of its
    ``registry_key`` before that key is rewritten and returns the fields it
    handled. *dists* and *modules*, each ``(old, new)``, drive the
    position-scoped ``library`` and ``identity`` rules; ``None`` turns them off.
    """

    rewrite_key: Callable[[object], tuple[object, int]]
    mentions: Callable[[str], bool]
    rewrite_copies: Callable[[dict], frozenset[str]] | None = None
    dists: tuple[str, str] | None = None
    modules: tuple[str, str] | None = None


def _walk(
    node: object,
    rules: _Rules,
    leftovers: list[str],
    trail: str = "",
    in_library: bool = False,
    in_identity: bool = False,
) -> int:
    """Recurse the whole tree once: rewrite key fields where they appear,
    and record a drift hit for every OTHER string the rules say still mentions
    the old name.

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
    """
    count = 0

    if isinstance(node, dict):
        claimed = rules.rewrite_copies(node) if rules.rewrite_copies is not None else frozenset()
        for key, value in node.items():
            if key in claimed:
                continue
            child_trail = f"{trail}.{key}" if trail else key
            if key in KEY_FIELDS:
                node[key], hit = rules.rewrite_key(value)
                count += hit
                # A declined value (lookalike prefix, or a grammar-guard miss)
                # is exactly the case the drift report exists to surface.
                if not hit and isinstance(value, str) and rules.mentions(value):
                    leftovers.append(child_trail)
            elif key in LIST_KEY_FIELDS and isinstance(value, list):
                for i, item in enumerate(value):
                    value[i], hit = rules.rewrite_key(item)
                    count += hit
                    if not hit and isinstance(item, str) and rules.mentions(item):
                        leftovers.append(f"{child_trail}[{i}]")
            elif key == "name" and in_library and rules.dists is not None and value == rules.dists[0]:
                # Position-scoped: only the library block's own name. A bare
                # `name` anywhere else is a graph/port/user value.
                node[key] = rules.dists[1]
                count += 1
            elif key == "module_name" and in_library and rules.modules is not None:
                node[key], hit = _rewrite_module(value, *rules.modules)
                count += hit
                if not hit and isinstance(value, str) and rules.mentions(value):
                    leftovers.append(child_trail)
            elif (
                key == "folder_path" and in_library and rules.modules is not None and rules.dists is not None
            ):
                (old_dist, new_dist), (old_module, new_module) = rules.dists, rules.modules
                node[key], hit = _rewrite_folder_path(value, old_dist, old_module, new_dist, new_module)
                count += hit
                if not hit and isinstance(value, str) and rules.mentions(value):
                    leftovers.append(child_trail)
            elif key == "module" and in_identity and rules.modules is not None:
                node[key], hit = _rewrite_module(value, *rules.modules)
                count += hit
                if not hit and isinstance(value, str) and rules.mentions(value):
                    leftovers.append(child_trail)
            elif isinstance(value, str):
                if rules.mentions(value):
                    leftovers.append(child_trail)
            else:
                count += _walk(
                    value,
                    rules,
                    leftovers,
                    child_trail,
                    in_library=(key == "library"),
                    in_identity=(key == "identity"),
                )

    elif isinstance(node, list):
        for i, item in enumerate(node):
            item_trail = f"{trail}[{i}]"
            if isinstance(item, str):
                if rules.mentions(item):
                    leftovers.append(item_trail)
            else:
                count += _walk(
                    item, rules, leftovers, item_trail, in_library=in_library, in_identity=in_identity
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
    rules = _Rules(
        rewrite_key=lambda value: _rewrite(value, old, new),
        mentions=lambda text: any(needle in text for needle in needles),
        dists=(old, new),
        modules=(old_module, new_module) if old_module is not None and new_module is not None else None,
    )
    leftovers: list[str] = []
    count = _walk(data, rules, leftovers)
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


class KeyMapRewriter:
    """Rewrite exact registry keys by a key map, tallying what it changes.

    A key field is rewritten only when its whole value is an ``old`` key of the
    map, so ``haybale-image:type:IMAGE_RGB`` never touches ``IMAGE_RGBA``. In the
    dict that holds a renamed ``registry_key`` (a node's ``identity``, a port's
    ``kwargs``), ``class_name`` and ``registry_id`` follow when they equal the old
    name, and ``module`` follows when the entry names both modules.

    Attributes:
        key_counts: Rewritten keys per ``old`` key.
        key_graphs: Graphs each ``old`` key was found in, filled by ``plan_key_map_graphs``.
        copies: Descriptive copies rewritten.
    """

    def __init__(self, renames: list[KeyRename]) -> None:
        self._by_old = {rename.old: rename for rename in renames}
        self.key_counts: Counter[str] = Counter()
        self.key_graphs: Counter[str] = Counter()
        self.copies = 0
        # An old key named whole, not as the head of a longer key or word.
        alternatives = "|".join(re.escape(old) for old in sorted(self._by_old, key=len, reverse=True))
        self._mention = re.compile(rf"(?<![A-Za-z0-9_.:-])(?:{alternatives})(?![A-Za-z0-9_])")

    def rewrite_key(self, value: object) -> tuple[object, int]:
        """Return the new key for an exact ``old`` key, else *value* unchanged."""
        rename = self._by_old.get(value) if isinstance(value, str) else None
        if rename is None:
            return value, 0
        self.key_counts[rename.old] += 1
        return rename.new, 1

    def mentions(self, text: str) -> bool:
        """Whether *text* names an ``old`` key whole."""
        return bool(self._by_old) and self._mention.search(text) is not None

    def rewrite_copies(self, node: dict) -> frozenset[str]:
        """Rewrite *node*'s copies of its renamed ``registry_key``; return the fields rewritten."""
        key = node.get("registry_key")
        rename = self._by_old.get(key) if isinstance(key, str) else None
        if rename is None:
            return frozenset()
        claimed: set[str] = set()
        for field_name in ("class_name", "registry_id"):
            if node.get(field_name) == rename.old_name:
                node[field_name] = rename.new_name
                claimed.add(field_name)
        if rename.old_module is not None and node.get("module") == rename.old_module:
            node["module"] = rename.new_module
            claimed.add("module")
        self.copies += len(claimed)
        return frozenset(claimed)


def patch_graph_keys(data: dict, rewriter: KeyMapRewriter) -> tuple[int, list[str]]:
    """Rewrite every key of *rewriter*'s map in *data* in place.

    Returns ``(keys_rewritten, leftover_paths)``; *rewriter* accumulates the
    per-key tallies across calls.
    """
    rules = _Rules(
        rewrite_key=rewriter.rewrite_key,
        mentions=rewriter.mentions,
        rewrite_copies=rewriter.rewrite_copies,
    )
    leftovers: list[str] = []
    count = _walk(data, rules, leftovers)
    return count, leftovers


def plan_key_map_graphs(
    root: Path, renames: list[KeyRename]
) -> tuple[list[FileChange], list[Occurrence], KeyMapRewriter]:
    """Compute the key map's graph changes under *root* without writing anything.

    Returns ``(changes, drift, rewriter)``; *rewriter* holds the tallies.
    """
    rewriter = KeyMapRewriter(renames)
    changes: list[FileChange] = []
    drift: list[Occurrence] = []

    for path in find_graph_files(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        before = Counter(rewriter.key_counts)
        count, leftovers = patch_graph_keys(data, rewriter)
        if count:
            changes.append(FileChange(path=path, kind="graph", count=count))
        rewriter.key_graphs.update(set(rewriter.key_counts - before))
        drift += [Occurrence(path=path, line=0, text=p) for p in leftovers]

    return changes, drift, rewriter


def apply_key_map_graphs(changes: list[FileChange], renames: list[KeyRename]) -> None:
    """Rewrite each planned graph on disk by the key map."""
    rewriter = KeyMapRewriter(renames)
    for change in changes:
        text = change.path.read_text(encoding="utf-8")
        data = json.loads(text)
        patch_graph_keys(data, rewriter)
        # Keep the file's own escaping, so every value the map doesn't touch stays byte-identical.
        change.path.write_text(json.dumps(data, indent=2, ensure_ascii=text.isascii()), encoding="utf-8")
