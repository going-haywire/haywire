"""Every ``lib:kind:id`` registry key hand-authored in the docs must resolve.

The component canons and guides declare a ``registry_key: `lib:kind:id`` `` line
next to each embedded source snippet (per doc-authoring.md §3a.4). Those keys
are content, not derived, so they can drift: a rename, a moved component, or a
typo leaves a dead key that ships to the agent over Farmhand. This test loads
every barn library and asserts each key resolves to a real registered class,
failing the gate on drift.

It walks the *source* ``docs/`` (not the baked mirror) so the keys are checked
at their authored location.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"

# The component kinds that appear as the middle token of a registry key. Only
# match these so prose colons (e.g. "Note: see X") aren't mistaken for keys.
# Deliberately excludes "library" — Library classes print a `lib:library:Library`
# line for readability, but there's no LIBRARY kind in _REGISTRY_GETTERS
# (packages/haywire-core/src/haywire/core/di/config.py), so it isn't a
# resolvable component key.
_KINDS = "node|type|adapter|widget|skin|setting|state|theme|panel|editor|farmhand"

# The id tail of a key — a plain class-name token. Themes used to carry a
# 4-part key (``lib:theme:{workbench|node}:ClassName``); the collapse to one
# Theme class (workbench vs node is now class_identity.theme_type, not a key
# segment) made every registry key uniformly 3-part, so no special-casing
# is needed here any more.
_ID_TAIL = r"[A-Za-z_][A-Za-z0-9_]*"

# A keyed source declaration: `` `lib:kind:id` `` appearing after "registry_key:"
# (plain text, per doc-authoring.md §3a.4 — not a markdown link; source files
# live outside docs_dir and can't be linked as doc-links). The lib segment is
# a distribution name (e.g. haybale-example), so it may contain hyphens as
# well as underscores.
_KEY_LINK_RE = re.compile(r"registry_key:\s*`?([a-z_][a-z0-9_-]*:(?:" + _KINDS + r"):" + _ID_TAIL + r")`?")


def _iter_doc_keys() -> list[tuple[Path, int, str]]:
    """Yield (file, line-number, key) for every declared registry key in docs/."""
    found: list[tuple[Path, int, str]] = []
    for md in sorted(DOCS_ROOT.rglob("*.md")):
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), start=1):
            for m in _KEY_LINK_RE.finditer(line):
                found.append((md, lineno, m.group(1)))
    return found


def test_doc_source_keys_exist() -> None:
    """Sanity: the extractor finds the planted keys (guards against a broken regex)."""
    keys = {key for _f, _ln, key in _iter_doc_keys()}
    assert "haybale-example:node:MathOP" in keys
    assert "haybale-testing:setting:TestingSettings" in keys
    assert len(keys) >= 15


def test_every_doc_key_resolves(library_system) -> None:
    """Each hand-authored ``lib:kind:id`` in docs resolves to a registered class."""
    failures: list[str] = []
    for md, lineno, key in _iter_doc_keys():
        if library_system.lookup_component_class(key) is None:
            rel = md.relative_to(REPO_ROOT).as_posix()
            failures.append(f"{rel}:{lineno}: unresolved registry key '{key}'")

    assert not failures, "Dead registry keys in docs:\n" + "\n".join(sorted(failures))
