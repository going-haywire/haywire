"""Tests for the Slot + EditorBinding classes."""

from types import SimpleNamespace

from haywire.ui.app.slot import EditorBinding, Slot
from haywire.ui.app.tab_slot import TabSlot
from haywire.ui.context_events import ContextChangedEvent, ContextChangeType


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
    """Stand-in BaseEditor that records draw/poll/cleanup calls."""

    instances: list["_FakeEditor"] = []

    def __init__(self) -> None:
        self.draw_calls: list = []
        self.poll_calls: list = []
        self.poll_returns = True
        self.cleanup_calls = 0
        _FakeEditor.instances.append(self)

    def draw(self, context, container) -> None:
        self.draw_calls.append((context, container))

    def poll(self, context, event) -> bool:
        self.poll_calls.append((context, event))
        return self.poll_returns

    def cleanup(self) -> None:
        self.cleanup_calls += 1


class _FakeEditorAlt(_FakeEditor):
    """Distinct class so hot-reload tests can swap to a different type."""


def _session_with_context() -> SimpleNamespace:
    return SimpleNamespace(context=SimpleNamespace())


class _FakeRegistry:
    """Stub EditorTypeRegistry for Slot construction — only the lifecycle hooks matter."""

    def add_batch_event_subscriber(self, _cb) -> None:
        pass

    def remove_batch_event_subscriber(self, _cb) -> None:
        pass


_REGISTRY = _FakeRegistry()


# ----------------------------------------------------------------------
# EditorBinding
# ----------------------------------------------------------------------


def test_editor_binding_lazy_creates_instance() -> None:
    binding = EditorBinding(editor_key="lib:editor:one", editor_cls=_FakeEditor)
    assert binding.instance is None

    instance = binding.ensure_instance()
    assert isinstance(instance, _FakeEditor)
    # Subsequent calls return the same instance.
    assert binding.ensure_instance() is instance


def test_editor_binding_id_single_instance_is_just_editor_key() -> None:
    binding = EditorBinding(editor_key="lib:editor:one", editor_cls=_FakeEditor)
    assert binding.binding_id == "lib:editor:one"


def test_editor_binding_id_multi_instance_composes_editor_key_and_payload() -> None:
    binding = EditorBinding(
        editor_key="studio:editor:graph_editor",
        editor_cls=_FakeEditor,
        payload="/path/to/a.haywire",
    )
    assert binding.binding_id == "studio:editor:graph_editor::/path/to/a.haywire"


# ----------------------------------------------------------------------
# Construction + initial active resolution
# ----------------------------------------------------------------------


def test_slot_resolves_initial_active_from_active_key() -> None:
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, bindings, active_key="a:e:2")
    assert slot.active_key == "a:e:2"


def test_slot_falls_back_to_first_binding_when_active_key_unknown() -> None:
    bindings = [EditorBinding("a:e:1", _FakeEditor)]
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, bindings, active_key="missing")
    assert slot.active_key == "a:e:1"


def test_slot_with_no_bindings_has_no_active_binding() -> None:
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, [], active_key=None)
    assert slot.active_binding is None
    assert slot.active_key is None


def test_slot_resolves_initial_active_with_payload() -> None:
    """composite active_key must exact-match the payload-carrying binding,
    not fall through to the first same-key binding."""
    bindings = [
        EditorBinding("a:e:graph", _FakeEditor, payload=None),
        EditorBinding("a:e:graph", _FakeEditor, payload="/tmp/a.haywire"),
        EditorBinding("a:e:graph", _FakeEditor, payload="/tmp/b.haywire"),
    ]
    slot = TabSlot(
        _session_with_context(),
        "main",
        _REGISTRY,
        bindings,
        active_key="a:e:graph::/tmp/b.haywire",
    )
    assert slot.active_binding is bindings[2]
    assert slot.active_binding_id == "a:e:graph::/tmp/b.haywire"


# ----------------------------------------------------------------------
# _render_area + draw
# ----------------------------------------------------------------------


