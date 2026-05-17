"""
Code generation system for Vue event constants and creators.

This module generates TypeScript/JavaScript code from Python event definitions,
ensuring consistency between frontend and backend event handling.
"""

import dataclasses
import os
from typing import Dict

from .event_definitions import GRAPH_EVENT_REGISTRY

class VueEventGenerator:
    @staticmethod
    def generate_event_constants() -> str:
        """Generate Vue/JavaScript constants and creators from Python event registry"""

        # Separate events by category
        user_events = {}
        sync_events = {}

        for event_type, event_class in GRAPH_EVENT_REGISTRY.items():
            event_info = {
                "type": event_type,
                "class_name": event_class.__name__,
                "description": getattr(event_class, "description", ""),
                "fields": [
                    f.name
                    for f in dataclasses.fields(event_class)
                    if f.name not in ["source_session_id", "timestamp", "requires_broadcast"]
                ],
            }

            if getattr(event_class, "category", "user") == "user":
                user_events[event_type] = event_info
            else:
                sync_events[event_type] = event_info

        # Generate pure JavaScript code with global window assignment (NiceGUI compatible)
        js_code = f"""// Auto-generated from Python event definitions
// DO NOT EDIT MANUALLY - Run `python ./scripts/generate_vue_events.py` to update

// Event type constants - Make available globally
window.GraphEvents = {{
  UserInteractions: {{
{VueEventGenerator._format_events_object(user_events)}
  }},
  
  SyncCommands: {{
{VueEventGenerator._format_events_object(sync_events)}
  }}
}};

// Event creators - Make available globally
window.EventCreators = {{
{VueEventGenerator._generate_event_creators(user_events)}
}};

// Event validators - Make available globally  
window.EventValidators = {{
{VueEventGenerator._generate_event_validators(user_events)}
}};

"""
        return js_code

    @staticmethod
    def _generate_typescript_interfaces(user_events: Dict, sync_events: Dict) -> str:
        """Generate TypeScript interfaces for each event"""
        interfaces = []

        for events in [user_events, sync_events]:
            for event_type, info in events.items():
                interface_name = f"{info['class_name']}Data"
                fields = info["fields"]

                interface = f"""
// {info["description"]}
export interface {interface_name} {{"""

                # Add fields (simplified type mapping)
                for field in fields:
                    field_type = VueEventGenerator._get_typescript_type(field, info.get("field_types", {}))
                    interface += f"""
  {field}: {field_type};"""

                interface += """
}"""
                interfaces.append(interface)

        return "\n".join(interfaces)

    @staticmethod
    def _get_typescript_type(field_name: str, field_types: Dict) -> str:
        """Map Python types to TypeScript types"""
        if field_name in field_types:
            return field_types[field_name]

        # Common type mappings
        if "position" in field_name.lower():
            return "{ x: number; y: number }"
        elif field_name.endswith("Id") or field_name.endswith("NodeId"):
            return "string"
        elif field_name.startswith("screen") or field_name.startswith("canvas"):
            return "number"
        elif "selected" in field_name.lower() and "list" in str(field_name).lower():
            return "string[]"
        elif field_name == "positionChanged":
            return "boolean"
        else:
            return "any"

    @staticmethod
    def _format_events_object(events: Dict) -> str:
        """Format events as JavaScript object properties"""
        lines = []
        for event_type, info in events.items():
            const_name = VueEventGenerator._camel_to_const(event_type)
            lines.append(f"    {const_name}: '{event_type}', // {info['description']}")
        return "\n".join(lines)

    @staticmethod
    def _generate_event_creators(events: Dict) -> str:
        """Generate event creator methods as object methods (not class methods)"""
        methods = []
        for event_type, info in events.items():
            method_name = f"create{info['class_name'].replace('Event', '')}"
            fields_param = ", ".join([f"{field}" for field in info["fields"]])
            field_assignments = ", ".join(info["fields"])

            method = f"""  {method_name}({fields_param}, sessionId = 'default') {{
    return {{
      event_type: '{event_type}',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: {{ {field_assignments} }},
      requires_broadcast: true
    }};
  }}"""
            methods.append(method)

        return ",\n\n".join(methods)

    @staticmethod
    def _generate_event_validators(events: Dict) -> str:
        """Generate event validation methods as object methods (not class methods)"""
        methods = []
        for event_type, info in events.items():
            method_name = f"validate{info['class_name'].replace('Event', '')}"
            required_fields = info["fields"]

            method = f"""  {method_name}(data) {{
    const requiredFields = {str(required_fields).replace("'", '"')};
    return requiredFields.every(field => field in data);
  }}"""
            methods.append(method)

        return ",\n\n".join(methods)

    @staticmethod
    def _camel_to_const(camel_str: str) -> str:
        """Convert camelCase to CONST_CASE"""
        import re

        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", camel_str).upper()


# Build script
def main():
    """Generate Vue event constants"""
    vue_code = VueEventGenerator.generate_event_constants()

    # Create generated directory if it doesn't exist
    current_dir = os.path.dirname(__file__)
    generated_dir = os.path.join(current_dir, "generated")
    os.makedirs(generated_dir, exist_ok=True)

    output_path = os.path.join(generated_dir, "graph_events.js")
    with open(output_path, "w") as f:
        f.write(vue_code)

    print("Vue event constants generated successfully!")
    print(f"File: {output_path}")


if __name__ == "__main__":
    main()
