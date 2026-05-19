"""Tests for the two-tier marketplace runtime (spec §6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from haywire.core.marketplace_runtime import (
    GlobalMarketplace,  # noqa: F401  # re-exported for downstream test modules
    MarketplaceEntry,
    ProjectMarketplace,  # noqa: F401  # re-exported for downstream test modules
    RemoteSubscription,  # noqa: F401  # re-exported for downstream test modules
    parse_global_marketplace,
    parse_project_marketplace,
    serialize_global_marketplace,
    serialize_project_marketplace,
)
from haywire.core.marketplace_errors import MalformedGlobalMarketplaceError


@pytest.mark.unit
def test_parse_empty_global(tmp_path: Path) -> None:
    """Empty file → empty GlobalMarketplace with all four sections empty."""
    f = tmp_path / "marketplace.toml"
    f.write_text("")
    gm = parse_global_marketplace(f)
    assert gm.marketplaces == []
    assert gm.marketstalls == []
    assert gm.packages == []
    assert gm.locals_ == []


@pytest.mark.unit
def test_parse_marketplaces_section(tmp_path: Path) -> None:
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[marketplaces]]\n"
        'url = "https://maybites.github.io/haywire/marketplace.toml"\n'
        "ignores = []\n"
        "doubles = []\n"
    )
    gm = parse_global_marketplace(f)
    assert len(gm.marketplaces) == 1
    sub = gm.marketplaces[0]
    assert sub.url == "https://maybites.github.io/haywire/marketplace.toml"
    assert sub.ignores == []
    assert sub.doubles == []


@pytest.mark.unit
def test_parse_marketstalls_section(tmp_path: Path) -> None:
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[marketstalls]]\n"
        'url = "https://author.example/marketstall.toml"\n'
        'ignores = ["haybale-skip"]\n'
        'doubles = ["haybale-double"]\n'
    )
    gm = parse_global_marketplace(f)
    assert len(gm.marketstalls) == 1
    sub = gm.marketstalls[0]
    assert sub.url == "https://author.example/marketstall.toml"
    assert sub.ignores == ["haybale-skip"]
    assert sub.doubles == ["haybale-double"]


@pytest.mark.unit
def test_parse_packages_section(tmp_path: Path) -> None:
    """Direct [[packages]] entries match the §7 MarketplaceEntry schema."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[packages]]\n"
        'name = "haybale-foo"\n'
        'min_version = "0.0.1"\n'
        'source = "git"\n'
        'install_spec = "haybale-foo @ git+https://x.example/r.git"\n'
    )
    gm = parse_global_marketplace(f)
    assert len(gm.packages) == 1
    pkg = gm.packages[0]
    assert pkg.name == "haybale-foo"
    assert pkg.source == "git"


@pytest.mark.unit
def test_parse_locals_section(tmp_path: Path) -> None:
    """[[locals]] entries match Plan D's schema: name + path + optional metadata."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[locals]]\n"
        'name = "haybale-my-project"\n'
        'path = "/Users/x/code/proj/barn/haybale-my-project"\n'
        'label = "My Project"\n'
    )
    gm = parse_global_marketplace(f)
    assert len(gm.locals_) == 1
    local = gm.locals_[0]
    assert local["name"] == "haybale-my-project"
    assert local["path"] == "/Users/x/code/proj/barn/haybale-my-project"
    assert local.get("label") == "My Project"


@pytest.mark.unit
def test_parse_all_four_sections(tmp_path: Path) -> None:
    """A realistic global file has all four sections mixed together."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[marketplaces]]\n"
        'url = "https://maybites.github.io/haywire/marketplace.toml"\n'
        "\n"
        "[[marketstalls]]\n"
        'url = "https://author.example/marketstall.toml"\n'
        "\n"
        "[[packages]]\n"
        'name = "haybale-direct"\n'
        'min_version = "0.0.1"\n'
        "\n"
        "[[locals]]\n"
        'name = "haybale-local"\n'
        'path = "/tmp/local"\n'
    )
    gm = parse_global_marketplace(f)
    assert len(gm.marketplaces) == 1
    assert len(gm.marketstalls) == 1
    assert len(gm.packages) == 1
    assert len(gm.locals_) == 1


