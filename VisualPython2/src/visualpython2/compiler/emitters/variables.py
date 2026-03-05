"""
Variable emitters for GetVariable, SetVariable, and incident variable nodes.

These emitters handle reading and writing to global variable stores
and SOC incident variable operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from visualpython2.compiler.emitters.base import NodeEmitter

if TYPE_CHECKING:
    from visualpython2.compiler.code_generator import CodeGenerator, GenerationContext


class GetVariableNodeEmitter(NodeEmitter):
    """Emitter for GetVariable nodes - retrieve global variables."""

    @property
    def node_type(self) -> str:
        return "get_variable"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code to retrieve a global variable."""
        from visualpython2.nodes.definitions import GetVariableNode

        if not isinstance(node, GetVariableNode):
            context.errors.append(f"Expected GetVariableNode but got {type(node).__name__}")
            return

        var_name = node.variable_name
        dynamic_name = self.get_input_value(node, "variable_name", context, generator.graph)

        # Generate output variable
        value_var = context.generate_variable_name("var_value")
        exists_var = context.generate_variable_name("var_exists")

        context.set_output_variable(node.id, "value", value_var)
        context.set_output_variable(node.id, "exists", exists_var)

        context.add_line(f"# Get variable: {node.name}")

        # Determine the variable name to use
        if dynamic_name:
            context.add_line(f"_var_name = {dynamic_name}")
        else:
            context.add_line(f"_var_name = {repr(var_name)}")

        # Generate the retrieval code using globals dict
        default_repr = repr(node.default_value) if node.default_value is not None else "None"
        context.add_line(f"{exists_var} = _var_name in _global_vars")
        context.add_line(f"{value_var} = _global_vars.get(_var_name, {default_repr})")
        context.add_blank_line()

        context.mark_node_processed(node.id)


class SetVariableNodeEmitter(NodeEmitter):
    """Emitter for SetVariable nodes - store global variables."""

    @property
    def node_type(self) -> str:
        return "set_variable"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code to set a global variable."""
        from visualpython2.nodes.definitions import SetVariableNode

        if not isinstance(node, SetVariableNode):
            context.errors.append(f"Expected SetVariableNode but got {type(node).__name__}")
            return

        var_name = node.variable_name
        dynamic_name = self.get_input_value(node, "variable_name", context, generator.graph)
        value = self.get_input_value(node, "value", context, generator.graph, default="None")

        # Generate success output variable
        success_var = context.generate_variable_name("set_success")
        context.set_output_variable(node.id, "success", success_var)

        context.add_line(f"# Set variable: {node.name}")

        # Determine the variable name to use
        if dynamic_name:
            context.add_line(f"_var_name = {dynamic_name}")
        else:
            context.add_line(f"_var_name = {repr(var_name)}")

        # Generate the set code
        context.add_line(f"_global_vars[_var_name] = {value}")
        context.add_line(f"{success_var} = True")
        context.add_blank_line()

        context.mark_node_processed(node.id)


class GetIncidentVarNodeEmitter(NodeEmitter):
    """
    Emitter for GetIncidentVar nodes - retrieve SOC incident variables.

    Generates code that calls the get_incident_var() runtime function
    to retrieve incident-scoped variables during playbook execution.
    """

    @property
    def node_type(self) -> str:
        return "get_incident_var"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code to retrieve an incident variable."""
        from visualpython2.nodes.definitions import GetIncidentVarNode

        if not isinstance(node, GetIncidentVarNode):
            context.errors.append(f"Expected GetIncidentVarNode but got {type(node).__name__}")
            return

        # Get the incident variable name from node properties
        incident_var_name = node.variable_name
        dynamic_name = self.get_input_value(node, "variable_name", context, generator.graph)

        # Get default value
        default_value = self.get_input_value(node, "default", context, generator.graph)
        if default_value is None:
            default_repr = repr(node.default_value) if hasattr(node, "default_value") and node.default_value is not None else "None"
        else:
            default_repr = default_value

        # Generate output variable
        var_name = context.generate_variable_name("incident_var")
        context.set_output_variable(node.id, "value", var_name)

        context.add_line(f"# Get incident variable: {node.name}")

        # Determine the variable name to use
        if dynamic_name:
            name_expr = dynamic_name
        else:
            name_expr = repr(incident_var_name)

        context.add_line(f"{var_name} = get_incident_var({name_expr}, {default_repr})")
        context.add_blank_line()

        context.mark_node_processed(node.id)


