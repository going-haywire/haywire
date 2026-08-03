import pytest

from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import FLOAT, STRING


def test_setting_accepts_itype():
    class bag(NodeSettings):
        x = setting[FLOAT](1.0)

    assert bag.__dict__["x"]._type is FLOAT


def test_setting_rejects_python_type():
    with pytest.raises(TypeError):  # noqa: PT012 (the class body is the call under test)

        class bag(NodeSettings):
            x = setting[float](1.0)  # type: ignore[type-var]  # python type no longer allowed

        _ = bag


def test_setting_rejects_explicit_python_type_kwarg():
    with pytest.raises(TypeError):  # noqa: PT012 (the class body is the call under test)

        class bag(NodeSettings):
            x = setting[STRING]("hi", type_=str)  # type: ignore[arg-type]  # a python type

        _ = bag
