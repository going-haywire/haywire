"""Test that the ambient workspace_root global behaves like its peers."""

from pathlib import Path

import pytest


def test_get_raises_before_set():
    import haywire.core.di.context as ctx_mod

    ctx_mod._workspace_root = None

    from haywire.core.di.context import get_workspace_root

    with pytest.raises(RuntimeError, match="workspace_root not set"):
        get_workspace_root()


def test_set_then_get_returns_path():
    from haywire.core.di.context import set_workspace_root, get_workspace_root

    p = Path("/tmp/some-workspace")
    set_workspace_root(p)
    assert get_workspace_root() == p


def test_set_str_path_normalises_to_path():
    """Accepts str OR Path; always returns Path."""
    from haywire.core.di.context import set_workspace_root, get_workspace_root

    set_workspace_root("/tmp/another")
    assert get_workspace_root() == Path("/tmp/another")
    assert isinstance(get_workspace_root(), Path)
