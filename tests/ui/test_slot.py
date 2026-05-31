"""Tests for the Slot class."""

from types import SimpleNamespace

from haywire.ui.app.tab_slot import TabSlot
from haywire.ui.editor.wrapper import EditorWrapper


class _FakeContainer:
    """Stand-in for a NiceGUI element with clear/visibility tracking."""

    def __init__(self) -> None:
        self.clear_calls = 0
        self.visible = True
        self.value: object = None
        self.deleted = False

    def clear(self) -> None:
        self.clear_calls += 1

    def set_visibility(self, visible: bool) -> None:
        self.visible = visible

    def set_value(self, value) -> None:
        self.value = value

    def delete(self) -> None:
        self.deleted = True

    def classes(self, _c):
        return self

    def style(self, _s):
        return self

    def props(self, _p):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _install_fake_tab_panels(monkeypatch):
    """Replace ``ui.tab_panels`` and ``ui.tab_panel`` with _FakeContainer instances.

    Returns ``(panels_created, panel_created)`` — two lists that receive the
    fakes in creation order so tests can assert against them.
    """
    from haywire.ui.app import slot as slot_module

    panels_created: list[_FakeContainer] = []
    panel_created: list[tuple[str, _FakeContainer]] = []

    def _fake_tab_panels(*_args, **_kwargs):
        c = _FakeContainer()
        c.value = _kwargs.get("value")
        panels_created.append(c)
        return c

    def _fake_tab_panel(name, *_args, **_kwargs):
        c = _FakeContainer()
        panel_created.append((name, c))
        return c

    monkeypatch.setattr(slot_module.ui, "tab_panels", _fake_tab_panels)
    monkeypatch.setattr(slot_module.ui, "tab_panel", _fake_tab_panel)
    monkeypatch.setattr(
        slot_module.ui, "label", lambda *_a, **_kw: SimpleNamespace(classes=lambda *_c, **_k: None)
    )
    return panels_created, panel_created


class _FakeEditor:
    """Stand-in BaseEditor that records draw/cleanup."""

    instances: list["_FakeEditor"] = []

    def __init__(self, wrapper) -> None:
        self.wrapper = wrapper
        self.draw_calls: list = []
        self.cleanup_calls = 0
        _FakeEditor.instances.append(self)

    def draw(self, context, container) -> None:
        self.draw_calls.append((context, container))

    def on_focus(self, context) -> None:
        pass

    def cleanup(self) -> None:
        self.cleanup_calls += 1


class _FakeEditorAlt(_FakeEditor):
    """Distinct class for tests that need a second editor type."""


def _session_with_context() -> SimpleNamespace:
    return SimpleNamespace(context=SimpleNamespace())


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


def _make_slot(*keys, session=None, active_key=None):
    """Build a TabSlot with one wrapper per key (no binding_id)."""
    reg = _FakeRegistry()
    sess = session or _session_with_context()
    slot = TabSlot(session=sess, name="left", registry=reg)
    for k in keys:
        slot.add_binding(editor_key=k, editor_cls=_FakeEditor)
    if active_key is not None:
        key, binding_id = EditorWrapper.split_id(active_key)
        match = slot.find_binding(key, binding_id)
        if match is not None:
            slot._active = match
    elif keys:
        slot._active = slot.find_binding(keys[0])
    return slot


# ----------------------------------------------------------------------
# Construction + initial active resolution
# ----------------------------------------------------------------------


def test_slot_resolves_initial_active_from_active_key() -> None:
    slot = _make_slot("a:e:1", "a:e:2", active_key="a:e:2")
    assert slot.active_key == "a:e:2"


def test_slot_falls_back_to_first_binding_when_active_key_unknown() -> None:
    slot = _make_slot("a:e:1", active_key="missing")
    # "missing" not found — _make_slot leaves _active = first binding
    slot._active = slot.find_binding("a:e:1")
    assert slot.active_key == "a:e:1"


