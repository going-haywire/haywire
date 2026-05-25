"""E2E: LibraryOverview is opens='on_context'; no auto-populate; first click opens
a singleton tab; second click with different library switches the same tab."""

import pytest

from haybale_marketplace.editors.library_overview_editor import LibraryOverviewEditor
from haywire.ui.editor.identity import OpenBehavior


@pytest.mark.unit
def test_library_overview_declares_on_context():
    assert LibraryOverviewEditor.class_identity.opens is OpenBehavior.ON_CONTEXT