def test_render_area_creates_tab_panels_and_draws_active(monkeypatch) -> None:
    """_render_area mounts a ui.tab_panels container, creates a tab_panel per
    binding, and eagerly draws only the active binding."""
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, bindings, active_key="a:e:1")
    panels_created, panel_created = _install_fake_tab_panels(monkeypatch)

    parent = _FakeContainer()
    slot._render_area_contents(parent)

    # Exactly one tab_panels container; one tab_panel per binding.
    assert len(panels_created) == 1
    assert panels_created[0].visible is True
    assert panels_created[0].value == "a:e:1"
    assert [name for name, _ in panel_created] == ["a:e:1", "a:e:2"]
    # Only the active binding was drawn; the inactive one is still lazy.
    assert bindings[0].instance is not None
    assert len(bindings[0].instance.draw_calls) == 1
    assert bindings[1].instance is None


# ----------------------------------------------------------------------
# switch_to
# ----------------------------------------------------------------------


def test_switch_to_toggles_active_panel_without_clearing(monkeypatch) -> None:
    """Switching sets the tab_panels value and lazy-draws the newly active
    binding into its own panel — the area container is not cleared."""
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, bindings, active_key="a:e:1")
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
    assert bindings[1].instance is not None
    assert len(bindings[1].instance.draw_calls) == 1
    # First binding's draw count is unchanged — siblings are not redrawn.
    assert len(bindings[0].instance.draw_calls) == 1


def test_switch_to_second_time_does_not_redraw(monkeypatch) -> None:
    """Switching back to a previously-drawn binding is a pure value flip —
    no second draw() call."""
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, bindings, active_key="a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())

    slot.switch_to("a:e:2")
    slot.switch_to("a:e:1")

    # Each binding was drawn exactly once despite two switches.
    assert len(bindings[0].instance.draw_calls) == 1
    assert len(bindings[1].instance.draw_calls) == 1


def test_switch_to_no_op_when_already_active(monkeypatch) -> None:
    bindings = [EditorBinding("a:e:1", _FakeEditor)]
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, bindings, active_key="a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())

    assert slot.switch_to("a:e:1") is False


def test_switch_to_unknown_key_returns_false_and_logs(caplog, monkeypatch) -> None:
    import logging

    bindings = [EditorBinding("a:e:1", _FakeEditor)]
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, bindings, active_key="a:e:1")
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
    b1 = EditorBinding("a:e:1", _FakeEditor)
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, [b1], active_key=None)
    assert slot.find_binding("a:e:1") is b1
    assert slot.find_binding("nope") is None


def test_find_binding_disambiguates_by_payload() -> None:
    ge_a = EditorBinding("studio:editor:graph_editor", _FakeEditor, payload="/a.haywire")
    ge_b = EditorBinding("studio:editor:graph_editor", _FakeEditor, payload="/b.haywire")
    slot = TabSlot(_session_with_context(), "main", _REGISTRY, [ge_a, ge_b], active_key=None)

    assert slot.find_binding("studio:editor:graph_editor", payload="/a.haywire") is ge_a
    assert slot.find_binding("studio:editor:graph_editor", payload="/b.haywire") is ge_b
    # Unknown payload with known key returns None — no silent fallback when
    # the caller explicitly asked for a specific instance.
    assert slot.find_binding("studio:editor:graph_editor", payload="/nope.haywire") is None


def test_find_binding_payload_less_caller_still_matches_first_binding() -> None:
    """Callers that pre-date payloads (pass no payload) keep working."""
    b = EditorBinding("studio:editor:graph_editor", _FakeEditor, payload="/a.haywire")
    slot = TabSlot(_session_with_context(), "main", _REGISTRY, [b], active_key=None)
    assert slot.find_binding("studio:editor:graph_editor") is b


def test_switch_to_disambiguates_by_payload(monkeypatch) -> None:
    bindings = [
        EditorBinding("studio:editor:graph_editor", _FakeEditor, payload="/a.haywire"),
        EditorBinding("studio:editor:graph_editor", _FakeEditor, payload="/b.haywire"),
    ]
    slot = TabSlot(_session_with_context(), "main", _REGISTRY, bindings, active_key=None)
    slot._active = bindings[0]
    panels_created, panel_created = _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())
    area = panels_created[0]

    changed = slot.switch_to("studio:editor:graph_editor", payload="/b.haywire")

    assert changed is True
    assert slot.active_binding is bindings[1]
    assert area.value == "studio:editor:graph_editor::/b.haywire"


def test_find_binding_warns_on_ambiguous_match(caplog) -> None:
    import logging

    dup_a = EditorBinding("a:e:1", _FakeEditor)
    dup_b = EditorBinding("a:e:1", _FakeEditor)
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, [dup_a, dup_b], active_key=None)

    with caplog.at_level(logging.WARNING, logger="haywire.ui.app.slot"):
        result = slot.find_binding("a:e:1")

    assert result is dup_a
    assert any("2 bindings match" in r.message for r in caplog.records)


