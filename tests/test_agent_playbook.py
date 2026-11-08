"""The playbook written into a project's CLAUDE.md covers every state `share` can report."""

import ast
from pathlib import Path

import pytest

from haywire_studio import packaging
from haywire_studio.playbook import PLAYBOOK, State, render_playbook

pytestmark = pytest.mark.unit


def test_one_row_per_state() -> None:
    assert [row.state for row in PLAYBOOK] == list(State)


def test_the_rendered_playbook_names_every_state() -> None:
    text = render_playbook()
    for state in State:
        assert f"| `{state.value}` |" in text


def test_share_cli_reports_only_states_the_playbook_knows() -> None:
    """No string literal that looks like a state may bypass the State enum."""
    source = (Path(packaging.__file__).parent / "share_cli.py").read_text()
    literals = {
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.isupper()
    }
    stray = {value for value in literals if value in {state.value for state in State}}
    assert stray == set()


def test_every_state_in_the_cli_maps_to_a_playbook_row() -> None:
    from haywire_studio.packaging.share_cli import _STATES

    assert set(_STATES.values()) <= {state.value for state in State}


def test_generated_claude_md_carries_the_playbook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)

    claude = (tmp_path / "my-project" / "CLAUDE.md").read_text()
    assert render_playbook() in claude
    assert "Never run `share --bump` twice for one change." in claude


def test_init_hints_at_distname_only_for_the_local_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("plain", auto_sync=False)
    assert "--distname haybale-<name>" in capsys.readouterr().out

    init_project("named", auto_sync=False, distname="haybale-named")
    assert "--distname haybale-<name>" not in capsys.readouterr().out
