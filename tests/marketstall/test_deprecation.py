"""`[deprecated]` travels from haybale.toml into a marketstall row.

The notice has to reach a consumer *before* they install, which the
`[project] classifiers` projection cannot do: it carries neither `reason` nor
`successor`, and nothing in the studio reads PyPI metadata.

Two deliberately different strictness regimes are pinned here:

* the **publisher** raises on a block it cannot serialize — an authoring
  mistake, shown to the one person who can fix it;
* the **consumer** degrades to ``None`` — an advisory notice must never cost
  someone the catalog entry for a library that still installs and runs.
"""

from __future__ import annotations

import pytest
import toml

from haywire.core.library.haybale import Deprecation, Haybale
from haywire.core.marketstall.parsing import _parse_deprecation, _parse_haybale_entry
from haywire.core.publishing.marketstall import _declared_deprecation


@pytest.mark.unit
def test_round_trips_through_toml() -> None:
    row = Haybale(
        name="haybale-old",
        version="0.0.41",
        install_spec="haybale-old @ git+https://example.com",
        deprecated=Deprecation(since="0.0.41", reason="Superseded.", successor="haybale-new"),
    )

    body = toml.dumps({"haybales": [row.to_dict()]})
    parsed = _parse_haybale_entry(toml.loads(body)["haybales"][0])

    assert parsed.deprecated == row.deprecated


@pytest.mark.unit
def test_deprecated_serializes_last() -> None:
    """It becomes a TOML table, and a bare key after a table header joins it.

    Emitting it mid-row would silently swallow every field written after it.
    """
    row = Haybale(
        name="haybale-old",
        version="0.0.41",
        install_spec="x",
        notes="NOTES.md",
        deprecated=Deprecation(since="0.0.41"),
    )

    assert list(row.to_dict())[-1] == "deprecated"


@pytest.mark.unit
def test_absent_emits_no_key() -> None:
    row = Haybale(name="haybale-live", version="1.0.0", install_spec="x")

    assert "deprecated" not in row.to_dict()
    assert _parse_haybale_entry({"name": "haybale-live", "version": "1.0.0"}).deprecated is None


@pytest.mark.unit
def test_optional_fields_omitted_when_empty() -> None:
    assert Deprecation(since="2.0.0").to_dict() == {"since": "2.0.0"}


@pytest.mark.unit
@pytest.mark.parametrize(
    "block",
    [
        pytest.param("not-a-table", id="wrong-type"),
        pytest.param({}, id="empty"),
        pytest.param({"reason": "no since"}, id="missing-since"),
        pytest.param({"since": ""}, id="blank-since"),
    ],
)
def test_consumer_degrades_to_none(block: object) -> None:
    """A malformed notice must not cost the user the whole catalog entry."""
    assert _parse_deprecation({"deprecated": block}) is None


@pytest.mark.unit
def test_consumer_keeps_the_rest_of_the_row() -> None:
    parsed = _parse_haybale_entry(
        {"name": "haybale-x", "version": "1.0.0", "deprecated": {"reason": "no since"}}
    )

    assert parsed.name == "haybale-x"
    assert parsed.deprecated is None


@pytest.mark.unit
def test_publisher_accepts_a_since_only_block() -> None:
    declared = _declared_deprecation({"deprecated": {"since": "1.0.0"}})

    assert declared == Deprecation(since="1.0.0")


@pytest.mark.unit
def test_publisher_passes_reason_and_successor_through() -> None:
    declared = _declared_deprecation(
        {"deprecated": {"since": "1.0.0", "reason": "Merged.", "successor": "haybale-new"}}
    )

    assert declared == Deprecation(since="1.0.0", reason="Merged.", successor="haybale-new")


@pytest.mark.unit
def test_publisher_returns_none_when_absent() -> None:
    assert _declared_deprecation({}) is None


@pytest.mark.unit
def test_publisher_normalises_tomlkit_strings() -> None:
    """``read_raw`` yields tomlkit types, and its String is a str *subclass*.

    ``toml.dumps`` serializes those as a sequence of characters, so a value
    passed through unnormalised reaches the row as ``["0", ".", "9"]``.
    """
    import tomlkit

    block = tomlkit.parse('since = "0.0.9"\nreason = "Gone."\n')
    declared = _declared_deprecation({"deprecated": block})
    assert declared is not None

    emitted = toml.dumps(declared.to_dict())
    assert 'since = "0.0.9"' in emitted
    assert '"0", "."' not in emitted


@pytest.mark.unit
@pytest.mark.parametrize(
    ("block", "match"),
    [
        pytest.param("not-a-table", "must be a table", id="wrong-type"),
        pytest.param({}, "requires `since`", id="empty"),
        pytest.param({"reason": "no since"}, "requires `since`", id="missing-since"),
    ],
)
def test_publisher_raises_rather_than_publishing_a_broken_notice(block: object, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _declared_deprecation({"deprecated": block})
