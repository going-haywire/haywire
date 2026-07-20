"""JSON-Schema derivation from Farmhand.run() signatures."""

import pytest

from haywire.core.farmhand.schema import derive_input_schema

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
    async def run(self, ctx, name: str | None = None, ids: list[str] = [], meta: dict = {}): ...

    schema = derive_input_schema(run)
    assert schema["properties"]["name"]["type"] == "string"
    assert schema["properties"]["ids"] == {"type": "array", "items": {"type": "string"}, "default": []}
    assert schema["properties"]["meta"]["type"] == "object"
    assert schema["required"] == []


def test_float_and_unannotated():
    async def run(self, ctx, x: float, anything=None): ...

    schema = derive_input_schema(run)
    assert schema["properties"]["x"] == {"type": "number"}
    assert schema["properties"]["anything"] == {"default": None}
