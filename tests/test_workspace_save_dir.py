# tests/test_workspace_save_dir.py
import pytest


@pytest.mark.unit
def test_default_save_dir_prefers_graphs_subdir(tmp_path):
    from haywire.core.workspace import default_save_dir

    (tmp_path / "graphs").mkdir()
    assert default_save_dir(tmp_path) == tmp_path / "graphs"


@pytest.mark.unit
def test_default_save_dir_falls_back_to_root(tmp_path):
    from haywire.core.workspace import default_save_dir

    assert default_save_dir(tmp_path) == tmp_path  # no graphs/ subdir
