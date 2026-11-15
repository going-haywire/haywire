"""scripts/release_sweep.py: name lists, import scan, the Waits for line, the reminders report."""

import json

import pytest

from scripts import release_sweep as sweep

pytestmark = pytest.mark.unit

OLD = """
COMPONENT = ["BaseNode", "OldThing", "Kept"]
WORKBENCH = ["hui", "Panel"]
COMPONENT_DEPRECATED: list[str] = []
WORKBENCH_DEPRECATED: list[str] = []
"""

NEW = """
COMPONENT = ["BaseNode", "NewThing"]
WORKBENCH = ["hui"]
COMPONENT_DEPRECATED: list[str] = ["Kept"]
WORKBENCH_DEPRECATED: list[str] = []
"""


def test_parse_names_counts_deprecated_names_as_served():
    parsed = sweep.parse_names(NEW)
    assert parsed["haywire.api"]["served"] == {"BaseNode", "NewThing", "Kept"}
    assert parsed["haywire.api"]["deprecated"] == {"Kept"}
    assert parsed["haywire.api.workbench"]["served"] == {"hui"}


def test_the_real_names_file_parses():
    from pathlib import Path

    parsed = sweep.parse_names(Path("tests/api/names.py").read_text())
    assert "BaseNode" in parsed["haywire.api"]["served"]
    assert "hui" in parsed["haywire.api.workbench"]["served"]


def test_api_changes_lists_removed_then_newly_deprecated_names():
    changes = sweep.api_changes(sweep.parse_names(OLD), sweep.parse_names(NEW))
    assert changes == [
        sweep.NameChange("haywire.api", "OldThing", "removed"),
        sweep.NameChange("haywire.api", "Kept", "deprecated"),
        sweep.NameChange("haywire.api.workbench", "Panel", "removed"),
    ]


def test_imports_of_reads_from_imports_aliases_and_internal_modules():
    source = """
from haywire.api import BaseNode, OldThing
from haywire.api.workbench import hui
import haywire.api as api
from haywire.core.node import Something
import haywire.ui.elements

class N(api.Kept):
    pass
"""
    found, internal = sweep.imports_of(source)
    assert found == {
        ("haywire.api", "BaseNode"),
        ("haywire.api", "OldThing"),
        ("haywire.api.workbench", "hui"),
        ("haywire.api", "Kept"),
    }
    assert internal == 2


def test_imports_of_a_broken_source_is_empty():
    assert sweep.imports_of("def (:") == (set(), 0)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("Waits for: going-haywire/haywire@840d29a21 (#107)\n\nrest", "840d29a21"),
        ("## Needs\n\nWaits for: going-haywire/haywire@c944cf7cd3fdad1f (#108)", "c944cf7cd3fdad1f"),
        ("Needs going-haywire/haywire#108", None),
        ("Waits for: going-haywire/other@840d29a21", None),
        ("", None),
    ],
)
def test_waits_for(body, expected):
    assert sweep.waits_for(body) == expected


def test_reminders_report(monkeypatch, capsys):
    issues = [
        {
            "repository": {"nameWithOwner": "going-haywire/haybale-a"},
            "number": 1,
            "title": "Raise the floor",
            "url": "https://github.com/going-haywire/haybale-a/issues/1",
            "body": "Waits for: going-haywire/haywire@aaaaaaa (#1)",
        },
        {
            "repository": {"nameWithOwner": "going-haywire/haybale-b"},
            "number": 2,
            "title": "Old style",
            "url": "https://github.com/going-haywire/haybale-b/issues/2",
            "body": "Needs #2",
        },
    ]
    monkeypatch.setattr(sweep, "run", lambda *cmd, cwd=None: json.dumps(issues))
    monkeypatch.setattr(sweep, "commit_status", lambda sha, ref: "released")

    assert sweep.main(["reminders", "--ref", "v9.9.9", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert [(r["issue"], r["status"]) for r in report["reminders"]] == [
        ("going-haywire/haybale-a#1", "released"),
        ("going-haywire/haybale-b#2", "no Waits for line"),
    ]


def test_a_failed_command_exits_2_and_says_so(monkeypatch, capsys):
    def fail(*cmd, cwd=None):
        raise sweep.CommandFailed("`gh search issues` failed: not logged in")

    monkeypatch.setattr(sweep, "run", fail)
    assert sweep.main(["reminders"]) == 2
    assert "could not be made" in capsys.readouterr().err