@pytest.mark.unit
def test_parse_malformed_toml_raises(tmp_path: Path) -> None:
    """A malformed TOML file raises MalformedGlobalMarketplaceError."""
    f = tmp_path / "marketplace.toml"
    f.write_text('this is = "not valid TOML\nbecause unterminated string')
    with pytest.raises(MalformedGlobalMarketplaceError) as exc_info:
        parse_global_marketplace(f)
    assert "marketplace.toml" in str(exc_info.value)


@pytest.mark.unit
def test_parse_duplicate_locals_raises(tmp_path: Path) -> None:
    """Two [[locals]] with the same name is the G5 collision — refused at parse time."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        '[[locals]]\nname = "haybale-foo"\npath = "/tmp/a"\n\n'
        '[[locals]]\nname = "haybale-foo"\npath = "/tmp/b"\n'
    )
    with pytest.raises(MalformedGlobalMarketplaceError) as exc_info:
        parse_global_marketplace(f)
    assert "haybale-foo" in str(exc_info.value)


@pytest.mark.unit
def test_parse_duplicate_packages_raises(tmp_path: Path) -> None:
    """Two [[packages]] with the same name — refused at parse time."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        '[[packages]]\nname = "haybale-foo"\nmin_version = "0.0.1"\n\n'
        '[[packages]]\nname = "haybale-foo"\nmin_version = "0.0.2"\n'
    )
    with pytest.raises(MalformedGlobalMarketplaceError) as exc_info:
        parse_global_marketplace(f)
    assert "haybale-foo" in str(exc_info.value)


@pytest.mark.unit
def test_parse_missing_file_returns_empty(tmp_path: Path) -> None:
    """A non-existent path returns an empty GlobalMarketplace (caller decides what to do)."""
    gm = parse_global_marketplace(tmp_path / "does-not-exist.toml")
    assert gm.marketplaces == [] and gm.marketstalls == []
    assert gm.packages == [] and gm.locals_ == []


@pytest.mark.unit
def test_parse_project_marketplace_empty(tmp_path: Path) -> None:
    f = tmp_path / "marketplace.toml"
    f.write_text("")
    pm = parse_project_marketplace(f)
    assert isinstance(pm, ProjectMarketplace)
    assert pm.locals_ == []
    assert pm.packages == []


@pytest.mark.unit
def test_parse_project_marketplace_locals_and_packages(tmp_path: Path) -> None:
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[locals]]\n"
        'name = "haybale-my-project"\n'
        'path = "/tmp/proj/barn/haybale-my-project"\n'
        "\n"
        "[[packages]]\n"
        'name = "haybale-cached"\n'
        'min_version = "0.0.1"\n'
        'source = "git"\n'
        'install_spec = "haybale-cached @ git+https://x.example/r.git"\n'
        'via = "https://author.example/marketstall.toml"\n'
    )
    pm = parse_project_marketplace(f)
    assert len(pm.locals_) == 1
    assert pm.locals_[0]["name"] == "haybale-my-project"
    assert len(pm.packages) == 1
    assert pm.packages[0].via == "https://author.example/marketstall.toml"


@pytest.mark.unit
def test_parse_project_marketplace_stale_entry(tmp_path: Path) -> None:
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[packages]]\n"
        'name = "haybale-stale-pkg"\n'
        'min_version = "0.0.1"\n'
        'source = "git"\n'
        'install_spec = "haybale-stale-pkg @ git+https://x.example/r.git"\n'
        "stale = true\n"
        'last_seen = "2026-05-10T08:00:00Z"\n'
    )
    pm = parse_project_marketplace(f)
    assert len(pm.packages) == 1
    assert pm.packages[0].stale is True
    assert pm.packages[0].last_seen == "2026-05-10T08:00:00Z"


