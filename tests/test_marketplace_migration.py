"""Tests for the one-time sources=[] → [[marketplaces]] migration (Plan E)."""

from __future__ import annotations

import pytest
import toml


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Sandbox ~/.haywire/ to a temp dir (mirrors Plan D's pattern)."""
    fake = tmp_path / "fake-home"
    fake.mkdir()
    monkeypatch.setenv("HOME", str(fake))
    monkeypatch.setattr("pathlib.Path.home", lambda: fake)
    import haywire_studio.config as cfg

    monkeypatch.setattr(cfg, "GLOBAL_CONFIG_DIR", fake / ".haywire")
    return fake


def test_ensure_global_config_seeds_official_marketplace(fake_home):
    """Fresh install: the file doesn't exist → write defaults including the official marketplace."""
    from haywire_studio.config import ensure_global_config

    ensure_global_config()
    mp = fake_home / ".haywire" / "marketplace.toml"
    data = toml.loads(mp.read_text())

    # New schema: [[marketplaces]] with the official URL.
    marketplaces = data.get("marketplaces", [])
    assert len(marketplaces) == 1
    assert marketplaces[0]["url"] == "https://maybites.github.io/haywire/marketplace.toml"
    assert marketplaces[0].get("ignores") == []
    assert marketplaces[0].get("doubles") == []

    # No legacy 'sources' key.
    assert "sources" not in data


def test_migrate_existing_sources_to_marketplaces(fake_home):
    """Pre-existing sources=[...] → [[marketplaces]] with same URLs."""
    from haywire_studio.config import ensure_global_config

    # Simulate an existing pre-migration file with two custom sources.
    mp = fake_home / ".haywire" / "marketplace.toml"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(
        toml.dumps(
            {
                "sources": [
                    {"name": "custom", "url": "https://custom.example/marketplace.toml"},
                    {"name": "team", "url": "https://team.example/marketplace.toml"},
                ]
            }
        )
    )

    ensure_global_config()  # Should migrate in-place.

    data = toml.loads(mp.read_text())
    assert "sources" not in data
    marketplaces = data.get("marketplaces", [])
    urls = sorted(m["url"] for m in marketplaces)
    assert "https://custom.example/marketplace.toml" in urls
    assert "https://team.example/marketplace.toml" in urls


def test_migrate_empty_sources_seeds_official_only(fake_home):
    """sources=[] → [[marketplaces]] with the official URL (default pre-seed)."""
    from haywire_studio.config import ensure_global_config

    mp = fake_home / ".haywire" / "marketplace.toml"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(toml.dumps({"sources": []}))

    ensure_global_config()

    data = toml.loads(mp.read_text())
    assert "sources" not in data
    marketplaces = data.get("marketplaces", [])
    assert len(marketplaces) == 1
    assert marketplaces[0]["url"] == "https://maybites.github.io/haywire/marketplace.toml"


def test_already_migrated_is_idempotent(fake_home):
    """A file already in the new schema is not re-migrated or modified."""
    from haywire_studio.config import ensure_global_config

    mp = fake_home / ".haywire" / "marketplace.toml"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(
        toml.dumps(
            {
                "marketplaces": [
                    {
                        "url": "https://my.example/m.toml",
                        "ignores": ["haybale-skip"],
                        "doubles": [],
                    }
                ]
            }
        )
    )

    ensure_global_config()
    ensure_global_config()  # Run twice — must be idempotent.

    data = toml.loads(mp.read_text())

    # No new entries added, no fields lost.
    assert len(data["marketplaces"]) == 1
    assert data["marketplaces"][0]["ignores"] == ["haybale-skip"]


def test_migration_preserves_locals_section(fake_home):
    """Plan D writes [[locals]] entries. Migration must not touch them."""
    from haywire_studio.config import ensure_global_config

    mp = fake_home / ".haywire" / "marketplace.toml"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(
        toml.dumps(
            {
                "sources": [],
                "locals": [
                    {"name": "haybale-my-project", "path": "/tmp/proj"},
                ],
            }
        )
    )

    ensure_global_config()

    data = toml.loads(mp.read_text())
    assert "sources" not in data
    assert len(data.get("locals", [])) == 1
    assert data["locals"][0]["name"] == "haybale-my-project"
