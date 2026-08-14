"""Library identity comparison — "are these two rows the same library?"

The name alone is not identity: two authors can publish `haybale-mesh` from
unrelated repos, and the marketplace has no namespace to stop them. This
module's job is to say when sameness is *provable*, and to answer "no" the
rest of the time — a wrong "same" silently swaps whose code gets installed.
"""

from __future__ import annotations

import pytest

from haywire.core.library.haybale import Haybale

pytestmark = pytest.mark.unit

_ALICE = "https://github.com/alice/mesh"
_BOB = "https://github.com/bob/mesh"


def _hb(name: str = "haybale-mesh", *, source: str = "git", origin: str = _ALICE, **kw) -> Haybale:
    return Haybale(name=name, version=kw.pop("version", "1.0.0"), source=source, origin=origin, **kw)


def _matches(a: Haybale, b: Haybale) -> bool:
    from haybale_marketplace.identity import identity_matches

    return identity_matches(a, b)


# ── PyPI: the one namespace with a global owner ──────────────────────────────


def test_two_pypi_rows_with_one_name_are_the_same_library() -> None:
    """PyPI names are globally unique, so the name IS identity there."""
    a = _hb(source="pypi", origin="")
    b = _hb(source="pypi", origin="")
    assert _matches(a, b) is True


def test_pypi_rows_match_even_with_differing_origins() -> None:
    """A mirror and the canonical feed may disagree about `origin` while both
    point at the same PyPI distribution — PyPI's namespace settles it."""
    assert _matches(_hb(source="pypi", origin=_ALICE), _hb(source="pypi", origin=_BOB)) is True


def test_different_names_are_never_the_same_library() -> None:
    assert _matches(_hb(name="haybale-a"), _hb(name="haybale-b")) is False


# ── git: no global namespace, so the repo decides ────────────────────────────


def test_git_rows_from_the_same_repo_are_the_same_library() -> None:
    assert _matches(_hb(origin=_ALICE), _hb(origin=_ALICE)) is True


def test_git_rows_from_different_repos_are_a_conflict() -> None:
    """The case this whole feature exists for: two unrelated projects, one name."""
    assert _matches(_hb(origin=_ALICE), _hb(origin=_BOB)) is False


def test_git_origin_comparison_ignores_case_and_trailing_slash() -> None:
    """Cosmetic URL differences must not read as two different projects."""
    assert _matches(_hb(origin=_ALICE), _hb(origin=_ALICE.upper() + "/")) is True


def test_git_origin_comparison_ignores_a_dot_git_suffix() -> None:
    assert _matches(_hb(origin=_ALICE), _hb(origin=_ALICE + ".git")) is True


# ── mixed and unknown: fail toward asking ────────────────────────────────────


def test_pypi_versus_git_is_a_conflict() -> None:
    """Deliberately NOT auto-resolved in PyPI's favour.

    Registering a name on PyPI is trivial, so preferring it would reliably hand
    the win to a squatter in the case that actually hurts. The user is informed
    and decides.
    """
    assert _matches(_hb(source="pypi", origin=""), _hb(source="git", origin=_ALICE)) is False


def test_a_missing_origin_on_a_git_row_is_a_conflict() -> None:
    """Cannot prove sameness, so do not claim it. Rare in practice: the share
    wizard cannot publish without a git URL to push to."""
    assert _matches(_hb(origin=""), _hb(origin=_ALICE)) is False


def test_two_git_rows_both_missing_origin_are_a_conflict() -> None:
    assert _matches(_hb(origin=""), _hb(origin="")) is False


# ── the installed copy: an editable local checkout is its own authority ──────


def _info(row: Haybale, *, editable: bool, folder: str = "", marketplace: str = ""):
    """A LibraryInfo standing in for an installed library."""
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.library.info import LibraryInfo
    from haywire.core.library.install_type import InstallType

    return LibraryInfo(
        row=row,
        identity=LibraryIdentity(folder_path=folder),
        enabled=True,
        install_type=InstallType.EDITABLE if editable else InstallType.REGULAR,
    )


def _installed_matches(info, candidate: Haybale, marketplace_path: str | None) -> bool:
    from haybale_marketplace.identity import installed_identity_matches

    return installed_identity_matches(info, candidate, marketplace_path)


def test_editable_project_local_checkout_is_its_own_authority(tmp_path) -> None:
    """A dev tree carries no `origin` (the share wizard writes it at publish),
    so without this rule an in-repo library would conflict on every refresh."""
    barn = tmp_path / "barn" / "haybale-mesh"
    barn.mkdir(parents=True)
    marketplace = str(tmp_path / ".haywire" / "marketplace.toml")

    info = _info(_hb(origin=""), editable=True, folder=str(barn))
    # Its own checkout, published under Alice's repo: not provably the same.
    assert _installed_matches(info, _hb(origin=_ALICE), marketplace) is False


def test_editable_project_local_matches_a_feed_row_from_its_own_remote(tmp_path) -> None:
    barn = tmp_path / "barn" / "haybale-mesh"
    barn.mkdir(parents=True)
    marketplace = str(tmp_path / ".haywire" / "marketplace.toml")

    info = _info(_hb(origin=_ALICE), editable=True, folder=str(barn))
    assert _installed_matches(info, _hb(origin=_ALICE), marketplace) is True


def test_a_non_local_install_falls_back_to_the_plain_rule() -> None:
    """A wheel from a feed is compared on its own metadata, as any row is."""
    info = _info(_hb(origin=_ALICE), editable=False)
    assert _installed_matches(info, _hb(origin=_ALICE), None) is True
    assert _installed_matches(info, _hb(origin=_BOB), None) is False
