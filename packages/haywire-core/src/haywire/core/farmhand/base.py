"""Farmhand — one class per MCP tool, contributed from a library's farmhands/ folder."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Optional

from haywire.core.farmhand.schema import derive_input_schema

if TYPE_CHECKING:
    from haywire.core.farmhand.context import FarmhandContext
    from haywire.core.farmhand.identity import FarmhandIdentity
    from haywire.core.library.identity import LibraryIdentity


class Farmhand:
    """Base class for MCP tools.

    Subclass, decorate with @farmhand, implement one async run(ctx, ...).
    The input schema derives from run()'s signature (type hints + defaults);
    set input_schema_override for constraints hints can't express.
    """

    class_identity: ClassVar["FarmhandIdentity"]
    class_library: ClassVar["LibraryIdentity"]
    input_schema_override: ClassVar[Optional[dict]] = None

    async def run(self, ctx: "FarmhandContext", **kwargs: Any) -> dict:
        raise NotImplementedError

    @classmethod
    def mcp_name(cls) -> str:
        lib_id, _, registry_id = cls.class_identity.registry_key.split(":")
        return f"{lib_id}_{registry_id}"

    @classmethod
    def input_schema(cls) -> dict:
        if cls.input_schema_override is not None:
            return cls.input_schema_override
        return derive_input_schema(cls.run)
