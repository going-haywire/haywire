"""Tests for the .haywire format migration chain.

The shipped fixtures under graphs/ are the real regression test: they are
v0-shaped on disk and upgraded on every load, so a broken upgrader fails
the suite rather than silently corrupting a load.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.graph.prehydration import CURRENT_FORMAT_VERSION, prehydrate
from haywire.core.graph.prehydration.upgrader import UnknownGraphFormat, validate

FIXTURES = Path(__file__).resolve().parents[3] / "graphs"


def _base(**extra):
    """A minimal dict that clears the structural floor."""
    return {"nodes": {}, "edges": {}, **extra}


# ---------------------------------------------------------------------------
# Chain behaviour
# ---------------------------------------------------------------------------


def test_ancient_upgrades_to_current():
    """A v0 dict gains meta + format_version and loses the legacy keys."""
    out = prehydrate(
        _base(
            graph_id="/tmp/old.haywire",
            name="Untitled 6",
            description="a graph",
            author="ann",
            version="1.0.0",
        )
    )

    assert out["format_version"] == CURRENT_FORMAT_VERSION
    assert "graph_id" not in out
    assert "name" not in out
    assert out["meta"] == {
        "values": {"description": "a graph", "author": "ann", "version": "1.0.0"},
        "promoted": {},
    }


def test_v1_does_not_invent_a_filestem():
    """v1 drops ``name`` rather than renaming it.

    The stem is a fact about the file, which an upgrader cannot see;
    load_from_file stamps it instead. Renaming would launder the stale
    "Untitled N" into a field promising to be the filename stem.
    """
    out = prehydrate(_base(graph_id="x", name="Untitled 6"))
    assert "filestem" not in out


def test_current_dict_is_returned_untouched():
    """The head short-circuits — no re-migration of an already-current file."""
    current = _base(
        format_version=CURRENT_FORMAT_VERSION,
        filestem="new",
        meta={"values": {"label": "L"}, "promoted": {}},
    )
    assert prehydrate(dict(current)) == current


def test_v1_shaped_dict_upgrades_to_v2():
    """A file that lost graph_id/name but predates meta still migrates."""
    out = prehydrate(_base(description="d"))
    assert out["format_version"] == CURRENT_FORMAT_VERSION
    assert out["meta"] == {"values": {"description": "d"}, "promoted": {}}


def test_partial_meta_is_preserved():
    """An existing meta key survives; a top-level twin does not overwrite it."""
    out = prehydrate(_base(name="x", meta={"values": {"label": "kept"}}, description="moved"))
    assert out["meta"]["values"] == {"label": "kept", "description": "moved"}


def test_user_version_is_not_a_schema_version():
    """meta.version is user free text and must never gate the chain.

    A user typing "9.9" into the metadata panel must not make the file
    claim to be schema v9.9 (which would be refused as from-the-future).
    """
    out = prehydrate(_base(name="x", version="9.9"))
    assert out["format_version"] == CURRENT_FORMAT_VERSION
    assert out["meta"]["values"]["version"] == "9.9"


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_future_version_is_refused():
    with pytest.raises(HaywireException, match="newer Haywire"):
        prehydrate(_base(format_version=CURRENT_FORMAT_VERSION + 1))


def test_non_graph_is_refused():
    with pytest.raises(HaywireException, match="not a recognisable"):
        prehydrate({"totally": "unrelated"})


def test_non_graph_lacking_legacy_keys_is_still_refused():
    """The short-circuit path validates too.

    v1's signal is absence-based ("graph_id and name are both gone"), which
    an unrelated dict satisfies. Without validation on the short-circuit it
    would be claimed at the head and never reach the terminator.
    """
    with pytest.raises(HaywireException, match="not a recognisable"):
        prehydrate({"unrelated": True, "no": "legacy keys here"})


def test_validate_checks_presence_not_truthiness():
    """An edge-less graph carries ``"edges": {}`` and must pass."""
    validate({"nodes": {}, "edges": {}})  # does not raise

    with pytest.raises(UnknownGraphFormat, match="edges"):
        validate({"nodes": {}})


# ---------------------------------------------------------------------------
# The shipped fixtures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["empty", "webcam", "loop", "settings", "oakNwebCam", "10x200nodes"],
)
def test_shipped_fixture_upgrades(name: str):
    """Every graph in graphs/ migrates cleanly to the current format."""
    data = json.loads((FIXTURES / f"{name}.haywire").read_text())
    out = prehydrate(data)

    assert out["format_version"] == CURRENT_FORMAT_VERSION
    assert "graph_id" not in out
    assert "name" not in out
    assert isinstance(out["meta"], dict)
    assert out["nodes"] is not None
    assert out["edges"] is not None
