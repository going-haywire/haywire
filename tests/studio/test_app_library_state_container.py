"""Tests verifying HaywireApp exposes the LibraryStateContainer."""

from haywire.core.state import LibraryStateContainer


class TestAppLibraryStateContainer:
    def test_app_exposes_library_state_container(self):
        from haywire_studio.app import HaywireApp

        app = HaywireApp()
        assert hasattr(app, "library_state_container")
        assert isinstance(app.library_state_container, LibraryStateContainer)
