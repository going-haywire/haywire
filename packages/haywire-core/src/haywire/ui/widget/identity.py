from haywire.core.registry.identity import BaseIdentity
from haywire.core.types.interface import IType


from dataclasses import dataclass, field
from typing import Set, Type


@dataclass
class WidgetIdentity(BaseIdentity):
    """Core identifying attributes of a widget"""

    compatible_types: Set[Type[IType]] = field(default_factory=set)