# ----------------------------------------------------------------------
# Visibility
# ----------------------------------------------------------------------


def test_set_visible_syncs_content_container() -> None:
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, [], active_key=None)
    container = _FakeContainer()
    slot._area_panel_container = container

    slot.set_visible(False)
    assert slot.visible is False
    assert container.visible is False

    slot.set_visible(True)
    assert slot.visible is True
    assert container.visible is True


# ----------------------------------------------------------------------
# handle_context_event
# ----------------------------------------------------------------------


def test_handle_context_event_redraws_active_panel_when_poll_true(monkeypatch) -> None:
    binding = EditorBinding("a:e:1", _FakeEditor)
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, [binding], active_key="a:e:1")
    _, panel_created = _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())
    panel = panel_created[0][1]
    instance = binding.instance
    assert instance is not None
    instance.draw_calls.clear()  # ignore the initial eager draw
    instance.poll_returns = True

    slot.handle_context_event(ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED))

    # Only the active binding's panel is cleared + redrawn.
    assert len(instance.poll_calls) == 1
    assert panel.clear_calls == 1
    assert len(instance.draw_calls) == 1


def test_handle_context_event_skips_when_poll_false(monkeypatch) -> None:
    binding = EditorBinding("a:e:1", _FakeEditor)
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, [binding], active_key="a:e:1")
    _, panel_created = _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())
    panel = panel_created[0][1]
    instance = binding.instance
    assert instance is not None
    instance.draw_calls.clear()
    instance.poll_returns = False

    slot.handle_context_event(ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED))

    assert len(instance.poll_calls) == 1
    assert panel.clear_calls == 0
    assert len(instance.draw_calls) == 0


def test_handle_context_event_is_noop_when_instance_not_yet_created(monkeypatch) -> None:
    """An inactive, never-drawn binding has no instance to poll."""
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, bindings, active_key="a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())

    # Active binding got its initial draw; swap to a non-existent active so
    # handle_context_event sees None as the active instance.
    slot._active = None
    slot.handle_context_event(ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED))
    assert bindings[1].instance is None


# ----------------------------------------------------------------------
# replace_class (hot-reload)
# ----------------------------------------------------------------------


def test_replace_class_swaps_class_clears_instance_and_redraws_active(monkeypatch) -> None:
    binding = EditorBinding("a:e:1", _FakeEditor)
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, [binding], active_key="a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())
    old = binding.instance
    cleanup_calls: list = []

    redrew = slot.replace_class("a:e:1", _FakeEditorAlt, cleanup_old=lambda inst: cleanup_calls.append(inst))

    assert redrew is True
    assert binding.editor_cls is _FakeEditorAlt
    # Old instance was cleaned up; fresh instance was drawn into the panel.
    assert cleanup_calls == [old]
    assert isinstance(binding.instance, _FakeEditorAlt)


def test_replace_class_returns_false_when_not_active(monkeypatch) -> None:
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, bindings, active_key="a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())

    redrew = slot.replace_class("a:e:2", _FakeEditorAlt)

    assert redrew is False
    assert bindings[1].editor_cls is _FakeEditorAlt


def test_replace_class_swallows_dead_client_runtime_error(monkeypatch) -> None:
    """When a background session's client has disconnected, NiceGUI raises
    RuntimeError from panel.clear(). Hot-reload must drop the panel and
    continue instead of propagating the error across sibling shells."""
    binding = EditorBinding("a:e:1", _FakeEditor)
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, [binding], active_key="a:e:1")
    panels_created, panel_created = _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())

    dead_panel = panel_created[0][1]

    def _raise_dead(self=dead_panel):
        raise RuntimeError("The client this element belongs to has been deleted.")

    dead_panel.clear = _raise_dead

    # Must not raise.
    redrew = slot.replace_class("a:e:1", _FakeEditorAlt)

    assert redrew is True
    assert binding.editor_cls is _FakeEditorAlt
    # Panel was dropped so subsequent operations treat the binding as undrawn.
    assert binding.binding_id not in slot._panels


# ----------------------------------------------------------------------
# remove_bindings
# ----------------------------------------------------------------------


