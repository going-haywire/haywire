from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Mapping
from haywire.core.library.identity import LibraryIdentity
from haywire.ui.widget.identity import WidgetIdentity

if TYPE_CHECKING:
    from haywire.core.types import WidgetModel


# ============================================================================
# Core Interface - Minimal Contract
# ============================================================================


class IWidget(ABC):
    """
    Minimal widget interface.

    Subclass ``BaseWidget`` for the standard authoring surface (``build()`` plus
    the ``bind()`` sugar / ``on_model_changed()`` floor). Implement ``IWidget``
    directly only for a fully custom widget that needs neither.
    """

    # Set by @widget decorator
    class_identity: ClassVar[WidgetIdentity]
    class_library: ClassVar[LibraryIdentity]

    @abstractmethod
    def __init__(self, element: "WidgetModel"):
        """
        Initialize widget with a WidgetModel.

        Args:
            element: WidgetModel (a DataPort, or a panel SettingWidgetModel
                adapter) containing the data to bind to.
        """
        pass

    @abstractmethod
    def render(self) -> Any:
        """
        Render the widget and return the UI element.

        Returns:
            NiceGUI element or other UI representation
        """
        pass

    def cleanup(self) -> None:
        """
        Optional cleanup method.
        Override if your widget needs to release resources.
        """
        pass

    # ---- DECLARED SIZE BOX ----------------------------------------------
    # The box a widget claims when nothing constrains it, so its contents stop
    # deciding its node's size floor. This sits on IWidget because both halves
    # of the declaration are already IWidget-level: the class-level default is
    # ``class_identity`` (set by @widget), and the per-call-site override is
    # produced by ``config()`` below. Only the *storage* of that override is
    # subclass business — hence the one hook, ``_size_overrides()``.
    # Read by the render path; see ``haywire.ui.widget.sizing``.

    def _size_overrides(self) -> Mapping[str, Any]:
        """Per-call-site overrides of the declared size box.

        Empty by default: an implementation that stores no widget config simply
        has no overrides and falls back to the class declaration. ``BaseWidget``
        supplies the port's ``widget_config``.
        """
        return {}

    def _resolve_size_field(self, name: str) -> int | None:
        # class_identity is absent on an undecorated subclass (test doubles).
        identity = getattr(self, "class_identity", None)
        value = self._size_overrides().get(name, getattr(identity, name, None))
        if value is None or (isinstance(value, int) and not isinstance(value, bool)):
            return value
        raise TypeError(
            f"{type(self).__name__}.{name} must be an int number of px or None, "
            f"got {value!r} ({type(value).__name__})"
        )

    @property
    def min_width(self) -> int | None:
        """Declared intrinsic width in px (pairs with :attr:`min_height`)."""
        return self._resolve_size_field("min_width")

    @property
    def min_height(self) -> int | None:
        """Declared intrinsic height in px (pairs with :attr:`min_width`)."""
        return self._resolve_size_field("min_height")

    @property
    def max_height(self) -> int | None:
        """Expanded-container ceiling in px, overriding the framework default."""
        return self._resolve_size_field("max_height")

    @classmethod
    def config(cls, **kwargs) -> Dict[str, Any]:
        """
        Generate widget configuration dictionary for use in port creation.

        This method simplifies widget configuration by combining the widget key
        and configuration into a single dictionary.

        Args:
            **kwargs: Widget configuration options (e.g., properties, etc.)

        Returns:
            Dictionary with 'key' and 'config' for port creation

        Example:
            SelectWidget.config(
                properties={'options': ['A', 'B', 'C']}
            )
            # Returns:
            # {
            #     'key': 'core:widget:SelectWidget',
            #     'config': {'properties': {'options': ['A', 'B', 'C']}}
            # }
        """
        if not hasattr(cls, "class_identity"):
            raise AttributeError(
                f"{cls.__name__} has no class_identity. Did you forget to apply @widget decorator?"
            )

        return {"key": cls.class_identity.registry_key, "config": kwargs}
