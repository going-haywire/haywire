import haywire.core.graph.editor  # noqa: F401  # import first to avoid circular import (CLAUDE.md)

import pytest

from haywire.barn.builtin import Library


def test_builtin_library_identity():
    """The bundled builtin library declares id='builtin'."""
    assert Library.class_identity.id == "builtin"


def test_builtin_library_is_baselibrary():
    from haywire.core.library.base import BaseLibrary

    assert issubclass(Library, BaseLibrary)


@pytest.mark.integration
def test_builtin_library_discovered_at_priority_one():
    """The registry discovers the bundled builtin library via core_libraries_path."""
    from pathlib import Path

    import haywire.barn as barn
    from haywire.core.library.registry import LibraryRegistry

    reg = LibraryRegistry()
    reg.load_core_libraries = True
    reg.core_libraries_path = str(Path(barn.__file__).parent)

    discovered = reg._discover_core_libraries()
    ids = [d.identity.id for d in discovered]
    assert "builtin" in ids
