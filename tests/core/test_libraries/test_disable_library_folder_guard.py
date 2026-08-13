"""LibraryRegistry.disable_library() refuses FOLDER-mechanism libraries.

The one guard core can compute without workspace context — see
internals/handoff/library-origin-and-required-classification.md,
"Known, accepted asymmetry" section. project_local protection stays
UI-layer-only; this guard covers FOLDER only (today: builtin).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from haywire.core.library.install_type import InstallType
from haywire.core.library.registry import LibraryRegistry


def make_library_mock(library_id: str = "builtin") -> MagicMock:
    lib = MagicMock()
    lib.identity.name = library_id
    lib.identity.label = library_id.capitalize()
    return lib


def register_with_install_type(
    reg: LibraryRegistry, library_id: str, install_type: InstallType
) -> MagicMock:
    lib = make_library_mock(library_id)
    reg._libraries[library_id] = lib
    reg._library_install_types[library_id] = install_type
    return lib


class TestDisableLibraryFolderGuard:
    def test_folder_library_cannot_be_disabled(self):
        reg = LibraryRegistry()
        lib = register_with_install_type(reg, "builtin", InstallType.FOLDER)

        result = reg.disable_library("builtin")

        assert result is False
        lib.disable.assert_not_called()

    def test_editable_library_can_still_be_disabled(self):
        # The guard is FOLDER-only — must not regress EDITABLE/REGULAR.
        reg = LibraryRegistry()
        lib = register_with_install_type(reg, "haybale-foo", InstallType.EDITABLE)

        result = reg.disable_library("haybale-foo")

        assert result is True
        lib.disable.assert_called_once()

    def test_regular_library_can_still_be_disabled(self):
        reg = LibraryRegistry()
        lib = register_with_install_type(reg, "some-pkg", InstallType.REGULAR)

        result = reg.disable_library("some-pkg")

        assert result is True
        lib.disable.assert_called_once()

    def test_unknown_library_still_returns_false(self):
        # Pre-existing not-found behavior, unaffected by the new guard.
        reg = LibraryRegistry()
        assert reg.disable_library("does-not-exist") is False

    def test_folder_library_with_no_tracked_install_type_is_not_blocked(self):
        # A library present in _libraries but never scanned (no entry in
        # _library_install_types) must not be blocked by a guard it can't
        # evaluate — mirrors get_library_install_type()'s own None-safe read.
        reg = LibraryRegistry()
        lib = make_library_mock("untracked")
        reg._libraries["untracked"] = lib
        # Deliberately no reg._library_install_types["untracked"] = ...

        result = reg.disable_library("untracked")

        assert result is True
        lib.disable.assert_called_once()
