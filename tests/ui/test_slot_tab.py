"""Tests for TabSlot — the tabbed variant for main/bottom slots."""

from types import SimpleNamespace

from haywire.core.session.signals import Reveal
from haywire.ui.app.tab_slot import TabSlot
from haywire.ui.editor.identity import OpenBehavior


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


def test_tab_slot_reveal_adds_binding_and_makes_active(monkeypatch):
    _install_ui_fakes(monkeypatch)
    cls = _editor_cls("a")
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=reg,
    )
    slot.render(_FakeContainer())

    opened = slot.reveal(Reveal(editor=cls, binding_id="/tmp/a", label="a.graph"))
    assert opened is True
    assert slot.active_binding_id == "a::/tmp/a"
    assert slot.find_binding("a", "/tmp/a") is not None


def test_tab_slot_reveal_existing_activates_no_duplicate(monkeypatch):
    _install_ui_fakes(monkeypatch)
    cls = _editor_cls("a")
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=reg,
    )
    slot.add_binding(editor_key="a", editor_cls=cls, binding_id="/tmp/a")
    binding = slot.find_binding("a", "/tmp/a")
    slot._active = binding
    slot.render(_FakeContainer())

    # Already the active tab: reveal returns False (no change).
    assert slot.reveal(Reveal(editor=cls, binding_id="/tmp/a", label="a")) is False
    assert len([b for b in slot.bindings if b.editor_key == "a"]) == 1


def test_tab_slot_close_binding_removes_and_promotes_sibling(monkeypatch):
    _install_ui_fakes(monkeypatch)
    cls_a = _editor_cls("a")
    cls_b = _editor_cls("b")
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=reg,
    )
    slot.add_binding(editor_key="a", editor_cls=cls_a, binding_id="p1")
    slot.add_binding(editor_key="b", editor_cls=cls_b, binding_id="p2")
    wrapper_a = slot.find_binding("a", "p1")
    slot._active = wrapper_a
    slot.render(_FakeContainer())

    assert slot.close_binding(wrapper_a) is True
    assert slot.find_binding("a", "p1") is None
    assert slot.active_binding_id == "b::p2"


def test_tab_slot_repayload_updates_ids(monkeypatch):
    _install_ui_fakes(monkeypatch)
    cls = _editor_cls("a")
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=reg,
    )
    slot.add_binding(editor_key="a", editor_cls=cls, binding_id="old")
    wrapper = slot.find_binding("a", "old")
    slot._active = wrapper
    slot.render(_FakeContainer())

    assert slot.repayload(wrapper, "new", new_label="new.graph") is True
    assert slot.active_binding_id == "a::new"
    assert slot.find_binding("a", "new") is not None
    assert slot.find_binding("a", "old") is None


def test_tab_slot_close_tabs_for_payload_closes_matching(monkeypatch):
    _install_ui_fakes(monkeypatch)
    cls = _editor_cls("a")
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=reg,
    )
    slot.add_binding(editor_key="a", editor_cls=cls, binding_id="p1")
    slot.add_binding(editor_key="a", editor_cls=cls, binding_id="p2")
    slot._active = slot.find_binding("a", "p1")
    slot.render(_FakeContainer())

    closed = slot.close_tabs_for("p1")
    assert closed == 1
    assert slot.find_binding("a", "p1") is None
    assert slot.find_binding("a", "p2") is not None


# ---------------------------------------------------------------------------
# Task 7: X-button calls wrapper.close() directly (no event)
# ---------------------------------------------------------------------------


import asyncio  # noqa: E402


def _run_async(coro):
    """Worker-thread runner for async tests — see test_editor_wrapper.py."""
    import threading

    box: list = []

    def _runner():
        loop = asyncio.new_event_loop()
        try:
            box.append(("ok", loop.run_until_complete(coro)))
        except BaseException as e:
            box.append(("err", e))
        finally:
            loop.close()

    t = threading.Thread(target=_runner)
    t.start()
    t.join()
    tag, value = box[0]
    if tag == "err":
        raise value
    return value


