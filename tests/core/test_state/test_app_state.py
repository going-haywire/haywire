"""Unit tests for AppState base class.

LibraryState (the abstract marker) is implicitly tested via AppState
(its concrete subclass).
"""

from haywire.core.state import AppState, LibraryState


class TestAppStateBase:
    def test_app_state_is_subclass_of_library_state(self):
        """AppState must inherit from the abstract marker base."""
        assert issubclass(AppState, LibraryState)

    def test_subclass_can_be_instantiated_with_no_arguments(self):
        class MyState(AppState):
            pass

        instance = MyState()
        assert isinstance(instance, AppState)
        assert isinstance(instance, LibraryState)

    def test_on_enable_is_optional(self):
        class NoHooks(AppState):
            pass

        instance = NoHooks()
        assert not hasattr(instance, "on_enable") or callable(instance.on_enable)

    def test_on_enable_when_defined_is_callable(self):
        calls: list[str] = []

        class WithHooks(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

            def on_disable(self) -> None:
                calls.append("disable")

        instance = WithHooks()
        instance.on_enable()
        instance.on_disable()
        assert calls == ["enable", "disable"]

    def test_subclass_can_carry_arbitrary_fields(self):
        class FullOfStuff(AppState):
            def __init__(self) -> None:
                self.devices: list[str] = []
                self.counter: int = 0

        instance = FullOfStuff()
        instance.devices.append("dev0")
        instance.counter += 1
        assert instance.devices == ["dev0"]
        assert instance.counter == 1