def test_remove_bindings_drops_matching_and_promotes_first_remaining(monkeypatch) -> None:
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, bindings, active_key="a:e:1")
    _, panel_created = _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())
    removed_panel = panel_created[0][1]
    old = bindings[0].instance
    cleanup_calls: list = []

    slot.remove_bindings("a:e:1", cleanup=lambda inst: cleanup_calls.append(inst))

    assert len(slot.bindings) == 1
    assert slot.active_key == "a:e:2"
    assert cleanup_calls == [old]
    # The removed binding's panel was deleted from the DOM.
    assert removed_panel.deleted is True


def test_add_binding_creates_panel_and_optionally_activates(monkeypatch) -> None:
    bindings = [EditorBinding("a:e:1", _FakeEditor)]
    slot = TabSlot(_session_with_context(), "main", _REGISTRY, bindings, active_key="a:e:1")
    panels_created, panel_created = _install_fake_tab_panels(monkeypatch)
    slot._render_area_contents(_FakeContainer())
    area = panels_created[0]

    new_binding = EditorBinding("a:e:2", _FakeEditor)
    slot.add_binding(new_binding, activate=True)

    # Panel was created for the new binding.
    assert [name for name, _ in panel_created] == ["a:e:1", "a:e:2"]
    # Active switched; tab_panels value reflects it.
    assert slot.active_key == "a:e:2"
    assert area.value == "a:e:2"
    assert new_binding.instance is not None


def test_remove_bindings_clears_active_when_no_bindings_remain(monkeypatch) -> None:
    _install_fake_tab_panels(monkeypatch)

    binding = EditorBinding("a:e:1", _FakeEditor)
    slot = TabSlot(_session_with_context(), "left", _REGISTRY, [binding], active_key="a:e:1")
    slot._render_area_contents(_FakeContainer())

    slot.remove_bindings("a:e:1")

    assert slot.bindings == []
    assert slot.active_binding is None


# ----------------------------------------------------------------------
# EditorBinding.split_id
# ----------------------------------------------------------------------


def test_editor_binding_split_id_roundtrips_single_instance():
    assert EditorBinding.split_id("editor:one") == ("editor:one", None)


def test_editor_binding_split_id_roundtrips_multi_instance():
    assert EditorBinding.split_id("editor:one::/tmp/a.graph") == ("editor:one", "/tmp/a.graph")


def test_editor_binding_split_id_round_trip_with_binding_id(monkeypatch):
    class _Fake:
        pass

    b = EditorBinding(editor_key="editor:one", editor_cls=_Fake, payload="/tmp/a.graph")
    assert EditorBinding.split_id(b.binding_id) == ("editor:one", "/tmp/a.graph")


# ----------------------------------------------------------------------
# EditorBinding.can_close
# ----------------------------------------------------------------------


def test_can_close_required_is_false():
    from haywire.ui.editor.identity import OpenBehavior

    cls = type("_C", (), {"class_identity": SimpleNamespace(opens=OpenBehavior.REQUIRED)})
    b = EditorBinding(editor_key="e", editor_cls=cls)
    assert b.can_close is False


def test_can_close_on_payload_is_true():
    from haywire.ui.editor.identity import OpenBehavior

    cls = type("_C", (), {"class_identity": SimpleNamespace(opens=OpenBehavior.ON_PAYLOAD)})
    b = EditorBinding(editor_key="e", editor_cls=cls)
    assert b.can_close is True


def test_can_close_on_context_is_true():
    from haywire.ui.editor.identity import OpenBehavior

    cls = type("_C", (), {"class_identity": SimpleNamespace(opens=OpenBehavior.ON_CONTEXT)})
    b = EditorBinding(editor_key="e", editor_cls=cls)
    assert b.can_close is True


def test_can_close_missing_opens_defaults_true():
    """Unknown/missing class_identity.opens defaults to closeable (permissive)."""
    cls = type("_C", (), {"class_identity": SimpleNamespace()})
    b = EditorBinding(editor_key="e", editor_cls=cls)
    assert b.can_close is True


def test_slot_switch_to_updates_active_key(monkeypatch):
    _install_fake_tab_panels(monkeypatch)
    cls_a = type("_A", (), {"class_identity": SimpleNamespace(opens="required")})
    cls_b = type("_B", (), {"class_identity": SimpleNamespace(opens="required")})
    a = EditorBinding(editor_key="a", editor_cls=cls_a)
    b = EditorBinding(editor_key="b", editor_cls=cls_b)
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=_REGISTRY,
        initial_bindings=[a, b],
        active_key="a",
    )
    parent = _FakeContainer()
    slot._render_area_contents(parent)
    assert slot.active_key == "a"

    slot.switch_to("b")
    assert slot.active_key == "b"


