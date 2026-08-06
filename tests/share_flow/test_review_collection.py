"""The Review screen collects decisions without writing.

`_collect` turns the screen's controls into a ShareDecisions. It is pure — no
file is touched until `advance_from_review` calls `apply_all` — which is the
property that lets a user revise freely and abandon safely.

Controls are faked with tiny value-carrying stubs rather than real NiceGUI
elements: `_collect` reads `.value` and nothing else, so a browser adds
nothing here but startup cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from haybale_share._flow.panels import _collect

pytestmark = pytest.mark.unit

ALPHA = Path("barn/haybale-alpha")
BETA = Path("barn/haybale-beta")


@dataclass
class _Control:
    """Stands in for any control `_collect` reads — it only wants `.value`."""

    value: object = ""


def _controls(*, additions=None, removals=None, floors=None) -> dict:
    return {
        "additions": additions or [],
        "removals": removals or [],
        "floors": floors or [],
    }


def test_untouched_controls_produce_an_inert_decision_set() -> None:
    """Defaults must write nothing.

    Every control starts on its no-op value, so a user who reads the screen and
    clicks Apply changes only what the flow told them it would.
    """
    decisions = _collect(
        _controls(
            additions=[(ALPHA, "numpy", "1.26.0", _Control("none"), _Control(""))],
            removals=[(ALPHA, "requests", _Control(False))],
            floors=[(ALPHA, "toml", "0.10.2", _Control("keep"), _Control(""))],
        ),
        None,
    )

    assert decisions.framework is None
    assert decisions.removals == {}
    assert decisions.floors == {}
    assert decisions.undeclared_acknowledged is False
    # An undeclared import still gets declared: that is the one state that
    # breaks a consumer's install, and declaring it is unambiguously correct.
    assert decisions.additions == {ALPHA: ["numpy"]}


def test_pin_modes_build_the_right_specifier() -> None:
    decisions = _collect(
        _controls(
            additions=[
                (ALPHA, "numpy", "1.26.0", _Control("installed"), _Control("")),
                (ALPHA, "toml", "0.10.2", _Control("custom"), _Control(">=0.10")),
                (BETA, "attrs", "23.1.0", _Control("none"), _Control("")),
            ]
        ),
        None,
    )

    assert decisions.additions == {ALPHA: ["numpy>=1.26.0", "toml>=0.10"], BETA: ["attrs"]}


def test_skipping_an_undeclared_import_records_the_acknowledgement() -> None:
    """The one decision with no safe default, so it is recorded rather than
    silently allowed."""
    decisions = _collect(
        _controls(additions=[(ALPHA, "numpy", "1.26.0", _Control("skip"), _Control(""))]),
        None,
    )

    assert decisions.additions == {}
    assert decisions.undeclared_acknowledged is True


def test_installed_pin_degrades_to_a_bare_declaration_when_unknown() -> None:
    """No installed version means no honest floor to write."""
    decisions = _collect(
        _controls(additions=[(ALPHA, "mystery", "", _Control("installed"), _Control(""))]),
        None,
    )

    assert decisions.additions == {ALPHA: ["mystery"]}


def test_only_ticked_removals_are_collected() -> None:
    decisions = _collect(
        _controls(
            removals=[
                (ALPHA, "requests", _Control(True)),
                (ALPHA, "urllib3", _Control(False)),
                (BETA, "click", _Control(True)),
            ]
        ),
        None,
    )

    assert decisions.removals == {ALPHA: ["requests"], BETA: ["click"]}


def test_floor_modes_write_only_what_changed() -> None:
    decisions = _collect(
        _controls(
            floors=[
                (ALPHA, "toml", "0.10.2", _Control("sync"), _Control("")),
                (ALPHA, "attrs", "23.1.0", _Control("keep"), _Control("")),
                (BETA, "click", "8.1.0", _Control("custom"), _Control(">=8.0")),
            ]
        ),
        None,
    )

    assert decisions.floors == {ALPHA: ["toml>=0.10.2"], BETA: ["click>=8.0"]}


def test_framework_specifier_passes_through() -> None:
    decisions = _collect(_controls(), ">=0.0.31")

    assert decisions.framework == ">=0.0.31"
