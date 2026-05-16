from dataclasses import dataclass

from haywire.core.registry.identity import BaseIdentity


@dataclass
class ThemeClassIdentity(BaseIdentity):
    """Identity metadata stored on decorated theme classes."""

    theme_type: str = ""  # 'workbench' or 'node'