def test_slot_with_no_bindings_has_no_active_binding() -> None:
    reg = _FakeRegistry()
    slot = TabSlot(session=_session_with_context(), name="left", registry=reg)
    assert slot.active_binding is None
    assert slot.active_key is None


def test_slot_resolves_initial_active_with_payload() -> None:
    """composite active_key must exact-match the binding_id-carrying binding,
    not fall through to the first same-key binding."""
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(editor_key="a:e:graph", editor_cls=_FakeEditor, binding_id=None)
    slot.add_binding(editor_key="a:e:graph", editor_cls=_FakeEditor, binding_id="/tmp/a.haywire")
    slot.add_binding(editor_key="a:e:graph", editor_cls=_FakeEditor, binding_id="/tmp/b.haywire")

    target = slot.find_binding("a:e:graph", "/tmp/b.haywire")
    slot._active = target

    assert slot.active_binding is target
    assert slot.active_binding_id == "a:e:graph::/tmp/b.haywire"


# ----------------------------------------------------------------------
# _render_area + draw
# ----------------------------------------------------------------------


def test_render_area_creates_tab_panels_and_draws_active(monkeypatch) -> None:
    """_render_area mounts a ui.tab_panels container, creates a tab_panel per
    binding, and eagerly draws only the active binding."""
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="left", registry=reg)
    slot.add_binding(editor_key="a:e:1", editor_cls=_FakeEditor)
    slot.add_binding(editor_key="a:e:2", editor_cls=_FakeEditor)
    w1 = slot.find_binding("a:e:1")
    slot._active = w1
    panels_created, panel_created = _install_fake_tab_panels(monkeypatch)

    parent = _FakeContainer()
    slot._render_area_contents(parent)

    # Exactly one tab_panels container; one tab_panel per binding.
    assert len(panels_created) == 1
    assert panels_created[0].visible is True
    assert panels_created[0].value == "a:e:1"
    assert [name for name, _ in panel_created] == ["a:e:1", "a:e:2"]
    # Only the active binding was drawn; the inactive one is still lazy.
    w2 = slot.find_binding("a:e:2")
    assert w1.instance is not None
    assert len(w1.instance.draw_calls) == 1
    assert w2.instance is None


# ----------------------------------------------------------------------
# switch_to
# ----------------------------------------------------------------------


def test_switch_to_toggles_active_panel_without_clearing(monkeypatch) -> None:
    """Switching sets the tab_panels value and lazy-draws the newly active
    binding into its own panel — the area container is not cleared."""
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="left", registry=reg)
    slot.add_binding(editor_key="a:e:1", editor_cls=_FakeEditor)
    slot.add_binding(editor_key="a:e:2", editor_cls=_FakeEditor)
    w1 = slot.find_binding("a:e:1")
    w2 = slot.find_binding("a:e:2")
    slot._active = w1
    panels_created, _ = _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())
    area = panels_created[0]

    changed = slot.switch_to("a:e:2")

    assert changed is True
    assert slot.active_key == "a:e:2"
    # DOM-level: value flipped, container itself untouched.
    assert area.value == "a:e:2"
    assert area.clear_calls == 0
    # Second binding was lazy-drawn on first activation.
    assert w2.instance is not None
    assert len(w2.instance.draw_calls) == 1
    # First binding's draw count is unchanged — siblings are not redrawn.
    assert len(w1.instance.draw_calls) == 1


def test_switch_to_second_time_does_not_redraw(monkeypatch) -> None:
    """Switching back to a previously-drawn binding is a pure value flip —
    no second draw() call."""
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="left", registry=reg)
    slot.add_binding(editor_key="a:e:1", editor_cls=_FakeEditor)
    slot.add_binding(editor_key="a:e:2", editor_cls=_FakeEditor)
    w1 = slot.find_binding("a:e:1")
    w2 = slot.find_binding("a:e:2")
    slot._active = w1
    _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())

    slot.switch_to("a:e:2")
    slot.switch_to("a:e:1")

    # Each binding was drawn exactly once despite two switches.
    assert len(w1.instance.draw_calls) == 1
    assert len(w2.instance.draw_calls) == 1


