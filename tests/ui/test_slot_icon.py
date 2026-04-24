"""Tests for IconSlot — the bar-of-icons variant for left/right slots."""

from types import SimpleNamespace

from haywire.ui.app.icon_slot import IconSlot
from haywire.ui.app.slot import EditorBinding


class _FakeRegistry:
    """Stub EditorTypeRegistry — only lifecycle hooks matter for Slot construction."""

    def add_batch_event_subscriber(self, _cb) -> None:
        pass

    def remove_batch_event_subscriber(self, _cb) -> None:
        pass


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

    def _fake_separator(*_a, **_k):
        return _FakeContainer()

    def _fake_icon(*_a, **_k):
        return _FakeContainer()

    def _fake_label(*_a, **_k):
        return _FakeContainer()

    monkeypatch.setattr(mod.ui, "row", _fake_row)
    monkeypatch.setattr(mod.ui, "column", _fake_col)
    monkeypatch.setattr(mod.ui, "button", _fake_button)
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
    state = SimpleNamespace(active_tab_key="a", visible=True, size=300)
    slot = IconSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=_REGISTRY,
        initial_bindings=[EditorBinding(editor_key="a", editor_cls=a)],
        slot_state=state,
        bar_place="left",
    )
    parent = _FakeContainer()
    slot.render(parent)

    kinds = [k for k, _ in created]
    # A row wrapper, then a column for the bar, then the area tab_panels.
    assert kinds[0] == "row"
    assert "col" in kinds
    assert "tab_panels" in kinds


def test_icon_slot_bar_click_fires_switch_and_workspace_changed(monkeypatch):
    from haywire.ui.context_events import ContextChangeType

    created = _install_ui_fakes(monkeypatch)
    a = _editor_cls("a")
    b = _editor_cls("b")
    notified = []
    session = SimpleNamespace(context=None, notify_context_changed=notified.append)
    state = SimpleNamespace(active_tab_key="a", visible=True, size=300)
    slot = IconSlot(
        session=session,
        name="left",
        registry=_REGISTRY,
        initial_bindings=[
            EditorBinding(editor_key="a", editor_cls=a),
            EditorBinding(editor_key="b", editor_cls=b),
        ],
        active_key="a",
        slot_state=state,
        bar_place="left",
    )
    slot.render(_FakeContainer())

    buttons = [c for (kind, c) in created if kind == "button" and getattr(c, "icon", None) == "ic"]
    # Two icon buttons rendered (one per binding).
    assert len(buttons) >= 2
    buttons[1].on_click()  # click the 'b' icon

    assert slot.active_key == "b"
    assert state.active_tab_key == "b"
    assert len(notified) == 1
    assert notified[0].change_type == ContextChangeType.WORKSPACE_CHANGED


def test_icon_slot_fold_toggle_flips_visible(monkeypatch):
    created = _install_ui_fakes(monkeypatch)
    a = _editor_cls("a")
    state = SimpleNamespace(active_tab_key="a", visible=True, size=300)
    vis_calls = []
    slot = IconSlot(
        session=SimpleNamespace(context=None, notify_context_changed=lambda _e: None),
        name="left",
        registry=_REGISTRY,
        initial_bindings=[EditorBinding(editor_key="a", editor_cls=a)],
        slot_state=state,
        bar_place="left",
        on_visibility_change=vis_calls.append,
    )
    slot.render(_FakeContainer())

    # The fold toggle is the first button created (before the icon buttons).
    fold_btns = [c for (kind, c) in created if kind == "button" and getattr(c, "icon", None) != "ic"]
    assert fold_btns, "fold toggle button should be present"
    fold_btns[0].on_click()
    assert slot.visible is False
    assert state.visible is False
    assert vis_calls == [False]
