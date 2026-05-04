"""reactive_field() — class access yields ReactivePath; instance access yields Reactive[T]."""

from haywire.ui.reactive import Reactive, ReactivePath, iter_reactive_fields, reactive_field


class _ExampleContext:
    """Test-only context class. Defined inside test module to avoid leakage."""

    counter: Reactive[int] = reactive_field(0)
    name: Reactive[str] = reactive_field("anon")

    def __init__(self) -> None:
        # Trigger descriptor's per-instance initialization.
        # Mirrors what SessionContext will do in __post_init__.
        for name, initial in iter_reactive_fields(type(self)):
            self.__dict__[name] = Reactive(initial)


def test_class_access_returns_reactive_path():
    p = _ExampleContext.counter
    assert isinstance(p, ReactivePath)
    assert p.owner is _ExampleContext
    assert p.attr == "counter"


def test_instance_access_returns_reactive_container():
    ctx = _ExampleContext()
    assert isinstance(ctx.counter, Reactive)
    assert ctx.counter.value == 0


def test_instance_value_is_independent_per_instance():
    a = _ExampleContext()
    b = _ExampleContext()
    a.counter.value = 5
    assert a.counter.value == 5
    assert b.counter.value == 0


def test_class_access_for_different_attr():
    p = _ExampleContext.name
    assert p.attr == "name"
    assert p.owner is _ExampleContext


def test_two_classes_descriptor_ownership_is_correct():
    class Other:
        flag: Reactive[bool] = reactive_field(False)

    p_self = _ExampleContext.counter
    p_other = Other.flag
    assert p_self.owner is _ExampleContext
    assert p_other.owner is Other


def test_iter_reactive_fields_subclass_shadows_base():
    """When a subclass re-declares a field, the subclass's initial value wins."""

    class Base:
        x: Reactive[int] = reactive_field(1)

    class Sub(Base):
        x: Reactive[int] = reactive_field(99)

    pairs = dict(iter_reactive_fields(Sub))
    assert pairs == {"x": 99}