def test_switch_to_no_op_when_already_active(monkeypatch) -> None:
    slot = _make_slot("a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())

    assert slot.switch_to("a:e:1") is False


def test_switch_to_unknown_key_returns_false_and_logs(caplog, monkeypatch) -> None:
    import logging

    slot = _make_slot("a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())

    with caplog.at_level(logging.WARNING, logger="haywire.ui.app.slot"):
        result = slot.switch_to("a:e:does-not-exist")

    assert result is False
    assert slot.active_key == "a:e:1"
    assert any("does-not-exist" in r.message for r in caplog.records)


# ----------------------------------------------------------------------
# find_binding
# ----------------------------------------------------------------------


def test_find_binding_returns_match() -> None:
    slot = _make_slot("a:e:1")
    w1 = slot.find_binding("a:e:1")
    assert w1 is not None
    assert w1.editor_key == "a:e:1"
    assert slot.find_binding("nope") is None


def test_find_binding_disambiguates_by_payload() -> None:
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    key = "studio:editor:graph_editor"
    slot.add_binding(editor_key=key, editor_cls=_FakeEditor, binding_id="/a.haywire")
    slot.add_binding(editor_key=key, editor_cls=_FakeEditor, binding_id="/b.haywire")
    ge_a = slot.find_binding(key, binding_id="/a.haywire")
    ge_b = slot.find_binding(key, binding_id="/b.haywire")

    assert ge_a is not None
    assert ge_b is not None
    assert ge_a is not ge_b
    # Unknown binding_id with known key returns None — no silent fallback when
    # the caller explicitly asked for a specific instance.
    assert slot.find_binding("studio:editor:graph_editor", binding_id="/nope.haywire") is None


def test_find_binding_payload_less_caller_still_matches_first_binding() -> None:
    """Callers that pre-date payloads (pass no binding_id) keep working."""
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(
        editor_key="studio:editor:graph_editor", editor_cls=_FakeEditor, binding_id="/a.haywire"
    )
    b = slot.find_binding("studio:editor:graph_editor", binding_id="/a.haywire")
    assert slot.find_binding("studio:editor:graph_editor") is b


def test_switch_to_disambiguates_by_payload(monkeypatch) -> None:
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(
        editor_key="studio:editor:graph_editor", editor_cls=_FakeEditor, binding_id="/a.haywire"
    )
    slot.add_binding(
        editor_key="studio:editor:graph_editor", editor_cls=_FakeEditor, binding_id="/b.haywire"
    )
    w_a = slot.find_binding("studio:editor:graph_editor", "/a.haywire")
    w_b = slot.find_binding("studio:editor:graph_editor", "/b.haywire")
    slot._active = w_a
    panels_created, _ = _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())
    area = panels_created[0]

    changed = slot.switch_to("studio:editor:graph_editor", binding_id="/b.haywire")

    assert changed is True
    assert slot.active_binding is w_b
    assert area.value == "studio:editor:graph_editor::/b.haywire"


def test_find_binding_warns_on_ambiguous_match(caplog) -> None:
    import logging

    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="left", registry=reg)
    slot.add_binding(editor_key="a:e:1", editor_cls=_FakeEditor)
    slot.add_binding(editor_key="a:e:1", editor_cls=_FakeEditor)

    with caplog.at_level(logging.WARNING, logger="haywire.ui.app.slot"):
        result = slot.find_binding("a:e:1")

    assert result is not None
    assert any("2 wrappers match" in r.message for r in caplog.records)


# ----------------------------------------------------------------------
# Visibility
# ----------------------------------------------------------------------


def test_set_visible_syncs_content_container() -> None:
    reg = _FakeRegistry()
    slot = TabSlot(session=_session_with_context(), name="left", registry=reg)
    container = _FakeContainer()
    slot._area_panel_container = container

    slot.set_visible(False)
    assert slot.visible is False
    assert container.visible is False

    slot.set_visible(True)
    assert slot.visible is True
    assert container.visible is True


