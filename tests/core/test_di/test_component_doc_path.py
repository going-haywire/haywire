"""``LibrarySystemService.get_component_doc_path`` finds the page ``haywire docs`` wrote."""

from types import SimpleNamespace

import pytest

from haywire.core.di.config import LibrarySystemService
from haywire.core.library.kinds import doc_filename

pytestmark = pytest.mark.unit


def _service(source_path):
    """A service stand-in whose library registry knows one source folder."""
    registry = SimpleNamespace(get_library_source=lambda lib_id: str(source_path))
    return SimpleNamespace(get_library_registry=lambda: registry)


@pytest.mark.parametrize("registry_key", ["lib:node:Thing", "lib:macro:blur-twice"])
def test_resolves_the_generated_page(tmp_path, registry_key):
    page = tmp_path / "docs" / doc_filename(registry_key)
    page.parent.mkdir()
    page.write_text("# Thing\n")

    assert LibrarySystemService.get_component_doc_path(_service(tmp_path), registry_key) == page


def test_none_when_no_page_was_generated(tmp_path):
    assert LibrarySystemService.get_component_doc_path(_service(tmp_path), "lib:node:Thing") is None
