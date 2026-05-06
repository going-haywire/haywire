"""Unit tests for the LibraryState base class."""

from haywire.core.state import LibraryState


class TestLibraryStateBase:
    def test_subclass_can_be_instantiated_with_no_arguments(self):
        class MyState(LibraryState):
            pass

        instance = MyState()
        assert isinstance(instance, LibraryState)

    def test_on_enable_is_optional(self):
        """A LibraryState without on_enable can still be instantiated."""

        class NoHooks(LibraryState):
            pass

        instance = NoHooks()
        assert not hasattr(instance, "on_enable") or callable(instance.on_enable)

    def test_on_enable_when_defined_is_callable(self):
        calls: list[str] = []

        class WithHooks(LibraryState):
            def on_enable(self) -> None:
                calls.append("enable")

            def on_disable(self) -> None:
                calls.append("disable")

        instance = WithHooks()
        instance.on_enable()
        instance.on_disable()
        assert calls == ["enable", "disable"]

    def test_subclass_can_carry_arbitrary_fields(self):
        """LibraryState imposes no field-level constraints."""

        class FullOfStuff(LibraryState):
            def __init__(self) -> None:
                self.devices: list[str] = []
                self.counter: int = 0

        instance = FullOfStuff()
        instance.devices.append("dev0")
        instance.counter += 1
        assert instance.devices == ["dev0"]
        assert instance.counter == 1
