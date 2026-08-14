"""Deprecation notice surfaces in the Library Browser badge and Library
Overview banner — see internals/handoff/deprecated-libraries-have-no-ui-surface.md.

Covers the two pure/near-pure decision points:
  - deprecation_message(): banner text, including the version-aware phrasing
    for an installed library below `since`.
  - LibraryOverviewEditor._row_by_dist_name(): successor lookup against the
    project catalog.

It gates nothing — no test here asserts an Install/Enable/Update button is
blocked or disabled by a deprecation notice, because the feature must not do
that (see the handoff's "It gates nothing" section).
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from haywire.core.library.haybale import Deprecation, Haybale


@pytest.mark.unit
def test_deprecation_message_none_when_not_deprecated():
    from haybale_marketplace.editors.library_overview_editor import deprecation_message

    row = Haybale(name="haybale-x", version="1.0.0")
    assert deprecation_message(row, installed=True) is None


@pytest.mark.unit
def test_deprecation_message_bare_since_only():
    from haybale_marketplace.editors.library_overview_editor import deprecation_message

    row = Haybale(
        name="haybale-x",
        version="1.0.0",
        deprecated=Deprecation(since="0.0.41"),
    )
    message = deprecation_message(row, installed=False)
    assert message == "Deprecated since v0.0.41"


@pytest.mark.unit
def test_deprecation_message_appends_reason():
    from haybale_marketplace.editors.library_overview_editor import deprecation_message

    row = Haybale(
        name="haybale-x",
        version="1.0.0",
        deprecated=Deprecation(since="0.0.41", reason="superseded by haybale-y"),
    )
    message = deprecation_message(row, installed=False)
    assert message == "Deprecated since v0.0.41 — superseded by haybale-y"


@pytest.mark.unit
def test_deprecation_message_version_aware_when_installed_below_since():
    from haybale_marketplace.editors.library_overview_editor import deprecation_message

    row = Haybale(
        name="haybale-x",
        version="0.0.30",
        deprecated=Deprecation(since="0.0.41"),
    )
    message = deprecation_message(row, installed=True)
    assert message == "You are on v0.0.30; this library was deprecated in v0.0.41"


@pytest.mark.unit
def test_deprecation_message_not_version_aware_when_not_installed():
    """A not-installed row's version is the catalog's *current* advertised
    version, not something the user is "on" — the version-aware phrasing
    must not fire."""
    from haybale_marketplace.editors.library_overview_editor import deprecation_message

    row = Haybale(
        name="haybale-x",
        version="0.0.30",
        deprecated=Deprecation(since="0.0.41"),
    )
    message = deprecation_message(row, installed=False)
    assert message == "Deprecated since v0.0.41"


@pytest.mark.unit
def test_deprecation_message_not_version_aware_when_installed_at_or_above_since():
    from haybale_marketplace.editors.library_overview_editor import deprecation_message

    row = Haybale(
        name="haybale-x",
        version="0.0.41",
        deprecated=Deprecation(since="0.0.41"),
    )
    message = deprecation_message(row, installed=True)
    assert message == "Deprecated since v0.0.41"


@pytest.mark.unit
def test_row_by_dist_name_finds_successor_in_catalog():
    from haybale_marketplace.editors.library_overview_editor import LibraryOverviewEditor
    from haybale_marketplace.state.marketplace_state import MarketplaceState

    editor = LibraryOverviewEditor(wrapper=None)  # type: ignore[arg-type]
    successor_row = Haybale(name="haybale-y", version="2.0.0")
    state = Mock(spec=MarketplaceState)
    state.get_project_haybales.return_value = [successor_row]
    context = Mock()
    context.app_data = {MarketplaceState: state}

    found = editor._row_by_dist_name("haybale-y", context)
    assert found is successor_row


@pytest.mark.unit
def test_row_by_dist_name_none_when_not_in_catalog():
    from haybale_marketplace.editors.library_overview_editor import LibraryOverviewEditor
    from haybale_marketplace.state.marketplace_state import MarketplaceState

    editor = LibraryOverviewEditor(wrapper=None)  # type: ignore[arg-type]
    state = Mock(spec=MarketplaceState)
    state.get_project_haybales.return_value = []
    context = Mock()
    context.app_data = {MarketplaceState: state}

    assert editor._row_by_dist_name("haybale-y", context) is None


@pytest.mark.unit
def test_row_by_dist_name_none_when_no_marketplace_state():
    from haybale_marketplace.editors.library_overview_editor import LibraryOverviewEditor

    editor = LibraryOverviewEditor(wrapper=None)  # type: ignore[arg-type]
    context = Mock()
    context.app_data = {}

    assert editor._row_by_dist_name("haybale-y", context) is None


@pytest.mark.unit
def test_row_by_dist_name_none_when_name_empty():
    from haybale_marketplace.editors.library_overview_editor import LibraryOverviewEditor

    editor = LibraryOverviewEditor(wrapper=None)  # type: ignore[arg-type]
    context = Mock()

    assert editor._row_by_dist_name("", context) is None
