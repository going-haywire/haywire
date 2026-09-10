"""The settings row's Developer submenu — "open the code behind this row".

Gated on ``ctx.developer_mode``. Two entries, each only when its registry key
resolves: the settings class the row renders, and the panel that drew it.

The key resolution is the part worth testing: a registered LibrarySettings /
FrameworkSettings carries its own identity, while a NodeSettings bag carries
none by design (settings_node.py) and must fall back to the owning node —
whose source file is where the inner ``class Settings`` is written anyway.
"""

import inspect
from pathlib import Path
from typing import Any, cast

import pytest
from nicegui import Client, ui
from nicegui.page import page as page_deco

from haywire.ui.panel.host_rendering import drawing_panel
from haywire.ui.panel.render_utils import (
    _bag_source_key,
    _build_developer_menu,
    _component_key,
    render_settings,
)

from tests.ui.panel.render_ctx import make_render_ctx

pytestmark = pytest.mark.unit


@page_deco("/_developer_row_menu_test")
def _noop_page() -> None:  # registration target for a headless Client
    pass


def _ctx(developer_mode: bool):
    ctx = make_render_ctx()
    ctx.developer_mode = developer_mode
    return ctx


def _walk(element):
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _render(bag, developer_mode: bool):
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(_ctx(developer_mode), bag)
    return anchor


def _labels(anchor) -> list[str]:
    return [e.text for e in _walk(anchor) if isinstance(e, ui.label) and e.text]


def _item_text(item: ui.menu_item) -> str:
    """A ``ui.menu_item``'s label.

    Neither a prop nor a child ``ui.label``: ``ui.menu_item(text)`` puts the
    string on a nested ``ui.item_section``, so a label-based scan misses it.
    """
    return next(
        (
            section.text
            for section in item.default_slot.children
            if isinstance(section, ui.item_section) and section.text
        ),
        "",
    )


def _has_developer_row(anchor) -> bool:
    return any(_item_text(e) == "Developer" for e in _walk(anchor) if isinstance(e, ui.menu_item))


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------


