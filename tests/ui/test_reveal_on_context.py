"""Regression tests for on_context reveal dispatch (singleton tab per class)."""

from haywire.ui.editor.identity import OpenBehavior

from tests.ui.test_app_shell import (
    _build_test_shell_with_editors,
)


class TestOnContextRevealDispatch:
    def test_first_reveal_opens_payload_less_tab(self):
        shell, session = _build_test_shell_with_editors(
            [
                ("studio:editor:Ctx", "main", OpenBehavior.ON_CONTEXT),
            ]
        )
        shell._reveal_editor("studio:editor:Ctx", payload=None)
        main_slot = shell._managed_slots["main"]
        binding = main_slot.find_binding("studio:editor:Ctx", None)
        assert binding is not None
        assert binding.payload is None

    def test_second_reveal_does_not_duplicate(self):
        shell, session = _build_test_shell_with_editors(
            [
                ("studio:editor:Ctx", "main", OpenBehavior.ON_CONTEXT),
            ]
        )
        shell._reveal_editor("studio:editor:Ctx", payload=None)
        shell._reveal_editor("studio:editor:Ctx", payload=None)
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
        shell._reveal_editor("studio:editor:Ctx", payload=None)
        main_slot = shell._managed_slots["main"]
        # Simulate switching to a different tab.
        main_slot.switch_to("studio:editor:Other", None)
        assert main_slot.active_key == "studio:editor:Other"
        # Reveal again — should switch back, not create a duplicate.
        shell._reveal_editor("studio:editor:Ctx", payload=None)
        assert main_slot.active_key == "studio:editor:Ctx"
        matching = [b for b in main_slot.bindings if b.editor_key == "studio:editor:Ctx"]
        assert len(matching) == 1
