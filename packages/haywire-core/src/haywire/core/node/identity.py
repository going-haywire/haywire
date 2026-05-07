from dataclasses import dataclass, field

from haywire.core.registry.identity import BaseIdentity


@dataclass
class NodeIdentity(BaseIdentity):
    """Core identifying attributes of a node"""

    search_tags: list[str] = field(default_factory=lambda: ["add", "sub", "math", "vector"])
    menu: str = "misc/custom"
    help_md: str | None = None
    help_url: str = "https://haywire.io/internals/node-help"
    _is_error: bool = False
    _error_priority: int = 0
