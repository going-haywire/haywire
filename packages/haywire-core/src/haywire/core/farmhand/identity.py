"""Class identity for Farmhand (MCP tool) components — extends BaseIdentity
like every sibling identity (NodeIdentity, EditorIdentity, LibraryStateClassIdentity)."""

from __future__ import annotations

from dataclasses import dataclass, field

from haywire.core.registry.identity import BaseIdentity


@dataclass
class ToolAnnotations:
    """SDK-free mirror of the MCP spec's tool annotations (consent hints)."""

    read_only_hint: bool = False
    destructive_hint: bool = False
    idempotent_hint: bool = False
    open_world_hint: bool = False

    def to_dict(self) -> dict:
        return {
            "readOnlyHint": self.read_only_hint,
            "destructiveHint": self.destructive_hint,
            "idempotentHint": self.idempotent_hint,
            "openWorldHint": self.open_world_hint,
        }


@dataclass
class FarmhandIdentity(BaseIdentity):
    """Inherits registry_id/registry_key/label/description/deprecation_warning/
    hidden/class_name/module from BaseIdentity; adds the MCP consent annotations."""

    annotations: ToolAnnotations = field(default_factory=ToolAnnotations)