# ----------------------------------------------------------------------
# add_binding
# ----------------------------------------------------------------------


def test_add_binding_creates_panel_and_optionally_activates(monkeypatch) -> None:
    slot = _make_slot("a:e:1")
    panels_created, panel_created = _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())
    area = panels_created[0]

    slot.add_binding(editor_key="a:e:2", editor_cls=_FakeEditor, activate=True)
    w2 = slot.find_binding("a:e:2")

    # BasePanel was created for the new binding.
    assert [name for name, _ in panel_created] == ["a:e:1", "a:e:2"]
    # Active switched; tab_panels value reflects it.
    assert slot.active_key == "a:e:2"
    assert area.value == "a:e:2"
    assert w2.instance is not None


# ----------------------------------------------------------------------
# remove_binding
# ----------------------------------------------------------------------


def test_remove_binding_drops_matching_and_promotes_first_remaining(monkeypatch) -> None:
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="left", registry=reg)
    slot.add_binding(editor_key="a:e:1", editor_cls=_FakeEditor)
    slot.add_binding(editor_key="a:e:2", editor_cls=_FakeEditor)
    w1 = slot.find_binding("a:e:1")
    slot._active = w1
    _, panel_created = _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())
    removed_panel = panel_created[0][1]

    slot.remove_binding("a:e:1")

    assert len(slot.bindings) == 1
    assert slot.active_key == "a:e:2"
    # The removed binding's panel was deleted from the DOM.
    assert removed_panel.deleted is True


def test_remove_binding_clears_active_when_no_bindings_remain(monkeypatch) -> None:
    _install_fake_tab_panels(monkeypatch)

    slot = _make_slot("a:e:1")
    slot._render_area_contents(_FakeContainer())

    slot.remove_binding("a:e:1")

    assert slot.bindings == []
    assert slot.active_binding is None


# ----------------------------------------------------------------------
# EditorWrapper.split_id (still exercised at the slot level)
# ----------------------------------------------------------------------


def test_wrapper_split_id_roundtrips_single_instance():
    assert EditorWrapper.split_id("editor:one") == ("editor:one", None)


def test_wrapper_split_id_roundtrips_multi_instance():
    assert EditorWrapper.split_id("editor:one::/tmp/a.graph") == ("editor:one", "/tmp/a.graph")


def test_wrapper_split_id_round_trip_with_binding_id():
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(editor_key="editor:one", editor_cls=_FakeEditor, binding_id="/tmp/a.graph")
    w = slot.find_binding("editor:one", "/tmp/a.graph")
    assert EditorWrapper.split_id(w.editor_binding_id) == ("editor:one", "/tmp/a.graph")


# ----------------------------------------------------------------------
# can_close (tested via wrapper, exercised via add_binding)
# ----------------------------------------------------------------------


def test_can_close_required_is_false():
    from haywire.ui.editor.identity import OpenBehavior

    cls = type("_C", (), {"class_identity": SimpleNamespace(opens=OpenBehavior.REQUIRED)})
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(editor_key="e", editor_cls=cls)
    w = slot.find_binding("e")
    assert w.can_close is False


def test_can_close_on_payload_is_true():
    from haywire.ui.editor.identity import OpenBehavior

    cls = type("_C", (), {"class_identity": SimpleNamespace(opens=OpenBehavior.ON_PAYLOAD)})
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(editor_key="e", editor_cls=cls)
    w = slot.find_binding("e")
    assert w.can_close is True


def test_can_close_on_context_is_true():
    from haywire.ui.editor.identity import OpenBehavior

    cls = type("_C", (), {"class_identity": SimpleNamespace(opens=OpenBehavior.ON_CONTEXT)})
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(editor_key="e", editor_cls=cls)
    w = slot.find_binding("e")
    assert w.can_close is True


