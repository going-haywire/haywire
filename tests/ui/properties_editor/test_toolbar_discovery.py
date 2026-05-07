# tests/ui/properties_editor/test_toolbar_discovery.py
"""PropertiesEditor toolbar = default_focus_ids ∪ registry.get_focuses_for(self),
sorted by Focus.order."""

from __future__ import annotations

from haywire.core.library.identity import LibraryIdentity
from haywire.ui.panel import Panel, PanelRegistry, panel
from haywire.ui.panel.focus import Focus

# Import the editor's actions Protocol so we can register a panel against it.
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    description="test",
    url="",
    help_url="",
    author="",
    author_url="",
    folder_path="/tmp/fake",
    module_name="fake",
    id="fake",
)


# A library-defined focus that PropertiesEditor doesn't know about by default.
class _LibraryFocus(Focus):
    id = "library_provided_focus_test"
    label = "Library Provided"
    icon = "library_books"
    order = 90

    @classmethod
    def available(cls, ctx):
        return True


@panel(
    action=PropertiesEditorActions,
    focus=_LibraryFocus,
    label="Library Panel",
)
class _LibraryProvidedPanel(Panel):
    def draw(self, ctx, layout, actions):
        pass


def test_toolbar_includes_default_focus_ids():
    """All default_focus_ids appear in the toolbar regardless of registered panels."""
    from haybale_studio.editors.properties_editor import PropertiesEditor
    from haybale_studio.focuses import AppFocus

    editor = PropertiesEditor(panel_registry=PanelRegistry())
    focuses = editor._compute_toolbar_focuses()
    # AppFocus should be in default_focus_ids.
    assert AppFocus in focuses


def test_toolbar_includes_library_focus_via_registry():
    """A library-defined focus appears in the toolbar via registry discovery."""
    from haybale_studio.editors.properties_editor import PropertiesEditor

    reg = PanelRegistry()
    reg._register_class(_LibraryProvidedPanel, _FAKE_LIBRARY_IDENTITY)
    editor = PropertiesEditor(panel_registry=reg)
    focuses = editor._compute_toolbar_focuses()
    assert _LibraryFocus in focuses


def test_toolbar_focuses_are_sorted_by_focus_order():
    from haybale_studio.editors.properties_editor import PropertiesEditor
    from haybale_studio.focuses import AppFocus, ExecutionFocus

    editor = PropertiesEditor(panel_registry=PanelRegistry())
    focuses = editor._compute_toolbar_focuses()
    app_idx = focuses.index(AppFocus)  # order 10
    exec_idx = focuses.index(ExecutionFocus)  # order 20
    assert app_idx < exec_idx
