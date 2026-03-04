"""
Data processing emitters for DatabaseQuery, Regex, Subgraph, and RunAutomation nodes.

These emitters handle database operations, regular expression matching/replacement,
reusable subgraph composition, and sub-automation calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from visualpython2.compiler.emitters.base import NodeEmitter

if TYPE_CHECKING:
    from visualpython2.compiler.code_generator import CodeGenerator, GenerationContext


class DatabaseQueryNodeEmitter(NodeEmitter):
    """
    Emitter for DatabaseQuery nodes - SQL database operations.

    The DatabaseQueryNode enables executing SQL queries against databases
    with configurable connection strings. Currently supports SQLite natively.
    """

    @property
    def node_type(self) -> str:
        return "database_query"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate code for a DatabaseQueryNode.

        Creates database connection and query execution code with proper
        error handling and resource cleanup.
        """
        from visualpython2.nodes.definitions import DatabaseQueryNode

        if not isinstance(node, DatabaseQueryNode):
            context.errors.append(f"Expected DatabaseQueryNode but got {type(node).__name__}")
            return

        # Add sqlite3 import
        context.imports.add("import sqlite3")

        # Get input values or use configured values
        connection_var = self.get_input_value(
            node, "connection_string", context, generator.graph
        )
        query_var = self.get_input_value(
            node, "query", context, generator.graph
        )
        params_var = self.get_input_value(
            node, "parameters", context, generator.graph
        )
        timeout_var = self.get_input_value(
            node, "timeout", context, generator.graph
        )

        # Generate output variable names
        rows_var = context.generate_variable_name("db_rows")
        row_count_var = context.generate_variable_name("db_row_count")
        columns_var = context.generate_variable_name("db_columns")
        success_var = context.generate_variable_name("db_success")
        error_var = context.generate_variable_name("db_error")
        last_insert_id_var = context.generate_variable_name("db_last_insert_id")
        rows_affected_var = context.generate_variable_name("db_rows_affected")

        # Set output variables for downstream nodes
        context.set_output_variable(node.id, "rows", rows_var)
        context.set_output_variable(node.id, "row_count", row_count_var)
        context.set_output_variable(node.id, "columns", columns_var)
        context.set_output_variable(node.id, "success", success_var)
        context.set_output_variable(node.id, "error_message", error_var)
        context.set_output_variable(node.id, "last_insert_id", last_insert_id_var)
        context.set_output_variable(node.id, "rows_affected", rows_affected_var)

        context.add_line(f"# Database query node: {node.name}")

        # Determine connection string
        if connection_var:
            context.add_line(f"_db_connection_string = {connection_var}")
        else:
            context.add_line(f"_db_connection_string = {repr(node.connection_string)}")

        # Determine query
        if query_var:
            context.add_line(f"_db_query = {query_var}")
        else:
            context.add_line(f"_db_query = {repr(node.query)}")

        # Determine parameters
        if params_var:
            context.add_line(f"_db_params = {params_var}")
        else:
            context.add_line(f"_db_params = {repr(node.parameters)}")

        # Determine timeout
        if timeout_var:
            context.add_line(f"_db_timeout = {timeout_var}")
        else:
            context.add_line(f"_db_timeout = {node.timeout}")

        # Initialize output variables
        context.add_line(f"{rows_var} = []")
        context.add_line(f"{row_count_var} = 0")
        context.add_line(f"{columns_var} = []")
        context.add_line(f"{success_var} = False")
        context.add_line(f"{error_var} = ''")
        context.add_line(f"{last_insert_id_var} = 0")
        context.add_line(f"{rows_affected_var} = 0")

        # Generate try/except block for database operations
        context.add_line("try:")
        context.indentation.indent()

        # Connect to database
        context.add_line("_db_conn = sqlite3.connect(_db_connection_string, timeout=_db_timeout)")
        context.add_line("_db_conn.row_factory = sqlite3.Row")
        context.add_line("try:")
        context.indentation.indent()

        # Execute query
        context.add_line("_db_cursor = _db_conn.cursor()")
        context.add_line("if _db_params:")
        context.indentation.indent()
        context.add_line("_db_cursor.execute(_db_query, _db_params)")
        context.indentation.dedent()
        context.add_line("else:")
        context.indentation.indent()
        context.add_line("_db_cursor.execute(_db_query)")
        context.indentation.dedent()

        # Check if SELECT query
        context.add_line("_db_is_select = _db_query.strip().upper().startswith(('SELECT', 'WITH'))")
        context.add_line("if _db_is_select:")
        context.indentation.indent()

        # Fetch results for SELECT queries
        if node.fetch_size > 0:
            context.add_line(f"_db_raw_rows = _db_cursor.fetchmany({node.fetch_size})")
        else:
            context.add_line("_db_raw_rows = _db_cursor.fetchall()")

        context.add_line(f"{columns_var} = [desc[0] for desc in _db_cursor.description] if _db_cursor.description else []")
        context.add_line(f"{rows_var} = [dict(row) for row in _db_raw_rows]")
        context.add_line(f"{row_count_var} = len({rows_var})")
        context.indentation.dedent()

        context.add_line("else:")
        context.indentation.indent()
        context.add_line("_db_conn.commit()")
        context.add_line(f"{last_insert_id_var} = _db_cursor.lastrowid or 0")
        context.add_line(f"{rows_affected_var} = _db_cursor.rowcount")
        context.add_line(f"{row_count_var} = _db_cursor.rowcount")
        context.indentation.dedent()

        context.add_line(f"{success_var} = True")

        # Close connection in inner try
        context.indentation.dedent()
        context.add_line("finally:")
        context.indentation.indent()
        context.add_line("_db_conn.close()")
        context.indentation.dedent()

        # Handle exceptions
        context.indentation.dedent()
        context.add_line("except sqlite3.Error as _db_e:")
        context.indentation.indent()
        context.add_line(f"{error_var} = f'SQLite Error: {{_db_e}}'")
        context.indentation.dedent()
        context.add_line("except Exception as _db_e:")
        context.indentation.indent()
        context.add_line(f"{error_var} = str(_db_e)")
        context.indentation.dedent()

        context.add_blank_line()
        context.mark_node_processed(node.id)