def test_slot_set_visible_fires_on_visibility_change(monkeypatch):
    _install_fake_tab_panels(monkeypatch)
    cls = type("_C", (), {"class_identity": SimpleNamespace(opens="required")})
    calls: list[bool] = []
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=_REGISTRY,
        initial_bindings=[EditorBinding(editor_key="e", editor_cls=cls)],
        on_visibility_change=calls.append,
    )
    slot.set_visible(False)
    assert calls == [False]
    slot.set_visible(False)  # idempotent — no duplicate notification
    assert calls == [False]
    slot.set_visible(True)
    assert calls == [False, True]


def test_slot_set_visible_updates_internal_state(monkeypatch):
    _install_fake_tab_panels(monkeypatch)
    cls = type("_C", (), {"class_identity": SimpleNamespace(opens="required")})
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=_REGISTRY,
        initial_bindings=[EditorBinding(editor_key="e", editor_cls=cls)],
    )
    slot.set_visible(False)
    assert slot.visible is False
    slot.set_visible(True)
    assert slot.visible is True


# ----------------------------------------------------------------------
# set_size
# ----------------------------------------------------------------------


def test_slot_set_size_updates_internal_size():
    cls = type("_C", (), {"class_identity": SimpleNamespace(opens="required")})
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="bottom",
        registry=_REGISTRY,
        initial_bindings=[EditorBinding(editor_key="e", editor_cls=cls)],
        size=300,
    )
    slot.set_size(275)
    assert slot._size == 275


def test_slot_subscribes_to_registry_on_construction(monkeypatch):
    from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType

    _install_fake_tab_panels(monkeypatch)

    class _FakeRegistry:
        def __init__(self):
            self.subscribers = []

        def add_batch_event_subscriber(self, cb):
            self.subscribers.append(cb)

        def remove_batch_event_subscriber(self, cb):
            self.subscribers.remove(cb)

        def get_by_default_TabSlot(self, _slot):
            return {}

        def get_by_key(self, _key):
            return None

    reg = _FakeRegistry()
    cls = type("_A", (), {"class_identity": SimpleNamespace(opens="required")})
    new_cls = type("_A2", (), {"class_identity": SimpleNamespace(opens="required")})
    a = EditorBinding(editor_key="a", editor_cls=cls)
    slot = TabSlot(
        session=SimpleNamespace(context=None),
        name="left",
        registry=reg,
        initial_bindings=[a],
    )
    assert len(reg.subscribers) == 1

    # Firing a CLASS_RELOADED event swaps the binding's class via the slot's subscriber.
    evt = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_RELOADED,
        registry_key="a",
        affected_class=new_cls,
    )
    reg.subscribers[0]([evt])
    assert a.editor_cls is new_cls

    # teardown unsubscribes.
    slot.teardown()
    assert reg.subscribers == []


# ---------------------------------------------------------------------------
# Slot.to_snapshot / from_snapshot
# ---------------------------------------------------------------------------

from types import SimpleNamespace as _SN


