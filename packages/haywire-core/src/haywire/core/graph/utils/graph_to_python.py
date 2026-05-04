import re

from haywire.core.types import PrimitiveField
from haywire.core.graph.base import BaseGraph


def graph_to_python_script(graph: "BaseGraph") -> str:
    """
    Convert a graph to executable Python script that reconstructs it.

    Generates code using class references instead of string literals for better
    IDE support and refactoring safety. Imports are placed inside the function.

    Args:
        graph: The BaseGraph instance to convert

    Returns:
        String containing the complete Python script with imports inside function
    """

    lines = []

    # Generate function name from graph name
    # Convert to valid Python identifier (snake_case)
    function_name = re.sub(r"[^a-zA-Z0-9_]", "_", graph.name.lower())
    function_name = re.sub(r"_+", "_", function_name)  # Collapse multiple underscores
    function_name = function_name.strip("_")  # Remove leading/trailing underscores
    if not function_name or function_name[0].isdigit():
        function_name = f"graph_{function_name}"

    # Track imports and node info
    imports: dict[str, list[str]] = {}  # {module_path: [class_names]}
    node_vars: dict[str, tuple[str, str]] = {}  # {node_id: (var_name, class_name)}

    # 1. Collect all node classes and generate imports
    for node_id, wrapper in graph.node_wrappers.items():
        node = wrapper.node

        # Get the actual class
        node_class = node.__class__
        class_name = node_class.__name__
        module_path = node_class.__module__

        # Generate clean variable name (lowercase, snake_case style)
        # Convert CamelCase to snake_case for variable name
        var_name = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()

        # Handle duplicate variable names
        base_var_name = var_name
        counter = 1
        while any(v[0] == var_name for v in node_vars.values()):
            var_name = f"{base_var_name}_{counter}"
            counter += 1

        node_vars[node_id] = (var_name, class_name)

        # Track import
        if module_path not in imports:
            imports[module_path] = []
        if class_name not in imports[module_path]:
            imports[module_path].append(class_name)

    # 2. Function definition and docstring
    lines.append(f"def {function_name}(graph):")
    lines.append('    """')
    lines.append(f"    Reconstruct graph: {graph.name}")
    if graph.description:
        lines.append("    ")
        lines.append(f"    {graph.description}")
    lines.append('    """')

    # 3. Imports section (inside function)
    for module_path in sorted(imports.keys()):
        class_names = sorted(imports[module_path])
        lines.append(f"    from {module_path} import {', '.join(class_names)}")

    lines.append("")

    # 4. Create all nodes with positions
    lines.append("    # Create nodes")
    for node_id, wrapper in graph.node_wrappers.items():
        var_name, class_name = node_vars[node_id]
        x, y = wrapper.node.props.posX, wrapper.node.props.posY

        lines.append(f"    {var_name} = graph.create_node_wrapper(")
        lines.append(f"        {class_name}.class_identity.registry_key,")
        lines.append(f"        position=({x}, {y})")
        lines.append("    )")

    lines.append("")

    # 5. Set non-default primitive port values
    has_value_sets = False
    for node_id, wrapper in graph.node_wrappers.items():
        var_name, _ = node_vars[node_id]
        value_lines: list[str] = []

        for port_id, port in wrapper.node.ports.items():
            # Only process inlets with primitive fields
            if not port.is_inlet() or not isinstance(port.type_cls, PrimitiveField):
                continue

            current_value = port.get_value()
            if isinstance(current_value, (int, str, float, bool)):
                # Get default value from field
                default_value = port.type_cls.default_kwargs.get("default", None)

                # Skip if value equals default
                if current_value == default_value:
                    continue

                # Format value for Python code
                if isinstance(current_value, str):
                    formatted_value = repr(current_value)
                elif isinstance(current_value, bool):
                    formatted_value = str(current_value)
                elif isinstance(current_value, (int, float)):
                    formatted_value = str(current_value)
                else:
                    # Skip complex types
                    continue

                value_lines.append(f"    {var_name}.node.out('{port_id}', {formatted_value})")

        if value_lines:
            if not has_value_sets:
                lines.append("    # Set non-default port values")
                has_value_sets = True
            lines.extend(value_lines)

    if has_value_sets:
        lines.append("")

    # 6. Create all edges
    lines.append("    # Create connections")
    for edge_id, edge_wrapper in graph.edge_wrappers.items():
        source_var, _ = node_vars[edge_wrapper.source_node_id]
        sink_var, _ = node_vars[edge_wrapper.sink_node_id]

        lines.append("    graph.create_edge_wrapper(")
        lines.append(f"        {source_var}.node_id, '{edge_wrapper.outlet_port_id}',")
        lines.append(f"        {sink_var}.node_id, '{edge_wrapper.inlet_port_id}'")
        lines.append("    )")

    lines.append("")
    lines.append("    return graph")

    return "\n".join(lines)
