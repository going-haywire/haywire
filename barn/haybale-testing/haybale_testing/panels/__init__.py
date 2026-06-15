from .graph.menu.canvas.canvas import TestCreateNodeMenuPanel
from .graph.menu.canvas.canvas import TestSessionStateMenuPanel
from .graph.menu.edge.edge import TestDeleteEdgeMenuPanel
from .graph.menu.edge.edge import TestInspectEdgeMenuPanel
from .graph.menu.edge.edge import TestEdgeErrorsMenuPanel
from .graph.menu.edge.edge import TestEdgePathMenuPanel
from .graph.menu.edge.edge import TestEdgeWarningsMenuPanel
from .graph.menu.node.node import TestDeleteNodeMenuPanel
from .graph.menu.node.node import TestCopyNodeMenuPanel
from .graph.menu.node.node import TestRedrawNodeMenuPanel
from .graph.menu.node.node import TestRevalidateNodeMenuPanel
from .graph.menu.node.node import TestResetNodeMenuPanel
from .graph.menu.selection.selection import TestCopySelectionMenuPanel
from .graph.menu.selection.selection import TestPasteSelectionMenuPanel

# Backwards-compat aliases for external consumers using old names
TestCreateNodePanel = TestCreateNodeMenuPanel
TestDeleteEdgePanel = TestDeleteEdgeMenuPanel
TestInspectEdgePanel = TestInspectEdgeMenuPanel
TestEdgeErrorsPanel = TestEdgeErrorsMenuPanel
TestEdgeConnectionPathPanel = TestEdgePathMenuPanel
TestEdgeWarningsPanel = TestEdgeWarningsMenuPanel
TestDeleteNodePanel = TestDeleteNodeMenuPanel
TestCopyNodePanel = TestCopyNodeMenuPanel
TestRedrawNodePanel = TestRedrawNodeMenuPanel
TestRevalidateNodePanel = TestRevalidateNodeMenuPanel
TestResetNodePanel = TestResetNodeMenuPanel
TestCopySelectionPanel = TestCopySelectionMenuPanel
TestPasteSelectionPanel = TestPasteSelectionMenuPanel
TestSessionStatePanel = TestSessionStateMenuPanel


__all__ = [
    "TestCopyNodeMenuPanel",
    "TestCopyNodePanel",
    "TestCopySelectionMenuPanel",
    "TestCopySelectionPanel",
    "TestCreateNodeMenuPanel",
    "TestCreateNodePanel",
    "TestDeleteEdgeMenuPanel",
    "TestDeleteEdgePanel",
    "TestDeleteNodeMenuPanel",
    "TestDeleteNodePanel",
    "TestEdgeConnectionPathPanel",
    "TestEdgeErrorsMenuPanel",
    "TestEdgeErrorsPanel",
    "TestEdgePathMenuPanel",
    "TestEdgeWarningsMenuPanel",
    "TestEdgeWarningsPanel",
    "TestInspectEdgeMenuPanel",
    "TestInspectEdgePanel",
    "TestPasteSelectionMenuPanel",
    "TestPasteSelectionPanel",
    "TestRedrawNodeMenuPanel",
    "TestRedrawNodePanel",
    "TestResetNodeMenuPanel",
    "TestResetNodePanel",
    "TestRevalidateNodeMenuPanel",
    "TestRevalidateNodePanel",
    "TestSessionStateMenuPanel",
    "TestSessionStatePanel",
]