@pytest.mark.unit
def test_parse_project_marketplace_ignores_marketplaces_marketstalls(tmp_path: Path) -> None:
    """Per spec §6: project marketplace has no [[marketplaces]] or [[marketstalls]] sections.
    If the file accidentally contains them, the parser silently ignores them (no error)."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[marketplaces]]\n"
        'url = "https://x.example/m.toml"\n'
        "\n"
        "[[locals]]\n"
        'name = "haybale-foo"\n'
        'path = "/tmp/foo"\n'
    )
    pm = parse_project_marketplace(f)
    assert len(pm.locals_) == 1


@pytest.mark.unit
def test_parse_project_marketplace_missing_file(tmp_path: Path) -> None:
    pm = parse_project_marketplace(tmp_path / "does-not-exist.toml")
    assert pm.locals_ == [] and pm.packages == []


@pytest.mark.unit
def test_serialize_empty_global() -> None:
    gm = GlobalMarketplace()
    out = serialize_global_marketplace(gm)
    # Round-trip: serializing an empty GM and re-parsing yields an empty GM.
    import toml as _toml

    parsed = _toml.loads(out)
    assert parsed.get("marketplaces", []) == []
    assert parsed.get("marketstalls", []) == []
    assert parsed.get("packages", []) == []
    assert parsed.get("locals", []) == []


@pytest.mark.unit
def test_serialize_round_trip(tmp_path: Path) -> None:
    """Parse → serialize → parse yields the same GlobalMarketplace."""
    f = tmp_path / "marketplace.toml"
    original = (
        "[[marketplaces]]\n"
        'url = "https://maybites.github.io/haywire/marketplace.toml"\n'
        'ignores = ["haybale-skip"]\n'
        "\n"
        "[[marketstalls]]\n"
        'url = "https://author.example/marketstall.toml"\n'
        "\n"
        "[[packages]]\n"
        'name = "haybale-direct"\n'
        'min_version = "0.0.1"\n'
        "\n"
        "[[locals]]\n"
        'name = "haybale-local"\n'
        'path = "/tmp/local"\n'
        'label = "Local"\n'
    )
    f.write_text(original)

    gm1 = parse_global_marketplace(f)
    serialized = serialize_global_marketplace(gm1)
    f.write_text(serialized)
    gm2 = parse_global_marketplace(f)

    assert len(gm2.marketplaces) == 1
    assert gm2.marketplaces[0].url == gm1.marketplaces[0].url
    assert gm2.marketplaces[0].ignores == ["haybale-skip"]
    assert len(gm2.marketstalls) == 1
    assert len(gm2.packages) == 1
    assert gm2.packages[0].name == "haybale-direct"
    assert len(gm2.locals_) == 1
    assert gm2.locals_[0]["label"] == "Local"


@pytest.mark.unit
def test_serialize_omits_empty_sections() -> None:
    """Only non-empty sections appear in the output."""
    gm = GlobalMarketplace(locals_=[{"name": "haybale-only", "path": "/tmp/x"}])
    out = serialize_global_marketplace(gm)
    assert "[[locals]]" in out
    assert "[[marketplaces]]" not in out
    assert "[[marketstalls]]" not in out
    assert "[[packages]]" not in out


@pytest.mark.unit
def test_serialize_project_marketplace_empty() -> None:
    pm = ProjectMarketplace()
    out = serialize_project_marketplace(pm)
    import toml as _toml

    parsed = _toml.loads(out)
    assert parsed.get("locals", []) == []
    assert parsed.get("packages", []) == []


@pytest.mark.unit
def test_serialize_project_marketplace_round_trip(tmp_path: Path) -> None:
    pm1 = ProjectMarketplace(
        locals_=[{"name": "haybale-proj", "path": "/tmp/proj"}],
        packages=[
            MarketplaceEntry(
                name="haybale-cached",
                min_version="0.0.1",
                source="git",
                install_spec="haybale-cached @ git+https://x.example/r.git",
                via="https://author.example/marketstall.toml",
            )
        ],
    )
    f = tmp_path / "marketplace.toml"
    f.write_text(serialize_project_marketplace(pm1))
    pm2 = parse_project_marketplace(f)
    assert len(pm2.locals_) == 1
    assert pm2.locals_[0]["name"] == "haybale-proj"
    assert len(pm2.packages) == 1
    assert pm2.packages[0].via == "https://author.example/marketstall.toml"


@pytest.mark.unit
def test_serialize_project_marketplace_preserves_stale(tmp_path: Path) -> None:
    pm1 = ProjectMarketplace(
        packages=[
            MarketplaceEntry(
                name="haybale-gone",
                min_version="0.0.1",
                source="git",
                install_spec="haybale-gone @ git+https://x.example/r.git",
                stale=True,
                last_seen="2026-05-10T08:00:00Z",
            )
        ]
    )
    f = tmp_path / "marketplace.toml"
    f.write_text(serialize_project_marketplace(pm1))
    pm2 = parse_project_marketplace(f)
    assert pm2.packages[0].stale is True
    assert pm2.packages[0].last_seen == "2026-05-10T08:00:00Z"
