"""Target-name validation and the five collision namespaces."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_path_separators_are_blocked():
    from haywire_studio.packaging.rename.checks import validate_target

    blockers, _ = validate_target("foo/bar")
    assert blockers
    assert "separator" in blockers[0].message.lower()


@pytest.mark.unit
def test_conventional_prefixes_need_no_confirm():
    from haywire_studio.packaging.rename.checks import validate_target

    for name in ("haybale-forecast", "hay-forecast"):
        blockers, needs_confirm = validate_target(name)
        assert not blockers
        assert not needs_confirm


@pytest.mark.unit
def test_unconventional_prefix_requests_confirmation():
    """A bare name is legal but usually a typo — warn, do not block."""
    from haywire_studio.packaging.rename.checks import validate_target

    blockers, needs_confirm = validate_target("forecast")
    assert not blockers
    assert needs_confirm


@pytest.mark.unit
def test_haywire_prefix_is_not_conventional():
    """haywire- belongs to the framework; a user library there is asked."""
    from haywire_studio.packaging.rename.checks import validate_target

    _, needs_confirm = validate_target("haywire-forecast")
    assert needs_confirm


@pytest.mark.unit
def test_invalid_module_name_is_blocked():
    from haywire_studio.packaging.rename.checks import validate_target

    blockers, _ = validate_target("9bad")
    assert blockers


@pytest.mark.unit
def test_collision_with_existing_barn_dir_blocks(tmp_path):
    from haywire_studio.packaging.rename.checks import check_collisions

    (tmp_path / "barn" / "hay-taken").mkdir(parents=True)
    (tmp_path / "barn" / "hay-src").mkdir(parents=True)

    blockers, _ = check_collisions(tmp_path, "hay-src", "hay-taken")
    assert any("barn" in b.message for b in blockers)


@pytest.mark.unit
def test_collision_on_module_name_blocks(tmp_path):
    """haybale-TEST_A and haybale-test-a both normalise to haybale_test_a."""
    from haywire_studio.packaging.rename.checks import check_collisions

    (tmp_path / "barn" / "haybale-TEST_A").mkdir(parents=True)
    (tmp_path / "barn" / "hay-src").mkdir(parents=True)

    blockers, _ = check_collisions(tmp_path, "hay-src", "haybale-test-a")
    assert any("module" in b.message.lower() for b in blockers)


@pytest.mark.unit
def test_collision_with_heaps_entry_blocks(tmp_path):
    """[[heaps]] is the user-authored local list — the one rename writes."""
    from haywire_studio.packaging.rename.checks import check_collisions

    (tmp_path / "barn" / "hay-src").mkdir(parents=True)
    marketplace = tmp_path / ".haywire"
    marketplace.mkdir()
    (marketplace / "marketplace.toml").write_text('[[heaps]]\nname = "hay-taken"\npath = "barn/hay-taken"\n')

    blockers, _ = check_collisions(tmp_path, "hay-src", "hay-taken")
    assert any("marketplace" in b.message.lower() for b in blockers)


@pytest.mark.unit
def test_same_name_blocks(tmp_path):
    from haywire_studio.packaging.rename.checks import check_collisions

    (tmp_path / "barn" / "hay-src").mkdir(parents=True)
    blockers, _ = check_collisions(tmp_path, "hay-src", "hay-src")
    assert blockers
