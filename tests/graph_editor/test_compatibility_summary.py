"""The visual layer can summarise compatibility findings for the on-open notice."""

import haywire.core.graph.editor  # noqa: F401  circular-import guard (CLAUDE.md)

import pytest

from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import (
    summarize_compatibility,
)


@pytest.mark.unit
class TestSummarizeCompatibility:
    def test_none_when_no_findings(self):
        assert summarize_compatibility(node_warning_count=0, library_messages=[]) is None

    def test_counts_affected_nodes(self):
        msg = summarize_compatibility(node_warning_count=3, library_messages=[])
        assert "3" in msg
        assert "node" in msg.lower()

    def test_includes_library_wide_messages(self):
        msg = summarize_compatibility(node_warning_count=0, library_messages=["FRAME default changed"])
        assert "FRAME default changed" in msg

    def test_combines_both(self):
        msg = summarize_compatibility(node_warning_count=2, library_messages=["lib change"])
        assert "2" in msg and "lib change" in msg
