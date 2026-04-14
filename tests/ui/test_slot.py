"""Tests for the Slot + EditorBinding classes."""

from types import SimpleNamespace

from haywire.ui.app.slot import EditorBinding, Slot
from haywire.ui.context_events import ContextChangedEvent, ContextChangeType


class _FakeContainer:
    """Stand-in for a NiceGUI element with clear/visibility tracking."""

    def __init__(self) -> None:
        self.clear_calls = 0
        self.visible = True

    def clear(self) -> None:
        self.clear_calls += 1

    def set_visibility(self, visible: bool) -> None:
        self.visible = visible

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


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


# ----------------------------------------------------------------------
# Construction + initial active resolution
# ----------------------------------------------------------------------


def test_slot_resolves_initial_active_from_active_key() -> None:
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:2")
    assert slot.active_key == "a:e:2"


def test_slot_falls_back_to_first_binding_when_active_key_unknown() -> None:
    bindings = [EditorBinding("a:e:1", _FakeEditor)]
    slot = Slot(_session_with_context(), "left", bindings, active_key="missing")
    assert slot.active_key == "a:e:1"


def test_slot_with_no_bindings_has_no_active_binding() -> None:
    slot = Slot(_session_with_context(), "left", [], active_key=None)
    assert slot.active_binding is None
    assert slot.active_key is None


# ----------------------------------------------------------------------
# render_area + draw
# ----------------------------------------------------------------------


def test_render_area_creates_container_and_draws_active(monkeypatch) -> None:
    """render_area mounts the area container under the parent and draws the
    active binding's editor into it."""
    bindings = [EditorBinding("a:e:1", _FakeEditor)]
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")

    # Capture the area container the slot creates by patching ui.element.
    created: list[_FakeContainer] = []

    class _FakeUiElement(_FakeContainer):
        def classes(self, _c):
            return self

        def style(self, _s):
            return self

    def _fake_element(_tag):
        c = _FakeUiElement()
        created.append(c)
        return c

    from haywire.ui.app import slot as slot_module

    monkeypatch.setattr(slot_module.ui, "element", _fake_element)

    parent = _FakeContainer()
    slot.render_area(parent)

    # Container created and stored; visibility synced.
    assert len(created) == 1
    assert created[0].visible is True
    # Active binding's instance was created and drawn.
    assert bindings[0].instance is not None
    assert len(bindings[0].instance.draw_calls) == 1


# ----------------------------------------------------------------------
# switch_to
# ----------------------------------------------------------------------


def test_switch_to_changes_active_and_redraws() -> None:
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    slot._area_container = _FakeContainer()  # bypass render_area

    changed = slot.switch_to("a:e:2")

    assert changed is True
    assert slot.active_key == "a:e:2"
    # Container cleared once for the redraw.
    assert slot._area_container.clear_calls == 1
    # Second binding's instance was created and drawn.
    assert bindings[1].instance is not None
    assert len(bindings[1].instance.draw_calls) == 1


def test_switch_to_no_op_when_already_active() -> None:
    bindings = [EditorBinding("a:e:1", _FakeEditor)]
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    slot._area_container = _FakeContainer()

    assert slot.switch_to("a:e:1") is False
    assert slot._area_container.clear_calls == 0


def test_switch_to_unknown_key_returns_false_and_logs(caplog) -> None:
    import logging

    bindings = [EditorBinding("a:e:1", _FakeEditor)]
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    slot._area_container = _FakeContainer()

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
    slot = Slot(_session_with_context(), "left", [b1], active_key=None)
    assert slot.find_binding("a:e:1") is b1
    assert slot.find_binding("nope") is None


def test_find_binding_warns_on_ambiguous_match(caplog) -> None:
    import logging

    dup_a = EditorBinding("a:e:1", _FakeEditor)
    dup_b = EditorBinding("a:e:1", _FakeEditor)
    slot = Slot(_session_with_context(), "left", [dup_a, dup_b], active_key=None)

    with caplog.at_level(logging.WARNING, logger="haywire.ui.app.slot"):
        result = slot.find_binding("a:e:1")

    assert result is dup_a
    assert any("2 bindings match" in r.message for r in caplog.records)


# ----------------------------------------------------------------------
# Visibility
# ----------------------------------------------------------------------