def test_can_close_missing_opens_defaults_true():
    """Unknown/missing class_identity.opens defaults to closeable (permissive)."""
    cls = type("_C", (), {"class_identity": SimpleNamespace()})
    reg = _FakeRegistry()
    sess = _session_with_context()
    slot = TabSlot(session=sess, name="main", registry=reg)
    slot.add_binding(editor_key="e", editor_cls=cls)
    w = slot.find_binding("e")
    assert w.can_close is True


def test_slot_switch_to_updates_active_key(monkeypatch):
    _install_fake_tab_panels(monkeypatch)
    cls_a = type("_A", (), {"class_identity": SimpleNamespace(opens="required")})
    cls_b = type("_B", (), {"class_identity": SimpleNamespace(opens="required")})
    reg = _FakeRegistry()
    sess = SimpleNamespace(context=None)
    slot = TabSlot(session=sess, name="left", registry=reg)
    slot.add_binding(editor_key="a", editor_cls=cls_a)
    slot.add_binding(editor_key="b", editor_cls=cls_b)
    slot._active = slot.find_binding("a")
    parent = _FakeContainer()
    slot._render_area_contents(parent)
    assert slot.active_key == "a"

    slot.switch_to("b")
    assert slot.active_key == "b"


def test_slot_set_visible_fires_on_visibility_change(monkeypatch):
    _install_fake_tab_panels(monkeypatch)
    cls = type("_C", (), {"class_identity": SimpleNamespace(opens="required")})
    calls: list[bool] = []
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=reg,
        on_visibility_change=calls.append,
    )
    slot.add_binding(editor_key="e", editor_cls=cls)
    slot.set_visible(False)
    assert calls == [False]
    slot.set_visible(False)  # idempotent — no duplicate notification
    assert calls == [False]
    slot.set_visible(True)
    assert calls == [False, True]


def test_slot_set_visible_updates_internal_state(monkeypatch):
    _install_fake_tab_panels(monkeypatch)
    cls = type("_C", (), {"class_identity": SimpleNamespace(opens="required")})
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=reg,
    )
    slot.add_binding(editor_key="e", editor_cls=cls)
    slot.set_visible(False)
    assert slot.visible is False
    slot.set_visible(True)
    assert slot.visible is True


# ----------------------------------------------------------------------
# set_size
# ----------------------------------------------------------------------


def test_slot_set_size_updates_internal_size():
    cls = type("_C", (), {"class_identity": SimpleNamespace(opens="required")})
    reg = _FakeRegistry()
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="bottom",
        registry=reg,
        size=300,
    )
    slot.add_binding(editor_key="e", editor_cls=cls)
    slot.set_size(275)
    assert slot._size == 275


# ---------------------------------------------------------------------------
# Slot.to_snapshot / populate_from_snapshot
# ---------------------------------------------------------------------------

from types import SimpleNamespace as _SN  # noqa: E402


class _FakeEditorCls2:
    def __init__(self, key, opens=None, slot="main", order=100):
        from haywire.ui.editor.identity import OpenBehavior

        self.class_identity = _SN(
            registry_key=key,
            label=key,
            icon="icon",
            opens=opens or OpenBehavior.REQUIRED,
            default_slot=slot,
            order=order,
        )


class _FakeRegistry2:
    def __init__(self, classes):
        self._classes = classes

    def get_by_key(self, key):
        return self._classes.get(key)

    def get_by_default_slot(self, slot):
        return {k: v for k, v in self._classes.items() if v.class_identity.default_slot == slot}

    def add_batch_event_subscriber(self, _cb):
        pass

    def remove_batch_event_subscriber(self, _cb):
        pass

    def add_event_subscriber(self, key, cb):
        pass

    def remove_event_subscriber(self, key, cb):
        pass


def _make_tab_slot2(registry=None, visible=True, size=200):
    from haywire.ui.app.tab_slot import TabSlot

    return TabSlot(
        session=_SN(context=None),
        name="main",
        registry=registry or _FakeRegistry2({}),
        bar_place="top",
        show_fold_toggle=False,
        visible=visible,
        size=size,
    )


