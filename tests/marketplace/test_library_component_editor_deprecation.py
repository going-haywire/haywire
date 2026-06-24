"""LibraryComponentEditor renders a deprecation banner when identity.deprecation_warning is set."""

import inspect
import pytest

from haybale_marketplace.editors.library_component_editor import LibraryComponentEditor


@pytest.mark.unit
def test_rebuild_reads_deprecation_warning():
    src = inspect.getsource(LibraryComponentEditor._rebuild)
    assert "deprecation_warning" in src
