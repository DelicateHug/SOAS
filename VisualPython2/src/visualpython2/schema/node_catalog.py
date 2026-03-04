"""Generate a JSON-serializable node catalog for the frontend editor."""

from __future__ import annotations

from typing import Any, Dict, List

from visualpython2.nodes.registry import NodeRegistry, NodeTypeInfo


def _get_port_defs(node_instance, ports, is_input: bool) -> List[Dict[str, Any]]:
    """Extract port definitions from a node instance."""
    result = []
    for port in ports:
        port_def: Dict[str, Any] = {
            "name": port.name,
            "type": port.port_type.name,
            "description": port.description,
        }
        if is_input:
            port_def["required"] = port.required
            port_def["default_value"] = port.default_value
        result.append(port_def)
    return result


# Property metadata: (node_type, property_name) -> {description, placeholder, ui_type}
_PROPERTY_METADATA: Dict[tuple[str, str], Dict[str, str]] = {
    # SubgraphInput
    ("subgraph_input", "port_name"): {
        "description": "Select the automation input parameter this node represents",
        "placeholder": "Select an input parameter",
        "ui_type": "automation_input_select",
    },
    ("subgraph_input", "port_type_setting"): {
        "description": "The data type of this input port",
    },
    ("subgraph_input", "description"): {
        "description": "A description of what this input is for",
        "placeholder": "Describe this input parameter...",
    },
    ("subgraph_input", "default_value"): {
        "description": "Default value when no parameter is provided",
        "placeholder": "Optional default value",
    },
    # SubgraphOutput
    ("subgraph_output", "port_name"): {
        "description": "Name for this output port",
        "placeholder": "Enter output name",
    },
    ("subgraph_output", "port_type_setting"): {
        "description": "The data type of this output port",
    },
    # RunAutomation
    ("run_automation", "automation_id"): {
        "description": "The sub-automation to execute",
    },
    ("run_automation", "synchronous"): {
        "description": "Wait for the sub-automation to complete before continuing",
    },
    # Code
    ("code", "code"): {
        "description": "Python code to execute",
        "placeholder": "# Write your code here...",
    },
    ("code", "language"): {
        "description": "Programming language for the code block",
    },
    ("code", "description"): {
        "description": "A description of what this code does",
        "placeholder": "Describe this code block...",
    },
    # Condition
    ("condition", "condition_code"): {
        "description": "Python expression that evaluates to True or False",
        "placeholder": "value > 0",
    },
    # ForLoop
    ("for_loop", "iterable_code"): {
        "description": "Python expression for the collection to iterate over",
        "placeholder": "range(10)",
    },
    # WhileLoop
    ("while_loop", "condition_code"): {
        "description": "Python expression checked before each iteration",
        "placeholder": "count < 100",
    },
    # SetVariable / GetVariable
    ("set_variable", "variable_name"): {
        "description": "Name of the global variable to set",
        "placeholder": "my_variable",
    },
    ("get_variable", "variable_name"): {
        "description": "Name of the global variable to read",
        "placeholder": "my_variable",
    },
    # SOAS Variables
    ("get_soas_var", "variable_name"): {
        "description": "Select the SOAS application variable to read",
    },
    ("set_soas_var", "variable_name"): {
        "description": "Select the SOAS application variable to write",
    },
    # User Secrets
    ("get_user_secret", "secret_name"): {
        "description": "Select the user secret to read",
    },
    # Incident Variables
    ("get_incident_var", "variable_name"): {
        "description": "Select the incident variable to read",
    },
    ("set_incident_var", "variable_name"): {
        "description": "Select the incident variable to write",
    },
    # Print
    ("print", "message"): {
        "description": "Message or expression to output",
        "placeholder": "Hello, world!",
    },
    # HTTP Request
    ("http_request", "url"): {
        "description": "The URL to send the request to",
        "placeholder": "https://api.example.com/endpoint",
    },
    ("http_request", "method"): {
        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
    },
    ("http_request", "headers"): {
        "description": "HTTP headers as a JSON object",
        "placeholder": '{"Content-Type": "application/json"}',
    },
    ("http_request", "body"): {
        "description": "Request body content",
        "placeholder": "{}",
    },
    # Comment
    ("comment", "text"): {
        "description": "Note text visible on the canvas",
        "placeholder": "Add a note here...",
    },
}


def _get_property_defs(node_instance) -> List[Dict[str, Any]]:
    """Extract property definitions from a node instance by inspecting serializable properties."""
    props = node_instance._get_serializable_properties()
    node_type = getattr(node_instance, "node_type", "")
    result = []
    for key, value in props.items():
        prop_def: Dict[str, Any] = {
            "name": key,
            "default_value": value,
        }
        # Infer type from default value
        if isinstance(value, bool):
            prop_def["type"] = "boolean"
        elif isinstance(value, int):
            prop_def["type"] = "integer"
        elif isinstance(value, float):
            prop_def["type"] = "float"
        elif isinstance(value, str):
            prop_def["type"] = "string"
        elif isinstance(value, list):
            prop_def["type"] = "list"
        elif isinstance(value, dict):
            prop_def["type"] = "dict"
        else:
            prop_def["type"] = "any"
        # Add UI type hints for special property editors
        if key == "automation_id":
            prop_def["ui_type"] = "automation_select"
        # Check node type for special variable selector UI hints
        if key == "variable_name" and node_type in ("get_soas_var", "set_soas_var"):
            prop_def["ui_type"] = "soas_variable_select"
        if key == "variable_name" and node_type in ("get_incident_var", "set_incident_var"):
            prop_def["ui_type"] = "incident_variable_select"
        if key == "secret_name" and node_type == "get_user_secret":
            prop_def["ui_type"] = "user_secret_select"
        # Apply property metadata (description, placeholder, ui_type overrides)
        meta = _PROPERTY_METADATA.get((node_type, key), {})
        if "description" in meta:
            prop_def["description"] = meta["description"]
        if "placeholder" in meta:
            prop_def["placeholder"] = meta["placeholder"]
        if "ui_type" in meta:
            prop_def["ui_type"] = meta["ui_type"]
        result.append(prop_def)
    return result


def generate_node_catalog(registry: NodeRegistry) -> List[Dict[str, Any]]:
    """Generate a JSON-serializable catalog of all node types for the frontend.

    Returns a list of dicts, each describing a node type with its ports,
    properties, category, color, and icon.
    """
    catalog: List[Dict[str, Any]] = []

    for info in registry.get_all_node_types():
        try:
            # Create a temporary instance to inspect ports and properties
            instance = info.node_class()

            entry: Dict[str, Any] = {
                "type": info.node_type,
                "name": info.name,
                "category": info.category,
                "color": info.color,
                "description": info.description,
                "icon": info.icon,
                "input_ports": _get_port_defs(instance, instance.input_ports, is_input=True),
                "output_ports": _get_port_defs(instance, instance.output_ports, is_input=False),
                "properties": _get_property_defs(instance),
            }
            catalog.append(entry)
        except Exception:
            # Skip nodes that can't be instantiated without arguments
            catalog.append({
                "type": info.node_type,
                "name": info.name,
                "category": info.category,
                "color": info.color,
                "description": info.description,
                "icon": info.icon,
                "input_ports": [],
                "output_ports": [],
                "properties": [],
            })

    return catalog
