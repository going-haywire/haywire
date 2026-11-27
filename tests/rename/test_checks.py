"""Target-name validation and the five collision namespaces."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_path_separators_are_blocked():
    from haywire_studio.packaging.rename.checks import validate_target

    _, blockers, _ = validate_target("foo/bar")
    assert blockers
    assert "separator" in blockers[0].message.lower()


@pytest.mark.unit
def test_conventional_prefixes_need_no_confirm():
    from haywire_studio.packaging.rename.checks import validate_target

    for name in ("haybale-forecast", "hay-forecast"):
        _, blockers, needs_confirm = validate_target(name)
        assert not blockers
        assert not needs_confirm


@pytest.mark.unit
def test_unconventional_prefix_requests_confirmation():
    """A bare name is legal but usually a typo — warn, do not block."""
    from haywire_studio.packaging.rename.checks import validate_target

    _, blockers, needs_confirm = validate_target("forecast")
    assert not blockers
    assert needs_confirm


@pytest.mark.unit
def test_haywire_prefix_is_not_conventional():
    """haywire- belongs to the framework; a user library there is asked."""
    from haywire_studio.packaging.rename.checks import validate_target

    _, _, needs_confirm = validate_target("haywire-forecast")
    assert needs_confirm


@pytest.mark.unit
def test_invalid_module_name_is_blocked():
    from haywire_studio.packaging.rename.checks import validate_target

    _, blockers, _ = validate_target("9bad")
    assert blockers


@pytest.mark.unit
def test_whitespace_padded_name_is_normalized():
    """Finding 3: validate_target's own .strip() implies stripping was
    always the intent — the normalized name must be returned, not just used
    internally for validation.
    """
    from haywire_studio.packaging.rename.checks import validate_target

    name, blockers, needs_confirm = validate_target("  hay-dst  ")
    assert not blockers
    assert name == "hay-dst"
    assert not needs_confirm


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


def _repo(tmp_path):
    import subprocess

    for args in (["init", "-q"], ["config", "user.email", "t@t.test"], ["config", "user.name", "T"]):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    (tmp_path / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.mark.unit
def test_clean_tree_ignores_the_haywire_folder(tmp_path):
    """Everything in .haywire/ is local (ADR 0096): the folder's own .gitignore keeps it out."""
    from haywire.core.storage import ensure_haywire_dir
    from haywire_studio.packaging.rename.checks import check_clean_tree

    ws = _repo(tmp_path)
    haywire_dir = ensure_haywire_dir(ws / ".haywire")
    (haywire_dir / "settings.json").write_text('{"network": {"port": {"value": 8131}}}')
    (haywire_dir / "marketplace.toml").write_text("")

    assert check_clean_tree(ws) == []


@pytest.mark.unit
def test_clean_tree_counts_a_file_beside_the_haywire_folder(tmp_path):
    from haywire.core.storage import ensure_haywire_dir
    from haywire_studio.packaging.rename.checks import check_clean_tree

    ws = _repo(tmp_path)
    (ensure_haywire_dir(ws / ".haywire") / "settings.json").write_text("{}")
    (ws / "notes.txt").write_text("")

    blockers = check_clean_tree(ws)

    assert len(blockers) == 1
    assert "notes.txt" in blockers[0].message
    assert ".haywire" not in blockers[0].message
