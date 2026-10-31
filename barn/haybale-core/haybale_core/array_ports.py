"""Ports that take their type from the array wired into a node."""

from typing import Any, Optional

__all__ = ["array_element_type", "array_of"]


def array_element_type(edge_wrapper: Any) -> Optional[Any]:
    """Return ``T`` when the edge comes from an ``ArrayType[T]`` outlet, else ``None``."""
    from haybale_core.types import ArrayType

    outlet = getattr(edge_wrapper, "_outlet_port", None)
    incoming = getattr(outlet, "stored_type", None)
    if isinstance(incoming, type) and issubclass(incoming, ArrayType):
        return getattr(incoming, "element_type_cls", None)
    return None


def array_of(element: Any) -> Any:
    """Return ``ArrayType[element]``."""
    from haybale_core.types import ArrayType

    return ArrayType[element]  # type: ignore[valid-type]  # element is a runtime type
