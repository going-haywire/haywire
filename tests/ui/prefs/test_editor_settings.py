"""External-editor command setting."""

import pytest

pytestmark = pytest.mark.unit


def test_external_editor_command_default():
    from haywire.ui.prefs.editor import EditorSettings

    assert EditorSettings().external_editor_command == "code --goto {file}:{line}"
