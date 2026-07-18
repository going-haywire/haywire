import pytest

from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import FLOAT, STRING


def test_setting_accepts_itype():
    class bag(NodeSettings):
        x = setting[FLOAT](1.0)

    assert bag.__dict__["x"]._type is FLOAT


def test_setting_rejects_python_type():
    with pytest.raises(TypeError):

        class bag(NodeSettings):
            x = setting[float](1.0)  # python type no longer allowed

        _ = bag


def test_setting_rejects_explicit_python_type_kwarg():
    with pytest.raises(TypeError):

        class bag(NodeSettings):
            x = setting[STRING]("hi", type_=str)  # type_=str is a python type

        _ = bag