class TestSlotToSnapshot:
    def test_active_key_is_serialized(self):
        from haywire.ui.editor.identity import OpenBehavior

        cls = _FakeEditorCls2("ed:graph", OpenBehavior.ON_PAYLOAD)
        reg = _FakeRegistry2({"ed:graph": cls})
        slot = _make_tab_slot2(registry=reg)
        slot.add_binding(editor_key="ed:graph", editor_cls=cls, binding_id="/a.haywire")
        w = slot.find_binding("ed:graph", "/a.haywire")
        slot._active = w
        snap = slot.to_snapshot()
        assert snap["active_key"] == "ed:graph::/a.haywire"

    def test_required_editors_excluded(self):
        from haywire.ui.editor.identity import OpenBehavior

        req_cls = _FakeEditorCls2("ed:required", OpenBehavior.REQUIRED)
        pay_cls = _FakeEditorCls2("ed:graph", OpenBehavior.ON_PAYLOAD)
        reg = _FakeRegistry2({"ed:required": req_cls, "ed:graph": pay_cls})
        slot = _make_tab_slot2(registry=reg)
        slot.add_binding(editor_key="ed:required", editor_cls=req_cls, binding_id=None)
        slot.add_binding(editor_key="ed:graph", editor_cls=pay_cls, binding_id="/a.haywire")
        w = slot.find_binding("ed:graph", "/a.haywire")
        slot._active = w
        snap = slot.to_snapshot()
        keys = [e["key"] for e in snap["editors"]]
        assert "ed:required" not in keys
        assert "ed:graph" in keys

    def test_payload_and_label_serialized(self):
        from haywire.ui.editor.identity import OpenBehavior

        cls = _FakeEditorCls2("ed:graph", OpenBehavior.ON_PAYLOAD)
        reg = _FakeRegistry2({"ed:graph": cls})
        slot = _make_tab_slot2(registry=reg)
        w = slot.add_binding(editor_key="ed:graph", editor_cls=cls, binding_id="/a.haywire")
        w.label = "a.haywire"
        slot._active = w
        snap = slot.to_snapshot()
        ed = snap["editors"][0]
        assert ed["key"] == "ed:graph"
        assert ed["binding_id"] == "/a.haywire"
        assert ed["label"] == "a.haywire"

    def test_visible_and_size(self):
        slot = _make_tab_slot2(visible=False, size=350)
        snap = slot.to_snapshot()
        assert snap["visible"] is False
        assert snap["size"] == 350


class TestSlotPopulateFromSnapshot:
    def test_required_editors_injected(self):
        from haywire.ui.editor.identity import OpenBehavior

        cls = _FakeEditorCls2("ed:required", OpenBehavior.REQUIRED, slot="main")
        registry = _FakeRegistry2({"ed:required": cls})
        session = _SN(context=None)
        slot = TabSlot(
            session=session,
            name="main",
            registry=registry,
            bar_place="top",
            show_fold_toggle=False,
        )
        slot.populate_from_snapshot({})
        assert any(b.editor_key == "ed:required" for b in slot.bindings)

    def test_on_payload_editors_restored(self):
        from haywire.ui.editor.identity import OpenBehavior

        cls = _FakeEditorCls2("ed:graph", OpenBehavior.ON_PAYLOAD, slot="main")
        registry = _FakeRegistry2({"ed:graph": cls})
        session = _SN(context=None)
        data = {
            "active_key": "ed:graph::/a.haywire",
            "editors": [{"key": "ed:graph", "binding_id": "/a.haywire", "label": "a.haywire"}],
        }
        slot = TabSlot(
            session=session,
            name="main",
            registry=registry,
            bar_place="top",
            show_fold_toggle=False,
        )
        slot.populate_from_snapshot(data)
        assert any(b.editor_key == "ed:graph" for b in slot.bindings)

    def test_unknown_editor_key_skipped(self):
        registry = _FakeRegistry2({})
        session = _SN(context=None)
        data = {"editors": [{"key": "ed:gone", "binding_id": "/x.haywire", "label": "x"}]}
        slot = TabSlot(
            session=session,
            name="main",
            registry=registry,
            bar_place="top",
            show_fold_toggle=False,
        )
        slot.populate_from_snapshot(data)
        assert slot.bindings == []

    def test_visible_and_size_restored(self):
        registry = _FakeRegistry2({})
        session = _SN(context=None)
        slot = TabSlot(
            session=session,
            name="bottom",
            registry=registry,
            bar_place="top",
            show_fold_toggle=True,
        )
        slot.populate_from_snapshot({"visible": False, "size": 275})
        assert slot.visible is False
        assert slot._size == 275