def test_no_developer_entry_when_developer_mode_is_off(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    assert not _has_developer_row(_render(node.filter, developer_mode=False))


def test_developer_entry_appears_when_developer_mode_is_on(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    assert _has_developer_row(_render(node.filter, developer_mode=True))


def test_source_key_resolution_is_skipped_when_developer_mode_is_off(make_node_with_setting, monkeypatch):
    """The gate must sit at the CALL SITE, before ``_bag_source_key`` /
    ``_component_key`` run — not just inside ``_build_developer_menu`` around
    the menu it draws. Those resolvers do registry lookups on every row's
    render; gating only the drawing still pays that cost on every session,
    developer mode or not."""
    import haywire.ui.panel.render_utils as render_utils_module

    calls: list[Any] = []
    original = render_utils_module._bag_source_key

    def _spy(obj):
        calls.append(obj)
        return original(obj)

    monkeypatch.setattr(render_utils_module, "_bag_source_key", _spy)

    node = make_node_with_setting(accessor="filter", field="threshold")
    _render(node.filter, developer_mode=False)

    assert calls == []


def test_the_ordinary_row_is_unchanged_by_the_flag(make_node_with_setting):
    """Developer mode ADDS one entry; it must not disturb the row or the menu
    entries that were already there."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    off = _render(node.filter, developer_mode=False)
    on = _render(node.filter, developer_mode=True)

    # The row's own labels (field name, widget chrome) are untouched.
    assert _labels(off) == _labels(on)

    # The menu gains exactly the Developer anchor, appended last.
    off_items = _top_level_items(off)
    on_items = _top_level_items(on)
    assert len(on_items) == len(off_items) + 1
    assert on_items[-1] is _developer_anchor(on)
    assert [_item_text(i) for i in on_items[:-1]] == [_item_text(i) for i in off_items]


# ---------------------------------------------------------------------------
# Key resolution
# ---------------------------------------------------------------------------


def test_node_settings_bag_falls_back_to_the_owning_node(make_node_with_setting):
    """A NodeSettings bag is never registered, so it has no key of its own —
    the owning node's key opens the same file the bag is declared in."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    bag = node.filter

    assert _component_key(bag) is None, "a NodeSettings bag must carry no identity"
    key = _bag_source_key(bag)
    assert key == _component_key(bag._node)
    assert key is not None
    assert key.endswith(":node:_PromotionTestNode")


def test_registered_settings_class_answers_its_own_key(library_system):
    from haywire.core.debug.debug_settings import DebugSettings

    assert _component_key(DebugSettings) == "__system__:setting:debug"


def test_a_declared_field_records_its_owning_class(library_system):
    """The registry render path has no bag instance — the owning class comes
    from the descriptor's _owner_cls, stamped at __set_name__."""
    from haywire.core.debug.debug_settings import DebugSettings

    defn = next(iter(DebugSettings._settings_descriptors().values()))
    assert _component_key(getattr(defn, "_owner_cls", None)) == "__system__:setting:debug"


def test_component_key_of_none_is_none():
    """Callers pass lookups that legitimately find nothing (no owning panel,
    no owning class); every one would otherwise need the same guard."""
    assert _component_key(None) is None


def test_component_key_of_an_unregistered_class_is_none():
    class NotRegistered:
        pass

    assert _component_key(NotRegistered) is None
    assert _component_key(NotRegistered()) is None


# ---------------------------------------------------------------------------
# The drawing-panel ContextVar
# ---------------------------------------------------------------------------


def test_drawing_panel_is_none_outside_a_panel():
    """Settings are also rendered outside any panel (the UI harness renders a
    bag straight onto a page), so None is an ordinary answer."""
    assert drawing_panel() is None


# ---------------------------------------------------------------------------
# Presentation — both of these shipped broken and were caught in the browser
# ---------------------------------------------------------------------------


def _context_menu(anchor):
    return next(e for e in _walk(anchor) if isinstance(e, ui.context_menu))


def _top_level_items(anchor) -> list:
    """The row menu's own entries — Reset/Promote and the Developer anchor."""
    return [c for c in _context_menu(anchor).default_slot.children if isinstance(c, ui.menu_item)]


def _developer_anchor(anchor):
    """The "Developer" flyout anchor, matched by TEXT.

    Not "the item that owns a FlyoutMenu" — the row menu grew a second flyout
    ("Promote to"), and that older test rendered the first one it found, which
    is now the promotion anchor.
    """
    from haywire.ui.elements.flyout import FlyoutMenu

    return next(
        item
        for item in _top_level_items(anchor)
        if _item_text(item) == "Developer"
        and any(isinstance(c, FlyoutMenu) for c in item.default_slot.children)
    )


def test_the_developer_anchor_is_not_greyed(make_node_with_setting):
    """Regression: built with hui.submenu_row, the anchor greyed ITSELF.

    SubmenuRow.__exit__ greys retroactively when nothing bumped
    flyout._leaves_drawn, and only render_panel bumps it — so a submenu of
    plain menu_items greyed out with its entries sitting inside it.
    """
    node = make_node_with_setting(accessor="filter", field="threshold")
    item = _developer_anchor(_render(node.filter, developer_mode=True))

    assert "hw-disabled" not in item._classes


def test_the_developer_anchor_is_a_menu_item_like_its_siblings(make_node_with_setting):
    """A row menu IS a QMenu, so its entries are q-items. A SubmenuRow is a
    hui.menu_row — built for a Popup column with no QMenu ancestor — and lands
    with different padding, out of alignment beside Reset and Promote."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    anchor = _render(node.filter, developer_mode=True)

    assert _developer_anchor(anchor) in _top_level_items(anchor)


def test_the_submenu_entries_do_not_wrap(make_node_with_setting):
    """Quasar flips the flyout leftward near a panel edge and shrink-to-fits,
    wrapping the longest label; a pinned leaf keeps the menu at its width."""
    from haywire.ui.elements.flyout import FlyoutMenu

    node = make_node_with_setting(accessor="filter", field="threshold")
    item = _developer_anchor(_render(node.filter, developer_mode=True))
    body = next(c for c in item.default_slot.children if isinstance(c, FlyoutMenu))

    leaves = [e for e in _walk(body) if isinstance(e, ui.menu_item)]
    assert leaves, "the flyout drew no entries"
    for leaf in leaves:
        assert leaf._style.get("white-space") == "nowrap", (
            f"{_item_text(leaf)!r} may wrap when the flyout opens leftward"
        )


def test_the_developer_anchor_matches_its_siblings_density(make_node_with_setting):
    """flyout_category defaults to dense (right for NodeMenuBuilder, whose own
    leaves are dense). A settings row's items are not dense, and a dense q-item
    has smaller padding — so the anchor sat visibly shorter than the menu."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    items = _top_level_items(_render(node.filter, developer_mode=True))

    densities = {item._props.get("dense") for item in items}
    assert len(densities) == 1, f"the Developer row must match its siblings, got {densities}"


def test_a_bag_with_no_resolvable_keys_draws_no_developer_row():
    """An unregistered bag rendered outside a panel resolves neither entry, so
    the submenu is dropped rather than drawn empty."""
    from haywire.core.settings import setting
    from haywire.core.settings.settings import Settings
    from haywire.barn.builtin.types import FLOAT

    class Orphan(Settings):
        value = setting[FLOAT](0.5)

    anchor = _render(Orphan(), developer_mode=True)
    assert not _has_developer_row(anchor), "an empty Developer submenu must not be drawn"


# ---------------------------------------------------------------------------
# The dependency boundary
#
# Core knows a registry key but must NOT know an editor class: naming one means
# haywire-core importing a barn library, the arrow backwards
# (.insights/project_app_library_dependency_direction.md). Core publishes;
# haybale-studio answers. A `try: import haybale_studio / except ImportError`
# reads as defensive and is the same illegal edge, just silently.
# ---------------------------------------------------------------------------


def _click(item: ui.menu_item) -> None:
    listener_id = next(iter(item._event_listeners))
    item._handle_event({"listener_id": listener_id, "args": {}})


def test_the_two_entries_are_siblings_of_each_other():
    """Regression: each entry's own sub-flyout ("A", "B" below) must land in
    the SAME sibling group as its neighbour, not a fresh private one-item
    group per entry.

    A fresh group per entry silently breaks hover sibling-close: opening one
    entry's body then has nothing else registered to close, so a second entry
    opened right after leaves the first one's body still visible onscreen
    (caught in manual review, not by an earlier version of this test). Uses
    _build_developer_menu directly with two always-resolving synthetic
    entries — going through render_settings's real settings-row fixture only
    ever resolves ONE of its two built-in entries (drawing_panel() is None
    outside a real panel), which is why this needs its own two-entry case.
    """
    from haywire.ui.elements.flyout import FlyoutMenu

    ctx = _ctx(developer_mode=True)
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        column = ui.column()
        with column, ui.context_menu():
            _build_developer_menu(ctx, ("A", "lib:setting:A"), ("B", "lib:setting:B"))

    top_items = [c for c in _context_menu(column).default_slot.children if isinstance(c, ui.menu_item)]
    dev_anchor = next(item for item in top_items if _item_text(item) == "Developer")
    dev_body = next(c for c in dev_anchor.default_slot.children if isinstance(c, FlyoutMenu))

    entry_anchors = [c for c in dev_body.default_slot.children if isinstance(c, ui.menu_item)]
    assert {_item_text(a) for a in entry_anchors} == {"A", "B"}

    entry_submenus = [
        next(c for c in a.default_slot.children if isinstance(c, FlyoutMenu)) for a in entry_anchors
    ]
    # Both entries' own sub-flyouts must be registered as children of the SAME
    # Developer-level FlyoutMenu — that shared list is the sibling group
    # open_on_hover closes against.
    assert set(dev_body._child_flyouts) == set(entry_submenus)


def test_settings_source_entry_nests_view_and_edit_leaves(make_node_with_setting):
    """ "Settings source" is not itself clickable — it is a sub-flyout anchor
    offering the two targets, "Open in Context" (CONTEXT) and "Open in Code
    Editor" (EDIT)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    ctx = _ctx(developer_mode=True)

    client = Client(cast(Any, _noop_page), request=None)
    with client:
        column = ui.column()
        with column:
            render_settings(ctx, node.filter)

    anchor = next(
        leaf
        for leaf in _walk(_developer_anchor(column))
        if isinstance(leaf, ui.menu_item) and _item_text(leaf) == "Settings source"
    )
    leaf_labels = {
        _item_text(leaf) for leaf in _walk(anchor) if isinstance(leaf, ui.menu_item) and leaf is not anchor
    }
    assert leaf_labels == {"Open in Context", "Open in Code Editor"}


def test_clicking_view_source_publishes_reveal_with_context_target(make_node_with_setting):
    from haywire.core.signals import RevealComponentSource

    node = make_node_with_setting(accessor="filter", field="threshold")
    ctx = _ctx(developer_mode=True)

    client = Client(cast(Any, _noop_page), request=None)
    with client:
        column = ui.column()
        with column:
            render_settings(ctx, node.filter)

    anchor = next(
        leaf
        for leaf in _walk(_developer_anchor(column))
        if isinstance(leaf, ui.menu_item) and _item_text(leaf) == "Settings source"
    )
    item = next(
        leaf
        for leaf in _walk(anchor)
        if isinstance(leaf, ui.menu_item) and _item_text(leaf) == "Open in Context"
    )
    _click(item)

    published = [c.args[0] for c in ctx.session.publish.call_args_list]
    reveals = [s for s in published if isinstance(s, RevealComponentSource)]
    assert len(reveals) == 1
    assert reveals[0].registry_key == _bag_source_key(node.filter)


def test_clicking_open_in_code_editor_publishes_reveal_source(make_node_with_setting):
    """The two entries publish two DIFFERENT signals, not one signal with a
    discriminator: each is fully handled by whichever editor claims it."""
    from haywire.core.signals import RevealSource

    node = make_node_with_setting(accessor="filter", field="threshold")
    ctx = _ctx(developer_mode=True)
    # Core resolves the key to a path ITSELF (that is what lets the signal be
    # file-shaped); the stub app must therefore answer the class lookup.
    ctx.app.library_service.lookup_component_class.return_value = type(node)

    client = Client(cast(Any, _noop_page), request=None)
    with client:
        column = ui.column()
        with column:
            render_settings(ctx, node.filter)

    anchor = next(
        leaf
        for leaf in _walk(_developer_anchor(column))
        if isinstance(leaf, ui.menu_item) and _item_text(leaf) == "Settings source"
    )
    item = next(
        leaf
        for leaf in _walk(anchor)
        if isinstance(leaf, ui.menu_item) and _item_text(leaf) == "Open in Code Editor"
    )
    _click(item)

    published = [c.args[0] for c in ctx.session.publish.call_args_list]
    reveals = [s for s in published if isinstance(s, RevealSource)]
    assert len(reveals) == 1
    assert reveals[0].binding_id == inspect.getfile(type(node))
    assert reveals[0].label == Path(reveals[0].binding_id).name


def test_render_utils_does_not_import_any_barn_library():
    """The rule as a test, not only as a lint config: this module is core UI and
    must not name a haybale_* package anywhere, including inside a function."""
    import inspect

    from haywire.ui.panel import render_utils

    source = inspect.getsource(render_utils)
    offenders = [
        line
        for line in source.splitlines()
        if line.lstrip().startswith(("import haybale_", "from haybale_"))
    ]
    assert offenders == [], f"core must not import a barn library: {offenders}"