class RegexMatchNodeEmitter(NodeEmitter):
    """
    Emitter for RegexMatch nodes - pattern matching operations.

    The RegexMatchNode enables visual regex pattern matching. Generated code
    uses Python's re module to find all matches in the input text.
    """

    @property
    def node_type(self) -> str:
        return "regex_match"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate code for a RegexMatchNode.

        Creates regex matching code with proper error handling and flag support.
        """
        from visualpython2.nodes.definitions import RegexMatchNode

        if not isinstance(node, RegexMatchNode):
            context.errors.append(f"Expected RegexMatchNode but got {type(node).__name__}")
            return

        # Add re import
        context.imports.add("import re")

        # Get input values
        text_var = self.get_input_value(node, "text", context, generator.graph)
        pattern_var = self.get_input_value(node, "pattern", context, generator.graph)

        # Generate output variable names
        matches_var = context.generate_variable_name("regex_matches")
        match_found_var = context.generate_variable_name("regex_match_found")
        first_match_var = context.generate_variable_name("regex_first_match")
        match_count_var = context.generate_variable_name("regex_match_count")
        groups_var = context.generate_variable_name("regex_groups")
        error_var = context.generate_variable_name("regex_error")

        # Set output variables
        context.set_output_variable(node.id, "matches", matches_var)
        context.set_output_variable(node.id, "match_found", match_found_var)
        context.set_output_variable(node.id, "first_match", first_match_var)
        context.set_output_variable(node.id, "match_count", match_count_var)
        context.set_output_variable(node.id, "groups", groups_var)
        context.set_output_variable(node.id, "error_message", error_var)

        context.add_line(f"# Regex match node: {node.name}")

        # Determine text value
        if text_var:
            context.add_line(f"_regex_text = str({text_var}) if {text_var} is not None else ''")
        else:
            context.add_line("_regex_text = ''")

        # Determine pattern value
        if pattern_var:
            context.add_line(f"_regex_pattern = {pattern_var}")
        else:
            context.add_line(f"_regex_pattern = {repr(node.default_pattern)}")

        # Initialize output variables
        context.add_line(f"{matches_var} = []")
        context.add_line(f"{match_found_var} = False")
        context.add_line(f"{first_match_var} = ''")
        context.add_line(f"{match_count_var} = 0")
        context.add_line(f"{groups_var} = []")
        context.add_line(f"{error_var} = ''")

        # Build flags
        flags_parts = []
        if node.case_insensitive:
            flags_parts.append("re.IGNORECASE")
        if node.multiline:
            flags_parts.append("re.MULTILINE")
        if node.dot_all:
            flags_parts.append("re.DOTALL")

        flags_expr = " | ".join(flags_parts) if flags_parts else "0"

        # Generate try/except block for regex operations
        context.add_line("try:")
        context.indentation.indent()

        context.add_line(f"_regex_compiled = re.compile(_regex_pattern, {flags_expr})")
        context.add_line(f"_regex_all_matches = _regex_compiled.findall(_regex_text)")

        # Handle groups - findall returns tuples if pattern has groups
        context.add_line("if _regex_all_matches:")
        context.indentation.indent()
        context.add_line("if isinstance(_regex_all_matches[0], tuple):")
        context.indentation.indent()
        context.add_line(f"{matches_var} = [m[0] if m else '' for m in _regex_all_matches]")
        context.indentation.dedent()
        context.add_line("else:")
        context.indentation.indent()
        context.add_line(f"{matches_var} = list(_regex_all_matches)")
        context.indentation.dedent()
        context.add_line(f"{match_found_var} = True")
        context.add_line(f"{first_match_var} = {matches_var}[0] if {matches_var} else ''")
        context.add_line(f"{match_count_var} = len({matches_var})")
        context.add_line("_regex_first_match_obj = _regex_compiled.search(_regex_text)")
        context.add_line("if _regex_first_match_obj and _regex_first_match_obj.groups():")
        context.indentation.indent()
        context.add_line(f"{groups_var} = list(_regex_first_match_obj.groups())")
        context.indentation.dedent()
        context.indentation.dedent()

        context.indentation.dedent()
        context.add_line("except re.error as _regex_e:")
        context.indentation.indent()
        context.add_line(f"{error_var} = f'Regex error: {{_regex_e}}'")
        context.indentation.dedent()
        context.add_line("except Exception as _regex_e:")
        context.indentation.indent()
        context.add_line(f"{error_var} = str(_regex_e)")
        context.indentation.dedent()

        context.add_blank_line()
        context.mark_node_processed(node.id)


class RegexReplaceNodeEmitter(NodeEmitter):
    """
    Emitter for RegexReplace nodes - pattern replacement operations.

    The RegexReplaceNode enables visual regex pattern replacement. Generated code
    uses Python's re module to replace all matches in the input text.
    """

    @property
    def node_type(self) -> str:
        return "regex_replace"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate code for a RegexReplaceNode.

        Creates regex replacement code with proper error handling and flag support.
        """
        from visualpython2.nodes.definitions import RegexReplaceNode

        if not isinstance(node, RegexReplaceNode):
            context.errors.append(f"Expected RegexReplaceNode but got {type(node).__name__}")
            return

        # Add re import
        context.imports.add("import re")

        # Get input values
        text_var = self.get_input_value(node, "text", context, generator.graph)
        pattern_var = self.get_input_value(node, "pattern", context, generator.graph)
        replacement_var = self.get_input_value(node, "replacement", context, generator.graph)

        # Generate output variable names
        result_var = context.generate_variable_name("regex_result")
        count_var = context.generate_variable_name("regex_replace_count")
        original_var = context.generate_variable_name("regex_original")
        changed_var = context.generate_variable_name("regex_changed")
        error_var = context.generate_variable_name("regex_replace_error")

        # Set output variables
        context.set_output_variable(node.id, "result", result_var)
        context.set_output_variable(node.id, "replacement_count", count_var)
        context.set_output_variable(node.id, "original_text", original_var)
        context.set_output_variable(node.id, "changed", changed_var)
        context.set_output_variable(node.id, "error_message", error_var)

        context.add_line(f"# Regex replace node: {node.name}")

        # Determine text value
        if text_var:
            context.add_line(f"_regex_text = str({text_var}) if {text_var} is not None else ''")
        else:
            context.add_line("_regex_text = ''")

        # Store original
        context.add_line(f"{original_var} = _regex_text")

        # Determine pattern value
        if pattern_var:
            context.add_line(f"_regex_pattern = {pattern_var}")
        else:
            context.add_line(f"_regex_pattern = {repr(node.default_pattern)}")

        # Determine replacement value
        if replacement_var:
            context.add_line(f"_regex_replacement = {replacement_var}")
        else:
            context.add_line(f"_regex_replacement = {repr(node.default_replacement)}")

        # Initialize output variables
        context.add_line(f"{result_var} = _regex_text")
        context.add_line(f"{count_var} = 0")
        context.add_line(f"{changed_var} = False")
        context.add_line(f"{error_var} = ''")

        # Build flags
        flags_parts = []
        if node.case_insensitive:
            flags_parts.append("re.IGNORECASE")
        if node.multiline:
            flags_parts.append("re.MULTILINE")
        if node.dot_all:
            flags_parts.append("re.DOTALL")

        flags_expr = " | ".join(flags_parts) if flags_parts else "0"

        # Generate try/except block for regex operations
        context.add_line("try:")
        context.indentation.indent()

        context.add_line(f"_regex_compiled = re.compile(_regex_pattern, {flags_expr})")

        # Perform replacement with optional count limit
        if node.max_replacements > 0:
            context.add_line(f"{result_var}, {count_var} = _regex_compiled.subn(_regex_replacement, _regex_text, count={node.max_replacements})")
        else:
            context.add_line(f"{result_var}, {count_var} = _regex_compiled.subn(_regex_replacement, _regex_text)")

        context.add_line(f"{changed_var} = {count_var} > 0")

        context.indentation.dedent()
        context.add_line("except re.error as _regex_e:")
        context.indentation.indent()
        context.add_line(f"{error_var} = f'Regex error: {{_regex_e}}'")
        context.add_line(f"{result_var} = _regex_text")
        context.indentation.dedent()
        context.add_line("except Exception as _regex_e:")
        context.indentation.indent()
        context.add_line(f"{error_var} = str(_regex_e)")
        context.add_line(f"{result_var} = _regex_text")
        context.indentation.dedent()

        context.add_blank_line()
        context.mark_node_processed(node.id)