class _VetoEditor:
    """Editor that vetoes close based on .allow."""

    class_identity = SimpleNamespace(
        registry_key="veto:editor:1",
        label="Veto",
        default_slot="main",
        opens=OpenBehavior.ON_PAYLOAD,
    )

    def __init__(self, wrapper):
        self.wrapper = wrapper
        self.consent_calls = 0
        self.allow = True

    async def handle_close_request(self):
        self.consent_calls += 1
        return self.allow

    def draw(self, context, container):
        pass


def test_on_tab_close_clicked_calls_wrapper_close(monkeypatch):
    _install_ui_fakes(monkeypatch)
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=reg,
    )
    slot.add_binding(editor_key="veto:editor:1", editor_cls=_VetoEditor)
    target = slot.find_binding("veto:editor:1")
    slot._active = target
    slot.render(_FakeContainer())
    target._instantiate()
    target._instance.allow = True

    _run_async(slot._on_tab_close_clicked("veto:editor:1"))

    # Tab gone after consent allowed
    assert slot.find_binding("veto:editor:1") is None


def test_on_tab_close_clicked_respects_veto(monkeypatch):
    _install_ui_fakes(monkeypatch)
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=reg,
    )
    slot.add_binding(editor_key="veto:editor:1", editor_cls=_VetoEditor)
    target = slot.find_binding("veto:editor:1")
    slot._active = target
    slot.render(_FakeContainer())
    target._instantiate()
    target._instance.allow = False  # veto

    _run_async(slot._on_tab_close_clicked("veto:editor:1"))

    # Tab still there
    assert slot.find_binding("veto:editor:1") is target


def test_on_tab_close_clicked_no_longer_emits_tab_close_requested(monkeypatch):
    """Regression: the X-button must NOT emit any session signal."""
    _install_ui_fakes(monkeypatch)
    cls = _editor_cls("a")
    reg = _FakeRegistry()
    signals_seen: list = []

    sess = SimpleNamespace(
        context=None,
        signal=lambda s: signals_seen.append(s),
        reveal=lambda r: None,
    )
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(editor_key="a", editor_cls=cls)
    target = slot.find_binding("a")
    slot._active = target
    slot.render(_FakeContainer())

    _run_async(slot._on_tab_close_clicked("a"))

    # No signals emitted by the close path
    assert signals_seen == []


# ---------------------------------------------------------------------------
# Task 10: dirty badge prefix
# ---------------------------------------------------------------------------


def _dirty_icon_calls(created):
    """Slot-drawn dirty markers — `ui.icon('circle')` elements in the bar."""
    return [c for kind, c in created if kind == "icon" and c._args and c._args[0] == "circle"]


def test_dirty_wrapper_renders_slot_owned_dirty_marker(monkeypatch):
    """When state.is_dirty is True, the slot draws a 'circle' dirty marker
    around the editor's tab interior so the user sees unsaved work — and the
    label text itself is never mutated (no '• ' prefix)."""
    created = _install_ui_fakes(monkeypatch)
    cls = _editor_cls("a", label="MyEditor")
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=reg,
    )
    slot.add_binding(editor_key="a", editor_cls=cls, binding_id="p1")
    target = slot.find_binding("a", "p1")
    target.label = "my.graph"
    slot._active = target
    target.set_dirty(True)

    # Clear the created log and re-render the bar
    created.clear()
    slot._render_bar_contents()

    # A slot-owned 'circle' dirty marker is drawn.
    assert _dirty_icon_calls(created), "No slot-owned 'circle' dirty marker found"
    # The label text is not bullet-prefixed — the dirty signal lives in the icon.
    label_calls = [c for kind, c in created if kind == "label"]
    assert not any(c._args and c._args[0].startswith("• ") for c in label_calls)


def test_clean_wrapper_renders_no_dirty_marker(monkeypatch):
    created = _install_ui_fakes(monkeypatch)
    cls = _editor_cls("a", label="MyEditor")
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="main",
        registry=reg,
    )
    slot.add_binding(editor_key="a", editor_cls=cls, binding_id="p1")
    target = slot.find_binding("a", "p1")
    target.label = "my.graph"
    slot._active = target
    # is_dirty is False by default

    created.clear()
    slot._render_bar_contents()

    assert not _dirty_icon_calls(created), "Clean wrapper should draw no dirty marker"
