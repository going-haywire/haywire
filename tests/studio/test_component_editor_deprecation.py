"""ComponentDocsEditor renders a deprecation banner when identity.deprecation_warning is set."""

import inspect
import pytest

from haybale_studio.editors.component_docs_editor import ComponentDocsEditor


@pytest.mark.unit
def test_rebuild_reads_deprecation_warning():
    src = inspect.getsource(ComponentDocsEditor._rebuild)
    assert "deprecation_warning" in src
