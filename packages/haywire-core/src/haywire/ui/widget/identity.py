from haywire.core.registry.identity import BaseIdentity


from dataclasses import dataclass


@dataclass
class WidgetIdentity(BaseIdentity):
    """Core identifying attributes of a widget"""
