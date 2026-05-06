"""Class identity for LibraryState subclasses.

BaseRegistry requires every registered class to carry a `class_identity`
attribute. For LibraryStates — which have no decorator — the registry
attaches one of these at registration time, derived from the class and
its owning library.

Mirrors the pattern of NodeIdentity, PanelIdentity, SettingsClassIdentity,
ThemeClassIdentity, etc.: a plain @dataclass inheriting from BaseIdentity.
LibraryState needs no extra fields beyond what BaseIdentity provides
(registry_id, registry_key, label, class_name, module, ...).
"""

from __future__ import annotations

from dataclasses import dataclass

from haywire.core.registry.identity import BaseIdentity


@dataclass
class LibraryStateClassIdentity(BaseIdentity):
    """Identity attached to a LibraryState subclass at registration time."""
