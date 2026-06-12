"""Smoke-test that GLOBAL_MARKETPLACE_DIR lives in haybale_marketplace.config."""

import importlib

import pytest


@pytest.mark.unit
def test_global_marketplace_dir_is_haybale_marketplace(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    import haybale_marketplace.config as mp_cfg

    importlib.reload(mp_cfg)

    expected = tmp_path / ".haywire" / "db" / "haybale_marketplace"
    assert mp_cfg.GLOBAL_MARKETPLACE_DIR == expected
