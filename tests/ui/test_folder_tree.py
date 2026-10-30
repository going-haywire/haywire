"""Tests for the eager-then-lazy FolderTreeModel."""

import sys
from pathlib import Path

import pytest

from haywire.ui.elements.folder_tree import FolderTreeModel

pytestmark = pytest.mark.unit


def _deep(root: Path) -> Path:
    leaf = root / "a" / "b" / "c" / "d" / "e"
    leaf.mkdir(parents=True)
    (leaf / "deep.txt").write_text("x")
    (root / "top.txt").write_text("x")
    return leaf


def _find(nodes: list[dict], label: str) -> dict:
    return next(n for n in nodes if n["label"] == label)


def test_three_levels_eager_then_sentinel(tmp_path: Path) -> None:
    _deep(tmp_path)
    model = FolderTreeModel(tmp_path)
    a = _find(model.nodes, "a")
    b = _find(a["children"], "b")
    c = _find(b["children"], "c")
    assert [n["label"] for n in c["children"]] == ["Click to load children"]
    sentinel = c["children"][0]
    assert model.is_sentinel(sentinel["id"])
    assert sentinel["id"] == f"{tmp_path / 'a' / 'b' / 'c'}::__load_more__"
    assert not model.is_sentinel(c["id"])


def test_expand_sentinel_loads_three_more_levels(tmp_path: Path) -> None:
    _deep(tmp_path)
    model = FolderTreeModel(tmp_path)
    c_id = str(tmp_path / "a" / "b" / "c")
    assert model.expand_sentinel(c_id) is True
    c = model.node(c_id)
    assert c is not None
    d = _find(c["children"], "d")
    e = _find(d["children"], "e")
    assert [n["label"] for n in e["children"]] == ["deep.txt"]
    # Already loaded: expanding again reloads the same subtree and still reports success.
    assert model.expand_sentinel(c_id) is True
    assert model.node(str(tmp_path / "a" / "b" / "c" / "d" / "e")) is not None


def test_expand_unknown_or_non_dir_returns_false(tmp_path: Path) -> None:
    _deep(tmp_path)
    model = FolderTreeModel(tmp_path)
    assert model.expand_sentinel(str(tmp_path / "nope")) is False
    assert model.expand_sentinel(str(tmp_path / "top.txt")) is False
    assert model.node(str(tmp_path / "nope")) is None


def test_show_files_false_lists_only_folders(tmp_path: Path) -> None:
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "inner.txt").write_text("x")
    (tmp_path / "file.txt").write_text("x")
    model = FolderTreeModel(tmp_path, show_files=False)
    assert [n["label"] for n in model.nodes] == ["dir"]
    assert model.nodes[0]["children"] == []


def test_excluded_and_dot_dirs_skipped_haywire_kept(tmp_path: Path) -> None:
    for name in ("node_modules", ".git", ".hidden", ".haywire", "keep"):
        (tmp_path / name).mkdir()
    (tmp_path / ".dotfile").write_text("x")
    model = FolderTreeModel(tmp_path, exclude_dirs=frozenset({"node_modules", ".git"}))
    assert sorted(n["label"] for n in model.nodes) == [".haywire", "keep"]


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlinked_dir_is_leaf(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "f.txt").write_text("x")
    (tmp_path / "link").symlink_to(target, target_is_directory=True)
    model = FolderTreeModel(tmp_path)
    link = _find(model.nodes, "link")
    assert "children" not in link


def test_permission_error_yields_no_children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "locked").mkdir()
    real_iterdir = Path.iterdir

    def fake_iterdir(self: Path):
        if self.name == "locked":
            raise PermissionError("denied")
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)
    model = FolderTreeModel(tmp_path)
    assert _find(model.nodes, "locked")["children"] == []


def test_rebuild_resets_sentinels(tmp_path: Path) -> None:
    _deep(tmp_path)
    model = FolderTreeModel(tmp_path)
    c_id = str(tmp_path / "a" / "b" / "c")
    model.expand_sentinel(c_id)
    model.rebuild()
    c = model.node(c_id)
    assert c is not None
    assert model.is_sentinel(c["children"][0]["id"])


def test_extensions_limit_files_ignoring_case(tmp_path: Path) -> None:
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "inner.png").write_text("x")
    (tmp_path / "a.PNG").write_text("x")
    (tmp_path / "b.txt").write_text("x")
    model = FolderTreeModel(tmp_path, extensions=frozenset({".png"}))
    assert [n["label"] for n in model.nodes] == ["dir", "a.PNG"]
    assert [n["label"] for n in model.nodes[0]["children"]] == ["inner.png"]
