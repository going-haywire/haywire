"""iter_reactive_fields walks a class's MRO and yields (name, initial) per descriptor."""

from haywire.core.session.reactive import Reactive, iter_reactive_fields, reactive_field


def test_iter_yields_each_descriptor():
    class C:
        x: Reactive[int] = reactive_field(1)
        y: Reactive[str] = reactive_field("hi")
        not_reactive = 99

    pairs = dict(iter_reactive_fields(C))
    assert pairs == {"x": 1, "y": "hi"}


def test_iter_includes_inherited_fields():
    class Base:
        a: Reactive[int] = reactive_field(0)

    class Sub(Base):
        b: Reactive[bool] = reactive_field(True)

    pairs = dict(iter_reactive_fields(Sub))
    assert pairs == {"a": 0, "b": True}


def test_iter_skips_non_reactive_attrs():
    class C:
        method_attr: Reactive[int] = reactive_field(7)

        def some_method(self) -> None:
            pass

    pairs = dict(iter_reactive_fields(C))
    assert pairs == {"method_attr": 7}
