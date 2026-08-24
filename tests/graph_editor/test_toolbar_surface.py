"""SelectionToolbar: a root surface of its own, hosting SelectionMenu behind the ⋯."""

from haybale_graph_editor.surfaces import SelectionActions, SelectionMenu, SelectionToolbar


def test_toolbar_surface_has_distinct_id():
    assert SelectionToolbar.id == "toolbar"
    assert SelectionToolbar.id != SelectionMenu.id


def test_toolbar_surface_polls_like_the_selection_menu(make_ctx_with_selection):
    # poll() is True iff there is a non-empty selection (any node/edge).
    ctx_empty = make_ctx_with_selection(nodes=set(), edges=set())
    ctx_one = make_ctx_with_selection(nodes={"n1"}, edges=set())
    assert SelectionToolbar.poll(ctx_empty) is False
    assert SelectionToolbar.poll(ctx_one) is True


def test_toolbar_declares_no_presentation():
    """It is a root surface, but not a properties tab — the strip skips it."""
    assert SelectionToolbar.presentation is None


def test_toolbar_provides_selection_actions():
    """There is no separate ToolbarActions any more: the ⋯ hosts SelectionMenu,
    so the toolbar's host must satisfy the same contract the menu's panels use.
    """
    assert SelectionToolbar.provides is SelectionActions


def test_selection_actions_is_runtime_checkable():
    # @runtime_checkable is the real contract: render_surface validates the
    # chosen host with isinstance(), which static typing cannot enforce.
    class _Provider:
        def copy_selection(self) -> None: ...
        def paste_at_click(self) -> None: ...
        def delete_selection(self) -> None: ...
        def redraw_selection(self) -> None: ...
        def revalidate_selection(self) -> None: ...
        def reset_selection(self) -> None: ...
        def dissolve_reroute(self, node_id: str) -> None: ...

    class _PartialProvider:
        """Three of seven — what SelectionToolbarProvider used to be."""

        def copy_selection(self) -> None: ...
        def delete_selection(self) -> None: ...
        def open_overflow_menu(self) -> None: ...

    assert isinstance(_Provider(), SelectionActions)
    assert not isinstance(_PartialProvider(), SelectionActions)
