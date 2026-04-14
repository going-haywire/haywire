"""Tests for the Slot + EditorBinding classes."""

from types import SimpleNamespace

from haywire.ui.app.slot import EditorBinding, Slot
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


def test_render_area_creates_tab_panels_and_draws_active(monkeypatch) -> None:
    """render_area mounts a ui.tab_panels container, creates a tab_panel per
    binding, and eagerly draws only the active binding."""
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    panels_created, panel_created = _install_fake_tab_panels(monkeypatch)

    parent = _FakeContainer()
    slot.render_area(parent)

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
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    panels_created, _ = _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())
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
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())

    slot.switch_to("a:e:2")
    slot.switch_to("a:e:1")

    # Each binding was drawn exactly once despite two switches.
    assert len(bindings[0].instance.draw_calls) == 1
    assert len(bindings[1].instance.draw_calls) == 1


def test_switch_to_no_op_when_already_active(monkeypatch) -> None:
    bindings = [EditorBinding("a:e:1", _FakeEditor)]
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())

    assert slot.switch_to("a:e:1") is False


def test_switch_to_unknown_key_returns_false_and_logs(caplog, monkeypatch) -> None:
    import logging

    bindings = [EditorBinding("a:e:1", _FakeEditor)]
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())

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


def test_find_binding_disambiguates_by_payload() -> None:
    ge_a = EditorBinding("studio:editor:graph_editor", _FakeEditor, payload="/a.haywire")
    ge_b = EditorBinding("studio:editor:graph_editor", _FakeEditor, payload="/b.haywire")
    slot = Slot(_session_with_context(), "main", [ge_a, ge_b], active_key=None)

    assert slot.find_binding("studio:editor:graph_editor", payload="/a.haywire") is ge_a
    assert slot.find_binding("studio:editor:graph_editor", payload="/b.haywire") is ge_b
    # Unknown payload with known key returns None — no silent fallback when
    # the caller explicitly asked for a specific instance.
    assert slot.find_binding("studio:editor:graph_editor", payload="/nope.haywire") is None


def test_find_binding_payload_less_caller_still_matches_first_binding() -> None:
    """Callers that pre-date payloads (pass no payload) keep working."""
    b = EditorBinding("studio:editor:graph_editor", _FakeEditor, payload="/a.haywire")
    slot = Slot(_session_with_context(), "main", [b], active_key=None)
    assert slot.find_binding("studio:editor:graph_editor") is b


def test_switch_to_disambiguates_by_payload(monkeypatch) -> None:
    bindings = [
        EditorBinding("studio:editor:graph_editor", _FakeEditor, payload="/a.haywire"),
        EditorBinding("studio:editor:graph_editor", _FakeEditor, payload="/b.haywire"),
    ]
    slot = Slot(_session_with_context(), "main", bindings, active_key=None)
    slot._active = bindings[0]
    panels_created, panel_created = _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())
    area = panels_created[0]

    changed = slot.switch_to("studio:editor:graph_editor", payload="/b.haywire")

    assert changed is True
    assert slot.active_binding is bindings[1]
    assert area.value == "studio:editor:graph_editor::/b.haywire"


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


def test_handle_context_event_redraws_active_panel_when_poll_true(monkeypatch) -> None:
    binding = EditorBinding("a:e:1", _FakeEditor)
    slot = Slot(_session_with_context(), "left", [binding], active_key="a:e:1")
    _, panel_created = _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())
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
    slot = Slot(_session_with_context(), "left", [binding], active_key="a:e:1")
    _, panel_created = _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())
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
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())

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
    slot = Slot(_session_with_context(), "left", [binding], active_key="a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())
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
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())

    redrew = slot.replace_class("a:e:2", _FakeEditorAlt)

    assert redrew is False
    assert bindings[1].editor_cls is _FakeEditorAlt


# ----------------------------------------------------------------------
# remove_bindings
# ----------------------------------------------------------------------


def test_remove_bindings_drops_matching_and_promotes_first_remaining(monkeypatch) -> None:
    bindings = [
        EditorBinding("a:e:1", _FakeEditor),
        EditorBinding("a:e:2", _FakeEditor),
    ]
    slot = Slot(_session_with_context(), "left", bindings, active_key="a:e:1")
    _, panel_created = _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())
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
    slot = Slot(_session_with_context(), "main", bindings, active_key="a:e:1")
    panels_created, panel_created = _install_fake_tab_panels(monkeypatch)
    slot.render_area(_FakeContainer())
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
    slot = Slot(_session_with_context(), "left", [binding], active_key="a:e:1")
    slot.render_area(_FakeContainer())

    slot.remove_bindings("a:e:1")

    assert slot.bindings == []
    assert slot.active_binding is None
