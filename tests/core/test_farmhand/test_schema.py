"""JSON-Schema derivation from Farmhand.run() signatures."""

import pytest

from haywire.core.farmhand.schema import _ANY_TYPE, derive_input_schema

pytestmark = pytest.mark.unit


def test_types_defaults_and_required():
    async def run(self, ctx, path: str, count: int = 10, deep: bool = False): ...

    schema = derive_input_schema(run)
    assert schema["type"] == "object"
    assert schema["properties"]["path"] == {"type": "string"}
    assert schema["properties"]["count"] == {"type": "integer", "default": 10}
    assert schema["properties"]["deep"] == {"type": "boolean", "default": False}
    assert schema["required"] == ["path"]


def test_optional_and_containers():
    # The mutable defaults are the fixture, not a mistake: this signature is
    # only ever introspected (never called), and the assertions below check
    # that `[]` is carried through into the derived schema's "default".
    async def run(self, ctx, name: str | None = None, ids: list[str] = [], meta: dict = {}):  # noqa: B006
        ...

    schema = derive_input_schema(run)
    assert schema["properties"]["name"]["type"] == "string"
    assert schema["properties"]["ids"] == {"type": "array", "items": {"type": "string"}, "default": []}
    assert schema["properties"]["meta"]["type"] == "object"
    assert schema["required"] == []


def test_float_and_unannotated():
    async def run(self, ctx, x: float, anything=None): ...

    schema = derive_input_schema(run)
    assert schema["properties"]["x"] == {"type": "number"}
    assert schema["properties"]["anything"] == {**_ANY_TYPE, "default": None}
    # No property may ever be a bare {} — that shape gets stringified by
    # Claude Code, silently corrupting untyped values.
    assert schema["properties"]["anything"] != {"default": None}


def test_multi_arm_union_yields_anyof_not_empty():
    async def run(self, ctx, value: int | str | bool = None): ...

    schema = derive_input_schema(run)
    prop = schema["properties"]["value"]
    assert "anyOf" in prop
    assert {"type": "integer"} in prop["anyOf"]
    assert {"type": "string"} in prop["anyOf"]
    assert {"type": "boolean"} in prop["anyOf"]


def test_unknown_type_yields_anyof_not_empty():
    class Unrecognized: ...

    async def run(self, ctx, value: Unrecognized): ...

    schema = derive_input_schema(run)
    assert schema["properties"]["value"] == _ANY_TYPE
