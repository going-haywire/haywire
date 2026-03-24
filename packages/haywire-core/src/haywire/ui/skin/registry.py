import inspect
import logging
from typing import Optional

from haywire.core.errors.haywire_exception import ErrorSeverity, HaywireException
from haywire.core.registry.lifecycle_event import LifeCycleEvent
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry

from .interface import IBaseSkin


class SkinRegistry(BaseRegistry):
    """Registry for NodeSkin classes with fallback support"""

    def __init__(self):
        super().__init__()
        self._default_skin_name: str | None = None
        self._default_priority: int = -1
        self._error_skin_name: str | None = None
        self._error_priority: int = -1

        self._error_skin: type[IBaseSkin] | None = None

    def _class_filter(self, cls):
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, IBaseSkin)
                and cls != IBaseSkin
                and hasattr(cls, "class_identity")
            )
        except TypeError:
            return False

    def _register_class(
        self, skin_cls: type[IBaseSkin], library_identity: Optional[LibraryIdentity] = None
    ) -> str | None:
        """
        Register a skin class.

        Uses the registry_key that was set by the @skin decorator during class definition.

        Args:
            skin_cls: The NodeSkin class
            library_identity: Optional library metadata for the skin.
        Returns:
            str: The haywire registry_key of the registered skin.
        """
        # Use registry_key that was set by the decorator
        registry_key = skin_cls.class_identity.registry_key

        # Check if this is an error node and register it automatically
        if skin_cls.class_identity._is_error:
            if self._error_skin is not None:
                if skin_cls.class_identity._error_priority > self._error_skin.class_identity._error_priority:
                    logging.warning(
                        f"Overriding already registered error skin: "
                        f"'{self._error_skin.class_identity.registry_key}'"
                        f" with : '{skin_cls.class_identity.registry_key}'"
                        f" due to higher _error_priority "
                        f"({skin_cls.class_identity._error_priority} > "
                        f"{self._error_skin.class_identity._error_priority})"
                    )
                    self._error_skin = skin_cls
            else:
                self._error_skin = skin_cls

        # Check if this is an error node and register it as such
        if skin_cls.class_identity._is_error:
            new_error_priority = skin_cls.class_identity._error_priority
            if new_error_priority > self._error_priority:
                if self._error_skin_name:
                    logging.warning(
                        f"Overriding already registered error skin: "
                        f"'{self._error_skin_name}'"
                        f" with : '{registry_key}'"
                        f" due to higher _error_priority "
                        f"({new_error_priority} > {self._error_priority})"
                    )
                self._error_skin_name = registry_key
                self._error_priority = new_error_priority

        # Check if this is a default node and register it as such
        if skin_cls.class_identity._is_default:
            new_default_priority = skin_cls.class_identity._default_priority
            if new_default_priority > self._default_priority:
                if self._default_skin_name:
                    logging.warning(
                        f"Overriding already registered default skin: "
                        f"'{self._default_skin_name}'"
                        f" with : '{registry_key}'"
                        f" due to higher _default_priority "
                        f"({new_default_priority} > {self._default_priority})"
                    )
                self._default_skin_name = registry_key
                self._default_priority = new_default_priority

        return super()._register(registry_key, skin_cls, library_identity)

    def _unregister_class(self, registry_key: str) -> type[IBaseSkin] | None:
        """Unregister a skin by its registry_key
        Args:
            registry_key: The haywire registry_key of the skin to unregister
        Returns:
            type[BaseSkin] | None: The unregistered skin class or None if not found
        """
        removed_class = super()._unregister(registry_key)

        # Check if we removed the current error skin
        if removed_class == self._error_skin:
            self._error_skin = None
            self._error_skin_name = None
            self._error_priority = -1

            # Find next error skin with highest priority
            self._find_next_error_skin()

        # Check if we removed the current default skin
        if registry_key == self._default_skin_name:
            self._default_skin_name = None
            self._default_priority = -1

            # Find next default skin with highest priority
            self._find_next_default_skin()

        return removed_class

    def _find_next_error_skin(self) -> None:
        """Find and set the error skin with the highest priority from remaining skins"""
        for key, skin_cls in self._classes.items():
            if hasattr(skin_cls, "class_identity") and skin_cls.class_identity._is_error:
                priority = skin_cls.class_identity._error_priority
                if priority > self._error_priority:
                    self._error_skin = skin_cls
                    self._error_skin_name = key
                    self._error_priority = priority

        if self._error_skin_name:
            logging.info(
                f"Fallback to error skin '{self._error_skin_name}' with priority {self._error_priority}"
            )
        else:
            logging.warning("No error skin left in registry")

    def _find_next_default_skin(self) -> None:
        """Find and set the default skin with the highest priority from remaining skins"""
        for key, skin_cls in self._classes.items():
            if hasattr(skin_cls, "class_identity") and skin_cls.class_identity._is_default:
                priority = skin_cls.class_identity._default_priority
                if priority > self._default_priority:
                    self._default_skin_name = key
                    self._default_priority = priority

        if self._default_skin_name:
            logging.info(
                f"Fallback to default skin '{self._default_skin_name}' "
                f"with priority {self._default_priority}"
            )
        else:
            logging.warning("No default skin left in registry")

    def get_default_skin_registry_key(self, fallback: str | None = None) -> str | None:
        """Get the default skin registry key
        Args:
            fallback: Fallback value if no default skin is set
        Returns:
            str | None: The registry key of the default skin or the fallback value
        """
        if self._default_skin_name is None:
            return fallback
        return self._default_skin_name

    def get_error_skin_registry_key(self) -> str | None:
        """Get the error skin registry key"""
        return self._error_skin_name

    def get_skin_event(self, key: str | None) -> type[LifeCycleEvent]:
        """
        Get last lifecycle skin event by registry key

        Args:
            key: Registry key in format "library_id:skin:skin_name"

        Returns:
            LifeCycleEvent: Last lifecycle event for the skin

        Raises:
            HaywireException: If skin not found or last event unsuccessful
        """
        lifecycle_event = None

        if key in self._regkey_to_last_lifecycle_event:
            lifecycle_event = self._regkey_to_last_lifecycle_event[key]

        if lifecycle_event is None:
            error = HaywireException.create(
                message=f"Skin '{key}' not found, using error skin as fallback",
                severity=ErrorSeverity.ERROR,
                category="Skin Not Found",
                operation="skin_lookup",
                registry_key=key,
                suggestions=[
                    "Try using existing skin instead",
                    "Library containing the skin may have failed to load",
                ],
                auto_retry=True,
            )
            raise error
        elif lifecycle_event.error:
            raise lifecycle_event.error
        elif not lifecycle_event.is_successful_event():
            error = HaywireException.create(
                message=f"Skin '{key}' failed to load, due to '{lifecycle_event.event_type}' ",
                severity=ErrorSeverity.ERROR,
                category="Skin Load Error",
                operation="skin_lookup",
                registry_key=key,
                suggestions=["Skin may have been removed", "Library containing the skin may been disabled"],
                auto_retry=True,
            )
            raise error

        return lifecycle_event
