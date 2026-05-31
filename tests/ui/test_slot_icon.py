"""Tests for IconSlot — the bar-of-icons variant for left/right slots."""

from types import SimpleNamespace

from haywire.core.session.signals import Reveal
from haywire.ui.app.icon_slot import IconSlot


class _FakeRegistry:
    """Stub EditorTypeRegistry — provides all subscriber hooks wrappers need."""

    def __init__(self):
        self._subscribers: dict = {}

    def add_batch_event_subscriber(self, _cb) -> None:
        pass

    def remove_batch_event_subscriber(self, _cb) -> None:
        pass

    def add_event_subscriber(self, key, cb) -> None:
        self._subscribers.setdefault(key, []).append(cb)

    def remove_event_subscriber(self, key, cb) -> None:
        if key in self._subscribers:
            try:
                self._subscribers[key].remove(cb)
            except ValueError:
                pass
            if not self._subscribers[key]:
                del self._subscribers[key]


_REGISTRY = _FakeRegistry()


class _FakeContainer:
    def __init__(self):
        self.clear_calls = 0
        self.visible = True
        self.value = None
        self.children = []
        self._props = {}
        self.handlers: dict = {}

    def clear(self):
        self.clear_calls += 1

    def set_visibility(self, v):
        self.visible = v

    def set_value(self, v):
        self.value = v

    def classes(self, *_a, **_k):
        return self

    def style(self, *_a, **_k):
        return self

    def props(self, *_a, **_k):
        return self

    def tooltip(self, *_a, **_k):
        return self

    def on(self, event=None, handler=None, *_a, **_k):
        # Capture per-element event handlers so tests can fire them
        # (e.g. the per-tab "click" the IconSlot wires for collapse/expand).
        if event is not None:
            self.handlers.setdefault(event, []).append(handler)
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


def _install_ui_fakes(monkeypatch):
    from haywire.ui.app import icon_slot as mod
    from haywire.ui.app import slot as slot_mod

    created = []

    def _fake_row(*_a, **_k):
        c = _FakeContainer()
        created.append(("row", c))
        return c

    def _fake_col(*_a, **_k):
        c = _FakeContainer()
        created.append(("col", c))
        return c

    def _fake_tab_panels(*_a, **_k):
        c = _FakeContainer()
        c.value = _k.get("value")
        created.append(("tab_panels", c))
        return c

    def _fake_tab_panel(name, *_a, **_k):
        c = _FakeContainer()
        c.name = name
        created.append(("tab_panel", c))
        return c

    def _fake_button(*_a, **_k):
        c = _FakeContainer()
        c.on_click = _k.get("on_click")
        c.icon = _k.get("icon")
        created.append(("button", c))
        return c

    def _fake_tabs(*_a, **_k):
        c = _FakeContainer()
        c.on_change = _k.get("on_change")
        c.value = _k.get("value")
        created.append(("tabs", c))
        return c

    def _fake_tab(*_a, **_k):
        c = _FakeContainer()
        c.name = _k.get("name") or (_a[0] if _a else None)
        c.icon = _k.get("icon")
        c._props = {"name": c.name}
        created.append(("tab", c))
        return c

    def _fake_separator(*_a, **_k):
        return _FakeContainer()

    def _fake_icon(*_a, **_k):
        return _FakeContainer()

    def _fake_label(*_a, **_k):
        return _FakeContainer()

    monkeypatch.setattr(mod.ui, "row", _fake_row)
    monkeypatch.setattr(mod.ui, "column", _fake_col)
    monkeypatch.setattr(mod.ui, "button", _fake_button)
    monkeypatch.setattr(mod.ui, "tabs", _fake_tabs)
    monkeypatch.setattr(mod.ui, "tab", _fake_tab)
    monkeypatch.setattr(mod.ui, "separator", _fake_separator)
    monkeypatch.setattr(mod.ui, "icon", _fake_icon)
    monkeypatch.setattr(slot_mod.ui, "tab_panels", _fake_tab_panels)
    monkeypatch.setattr(slot_mod.ui, "tab_panel", _fake_tab_panel)
    monkeypatch.setattr(slot_mod.ui, "label", _fake_label)
    return created


def _editor_cls(key, icon="ic", label="Lbl"):
    return type(
        f"_E_{key}",
        (),
        {"class_identity": SimpleNamespace(registry_key=key, icon=icon, label=label, opens="required")},
    )


def test_icon_slot_renders_row_with_bar_and_area(monkeypatch):
    created = _install_ui_fakes(monkeypatch)
    a = _editor_cls("a")
    reg = _FakeRegistry()
    slot = IconSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=reg,
        bar_place="left",
    )
    slot.add_binding(editor_key="a", editor_cls=a)
    slot._active = slot.find_binding("a")
    parent = _FakeContainer()
    slot.render(parent)

    kinds = [k for k, _ in created]
    # A row wrapper, then a column for the bar, then the area tab_panels.
    assert kinds[0] == "row"
    assert "col" in kinds
    assert "tab_panels" in kinds