class SetIncidentVarNodeEmitter(NodeEmitter):
    """
    Emitter for SetIncidentVar nodes - store SOC incident variables.

    Generates code that calls the set_incident_var() runtime function
    to store incident-scoped variables during playbook execution.
    """

    @property
    def node_type(self) -> str:
        return "set_incident_var"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code to set an incident variable."""
        from visualpython2.nodes.definitions import SetIncidentVarNode

        if not isinstance(node, SetIncidentVarNode):
            context.errors.append(f"Expected SetIncidentVarNode but got {type(node).__name__}")
            return

        # Get the incident variable name from node properties
        incident_var_name = node.variable_name
        dynamic_name = self.get_input_value(node, "variable_name", context, generator.graph)

        # Get the value to set
        value = self.get_input_value(node, "value", context, generator.graph, default="None")

        context.add_line(f"# Set incident variable: {node.name}")

        # Determine the variable name to use
        if dynamic_name:
            name_expr = dynamic_name
        else:
            name_expr = repr(incident_var_name)

        context.add_line(f"set_incident_var({name_expr}, {value})")
        context.add_blank_line()

        context.mark_node_processed(node.id)


class GetIncidentDataNodeEmitter(NodeEmitter):
    """
    Emitter for GetIncidentData nodes - retrieve full incident data object.

    Generates code that calls the get_incident_data() runtime function
    to retrieve the complete incident data dictionary during playbook execution.
    """

    @property
    def node_type(self) -> str:
        return "get_incident_data"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code to retrieve the incident data object."""
        from visualpython2.nodes.definitions import GetIncidentDataNode

        if not isinstance(node, GetIncidentDataNode):
            context.errors.append(f"Expected GetIncidentDataNode but got {type(node).__name__}")
            return

        # Generate output variable
        var_name = context.generate_variable_name("incident_data")
        context.set_output_variable(node.id, "value", var_name)

        context.add_line(f"# Get incident data: {node.name}")
        context.add_line(f"{var_name} = get_incident_data()")
        context.add_blank_line()

        context.mark_node_processed(node.id)


class GetGroupIncidentsNodeEmitter(NodeEmitter):
    """Emitter for GetGroupIncidents nodes - retrieve all incidents in the group."""

    @property
    def node_type(self) -> str:
        return "get_group_incidents"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code to retrieve all group incidents."""
        from visualpython2.nodes.definitions import GetGroupIncidentsNode

        if not isinstance(node, GetGroupIncidentsNode):
            context.errors.append(f"Expected GetGroupIncidentsNode but got {type(node).__name__}")
            return

        incidents_var = context.generate_variable_name("group_incidents")
        count_var = context.generate_variable_name("group_count")
        context.set_output_variable(node.id, "incidents", incidents_var)
        context.set_output_variable(node.id, "count", count_var)

        context.add_line(f"# Get group incidents: {node.name}")
        context.add_line(f"{incidents_var} = get_group_incidents()")
        context.add_line(f"{count_var} = len({incidents_var})")
        context.add_blank_line()

        context.mark_node_processed(node.id)


class GetGroupIncidentByIndexNodeEmitter(NodeEmitter):
    """Emitter for GetGroupIncidentByIndex nodes - retrieve a specific incident by index."""

    @property
    def node_type(self) -> str:
        return "get_group_incident"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code to retrieve a group incident by index."""
        from visualpython2.nodes.definitions import GetGroupIncidentByIndexNode

        if not isinstance(node, GetGroupIncidentByIndexNode):
            context.errors.append(f"Expected GetGroupIncidentByIndexNode but got {type(node).__name__}")
            return

        index_input = self.get_input_value(node, "index", context, generator.graph)
        data_var = context.generate_variable_name("group_incident_data")
        context.set_output_variable(node.id, "data", data_var)

        context.add_line(f"# Get group incident by index: {node.name}")
        if index_input:
            context.add_line(f"{data_var} = get_group_incident({index_input})")
        else:
            context.add_line(f"{data_var} = get_group_incident({node.index})")
        context.add_blank_line()

        context.mark_node_processed(node.id)


