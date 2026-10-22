from haybale_testing.panels.graph.menu.canvas.canvas import TestCreateNodeMenuPanel
from haybale_testing.panels.graph.menu.canvas.canvas import TestSessionStateMenuPanel
from haybale_testing.panels.graph.menu.edge.edge import TestDeleteEdgeMenuPanel
from haybale_testing.panels.graph.menu.edge.edge import TestInspectEdgeMenuPanel
from haybale_testing.panels.graph.menu.edge.edge import TestEdgeErrorsMenuPanel
from haybale_testing.panels.graph.menu.edge.edge import TestEdgePathMenuPanel
from haybale_testing.panels.graph.menu.edge.edge import TestEdgeWarningsMenuPanel
from haybale_testing.panels.graph.menu.node.node import TestDeleteNodeMenuPanel
from haybale_testing.panels.graph.menu.node.node import TestCopyNodeMenuPanel
from haybale_testing.panels.graph.menu.node.node import TestRedrawNodeMenuPanel
from haybale_testing.panels.graph.menu.node.node import TestRevalidateNodeMenuPanel
from haybale_testing.panels.graph.menu.node.node import TestResetNodeMenuPanel
from haybale_testing.panels.graph.menu.selection.selection import TestCopySelectionMenuPanel
from haybale_testing.panels.graph.menu.selection.selection import TestPasteSelectionMenuPanel

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
