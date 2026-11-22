from __future__ import annotations

from haybale_testing.panels.graph.menu.canvas.canvas import (
    TestCreateNodeMenuPanel,
    TestSessionStateMenuPanel,
)
from haybale_testing.panels.graph.menu.edge.edge import (
    TestDeleteEdgeMenuPanel,
    TestEdgeErrorsMenuPanel,
    TestEdgePathMenuPanel,
    TestEdgeWarningsMenuPanel,
    TestInspectEdgeMenuPanel,
)
from haybale_testing.panels.graph.menu.node.node import (
    TestCopyNodeMenuPanel,
    TestDeleteNodeMenuPanel,
    TestRedrawNodeMenuPanel,
    TestResetNodeMenuPanel,
    TestRevalidateNodeMenuPanel,
)
from haybale_testing.panels.graph.menu.selection.selection import (
    TestCopySelectionMenuPanel,
    TestPasteSelectionMenuPanel,
)

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
