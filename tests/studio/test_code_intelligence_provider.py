"""Unit tests for the jedi-backed code-intelligence provider helpers."""

from __future__ import annotations

from pathlib import Path

import jedi
import pytest

from haywire_studio.code_intelligence import (
    _completion_payload,
    _confined_path,
    _signature_and_doc,
)

from tests.conftest import _restore_ambient_di, _snapshot_ambient_di


def test_completion_payload_returns_plain_jedi_vocabulary():
    code = "import os\nos."
    script = jedi.Script(code)
    completions = script.complete(2, 3)
    payload = _completion_payload(completions, explicit=False)
    assert payload  # os has many attributes
    first = payload[0]
    # plain data only: name + kind + signature + docstring, NO type/boost/html
    assert set(first.keys()) == {"name", "kind", "signature", "docstring"}
    assert "<" not in first["docstring"]  # not HTML


def test_completion_payload_filters_dunders_when_not_explicit():
    code = "import os\nos."
    completions = jedi.Script(code).complete(2, 3)
    names = {c["name"] for c in _completion_payload(completions, explicit=False)}
    assert not any(n.startswith("__") for n in names)


def test_completion_payload_keeps_dunders_when_explicit():
    code = "import os\nos."
    completions = jedi.Script(code).complete(2, 3)
    names = {c["name"] for c in _completion_payload(completions, explicit=True)}
    assert any(n.startswith("__") for n in names)


def test_signature_and_doc_returns_plain_text():
    code = "def greet(name: str) -> str:\n    '''Say hello.'''\n    return name\ngreet"
    names = jedi.Script(code).help(4, 5)
    sig, doc = _signature_and_doc(names[0])
    assert "greet(name" in sig
    assert "Say hello." in doc
    assert "<" not in sig
    assert "<" not in doc


# ---------------------------------------------------------------------------
# _confined_path
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_root(tmp_path: Path):
    """Point the ambient workspace root at *tmp_path* for the duration of a test.

    Mirrors the snapshot/restore idiom used by tests/farmhand/conftest.py and
    tests/marketplace/test_component_drilldown.py.
    """
    from haywire.core.di.context import set_workspace_root

    snap = _snapshot_ambient_di()
    set_workspace_root(str(tmp_path))
    yield tmp_path
    _restore_ambient_di(snap)


def test_confined_path_accepts_workspace_relative_path(workspace_root: Path):
    target = workspace_root / "graphs" / "my_node.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")

    assert _confined_path(str(target)) == str(target)


def test_confined_path_accepts_sys_path_entry(workspace_root: Path):
    # Any importable module file lives under some sys.path entry — os itself
    # is a reliable one across platforms/venvs.
    import os

    os_path = os.__file__
    assert os_path is not None

    assert _confined_path(os_path) == os_path


def test_confined_path_rejects_etc_passwd(workspace_root: Path):
    assert _confined_path("/etc/passwd") is None


def test_confined_path_rejects_traversal_out_of_workspace(workspace_root: Path):
    traversal = str(workspace_root / ".." / ".." / "etc" / "passwd")
    assert _confined_path(traversal) is None


def test_confined_path_handles_none_input(workspace_root: Path):
    assert _confined_path(None) is None


def test_confined_path_logs_warning_on_rejection(workspace_root: Path, caplog: pytest.LogCaptureFixture):
    with caplog.at_level("WARNING", logger="haywire_studio.code_intelligence"):
        result = _confined_path("/etc/passwd")
    assert result is None
    assert any("rejected" in record.message for record in caplog.records)


def test_confined_path_without_workspace_root_still_allows_sys_path(monkeypatch: pytest.MonkeyPatch):
    """If the workspace root isn't set yet, sys.path roots alone still apply."""
    from haywire.core.di import context as di_context

    snap = _snapshot_ambient_di()
    di_context._workspace_root = None
    try:
        import os

        os_path = os.__file__
        assert os_path is not None
        assert _confined_path(os_path) == os_path
        assert _confined_path("/etc/passwd") is None
    finally:
        _restore_ambient_di(snap)


def test_confined_path_rejected_result_still_yields_valid_script(workspace_root: Path):
    """The endpoints pass _confined_path's result straight into jedi.Script;
    a rejection (None) must not blow up jedi, just drop relative-import
    resolution — this is how the endpoint quietly degrades instead of 500ing.
    """
    resolved = _confined_path("/etc/passwd")
    assert resolved is None
    # This is exactly what each endpoint does: jedi.Script(code, path=<result>)
    script = jedi.Script("import os\nos.", path=resolved)
    completions = script.complete(2, 3)
    assert completions  # still functions, just without relative-import context
