"""node_menu_builder surfaces deprecation_warning on deprecated node entries."""

import inspect
import pytest

from haybale_graph_editor.editors.graph_canvas.node_menu_builder import NodeMenuBuilder


@pytest.mark.unit
def test_create_menu_item_reads_deprecation_warning():
    src = inspect.getsource(NodeMenuBuilder._create_menu_item_for_node)
    assert "deprecation_warning" in src


@pytest.mark.unit
def test_create_search_result_reads_deprecation_warning():
    src = inspect.getsource(NodeMenuBuilder._create_search_result_item)
    assert "deprecation_warning" in src
