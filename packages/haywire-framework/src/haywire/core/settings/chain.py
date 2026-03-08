# haywire/core/settings/chain.py
"""
ResolutionChain - resolves setting values through the tier hierarchy.
"""

from __future__ import annotations
from typing import Any, TYPE_CHECKING

from .enums import SettingMode
from .value import SettingValue

if TYPE_CHECKING:
    from .registry import GlobalSettingsRegistry


class ResolutionChain:
    """
    Resolves a setting value through the four-tier hierarchy by delegating
    to GlobalSettingsRegistry.resolve() with an optional local override:

        global OVERRIDE > workspace OVERRIDE > local SET > workspace SET > global SET > default

    The two global tiers (global + workspace) are managed entirely by the registry.
    This chain only owns the per-instance local store.

    Args:
        local_store: Mutable dict mapping full_key -> raw value for this instance.
        global_registry: The singleton GlobalSettingsRegistry.
    """

    def __init__(self, local_store: dict[str, Any], global_registry: 'GlobalSettingsRegistry'):
        self._local = local_store
        self._global = global_registry

    def resolve(self, full_key: str, default: Any) -> Any:
        """
        Resolve the effective value for full_key.

        Delegates to registry.resolve() with the local store value (if any)
        so all tier priority logic lives in one place.

        When the registry returns source='default' (nothing set in any tier),
        returns the caller-supplied `default` rather than the schema definition's
        stored default — these are the same value in normal usage (the holder
        passes descriptor._default), but keeping the chain's default separate
        avoids coupling chain tests to schema state.
        """
        local_sv = (
            SettingValue(mode=SettingMode.SET, value=self._local[full_key])
            if full_key in self._local
            else None
        )
        try:
            value, source = self._global.resolve(full_key, local=local_sv)
            return default if source == 'default' else value
        except KeyError:
            # Key not in registry (e.g. during hot-reload transition) — fall back to default
            if full_key in self._local:
                return self._local[full_key]
            return default

    def resolve_shadow(self, local_key: str, global_key: str, default: Any) -> Any:
        """
        Resolve a shadow/watch field where the local store key and the global
        registry key differ.

        The local override (if any) is looked up by local_key; the global tiers
        are looked up by global_key.
        """
        local_sv = (
            SettingValue(mode=SettingMode.SET, value=self._local[local_key])
            if local_key and local_key in self._local
            else None
        )
        try:
            value, source = self._global.resolve(global_key, local=local_sv)
            return default if source == 'default' else value
        except KeyError:
            if local_key and local_key in self._local:
                return self._local[local_key]
            return default

    def has_local(self, full_key: str) -> bool:
        """Return True if there is a local instance override for full_key."""
        return full_key in self._local

    def get_local(self, full_key: str) -> Any:
        """Return the local instance value for full_key (KeyError if not set)."""
        return self._local[full_key]

    def set_local(self, full_key: str, value: Any) -> None:
        """Store a local instance override for full_key."""
        self._local[full_key] = value

    def clear_local(self, full_key: str) -> None:
        """Remove local instance override for full_key (revert to global/default)."""
        self._local.pop(full_key, None)
