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


# ─────────────────────────────────────────────────────────────────────────────
# The default file is the switching UI.
#
# There is no unsubscribe in the Library Browser, so changing channel means
# hand-editing this file. That makes it the one place a user is guaranteed to
# open — the alternatives have to be legible right there, not in a doc they
# would need to know to look for.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_config(tmp_path, monkeypatch):
    """A reloaded config module rooted at a throwaway home."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    import haybale_marketplace.config as mp_cfg

    importlib.reload(mp_cfg)
    mp_cfg.ensure_marketplace_config()
    return mp_cfg, (mp_cfg.GLOBAL_MARKETPLACE_DIR / "marketplace.toml")


@pytest.mark.unit
def test_default_subscribes_to_the_official_feed_and_curated_stable(fresh_config):
    """Two markets: the framework's own libraries, and the curated catalogue.

    `stable` and not `latest` — its assertion (the set resolves and loads
    together) is the one a default should make, because a separate resolve per
    install is exactly what the runtime cannot check for itself.
    """
    import toml

    mp_cfg, path = fresh_config
    data = toml.loads(path.read_text())

    assert [m["url"] for m in data["markets"]] == [
        mp_cfg.OFFICIAL_FEED_URL,
        mp_cfg.CURATED_STABLE_URL,
    ]
    assert all(m["preference"] == [] and m["blocked"] == [] for m in data["markets"])


@pytest.mark.unit
def test_default_parses_with_the_consumer_parser(fresh_config):
    """It is a real subscription file, not just well-formed TOML."""
    from haywire.core.marketstall.parsing import parse_global_marketplace

    _, path = fresh_config
    parsed = parse_global_marketplace(path)

    assert len(parsed.markets) == 2
    assert parsed.stalls == []
    assert parsed.haybales == []


@pytest.mark.unit
def test_default_offers_the_other_channels_as_comments(fresh_config):
    """Written as text, not toml.dumps, precisely so these survive."""
    mp_cfg, path = fresh_config
    text = path.read_text()

    assert f'# url = "{mp_cfg.CURATED_FEED_BASE}/latest/marketplace.toml"' in text
    assert f'# url = "{mp_cfg.CURATED_FEED_BASE}/edge/marketplace.toml"' in text
    assert f"{mp_cfg.CURATED_FEED_BASE}/archives.html" in text
    for assertion in ("TOGETHER", "on its own", "newest on PyPI"):
        assert assertion in text, f"the file must say what {assertion!r} channel proves"


@pytest.mark.unit
def test_commented_channels_are_not_active_subscriptions(fresh_config):
    """A comment that parsed would silently subscribe a user to three feeds."""
    import toml

    mp_cfg, path = fresh_config
    urls = [m["url"] for m in toml.loads(path.read_text())["markets"]]

    assert f"{mp_cfg.CURATED_FEED_BASE}/latest/marketplace.toml" not in urls
    assert f"{mp_cfg.CURATED_FEED_BASE}/edge/marketplace.toml" not in urls


@pytest.mark.unit
def test_an_existing_file_is_never_touched(fresh_config):
    """The user's own edits and subscriptions outrank any default."""
    mp_cfg, path = fresh_config
    path.write_text('[[markets]]\nurl = "https://example.com/mine.toml"\n')

    mp_cfg.ensure_marketplace_config()

    assert path.read_text() == '[[markets]]\nurl = "https://example.com/mine.toml"\n'
