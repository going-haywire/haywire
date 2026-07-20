"""JSON Schema derivation from a Farmhand.run() signature.

The node-worker() signature-analysis idiom applied to MCP input schemas:
type hints + defaults become the schema; self and ctx are skipped.
"""

from __future__ import annotations

import inspect
import types
import typing
from typing import Any

_PRIMITIVES: dict[Any, dict] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    dict: {"type": "object"},
    list: {"type": "array"},
}


def derive_input_schema(fn) -> dict:
    sig = inspect.signature(fn)
    hints = typing.get_type_hints(fn)
    properties: dict[str, dict] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name in ("self", "ctx") or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        prop = dict(_annotation_to_schema(hints.get(name)))
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            prop["default"] = param.default
        properties[name] = prop

    return {"type": "object", "properties": properties, "required": required}


def _annotation_to_schema(annotation: Any) -> dict:
    if annotation is None or annotation is inspect.Parameter.empty:
        return {}
    if annotation in _PRIMITIVES:
        return _PRIMITIVES[annotation]

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    # Optional[X] / X | None -> schema of X (presence is handled by required=)
    if origin in (typing.Union, types.UnionType):
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _annotation_to_schema(non_none[0])
        return {}
    if origin is list:
        item = _annotation_to_schema(args[0]) if args else {}
        return {"type": "array", "items": item}
    if origin is dict:
        return {"type": "object"}
    return {}  # unknown types: accept anything (schema evolution convention, spec §5)