class _FakeEditorCls2:
    def __init__(self, key, opens=None, slot="main"):
        from haywire.ui.editor.identity import OpenBehavior

        self.class_identity = _SN(
            registry_key=key,
            label=key,
            icon="icon",
            opens=opens or OpenBehavior.REQUIRED,
            default_slot=slot,
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


def _make_tab_slot2(bindings, active_key=None, visible=True, size=200):
    from haywire.ui.app.tab_slot import TabSlot

    return TabSlot(
        session=_SN(context=None, notify_context_changed=lambda _e: None),
        name="main",
        registry=_FakeRegistry2({}),
        initial_bindings=bindings,
        active_key=active_key,
        bar_place="top",
        show_fold_toggle=False,
        visible=visible,
        size=size,
    )


class TestSlotToSnapshot:
    def test_active_key_is_serialized(self):
        from haywire.ui.editor.identity import OpenBehavior
        from haywire.ui.app.slot import EditorBinding

        cls = _FakeEditorCls2("ed:graph", OpenBehavior.ON_PAYLOAD)
        binding = EditorBinding(editor_key="ed:graph", editor_cls=cls, payload="/a.haywire")
        slot = _make_tab_slot2([binding], active_key="ed:graph::/a.haywire")
        snap = slot.to_snapshot()
        assert snap["active_key"] == "ed:graph::/a.haywire"

    def test_required_editors_excluded(self):
        from haywire.ui.editor.identity import OpenBehavior
        from haywire.ui.app.slot import EditorBinding

        req_cls = _FakeEditorCls2("ed:required", OpenBehavior.REQUIRED)
        pay_cls = _FakeEditorCls2("ed:graph", OpenBehavior.ON_PAYLOAD)
        bindings = [
            EditorBinding(editor_key="ed:required", editor_cls=req_cls, payload=None),
            EditorBinding(editor_key="ed:graph", editor_cls=pay_cls, payload="/a.haywire"),
        ]
        slot = _make_tab_slot2(bindings, active_key="ed:graph::/a.haywire")
        snap = slot.to_snapshot()
        keys = [e["key"] for e in snap["editors"]]
        assert "ed:required" not in keys
        assert "ed:graph" in keys

    def test_payload_and_label_serialized(self):
        from haywire.ui.editor.identity import OpenBehavior
        from haywire.ui.app.slot import EditorBinding

        cls = _FakeEditorCls2("ed:graph", OpenBehavior.ON_PAYLOAD)
        binding = EditorBinding(editor_key="ed:graph", editor_cls=cls, payload="/a.haywire")
        binding.label = "a.haywire"
        slot = _make_tab_slot2([binding], active_key="ed:graph::/a.haywire")
        snap = slot.to_snapshot()
        ed = snap["editors"][0]
        assert ed["key"] == "ed:graph"
        assert ed["payload"] == "/a.haywire"
        assert ed["label"] == "a.haywire"

    def test_visible_and_size(self):
        slot = _make_tab_slot2([], visible=False, size=350)
        snap = slot.to_snapshot()
        assert snap["visible"] is False
        assert snap["size"] == 350


class TestSlotFromSnapshot:
    def test_required_editors_injected(self):
        from haywire.ui.editor.identity import OpenBehavior
        from haywire.ui.app.tab_slot import TabSlot

        cls = _FakeEditorCls2("ed:required", OpenBehavior.REQUIRED, slot="main")
        registry = _FakeRegistry2({"ed:required": cls})
        session = _SN(context=None, notify_context_changed=lambda _e: None)
        slot = TabSlot.from_snapshot(
            data={},
            registry=registry,
            session=session,
            name="main",
            bar_place="top",
            show_fold_toggle=False,
        )
        assert any(b.editor_key == "ed:required" for b in slot.bindings)

    def test_on_payload_editors_restored(self):
        from haywire.ui.editor.identity import OpenBehavior
        from haywire.ui.app.tab_slot import TabSlot

        cls = _FakeEditorCls2("ed:graph", OpenBehavior.ON_PAYLOAD, slot="main")
        registry = _FakeRegistry2({"ed:graph": cls})
        session = _SN(context=None, notify_context_changed=lambda _e: None)
        data = {
            "active_key": "ed:graph::/a.haywire",
            "editors": [{"key": "ed:graph", "payload": "/a.haywire", "label": "a.haywire"}],
        }
        slot = TabSlot.from_snapshot(
            data=data,
            registry=registry,
            session=session,
            name="main",
            bar_place="top",
            show_fold_toggle=False,
        )
        assert any(b.editor_key == "ed:graph" for b in slot.bindings)

    def test_unknown_editor_key_skipped(self):
        from haywire.ui.app.tab_slot import TabSlot

        registry = _FakeRegistry2({})
        session = _SN(context=None, notify_context_changed=lambda _e: None)
        data = {"editors": [{"key": "ed:gone", "payload": "/x.haywire", "label": "x"}]}
        slot = TabSlot.from_snapshot(
            data=data,
            registry=registry,
            session=session,
            name="main",
            bar_place="top",
            show_fold_toggle=False,
        )
        assert slot.bindings == []

    def test_visible_and_size_restored(self):
        from haywire.ui.app.tab_slot import TabSlot

        registry = _FakeRegistry2({})
        session = _SN(context=None, notify_context_changed=lambda _e: None)
        slot = TabSlot.from_snapshot(
            data={"visible": False, "size": 275},
            registry=registry,
            session=session,
            name="bottom",
            bar_place="top",
            show_fold_toggle=True,
        )
        assert slot.visible is False
        assert slot._size == 275