class TestSlotHotLoadOrdering:
    """A REQUIRED editor hot-loaded at runtime (CLASS_ADDED) lands at the bar
    position dictated by class_identity.order, not at the end."""

    def _emit_class_added(self, slot, cls):
        from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType

        event = LifeCycleEvent(
            registry_key=cls.class_identity.registry_key,
            event_type=LifeCycleEventType.CLASS_ADDED,
            affected_class=cls,
            library_identity=_SN(id="lib"),
        )
        slot._on_lifecycle_events([event])

    def test_low_order_hot_load_inserts_before_higher_order(self):
        existing = _FakeEditorCls2("ed:b", slot="main", order=100)
        reg = _FakeRegistry2({"ed:b": existing})
        slot = _make_tab_slot2(registry=reg)
        slot.add_binding(editor_key="ed:b", editor_cls=existing)

        new_cls = _FakeEditorCls2("ed:a", slot="main", order=10)
        reg._classes["ed:a"] = new_cls
        self._emit_class_added(slot, new_cls)

        assert [b.editor_key for b in slot.bindings] == ["ed:a", "ed:b"]

    def test_high_order_hot_load_appends_after_lower_order(self):
        existing = _FakeEditorCls2("ed:a", slot="main", order=10)
        reg = _FakeRegistry2({"ed:a": existing})
        slot = _make_tab_slot2(registry=reg)
        slot.add_binding(editor_key="ed:a", editor_cls=existing)

        new_cls = _FakeEditorCls2("ed:z", slot="main", order=200)
        reg._classes["ed:z"] = new_cls
        self._emit_class_added(slot, new_cls)

        assert [b.editor_key for b in slot.bindings] == ["ed:a", "ed:z"]

    def test_hot_load_inserts_between_existing_required(self):
        low = _FakeEditorCls2("ed:low", slot="main", order=10)
        high = _FakeEditorCls2("ed:high", slot="main", order=100)
        reg = _FakeRegistry2({"ed:low": low, "ed:high": high})
        slot = _make_tab_slot2(registry=reg)
        slot.add_binding(editor_key="ed:low", editor_cls=low)
        slot.add_binding(editor_key="ed:high", editor_cls=high)

        mid = _FakeEditorCls2("ed:mid", slot="main", order=50)
        reg._classes["ed:mid"] = mid
        self._emit_class_added(slot, mid)

        assert [b.editor_key for b in slot.bindings] == ["ed:low", "ed:mid", "ed:high"]

    def test_hot_load_required_stays_ahead_of_payload_tabs(self):
        from haywire.ui.editor.identity import OpenBehavior

        pay = _FakeEditorCls2("ed:graph", OpenBehavior.ON_PAYLOAD, slot="main", order=100)
        reg = _FakeRegistry2({"ed:graph": pay})
        slot = _make_tab_slot2(registry=reg)
        slot.add_binding(editor_key="ed:graph", editor_cls=pay, binding_id="/a.haywire")

        # A REQUIRED editor with high order must still precede the open tab.
        new_cls = _FakeEditorCls2("ed:req", slot="main", order=200)
        reg._classes["ed:req"] = new_cls
        self._emit_class_added(slot, new_cls)

        assert [b.editor_key for b in slot.bindings] == ["ed:req", "ed:graph"]
