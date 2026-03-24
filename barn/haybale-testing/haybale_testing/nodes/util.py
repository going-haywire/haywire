from haywire.core.library.utils import camel_to_dot_case


def simple_function(node_registry_id: str) -> str:
    """Generate the registry key from the library and class name."""
    camel_class_name = camel_to_dot_case(node_registry_id)
    return f"{node_registry_id}:{camel_class_name}"