def test_set_visible_syncs_area_container() -> None:
    slot = Slot(_session_with_context(), "left", [], active_key=None)
    container = _FakeContainer()
    slot._area_container = container

    slot.set_visible(False)
    assert slot.visible is False
    assert container.visible is False

    slot.set_visible(True)
    assert slot.visible is True
    assert container.visible is True


# ----------------------------------------------------------------------
# handle_context_event
# ----------------------------------------------------------------------


def test_handle_context_event_redraws_when_poll_true() -> None:
    binding = EditorBinding("a:e:1", _FakeEditor)
    slot = Slot(_session_with_context(), "left", [binding], active_key="a:e:1")
    container = _FakeContainer()
    slot._area_container = container
    # Force-create the instance so handle_context_event has something to poll.
    instance = binding.ensure_instance()
    instance.poll_returns = True

    event = ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
    slot.handle_context_event(event)

    assert len(instance.poll_calls) == 1
    assert container.clear_calls == 1
    assert len(instance.draw_calls) == 1


def test_handle_context_event_skips_when_poll_false() -> None:
    binding = EditorBinding("a:e:1", _FakeEditor)
    slot = Slot(_session_with_context(), "left", [binding], active_key="a:e:1")
    container = _FakeContainer()
    slot._area_container = container
    instance = binding.ensure_instance()
    instance.poll_returns = False

    slot.handle_context_event(ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED))

    assert len(instance.poll_calls) == 1
    assert container.clear_calls == 0
    assert len(instance.draw_calls) == 0


def test_handle_context_event_is_noop_when_instance_not_yet_created() -> None:
    """Lazy instances haven't drawn yet so there's nothing to poll."""
    binding = EditorBinding("a:e:1", _FakeEditor)
    slot = Slot(_session_with_context(), "left", [binding], active_key="a:e:1")
    slot._area_container = _FakeContainer()
    # Instance never created via ensure_instance.

    slot.handle_context_event(ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED))

    assert binding.instance is None


# ----------------------------------------------------------------------
# replace_class (hot-reload)
# ----------------------------------------------------------------------


def test_replace_class_swaps_class_clears_instance_and_redraws_active() -> None:
    binding = EditorBinding("a:e:1", _FakeEditor)
    slot = Slot(_session_with_context(), "left", [binding], active_key="a:e:1")
    slot._area_container = _FakeContainer()
    old = binding.ensure_instance()
    cleanup_calls: list = []

    redrew = slot.replace_class("a:e:1", _FakeEditorAlt, cleanup_old=lambda inst: cleanup_calls.append(inst))

    assert redrew is True
    assert binding.editor_cls is _FakeEditorAlt
    # Old instance was cleaned up; new instance will be lazy-created on draw.
    assert cleanup_calls == [old]
    # _draw_active triggered ensure_instance with the new class.
    assert isinstance(binding.instance, _FakeEditorAlt)


def test_replace_class_returns_false_when_not_active() -> None:
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    slot._area_container = _FakeContainer()

    redrew = slot.replace_class("a:e:2", _FakeEditorAlt)

    assert redrew is False
    assert bindings[1].editor_cls is _FakeEditorAlt
    # Inactive binding had no instance, so cleanup wasn't called.


# ----------------------------------------------------------------------
# remove_bindings
# ----------------------------------------------------------------------


def test_remove_bindings_drops_matching_and_promotes_first_remaining() -> None:
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    slot._area_container = _FakeContainer()
    cleanup_calls: list = []
    old = bindings[0].ensure_instance()

    slot.remove_bindings("a:e:1", cleanup=lambda inst: cleanup_calls.append(inst))

    assert len(slot.bindings) == 1
    assert slot.active_key == "a:e:2"
    assert cleanup_calls == [old]


def test_remove_bindings_clears_active_when_no_bindings_remain(monkeypatch) -> None:
    from haywire.ui.app import slot as slot_module

    # _draw_active renders a "No editor" label when active is None; stub out
    # ui.label so the test doesn't need a real NiceGUI slot stack.
    monkeypatch.setattr(
        slot_module.ui, "label", lambda *_a, **_kw: SimpleNamespace(classes=lambda *_c, **_k: None)
    )

    binding = EditorBinding("a:e:1", _FakeEditor)
    slot = Slot(_session_with_context(), "left", [binding], active_key="a:e:1")
    slot._area_container = _FakeContainer()

    slot.remove_bindings("a:e:1")

    assert slot.bindings == []
    assert slot.active_binding is None
