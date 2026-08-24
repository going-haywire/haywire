from haybale_graph_editor.surfaces import SelectionMenu, SelectionToolbar
from haybale_graph_editor.panels.graph.toolbar.selection import (
    CopyToolbarPanel,
    DeleteToolbarPanel,
    SelectionOverflowPanel,
)


def test_panels_sit_on_the_toolbar_surface():
    for cls in (CopyToolbarPanel, DeleteToolbarPanel, SelectionOverflowPanel):
        assert cls.class_identity.surface is SelectionToolbar


def test_overflow_hosts_the_selection_menu():
    """The ⋯ renders SelectionMenu directly rather than round-tripping a
    synthetic event through the canvas to reopen it."""
    assert SelectionOverflowPanel.class_identity.hosts == (SelectionMenu,)


def test_copy_and_delete_are_leaves():
    """A leaf is what the popup-emptiness rule counts as content."""
    assert CopyToolbarPanel.class_identity.hosts == ()
    assert DeleteToolbarPanel.class_identity.hosts == ()


def test_panels_declare_no_poll_of_their_own(make_ctx_with_selection):
    """SelectionToolbar.poll is exactly "something is selected"; the host gates
    the surface once before querying, so restating that on each panel would be
    a second place to keep in sync for no behaviour."""
    empty = make_ctx_with_selection(nodes=set(), edges=set())
    for cls in (CopyToolbarPanel, DeleteToolbarPanel, SelectionOverflowPanel):
        assert cls.poll(empty) is True
    assert SelectionToolbar.poll(empty) is False
