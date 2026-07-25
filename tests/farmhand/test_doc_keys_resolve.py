"""Every ``lib:kind:id`` registry key hand-authored in the docs must resolve.

The component canons and guides carry source-file links whose *text* is the
component's registry key (e.g. ``[example:node:MathOP](...)`` — planted by the
docs-bake work). Those keys are content, not derived, so they can drift: a
rename, a moved component, or a typo leaves a dead key that ships to the agent
over Farmhand. This test loads every barn library and asserts each key resolves
to a real registered class, failing the gate on drift.

It walks the *source* ``docs/`` (not the baked mirror) so the keys are checked
at their authored location — the baked links have already been rewritten to
GitHub URLs and no longer contain the raw key/path pairing.
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
_KINDS = "node|type|adapter|widget|skin|setting|state|theme|panel|editor"

# The id tail of a key. Themes carry a 4-part key
# (``lib:theme:{workbench|node}:ClassName``), so allow an optional
# ``{workbench|node}:`` segment before the final class-name token.
_ID_TAIL = r"(?:(?:workbench|node):)?[A-Za-z_][A-Za-z0-9_]*"

# A keyed source link: [`lib:kind:id`](target) or [lib:kind:id](target). The
# key sits in the link *text*; the target is a relative source-file path.
_KEY_LINK_RE = re.compile(r"\[`?([a-z_][a-z0-9_]*:(?:" + _KINDS + r"):" + _ID_TAIL + r")`?\]\((\.\.[^)]*)\)")


def _iter_doc_keys() -> list[tuple[Path, int, str]]:
    """Yield (file, line-number, key) for every keyed source link in docs/."""
    found: list[tuple[Path, int, str]] = []
    for md in sorted(DOCS_ROOT.rglob("*.md")):
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), start=1):
            for m in _KEY_LINK_RE.finditer(line):
                found.append((md, lineno, m.group(1)))
    return found


def test_doc_source_keys_exist() -> None:
    """Sanity: the extractor finds the planted keys (guards against a broken regex)."""
    keys = {key for _f, _ln, key in _iter_doc_keys()}
    assert "example:node:MathOP" in keys
    assert "testing:setting:TestingSettings" in keys
    assert len(keys) >= 15


def test_every_doc_key_resolves(library_system) -> None:
    """Each hand-authored ``lib:kind:id`` in docs resolves to a registered class."""
    failures: list[str] = []
    for md, lineno, key in _iter_doc_keys():
        if library_system.lookup_component_class(key) is None:
            rel = md.relative_to(REPO_ROOT).as_posix()
            failures.append(f"{rel}:{lineno}: unresolved registry key '{key}'")

    assert not failures, "Dead registry keys in docs:\n" + "\n".join(sorted(failures))
