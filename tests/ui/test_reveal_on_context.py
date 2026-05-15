"""Regression tests for on_context reveal dispatch (singleton tab per class)."""

from types import SimpleNamespace

from haywire.core.session.signals import Reveal
from haywire.ui.app.shell import AppShell
from haywire.ui.app.tab_slot import TabSlot
from haywire.ui.editor.identity import OpenBehavior


# ---------------------------------------------------------------------------
# Shared fakes (used only by this module)
# ---------------------------------------------------------------------------


class _FakeSession:
    def __init__(self) -> None:
        self.workspace_manager = SimpleNamespace(
            active=SimpleNamespace(
                left=SimpleNamespace(active_tab_key="left:editor:one", visible=True, size=300),
                right=SimpleNamespace(active_tab_key="right:editor:one", visible=True, size=300),
                main=SimpleNamespace(tabs=[], active_tab_key="main:editor:one"),
                bottom=SimpleNamespace(tabs=[], active_tab_key=None, visible=False, size=200),
            )
        )
        self._editors = {}

    def subscribe(self, _event_type, _handler):
        return lambda: None


def _make_editor_cls(registry_key: str, default_slot: str, opens=OpenBehavior.REQUIRED) -> type:
    return type(
        f"_FakeEditor_{registry_key.replace(':', '_')}",
        (),
        {
            "class_identity": SimpleNamespace(
                registry_key=registry_key,
                default_slot=default_slot,
                opens=opens,
                label=registry_key,
                icon="icon",
            )
        },
    )


class _FakeEditorRegistry:
    def __init__(self, classes: dict) -> None:
        self._classes = classes

    def get_by_key(self, registry_key: str):
        return self._classes.get(registry_key)


class _FakeBinding:
    """Minimal binding stand-in returned by _FakeTabbedSlot.find_binding."""

    def __init__(self, editor_key: str, binding_id, editor_cls=None) -> None:
        self.editor_key = editor_key
        self.binding_id = binding_id
        self.editor_cls = editor_cls


class _FakeTabbedSlot(TabSlot):
    """Minimal tabbed-slot stand-in that passes isinstance(slot, TabSlot).

    Overrides the real TabSlot methods with fake in-memory implementations so
    the NiceGUI rendering path is never invoked.
    """

    # Shadow every read-only property Slot defines so plain instance attributes
    # can be set without hitting Python's data-descriptor setter guard.
    active_key = None  # type: ignore[assignment]
    active_binding = None  # type: ignore[assignment]
    active_binding_id = None  # type: ignore[assignment]
    visible = None  # type: ignore[assignment]
    bindings = None  # type: ignore[assignment]

    def __init__(self, name: str) -> None:
        # Bypass Slot.__init__ — we manage all state as plain attributes.
        self.name = name
        self.bindings: list[_FakeBinding] = []
        self.active_key: str | None = None
        self.active_binding: _FakeBinding | None = None

    def find_binding(self, editor_key: str, binding_id):
        for b in self.bindings:
            if b.editor_key == editor_key and b.binding_id == binding_id:
                return b
        return None

    def reveal(self, command) -> bool:
        """Find-or-add the binding and make it active. Returns True iff active changed."""
        editor_cls = command.editor
        editor_key = editor_cls.class_identity.registry_key
        binding_id = command.binding_id
        existing = self.find_binding(editor_key, binding_id)
        if existing is not None:
            return self.switch_to(editor_key, binding_id)
        binding = _FakeBinding(editor_key, binding_id, editor_cls=editor_cls)
        self.bindings.append(binding)
        self.active_key = editor_key
        self.active_binding = binding
        return True

    def switch_to(self, editor_key: str, binding_id=None) -> bool:
        if self.active_key == editor_key:
            return False
        self.active_key = editor_key
        for b in self.bindings:
            if b.editor_key == editor_key and b.binding_id == binding_id:
                self.active_binding = b
                break
        return True

    def set_visible(self, visible: bool) -> None:
        pass

    def _refresh_bar(self) -> None:
        pass


def _build_test_shell_with_editors(entries: list[tuple]) -> tuple:
    """Build an AppShell wired with fake editors and a tabbed main slot.

    Args:
        entries: list of (registry_key, default_slot, OpenBehavior).

    Returns:
        (shell, session) ready for _reveal_editor tests.
    """
    classes = {key: _make_editor_cls(key, slot, opens) for key, slot, opens in entries}
    registry = _FakeEditorRegistry(classes)
    session = _FakeSession()
    shell = AppShell(session=session, editor_registry=registry)

    # Replace managed slots with fake tabbed slots for all referenced slots.
    slot_names = {slot for _, slot, _ in entries}
    for slot_name in slot_names:
        shell._managed_slots[slot_name] = _FakeTabbedSlot(slot_name)

    return shell, session


def _reveal(shell: AppShell, registry_key: str, binding_id=None) -> None:
    """Look up the editor class on the shell and dispatch a Reveal for it."""
    editor_cls = shell._editor_registry.get_by_key(registry_key)
    shell._reveal_editor(Reveal(editor=editor_cls, binding_id=binding_id))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOnContextRevealDispatch:
    def test_first_reveal_opens_payload_less_tab(self):
        shell, session = _build_test_shell_with_editors(
            [
                ("studio:editor:Ctx", "main", OpenBehavior.ON_CONTEXT),
            ]
        )
        _reveal(shell, "studio:editor:Ctx")
        main_slot = shell._managed_slots["main"]
        binding = main_slot.find_binding("studio:editor:Ctx", None)
        assert binding is not None
        assert binding.binding_id is None

    def test_second_reveal_does_not_duplicate(self):
        shell, session = _build_test_shell_with_editors(
            [
                ("studio:editor:Ctx", "main", OpenBehavior.ON_CONTEXT),
            ]
        )
        _reveal(shell, "studio:editor:Ctx")
        _reveal(shell, "studio:editor:Ctx")
        main_slot = shell._managed_slots["main"]
        matching = [b for b in main_slot.bindings if b.editor_key == "studio:editor:Ctx"]
        assert len(matching) == 1

    def test_second_reveal_activates_existing_tab(self):
        shell, session = _build_test_shell_with_editors(
            [
                ("studio:editor:Ctx", "main", OpenBehavior.ON_CONTEXT),
                ("studio:editor:Other", "main", OpenBehavior.REQUIRED),
            ]
        )
        _reveal(shell, "studio:editor:Ctx")
        main_slot = shell._managed_slots["main"]
        # Simulate switching to a different tab.
        main_slot.switch_to("studio:editor:Other", None)
        assert main_slot.active_key == "studio:editor:Other"
        # Reveal again — should switch back, not create a duplicate.
        _reveal(shell, "studio:editor:Ctx")
        assert main_slot.active_key == "studio:editor:Ctx"
        matching = [b for b in main_slot.bindings if b.editor_key == "studio:editor:Ctx"]
        assert len(matching) == 1
