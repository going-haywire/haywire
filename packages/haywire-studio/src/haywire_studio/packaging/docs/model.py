from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from haywire.core.node.inspector import PortInfo, SettingInfo


@dataclass(frozen=True)
class ComponentRecord:
    registry_key: str
    kind: str
    library_id: str
    label: str
    description: str
    deprecation: str
    hidden: bool
    search_tags: list[str] = field(default_factory=list)
    menu: str = ""
    docstring: str = ""
    instructions: str = ""
    ports: list[PortInfo] = field(default_factory=list)
    settings: list[SettingInfo] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    #: Declared with ``@node(template=True)``: cloned by the New Node wizard, never placed.
    template: bool = False
    #: The registered class's own name, which the naming check reads.
    class_name: str = ""
    #: Unregistered public node classes of the same library that a node
    #: inherits from, nearest first. Each is an abstract base (rule N7).
    node_bases: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LibraryDoc:
    library_id: str
    label: str
    version: str
    description: str
    components: list[ComponentRecord] = field(default_factory=list)
