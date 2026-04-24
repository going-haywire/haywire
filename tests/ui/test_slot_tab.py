"""Tests for TabSlot — the tabbed variant for main/bottom slots."""

from types import SimpleNamespace

from haywire.ui.app.tab_slot import TabSlot
from haywire.ui.app.slot import EditorBinding
from haywire.ui.editor.identity import OpenBehavior
from haywire.ui.workspace.workspace_state import TabState


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

    def delete(self):
        self.deleted = True

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
    from haywire.ui.app import tab_slot as mod
    from haywire.ui.app import slot as slot_mod

    created = []

    def _factory(kind):
        def _make(*_a, **_k):
            c = _FakeContainer()
            c._kind = kind
            c._args = _a
            c._kwargs = _k
            created.append((kind, c))
            return c

        return _make

    for kind in ["row", "column", "button", "label", "icon", "separator"]:
        monkeypatch.setattr(mod.ui, kind, _factory(kind), raising=False)
    monkeypatch.setattr(mod.ui, "tabs", _factory("tabs"), raising=False)
    monkeypatch.setattr(mod.ui, "tab", _factory("tab"), raising=False)
    monkeypatch.setattr(slot_mod.ui, "tab_panels", _factory("tab_panels"))
    monkeypatch.setattr(slot_mod.ui, "tab_panel", _factory("tab_panel"))
    monkeypatch.setattr(slot_mod.ui, "label", _factory("label"))
    return created


def _editor_cls(key, opens=OpenBehavior.ON_PAYLOAD, label="Lbl"):
    return type(
        f"_E_{key}",
        (),
        {"class_identity": SimpleNamespace(registry_key=key, label=label, opens=opens)},
    )


def test_tab_slot_open_tab_adds_binding_and_tabstate(monkeypatch):
    _install_ui_fakes(monkeypatch)
    cls = _editor_cls("a")
    state = SimpleNamespace(tabs=[TabState()], active_tab_key=None)
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=_REGISTRY,
        initial_bindings=[],
        slot_state=state,
    )
    slot.render(_FakeContainer())

    opened = slot.open_tab(cls, editor_key="a", payload="/tmp/a", label="a.graph")
    assert opened is True
    assert state.active_tab_key == "a::/tmp/a"
    assert any(t.editor_key == "a" and t.payload == "/tmp/a" for t in state.tabs)
    assert slot.find_binding("a", "/tmp/a") is not None


def test_tab_slot_open_tab_existing_activates_no_duplicate(monkeypatch):
    _install_ui_fakes(monkeypatch)
    cls = _editor_cls("a")
    state = SimpleNamespace(
        tabs=[TabState(editor_key="a", label="a", metadata={"payload": "/tmp/a"})],
        active_tab_key="a::/tmp/a",
    )
    binding = EditorBinding(editor_key="a", editor_cls=cls, payload="/tmp/a")
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=_REGISTRY,
        initial_bindings=[binding],
        active_key="a::/tmp/a",
        slot_state=state,
    )
    slot.render(_FakeContainer())

    # Already the active tab: open returns False (no change).
    assert slot.open_tab(cls, "a", "/tmp/a", "a") is False
    assert len([t for t in state.tabs if t.editor_key == "a"]) == 1


def test_tab_slot_close_tab_removes_and_promotes_sibling(monkeypatch):
    _install_ui_fakes(monkeypatch)
    cls_a = _editor_cls("a")
    cls_b = _editor_cls("b")
    state = SimpleNamespace(
        tabs=[
            TabState(editor_key="a", label="a", metadata={"payload": "p1"}),
            TabState(editor_key="b", label="b", metadata={"payload": "p2"}),
        ],
        active_tab_key="a::p1",
    )
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=_REGISTRY,
        initial_bindings=[
            EditorBinding(editor_key="a", editor_cls=cls_a, payload="p1"),
            EditorBinding(editor_key="b", editor_cls=cls_b, payload="p2"),
        ],
        active_key="a::p1",
        slot_state=state,
    )
    slot.render(_FakeContainer())

    assert slot.close_tab("a", "p1") is True
    assert not any(t.editor_key == "a" and t.payload == "p1" for t in state.tabs)
    assert state.active_tab_key == "b::p2"


def test_tab_slot_repayload_tab_updates_ids(monkeypatch):
    _install_ui_fakes(monkeypatch)
    cls = _editor_cls("a")
    state = SimpleNamespace(
        tabs=[TabState(editor_key="a", label="a", metadata={"payload": "old"})],
        active_tab_key="a::old",
    )
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=_REGISTRY,
        initial_bindings=[EditorBinding(editor_key="a", editor_cls=cls, payload="old")],
        active_key="a::old",
        slot_state=state,
    )
    slot.render(_FakeContainer())

    assert slot.repayload_tab("a", "old", "new", new_label="new.graph") is True
    assert state.active_tab_key == "a::new"
    assert state.tabs[0].label == "new.graph"
    assert state.tabs[0].metadata["payload"] == "new"


def test_tab_slot_close_tabs_for_payload_closes_matching(monkeypatch):
    _install_ui_fakes(monkeypatch)
    cls = _editor_cls("a")
    state = SimpleNamespace(
        tabs=[
            TabState(editor_key="a", label="a", metadata={"payload": "p1"}),
            TabState(editor_key="a", label="a", metadata={"payload": "p2"}),
        ],
        active_tab_key="a::p1",
    )
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=_REGISTRY,
        initial_bindings=[
            EditorBinding(editor_key="a", editor_cls=cls, payload="p1"),
            EditorBinding(editor_key="a", editor_cls=cls, payload="p2"),
        ],
        active_key="a::p1",
        slot_state=state,
    )
    slot.render(_FakeContainer())

    closed = slot.close_tabs_for_payload("p1")
    assert closed == 1
    assert len([t for t in state.tabs if t.payload == "p1"]) == 0
    assert len([t for t in state.tabs if t.payload == "p2"]) == 1
