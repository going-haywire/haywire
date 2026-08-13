"""FarmhandRegistry — typed class registry for Farmhand (MCP tool) components (kind 'farmhand')."""

from __future__ import annotations

import inspect
import logging
from typing import Optional

from haywire.core.farmhand.base import Farmhand
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry

logger = logging.getLogger(__name__)


class FarmhandRegistry(BaseRegistry[Farmhand]):
    """Registry for Farmhand classes using {distribution_name}:farmhand:{name} keys.

    The 'haybale-studio' prefix belongs to barn/haybale-studio, home of the
    baseline tools; the reservation is enforced by distribution-name
    uniqueness at discovery, not by this registry (user decision 2026-07-19).
    """

    KIND = "farmhand"

    def _class_filter(self, cls) -> bool:
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, Farmhand)
                and cls is not Farmhand
                and hasattr(cls, "class_identity")
            )
        except TypeError:
            return False

    def _register_class(
        self, cls: type[Farmhand], library_identity: Optional[LibraryIdentity] = None
    ) -> str | None:
        return super()._register(cls.class_identity.registry_key, cls, library_identity)

    def _unregister_class(self, registry_key: str) -> type[Farmhand] | None:
        return super()._unregister(registry_key)
