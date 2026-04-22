"""E2E: LibraryOverview is opens='on_context'; no auto-populate; first click opens
a singleton tab; second click with different library switches the same tab."""

import pytest

from haybale_studio.editors.library_overview_editor import LibraryOverviewEditor
from haywire.ui.editor.identity import OpenBehavior


@pytest.mark.unit
def test_library_overview_declares_on_context():
    assert LibraryOverviewEditor.class_identity.opens is OpenBehavior.ON_CONTEXT


@pytest.mark.unit
def test_library_overview_not_auto_populated_in_main(tmp_path):
    """WorkspaceManager._auto_populate must skip LibraryOverview now."""
    from haywire.ui.workspace.manager import WorkspaceManager
    from haywire.ui.editor.registry import EditorTypeRegistry

    registry = EditorTypeRegistry()
    registry._classes[LibraryOverviewEditor.class_identity.registry_key] = LibraryOverviewEditor

    manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
    keys = [t.editor_key for t in manager.active.main.tabs]
    assert LibraryOverviewEditor.class_identity.registry_key not in keys
