"""External editor command building."""

import pytest

pytestmark = pytest.mark.unit


def test_build_command_substitutes_file_and_line():
    from haywire.ui.utils import _build_editor_command

    cmd = _build_editor_command("code --goto {file}:{line}", "/tmp/a.py", 42)
    assert cmd == ["code", "--goto", "/tmp/a.py:42"]


def test_build_command_defaults_line_to_1():
    from haywire.ui.utils import _build_editor_command

    cmd = _build_editor_command("code --goto {file}:{line}", "/tmp/a.py", None)
    assert cmd == ["code", "--goto", "/tmp/a.py:1"]


def test_build_command_empty_template_returns_none():
    from haywire.ui.utils import _build_editor_command

    assert _build_editor_command("", "/tmp/a.py", 1) is None
    assert _build_editor_command("   ", "/tmp/a.py", 1) is None


def test_build_command_without_placeholders_appends_file():
    from haywire.ui.utils import _build_editor_command

    # A template with no {file} still gets the path as the last arg.
    cmd = _build_editor_command("myeditor", "/tmp/a.py", 5)
    assert cmd == ["myeditor", "/tmp/a.py"]
