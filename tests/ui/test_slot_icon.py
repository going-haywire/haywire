"""Tests for IconSlot — the bar-of-icons variant for left/right slots."""

from types import SimpleNamespace

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

    def on(self, *_a, **_k):
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
    """Selecting a tab swaps the active binding. The legacy
    WORKSPACE_CHANGED emission was deleted (Q6A) — on_focus runs via
    Slot._activate during switch_to, no separate bus event is needed.

    Drives the q-tabs change handler directly with the target tab element,
    mirroring how NiceGUI delivers ``on_change`` events.
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

    tabs_container = next(c for (kind, c) in created if kind == "tabs")
    tab_elements = [c for (kind, c) in created if kind == "tab"]
    assert len(tab_elements) == 2, "one tab per wrapper expected"

    # Simulate a Quasar value-change event: the payload's `value` is the
    # selected ui.tab element, not its name string.
    tab_b = next(t for t in tab_elements if t.name == "b")
    event = SimpleNamespace(value=tab_b)
    tabs_container.on_change(event)

    assert slot.active_key == "b"
    # No signal is emitted by the slot itself for the switch — on_focus
    # handles "wrapper just became active" directly, and any context-state
    # signals come from the editor's own on_focus implementation.
    assert signals == []


def test_icon_slot_fold_toggle_flips_visible(monkeypatch):
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

    # The fold toggle is the first button created (before the icon buttons).
    fold_btns = [c for (kind, c) in created if kind == "button" and getattr(c, "icon", None) != "ic"]
    assert fold_btns, "fold toggle button should be present"
    fold_btns[0].on_click()
    assert slot.visible is False
    assert vis_calls == [False]
