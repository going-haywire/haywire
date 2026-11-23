"""Which docs tree the studio and the Farmhand bridge serve: packaged, baked, or the raw monorepo docs."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from haywire.core.docs.tree import resolve_docs_root

MARKER = Path("components") / "nodes" / "node-canon.md"


def _tree(root: Path, mtime: float) -> Path:
    page = root / MARKER
    page.parent.mkdir(parents=True)
    page.write_text("# Nodes\n")
    os.utime(page, (mtime, mtime))
    return root


@pytest.fixture
def checkout(tmp_path):
    pkg = tmp_path / "packages" / "haywire-core" / "src" / "haywire"
    pkg.mkdir(parents=True)
    return tmp_path, pkg


def test_a_fresh_bake_wins_over_the_raw_docs(checkout):
    root, pkg = checkout
    _tree(root / "docs", 1000)
    baked = _tree(pkg / "_baked_docs", 2000)
    assert resolve_docs_root(pkg, pkg / "core" / "docs" / "tree.py") == baked


def test_a_stale_bake_gives_way_to_the_raw_docs(checkout):
    root, pkg = checkout
    raw = _tree(root / "docs", 3000)
    _tree(pkg / "_baked_docs", 2000)
    assert resolve_docs_root(pkg, pkg / "core" / "docs" / "tree.py") == raw


def test_the_packaged_docs_win_in_a_wheel(checkout):
    root, pkg = checkout
    _tree(root / "docs", 3000)
    packaged = _tree(pkg / "docs", 1000)
    assert resolve_docs_root(pkg, pkg / "core" / "docs" / "tree.py") == packaged


def test_without_any_tree_it_says_so(checkout):
    _, pkg = checkout
    with pytest.raises(FileNotFoundError):
        resolve_docs_root(pkg, pkg / "core" / "docs" / "tree.py")
