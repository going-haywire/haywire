"""External-editor command setting."""

import pytest

pytestmark = pytest.mark.unit


def test_editor_command_default():
    from haywire.core.tooling.settings import ExternalToolsSettings

    assert ExternalToolsSettings().editor_command == "code --goto {file}:{line}"