class SubgraphNodeEmitter(NodeEmitter):
    """
    Emitter for Subgraph nodes - reusable subgraph execution.

    The SubgraphNode enables modular composition by allowing users to encapsulate
    groups of nodes as reusable functions.
    """

    @property
    def node_type(self) -> str:
        return "subgraph"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate code for a SubgraphNode.

        Creates a function definition from the subgraph's internal graph and
        calls it with the provided input values.
        """
        from visualpython2.nodes.definitions import SubgraphNode
        from visualpython2.compiler.code_generator import CodeContext

        if not isinstance(node, SubgraphNode):
            context.errors.append(f"Expected SubgraphNode but got {type(node).__name__}")
            return

        # Generate unique function name for this subgraph
        func_name = context.generate_variable_name(f"subgraph_{node.subgraph_name.replace(' ', '_').lower()}")

        context.add_line(f"# Subgraph: {node.name} ({node.subgraph_name})")

        # Circular reference detection for reference-based nodes
        _tracking_path = None
        if node.is_reference_based and node.subgraph_path:
            if node.subgraph_path in context.subgraph_inline_stack:
                context.errors.append(
                    f"Circular subgraph reference detected: '{node.subgraph_path}'"
                )
                context.add_line(f"# Error: Circular reference to '{node.subgraph_path}'")
                context.add_line("pass")
                context.mark_node_processed(node.id)
                return
            context.subgraph_inline_stack.add(node.subgraph_path)
            _tracking_path = node.subgraph_path

        # Get the internal graph data (reads from library file for reference-based nodes)
        graph_data = node.get_internal_graph_data()

        if graph_data is None:
            context.add_line(f"# Warning: Subgraph '{node.subgraph_name}' has no graph data")
            context.add_line("pass")
            context.mark_node_processed(node.id)
            if _tracking_path:
                context.subgraph_inline_stack.discard(_tracking_path)
            return

        # Collect input values
        input_values: Dict[str, str] = {}
        for port_name in node.input_mappings:
            input_var = self.get_input_value(node, port_name, context, generator.graph)
            if input_var:
                input_values[port_name] = input_var
            else:
                # Use default value if no connection
                input_port = node.get_input_port(port_name)
                if input_port and input_port.default_value is not None:
                    input_values[port_name] = repr(input_port.default_value)
                else:
                    input_values[port_name] = "None"

        # Generate function parameters
        param_names = list(node.input_mappings.keys())
        params_str = ", ".join(param_names) if param_names else ""

        # Generate the subgraph function definition
        context.add_line(f"def {func_name}({params_str}):")
        context.indentation.indent()

        # Enter function scope
        context.enter_scope(CodeContext.FUNCTION, branch_name="subgraph")

        # Generate subgraph body
        self._emit_subgraph_body(node, graph_data, context, generator)

        # Generate return statement with output values
        output_names = list(node.output_mappings.keys())
        if output_names:
            return_dict_items = ", ".join([f"'{name}': _{name}_output" for name in output_names])
            context.add_line(f"return {{{return_dict_items}}}")
        else:
            context.add_line("return {}")

        # Exit function scope
        context.exit_scope()
        context.indentation.dedent()
        context.add_blank_line()

        # Call the subgraph function with input values
        args_str = ", ".join([f"{name}={input_values.get(name, 'None')}" for name in param_names])
        result_var = context.generate_variable_name("subgraph_result")
        context.add_line(f"{result_var} = {func_name}({args_str})")

        # Extract output values
        for port_name in output_names:
            output_var = context.generate_variable_name(f"subgraph_out_{port_name}")
            context.set_output_variable(node.id, port_name, output_var)
            context.add_line(f"{output_var} = {result_var}.get('{port_name}')")

        context.add_blank_line()
        context.mark_node_processed(node.id)

        # Clean up circular reference tracking
        if _tracking_path:
            context.subgraph_inline_stack.discard(_tracking_path)

    def _emit_subgraph_body(
        self,
        subgraph_node: object,
        graph_data: Dict[str, Any],
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Emit the body of the subgraph function.

        This method fully compiles the nested workflow into inline Python code,
        supporting nested subgraphs (workflows within workflows).
        """
        from visualpython2.nodes.definitions import SubgraphNode
        from visualpython2.compiler.code_generator import CodeContext

        if not isinstance(subgraph_node, SubgraphNode):
            context.add_line("pass  # Invalid subgraph node")
            return

        nodes_data = graph_data.get("nodes", [])
        connections_data = graph_data.get("connections", [])

        # Build a mapping of node IDs to node data
        node_map: Dict[str, Dict[str, Any]] = {n["id"]: n for n in nodes_data}

        # Find SubgraphInput nodes and assign input values
        for port_name, input_node_id in subgraph_node.input_mappings.items():
            input_node_data = node_map.get(input_node_id)
            if input_node_data:
                # The input value is available as a function parameter
                output_var = context.generate_variable_name(f"input_{port_name}")
                context.set_output_variable(input_node_id, "value", output_var)
                context.add_line(f"{output_var} = {port_name}")

        # Build subgraph context mapping for tracking output variables
        subgraph_context_vars: Dict[str, Dict[str, str]] = {}

        # Process SubgraphInput nodes first to establish input variable mappings
        for node_data in nodes_data:
            if node_data.get("type") == "subgraph_input":
                node_id = node_data.get("id")
                port_name = node_data.get("properties", {}).get("port_name", "input")
                if node_id in [nid for nid in subgraph_node.input_mappings.values()]:
                    # Already handled above
                    pass
                else:
                    # Standalone input node - use default value
                    default_val = node_data.get("properties", {}).get("default_value")
                    output_var = context.generate_variable_name(f"input_{port_name}")
                    context.set_output_variable(node_id, "value", output_var)
                    context.add_line(f"{output_var} = {repr(default_val)}")
                subgraph_context_vars[node_id] = {"value": context.get_output_variable(node_id, "value")}

        # Build execution order from connections
        execution_order = self._get_subgraph_execution_order(nodes_data, connections_data)

        # Process nodes in execution order
        for node_id in execution_order:
            node_data = node_map.get(node_id)
            if not node_data:
                continue

            node_type = node_data.get("type")
            node_name = node_data.get("name", node_type)

            if node_type == "subgraph_input":
                # Already handled above
                continue

            if node_type == "subgraph_output":
                # Handle output collection
                port_name = node_data.get("properties", {}).get("port_name", "output")

                # Find what's connected to this output node's value input
                value_source = self._find_input_source(
                    node_id, "value", connections_data, context
                )

                # Set the output variable
                if value_source:
                    context.add_line(f"_{port_name}_output = {value_source}")
                else:
                    context.add_line(f"_{port_name}_output = None")
                continue

            if node_type == "subgraph":
                # Nested subgraph - recursively generate
                self._emit_nested_subgraph(node_data, connections_data, context, generator)
                continue

            if node_type == "code":
                # Code node - emit the code
                self._emit_code_node(node_data, connections_data, context)
                continue

            # For other node types, generate based on type
            self._emit_generic_node(node_data, connections_data, context)

        # If no output nodes were found, ensure we have placeholders
        for port_name in subgraph_node.output_mappings:
            output_var_name = f"_{port_name}_output"
            # Check if we already defined this variable
            if output_var_name not in context.get_generated_code():
                context.add_line(f"{output_var_name} = None  # No connection found")

    def _get_subgraph_execution_order(
        self,
        nodes_data: List[Dict[str, Any]],
        connections_data: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Determine execution order of nodes in a subgraph.

        Uses topological sort based on data flow connections.
        """
        from collections import deque

        # Build dependency graph
        node_ids = {n["id"] for n in nodes_data}
        in_degree: Dict[str, int] = {nid: 0 for nid in node_ids}
        outgoing: Dict[str, List[str]] = {nid: [] for nid in node_ids}

        for conn in connections_data:
            src = conn.get("source_node_id")
            tgt = conn.get("target_node_id")
            if src in node_ids and tgt in node_ids:
                outgoing[src].append(tgt)
                in_degree[tgt] += 1

        # Kahn's algorithm for topological sort
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)

            for successor in outgoing[node_id]:
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        return result

    def _find_input_source(
        self,
        node_id: str,
        port_name: str,
        connections_data: List[Dict[str, Any]],
        context: GenerationContext,
    ) -> Optional[str]:
        """
        Find the variable that provides a value to an input port.
        """
        for conn in connections_data:
            if (conn.get("target_node_id") == node_id and
                conn.get("target_port_name") == port_name):
                source_node_id = conn.get("source_node_id")
                source_port_name = conn.get("source_port_name")
                return context.get_output_variable(source_node_id, source_port_name)
        return None

    def _emit_code_node(
        self,
        node_data: Dict[str, Any],
        connections_data: List[Dict[str, Any]],
        context: GenerationContext,
    ) -> None:
        """
        Emit code for a Code node within a subgraph.
        """
        node_id = node_data.get("id")
        node_name = node_data.get("name", "Code")
        properties = node_data.get("properties", {})
        code = properties.get("code", "")

        if not code or not code.strip():
            context.add_line("pass  # Empty code node")
            return

        # Get input value if connected
        input_var = self._find_input_source(node_id, "value", connections_data, context)

        # Generate a variable for the result
        result_var = context.generate_variable_name("result")
        context.set_output_variable(node_id, "result", result_var)

        context.add_line(f"# Code node: {node_name}")

        # Create the inputs dict
        if input_var:
            context.add_line(f"inputs = {{'value': {input_var}}}")
        else:
            context.add_line("inputs = {}")

        context.add_line("outputs = {}")
        context.add_line("globals = _global_vars")

        # Emit the user's Python code
        code_lines = code.strip().split("\n")
        for line in code_lines:
            context.add_line(line)

        # Extract result
        context.add_line(f"{result_var} = outputs.get('result')")
        context.add_blank_line()

    def _emit_nested_subgraph(
        self,
        node_data: Dict[str, Any],
        parent_connections: List[Dict[str, Any]],
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Emit code for a nested subgraph within another subgraph.
        """
        from visualpython2.compiler.code_generator import CodeContext

        node_id = node_data.get("id")
        properties = node_data.get("properties", {})
        subgraph_name = properties.get("subgraph_name", "Nested")
        is_reference_based = properties.get("is_reference_based", False)

        embedded_data = None
        if is_reference_based:
            subgraph_path = properties.get("subgraph_path")
            if subgraph_path:
                # Check for circular references
                if subgraph_path in context.subgraph_inline_stack:
                    context.errors.append(
                        f"Circular subgraph reference detected: '{subgraph_path}'"
                    )
                    context.add_line(f"# Error: Circular reference to '{subgraph_path}'")
                    context.add_line("pass")
                    return
                context.subgraph_inline_stack.add(subgraph_path)
                try:
                    import json as _json
                    with open(subgraph_path, "r", encoding="utf-8") as f:
                        file_data = _json.load(f)
                    if "graph" in file_data:
                        embedded_data = file_data["graph"]
                    elif "subgraph" in file_data:
                        embedded_data = file_data["subgraph"]
                    else:
                        embedded_data = file_data
                except Exception as e:
                    context.add_line(f"# Error: Could not load nested subgraph from '{subgraph_path}': {e}")
                    context.add_line("pass")
                    context.subgraph_inline_stack.discard(subgraph_path)
                    return
            else:
                context.add_line(f"# Warning: Reference-based subgraph '{subgraph_name}' has no path")
                context.add_line("pass")
                return
        else:
            embedded_data = properties.get("embedded_graph_data")

        if not embedded_data:
            context.add_line(f"# Warning: Nested subgraph '{subgraph_name}' has no graph data")
            context.add_line("pass")
            return

        # Generate function name
        func_name = context.generate_variable_name(f"nested_{subgraph_name.replace(' ', '_').lower()}")

        context.add_line(f"# Nested subgraph: {subgraph_name}")

        # Collect inputs
        input_mappings = properties.get("input_mappings", {})
        output_mappings = properties.get("output_mappings", {})

        input_values: Dict[str, str] = {}
        for port_name in input_mappings:
            input_var = self._find_input_source(node_id, port_name, parent_connections, context)
            input_values[port_name] = input_var if input_var else "None"

        # Generate function parameters
        param_names = list(input_mappings.keys())
        params_str = ", ".join(param_names) if param_names else ""

        # Generate the nested function
        context.add_line(f"def {func_name}({params_str}):")
        context.indentation.indent()
        context.enter_scope(CodeContext.FUNCTION, branch_name="nested_subgraph")

        # Recursively emit the nested subgraph body
        from visualpython2.nodes.definitions import SubgraphNode
        nested_subgraph = SubgraphNode(node_id=node_id, name=subgraph_name)
        nested_subgraph._input_mappings = input_mappings
        nested_subgraph._output_mappings = output_mappings
        nested_subgraph._embedded_graph_data = embedded_data
        nested_subgraph._subgraph_loaded = True

        self._emit_subgraph_body(nested_subgraph, embedded_data, context, generator)

        # Return statement
        output_names = list(output_mappings.keys())
        if output_names:
            return_dict_items = ", ".join([f"'{name}': _{name}_output" for name in output_names])
            context.add_line(f"return {{{return_dict_items}}}")
        else:
            context.add_line("return {}")

        context.exit_scope()
        context.indentation.dedent()
        context.add_blank_line()

        # Call the nested function
        args_str = ", ".join([f"{name}={input_values.get(name, 'None')}" for name in param_names])
        result_var = context.generate_variable_name("nested_result")
        context.add_line(f"{result_var} = {func_name}({args_str})")

        # Extract outputs
        for port_name in output_names:
            output_var = context.generate_variable_name(f"nested_out_{port_name}")
            context.set_output_variable(node_id, port_name, output_var)
            context.add_line(f"{output_var} = {result_var}.get('{port_name}')")

        context.add_blank_line()

        # Clean up circular reference tracking
        if is_reference_based and properties.get("subgraph_path"):
            context.subgraph_inline_stack.discard(properties["subgraph_path"])

    def _emit_generic_node(
        self,
        node_data: Dict[str, Any],
        connections_data: List[Dict[str, Any]],
        context: GenerationContext,
    ) -> None:
        """
        Emit code for a generic node type within a subgraph.
        """
        node_id = node_data.get("id")
        node_type = node_data.get("type", "unknown")
        node_name = node_data.get("name", node_type)

        context.add_line(f"# {node_type} node: {node_name}")

        # Generate a placeholder output variable
        result_var = context.generate_variable_name(f"{node_type}_result")
        context.set_output_variable(node_id, "result", result_var)
        context.set_output_variable(node_id, "value", result_var)
        context.set_output_variable(node_id, "output", result_var)

        context.add_line(f"{result_var} = None  # Placeholder for {node_type} node")


class SubgraphInputNodeEmitter(NodeEmitter):
    """
    Emitter for SubgraphInput nodes - input parameter definition within subgraphs.

    Within a subgraph, SubgraphInput nodes receive values passed from the parent
    SubgraphNode and make them available to downstream nodes.
    """

    @property
    def node_type(self) -> str:
        return "subgraph_input"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code for a SubgraphInputNode."""
        from visualpython2.nodes.definitions import SubgraphInputNode

        if not isinstance(node, SubgraphInputNode):
            context.errors.append(f"Expected SubgraphInputNode but got {type(node).__name__}")
            return

        # Generate output variable for the input value
        value_var = context.generate_variable_name(f"subgraph_input_{node.port_name}")
        context.set_output_variable(node.id, "value", value_var)

        context.add_line(f"# Subgraph input: {node.port_name}")

        # The value should be provided by the subgraph execution context
        default_repr = repr(node.default_value) if node.default_value is not None else "None"
        context.add_line(f"{value_var} = _subgraph_inputs.get('{node.port_name}', {default_repr})")
        context.add_blank_line()

        context.mark_node_processed(node.id)


class SubgraphOutputNodeEmitter(NodeEmitter):
    """
    Emitter for SubgraphOutput nodes - output parameter definition within subgraphs.

    Within a subgraph, SubgraphOutput nodes capture values to be returned to the
    parent SubgraphNode.
    """

    @property
    def node_type(self) -> str:
        return "subgraph_output"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code for a SubgraphOutputNode."""
        from visualpython2.nodes.definitions import SubgraphOutputNode

        if not isinstance(node, SubgraphOutputNode):
            context.errors.append(f"Expected SubgraphOutputNode but got {type(node).__name__}")
            return

        context.add_line(f"# Subgraph output: {node.port_name}")

        # Get the value being output
        value_var = self.get_input_value(node, "value", context, generator.graph)

        if value_var:
            context.add_line(f"_subgraph_outputs['{node.port_name}'] = {value_var}")
        else:
            context.add_line(f"_subgraph_outputs['{node.port_name}'] = None")

        context.add_blank_line()
        context.mark_node_processed(node.id)


class RunAutomationNodeEmitter(NodeEmitter):
    """
    Emitter for RunAutomation nodes - execute another automation as a sub-automation.

    Generates code that calls the soas_runtime helper to trigger a child automation
    via the SOAS API, with support for synchronous (wait) and asynchronous (fire-and-forget) modes.
    """

    @property
    def node_type(self) -> str:
        return "run_automation"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Generate code for a RunAutomationNode."""
        from visualpython2.nodes.definitions import RunAutomationNode

        if not isinstance(node, RunAutomationNode):
            context.errors.append(f"Expected RunAutomationNode but got {type(node).__name__}")
            return

        context.imports.add("from soas_runtime import run_automation as _soas_run_automation")

        automation_id = node.automation_id
        automation_name = node.automation_name or automation_id
        synchronous = node.synchronous

        context.add_line(f"# Run sub-automation: {automation_name}")

        # Generate unique variable names based on node id
        safe_id = node.id.replace("-", "_")

        # Determine how to build the parameters dict
        if node._input_defs:
            # Dynamic ports mode: gather individual port values into a dict
            params_var = f"_run_params_{safe_id}"
            context.add_line(f"{params_var} = {{}}")
            for defn in node._input_defs:
                port_name = defn["name"]
                port_var = self.get_input_value(
                    node, port_name, context, generator.graph
                )
                if port_var:
                    context.add_line(f"{params_var}[{repr(port_name)}] = {port_var}")
                elif defn.get("default_value") is not None:
                    context.add_line(
                        f"{params_var}[{repr(port_name)}] = {repr(defn['default_value'])}"
                    )
        else:
            # Legacy mode: single parameters dict port
            params_var = self.get_input_value(
                node, "parameters", context, generator.graph, default="{}"
            )

        result_var = f"_run_result_{safe_id}"

        context.add_line(
            f"{result_var} = _soas_run_automation("
            f"{repr(automation_id)}, parameters={params_var}, "
            f"synchronous={repr(synchronous)})"
        )

        # Register output variables
        exec_id_var = f"_run_exec_id_{safe_id}"
        success_var = f"_run_success_{safe_id}"
        output_var = f"_run_output_{safe_id}"
        error_var = f"_run_error_{safe_id}"

        context.add_line(f"{exec_id_var} = {result_var}['execution_id']")
        context.add_line(f"{success_var} = {result_var}['success']")
        context.add_line(f"{output_var} = {result_var}['output']")
        context.add_line(f"{error_var} = {result_var}['error']")

        context.set_output_variable(node.id, "execution_id", exec_id_var)
        context.set_output_variable(node.id, "success", success_var)
        context.set_output_variable(node.id, "output", output_var)
        context.set_output_variable(node.id, "error", error_var)

        context.add_blank_line()
        context.mark_node_processed(node.id)