def test_icon_slot_bar_change_switches_active_binding(monkeypatch):
    """Clicking a tab swaps the active binding. The legacy
    WORKSPACE_CHANGED emission was deleted (Q6A) — on_focus runs via
    Slot._activate during switch_to, no separate bus event is needed.

    Drives the per-tab click handler — the sole switch/collapse driver now
    that tabs ``on_change`` is no longer wired (it would race the click).
    """
    created = _install_ui_fakes(monkeypatch)
    a = _editor_cls("a")
    b = _editor_cls("b")
    signals = []
    session = SimpleNamespace(context=None, signal=signals.append)
    reg = _FakeRegistry()
    slot = IconSlot(
        session=session,
        name="left",
        registry=reg,
        bar_place="left",
    )
    slot.add_binding(editor_key="a", editor_cls=a)
    slot.add_binding(editor_key="b", editor_cls=b)
    slot._active = slot.find_binding("a")
    slot.render(_FakeContainer())

    tab_elements = [c for (kind, c) in created if kind == "tab"]
    assert len(tab_elements) == 2, "one tab per wrapper expected"

    _click_tab(created, "b")

    assert slot.active_key == "b"
    # No signal is emitted by the slot itself for the switch — on_focus
    # handles "wrapper just became active" directly, and any context-state
    # signals come from the editor's own on_focus implementation.
    assert signals == []


def _click_tab(created, name):
    """Fire the per-tab 'click' handler the IconSlot wired for ``name``."""
    tab = next(c for (kind, c) in created if kind == "tab" and c.name == name)
    for handler in tab.handlers.get("click", []):
        handler(SimpleNamespace())


def test_icon_slot_has_no_fold_toggle_button(monkeypatch):
    """The fold-toggle button is gone — collapse/expand is icon-driven now."""
    created = _install_ui_fakes(monkeypatch)
    a = _editor_cls("a")
    reg = _FakeRegistry()
    slot = IconSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=reg,
        bar_place="left",
    )
    slot.add_binding(editor_key="a", editor_cls=a)
    slot._active = slot.find_binding("a")
    slot.render(_FakeContainer())

    # No ui.button is created for the icon bar anymore.
    assert not [c for (kind, c) in created if kind == "button"]


def test_icon_slot_click_active_icon_collapses(monkeypatch):
    """Clicking the active icon collapses the slot (VS Code idiom)."""
    created = _install_ui_fakes(monkeypatch)
    a = _editor_cls("a")
    vis_calls = []
    reg = _FakeRegistry()
    slot = IconSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=reg,
        bar_place="left",
        on_visibility_change=vis_calls.append,
    )
    slot.add_binding(editor_key="a", editor_cls=a)
    slot._active = slot.find_binding("a")
    slot.render(_FakeContainer())

    _click_tab(created, "a")  # "a" is the active icon
    assert slot.visible is False
    assert vis_calls == [False]


def test_icon_slot_click_while_collapsed_reexpands(monkeypatch):
    """Clicking any icon while collapsed re-opens the slot."""
    created = _install_ui_fakes(monkeypatch)
    a = _editor_cls("a")
    vis_calls = []
    reg = _FakeRegistry()
    slot = IconSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=reg,
        bar_place="left",
        on_visibility_change=vis_calls.append,
    )
    slot.add_binding(editor_key="a", editor_cls=a)
    slot._active = slot.find_binding("a")
    slot.render(_FakeContainer())

    _click_tab(created, "a")  # collapse
    assert slot.visible is False
    _click_tab(created, "a")  # re-expand
    assert slot.visible is True
    assert vis_calls == [False, True]


def test_icon_slot_click_inactive_icon_switches_without_collapsing(monkeypatch):
    """Clicking a different icon switches the active editor and stays open.

    Regression: a tabs ``on_change`` handler used to race the per-tab click —
    on_change switched first (mutating _active), then the click handler saw
    the just-switched tab as active and collapsed the slot. The slot must NOT
    toggle visibility on a plain cross-tab click.
    """
    created = _install_ui_fakes(monkeypatch)
    a = _editor_cls("a")
    b = _editor_cls("b")
    vis_calls = []
    reg = _FakeRegistry()
    slot = IconSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=reg,
        bar_place="left",
        on_visibility_change=vis_calls.append,
    )
    slot.add_binding(editor_key="a", editor_cls=a)
    slot.add_binding(editor_key="b", editor_cls=b)
    slot._active = slot.find_binding("a")
    slot.render(_FakeContainer())

    _click_tab(created, "b")
    assert slot.active_key == "b"
    assert slot.visible is True
    # No visibility transition fired — the click only switched.
    assert vis_calls == []


def test_icon_slot_collapsed_click_other_icon_expands_and_switches(monkeypatch):
    """While collapsed, clicking a non-active icon expands AND switches to it."""
    created = _install_ui_fakes(monkeypatch)
    a = _editor_cls("a")
    b = _editor_cls("b")
    reg = _FakeRegistry()
    slot = IconSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=reg,
        bar_place="left",
    )
    slot.add_binding(editor_key="a", editor_cls=a)
    slot.add_binding(editor_key="b", editor_cls=b)
    slot._active = slot.find_binding("a")
    slot.render(_FakeContainer())

    _click_tab(created, "a")  # collapse (a is active)
    assert slot.visible is False
    _click_tab(created, "b")  # expand + switch to b
    assert slot.visible is True
    assert slot.active_key == "b"


def test_icon_slot_reveal_into_collapsed_slot_auto_expands(monkeypatch):
    """A programmatic reveal into a collapsed icon slot pops it open, even
    when the revealed editor is already the active one."""
    created = _install_ui_fakes(monkeypatch)
    a = _editor_cls("a")
    reg = _FakeRegistry()
    slot = IconSlot(
        session=SimpleNamespace(context=None),
        name="right",
        registry=reg,
        bar_place="right",
    )
    slot.add_binding(editor_key="a", editor_cls=a)
    slot._active = slot.find_binding("a")
    slot.render(_FakeContainer())

    _click_tab(created, "a")  # collapse; "a" stays the active binding
    assert slot.visible is False

    # Reveal the already-active editor — should re-open the slot.
    changed = slot.reveal(Reveal(editor=a, binding_id=None, label="A"))
    assert slot.visible is True
    assert changed is True  # the expand is the observable change