class GetGroupIncidentCountNodeEmitter(NodeEmitter):
    """Emitter for GetGroupIncidentCount nodes - retrieve the number of incidents in the group."""

    @property
    def node_type(self) -> str:
        return "get_group_incident_count"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code to retrieve the group incident count."""
        from visualpython2.nodes.definitions import GetGroupIncidentCountNode

        if not isinstance(node, GetGroupIncidentCountNode):
            context.errors.append(f"Expected GetGroupIncidentCountNode but got {type(node).__name__}")
            return

        count_var = context.generate_variable_name("group_incident_count")
        context.set_output_variable(node.id, "count", count_var)

        context.add_line(f"# Get group incident count: {node.name}")
        context.add_line(f"{count_var} = get_group_incident_count()")
        context.add_blank_line()

        context.mark_node_processed(node.id)


class GetSOASVarNodeEmitter(NodeEmitter):
    """Emitter for GetSOASVar nodes - retrieve SOAS application-level variables."""

    @property
    def node_type(self) -> str:
        return "get_soas_var"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code to retrieve a SOAS variable."""
        from visualpython2.nodes.definitions import GetSOASVarNode

        if not isinstance(node, GetSOASVarNode):
            context.errors.append(f"Expected GetSOASVarNode but got {type(node).__name__}")
            return

        soas_var_name = node.variable_name
        dynamic_name = self.get_input_value(node, "variable_name", context, generator.graph)

        # Get default value
        default_value = self.get_input_value(node, "default", context, generator.graph)
        if default_value is None:
            default_repr = repr(node.default_value) if hasattr(node, "default_value") and node.default_value is not None else "None"
        else:
            default_repr = default_value

        # Generate output variables
        value_var = context.generate_variable_name("soas_var")
        exists_var = context.generate_variable_name("soas_exists")
        context.set_output_variable(node.id, "value", value_var)
        context.set_output_variable(node.id, "exists", exists_var)

        context.add_line(f"# Get SOAS variable: {node.name}")

        if dynamic_name:
            name_expr = dynamic_name
        else:
            name_expr = repr(soas_var_name)

        context.add_line(f"{exists_var} = {name_expr} in _soas_vars")
        context.add_line(f"{value_var} = get_soas_var({name_expr}, {default_repr})")
        context.add_blank_line()

        context.mark_node_processed(node.id)


class SetSOASVarNodeEmitter(NodeEmitter):
    """Emitter for SetSOASVar nodes - store SOAS application-level variables."""

    @property
    def node_type(self) -> str:
        return "set_soas_var"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code to set a SOAS variable."""
        from visualpython2.nodes.definitions import SetSOASVarNode

        if not isinstance(node, SetSOASVarNode):
            context.errors.append(f"Expected SetSOASVarNode but got {type(node).__name__}")
            return

        soas_var_name = node.variable_name
        dynamic_name = self.get_input_value(node, "variable_name", context, generator.graph)
        value = self.get_input_value(node, "value", context, generator.graph, default="None")

        success_var = context.generate_variable_name("soas_set_success")
        context.set_output_variable(node.id, "success", success_var)

        context.add_line(f"# Set SOAS variable: {node.name}")

        if dynamic_name:
            name_expr = dynamic_name
        else:
            name_expr = repr(soas_var_name)

        context.add_line(f"{success_var} = set_soas_var({name_expr}, {value})")
        context.add_blank_line()

        context.mark_node_processed(node.id)


class GetUserSecretNodeEmitter(NodeEmitter):
    """Emitter for GetUserSecret nodes - retrieve per-user secrets."""

    @property
    def node_type(self) -> str:
        return "get_user_secret"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code to retrieve a user secret."""
        from visualpython2.nodes.definitions import GetUserSecretNode

        if not isinstance(node, GetUserSecretNode):
            context.errors.append(f"Expected GetUserSecretNode but got {type(node).__name__}")
            return

        secret_name = node.secret_name
        dynamic_name = self.get_input_value(node, "secret_name", context, generator.graph)

        # Get default value
        default_value = self.get_input_value(node, "default", context, generator.graph)
        if default_value is None:
            default_repr = repr(node.default_value) if hasattr(node, "default_value") and node.default_value is not None else "None"
        else:
            default_repr = default_value

        # Generate output variables
        value_var = context.generate_variable_name("user_secret")
        exists_var = context.generate_variable_name("user_secret_exists")
        context.set_output_variable(node.id, "value", value_var)
        context.set_output_variable(node.id, "exists", exists_var)

        context.add_line(f"# Get user secret: {node.name}")

        if dynamic_name:
            name_expr = dynamic_name
        else:
            name_expr = repr(secret_name)

        context.add_line(f"{exists_var} = {name_expr} in _user_secrets")
        context.add_line(f"{value_var} = get_user_secret({name_expr}, {default_repr})")
        context.add_blank_line()

        context.mark_node_processed(node.id)
