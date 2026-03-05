"""
Control flow emitters for Start, End, If, ForLoop, WhileLoop, TryCatch, and Merge nodes.

These emitters handle the branching, looping, and convergence structures
in the visual graph and produce corresponding Python control flow code.
"""

from __future__ import annotations

from typing import List, Optional, Set, TYPE_CHECKING

from visualpython2.compiler.emitters.base import NodeEmitter

if TYPE_CHECKING:
    from visualpython2.compiler.code_generator import (
        CodeGenerator,
        CodeContext,
        GenerationContext,
    )


class StartNodeEmitter(NodeEmitter):
    """Emitter for Start nodes - entry point of execution."""

    @property
    def node_type(self) -> str:
        return "start"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """Start nodes mark the beginning and extract input parameters."""
        from visualpython2.nodes.definitions import StartNode

        context.add_line("# Script execution begins")

        # If the Start node has dynamic output ports (automation inputs),
        # extract each parameter from _subgraph_inputs
        if isinstance(node, StartNode) and node._input_defs:
            context.add_blank_line()
            context.add_line("# Extract automation input parameters")
            for defn in node._input_defs:
                param_name = defn["name"]
                default_value = defn.get("default_value")
                default_repr = repr(default_value) if default_value is not None else "None"

                var_name = context.generate_variable_name(f"param_{param_name}")
                context.set_output_variable(node.id, param_name, var_name)
                context.add_line(
                    f"{var_name} = _subgraph_inputs.get('{param_name}', {default_repr})"
                )
            context.add_blank_line()

        context.mark_node_processed(node.id)


class EndNodeEmitter(NodeEmitter):
    """Emitter for End nodes - termination point of execution."""

    @property
    def node_type(self) -> str:
        return "end"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """End nodes capture results and terminate execution paths."""
        result_var = self.get_input_value(node, "result", context, generator.graph)

        if result_var:
            context.add_line(f"# End of execution - result: {result_var}")
            context.add_line(f"_end_result = {result_var}")
        else:
            context.add_line("# End of execution")
            context.add_line("pass  # End node")

        context.mark_node_processed(node.id)


class IfNodeEmitter(NodeEmitter):
    """Emitter for If nodes - conditional branching."""

    @property
    def node_type(self) -> str:
        return "if"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate code for an IfNode.

        Creates an if/else structure and recursively generates code
        for each branch. Tracks variable scopes to detect variables that
        are only defined in one branch (conditional variables).

        When both branches converge to the same node (typically a merge node),
        that convergence node is emitted after the if/else block completes,
        ensuring proper code structure.
        """
        from visualpython2.nodes.definitions import IfNode
        from visualpython2.compiler.code_generator import CodeContext

        if not isinstance(node, IfNode):
            context.errors.append(f"Expected IfNode but got {type(node).__name__}")
            return

        # Get condition and value inputs
        condition_var = self.get_input_value(node, "condition", context, generator.graph)
        value_var = self.get_input_value(node, "value", context, generator.graph)

        # Store the result (defined at current scope, not conditional)
        result_var = context.generate_variable_name("condition_result")
        context.set_output_variable(node.id, "result", result_var)

        context.add_line(f"# If node: {node.name}")

        operator = getattr(node, "operator", "custom")
        compare_value = getattr(node, "compare_value", "")

        if operator == "custom":
            # Legacy custom expression mode
            if node.condition_code:
                if value_var:
                    context.add_line(f"value = {value_var}")
                if condition_var:
                    context.add_line(f"condition = {condition_var}")
                condition_expr = node.condition_code.strip()
            elif condition_var:
                condition_expr = condition_var
            else:
                condition_expr = "False"
            context.add_line(f"{result_var} = bool({condition_expr})")
        else:
            # Operator-based comparison
            val_expr = value_var or condition_var or "None"
            self._emit_operator_code(operator, val_expr, compare_value, result_var, context)

        context.add_line(f"if {result_var}:")

        # Find convergence nodes - nodes that both branches lead to
        # These should be emitted after the if/else block, not inside branches
        convergence_nodes = self._find_convergence_nodes(node, generator)

        # True branch - enter scope for variable tracking
        context.indentation.indent()
        context.enter_scope(CodeContext.IF_BRANCH, branch_name="true_branch")

        true_branch_nodes = generator.get_flow_connected_nodes(node.id, "true_branch")
        if true_branch_nodes:
            for branch_node in true_branch_nodes:
                # Skip convergence nodes - they'll be emitted after if/else
                if branch_node.id not in convergence_nodes:
                    self._emit_branch_flow(branch_node, context, generator, convergence_nodes)
                else:
                    context.add_line("pass  # Continues to merge point")
        else:
            context.add_line("pass")

        # Exit true branch scope
        true_branch_scope = context.scope_manager.current_scope
        context.exit_scope()
        context.indentation.dedent()

        # False branch
        context.add_line("else:")
        context.indentation.indent()
        context.enter_scope(CodeContext.IF_BRANCH, branch_name="false_branch")

        false_branch_nodes = generator.get_flow_connected_nodes(node.id, "false_branch")
        if false_branch_nodes:
            for branch_node in false_branch_nodes:
                # Skip convergence nodes - they'll be emitted after if/else
                if branch_node.id not in convergence_nodes:
                    self._emit_branch_flow(branch_node, context, generator, convergence_nodes)
                else:
                    context.add_line("pass  # Continues to merge point")
        else:
            context.add_line("pass")

        # Exit false branch scope
        false_branch_scope = context.scope_manager.current_scope
        context.exit_scope()
        context.indentation.dedent()

        # Merge branch scopes to identify truly conditional variables
        if true_branch_scope and false_branch_scope:
            context.scope_manager.merge_branch_scopes(
                [true_branch_scope, false_branch_scope]
            )

        context.add_blank_line()
        context.mark_node_processed(node.id)

        # Now emit convergence nodes after the if/else block
        for conv_node_id in convergence_nodes:
            conv_node = generator.graph.get_node(conv_node_id)
            if conv_node and not context.is_node_processed(conv_node.id):
                generator._emit_flow_from_node(conv_node, context)

    def _emit_operator_code(
        self,
        operator: str,
        val_expr: str,
        compare_value: str,
        result_var: str,
        context: "GenerationContext",
    ) -> None:
        """Emit Python code for an operator-based comparison."""
        cmp_repr = repr(compare_value)

        if operator == "is_truthy":
            context.add_line(f"{result_var} = bool({val_expr})")
        elif operator == "is_falsy":
            context.add_line(f"{result_var} = not bool({val_expr})")
        elif operator == "equals":
            context.add_line(f"{result_var} = str({val_expr}) == {cmp_repr}")
        elif operator == "not_equals":
            context.add_line(f"{result_var} = str({val_expr}) != {cmp_repr}")
        elif operator == "contains":
            context.add_line(f"{result_var} = {cmp_repr} in str({val_expr})")
        elif operator == "not_contains":
            context.add_line(f"{result_var} = {cmp_repr} not in str({val_expr})")
        elif operator == "starts_with":
            context.add_line(f"{result_var} = str({val_expr}).startswith({cmp_repr})")
        elif operator == "ends_with":
            context.add_line(f"{result_var} = str({val_expr}).endswith({cmp_repr})")
        elif operator in ("greater_than", "greater_equal", "less_than", "less_equal"):
            op_map = {
                "greater_than": ">",
                "greater_equal": ">=",
                "less_than": "<",
                "less_equal": "<=",
            }
            py_op = op_map[operator]
            context.add_line("try:")
            context.indentation.indent()
            context.add_line(f"{result_var} = float({val_expr}) {py_op} float({cmp_repr})")
            context.indentation.dedent()
            context.add_line("except (ValueError, TypeError):")
            context.indentation.indent()
            context.add_line(f"{result_var} = False")
            context.indentation.dedent()
        elif operator == "matches_regex":
            context.imports.add("import re as _re")
            context.add_line(f"{result_var} = bool(_re.search({cmp_repr}, str({val_expr})))")
        else:
            # Fallback
            context.add_line(f"{result_var} = bool({val_expr})")

    def _find_convergence_nodes(
        self,
        if_node: object,
        generator: CodeGenerator,
    ) -> Set[str]:
        """
        Find nodes that both true and false branches eventually lead to.

        These are convergence points (typically merge nodes) that should be
        emitted after the if/else block rather than inside a branch.

        Args:
            if_node: The if node being processed.
            generator: The code generator for graph access.

        Returns:
            Set of node IDs that are convergence points.
        """
        # Get immediate successors of each branch
        true_successors = self._get_all_successors(if_node.id, "true_branch", generator)
        false_successors = self._get_all_successors(if_node.id, "false_branch", generator)

        # Convergence nodes are those reachable from both branches
        convergence = true_successors & false_successors

        return convergence

    def _get_all_successors(
        self,
        node_id: str,
        port_name: str,
        generator: CodeGenerator,
    ) -> Set[str]:
        """
        Get all successor node IDs reachable from a given port.

        Args:
            node_id: The source node ID.
            port_name: The output port name.
            generator: The code generator for graph access.

        Returns:
            Set of node IDs reachable from the port.
        """
        successors: Set[str] = set()
        visited: Set[str] = set()

        def traverse(nid: str, pname: str) -> None:
            connections = generator.graph.get_connections_for_port(nid, pname, is_input=False)
            for conn in connections:
                target_id = conn.target_node_id
                if target_id not in visited:
                    visited.add(target_id)
                    successors.add(target_id)
                    # Continue traversing from the target node's exec_out
                    target_node = generator.graph.get_node(target_id)
                    if target_node:
                        # Don't traverse through if nodes to avoid infinite loops
                        if target_node.node_type != "if":
                            traverse(target_id, "exec_out")

        traverse(node_id, port_name)
        return successors

    def _emit_branch_flow(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
        convergence_nodes: Set[str],
    ) -> None:
        """
        Emit code for a branch, stopping at convergence nodes.

        Args:
            node: The starting node of the branch.
            context: The generation context.
            generator: The code generator.
            convergence_nodes: Set of node IDs to stop at (convergence points).
        """
        if context.is_node_processed(node.id):
            return

        if node.id in convergence_nodes:
            # Don't emit convergence nodes inside branches
            return

        # Emit this node
        generator.emit_node(node, context)

        # Follow flow output to next nodes
        if node.node_type not in ("if", "for_loop"):
            flow_out_port = node.get_output_port("exec_out")
            if flow_out_port:
                next_nodes = generator.get_flow_connected_nodes(node.id, "exec_out")
                for next_node in next_nodes:
                    self._emit_branch_flow(next_node, context, generator, convergence_nodes)


class ForLoopNodeEmitter(NodeEmitter):
    """Emitter for ForLoop nodes - iteration over collections."""

    @property
    def node_type(self) -> str:
        return "for_loop"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate code for a ForLoopNode.

        Creates a for loop structure with the configured iteration variable.
        Variables defined inside the loop body are tracked as conditional
        since they depend on the loop executing at least once.
        """
        from visualpython2.nodes.definitions import ForLoopNode
        from visualpython2.compiler.code_generator import CodeContext

        if not isinstance(node, ForLoopNode):
            context.errors.append(f"Expected ForLoopNode but got {type(node).__name__}")
            return

        # Get iterable
        iterable_var = self.get_input_value(
            node, "iterable", context, generator.graph, default="[]"
        )

        # Get iteration variable name
        iter_var = node.iteration_variable or "item"
        index_var = context.generate_variable_name("index")

        # Set output variables for loop body access (tracked at current scope)
        # These are available inside the loop body
        context.set_output_variable(node.id, "item", iter_var, track_scope=False)
        context.set_output_variable(node.id, "index", index_var, track_scope=False)

        context.add_line(f"# For loop: {node.name}")
        context.add_line(f"for {index_var}, {iter_var} in enumerate({iterable_var}):")

        # Loop body - enter scope for variable tracking
        context.indentation.indent()
        context.enter_scope(CodeContext.LOOP_BODY, branch_name="loop_body")

        loop_body_nodes = generator.get_flow_connected_nodes(node.id, "loop_body")
        if loop_body_nodes:
            for body_node in loop_body_nodes:
                generator.emit_node(body_node, context)
        else:
            context.add_line("pass")

        # Exit loop body scope
        context.exit_scope()
        context.indentation.dedent()
        context.add_blank_line()

        # Handle completed flow (nodes after the loop)
        context.mark_node_processed(node.id)


class WhileLoopNodeEmitter(NodeEmitter):
    """
    Emitter for WhileLoop nodes - condition-based iteration.

    The WhileLoopNode enables visual condition-based iteration similar to Python's
    while loop. The loop continues executing the body as long as the condition
    evaluates to True.
    """

    @property
    def node_type(self) -> str:
        return "while_loop"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate code for a WhileLoopNode.

        Creates a while loop structure that iterates as long as the condition
        is True. Variables defined inside the loop body are tracked as conditional
        since they depend on the loop executing at least once.
        """
        from visualpython2.nodes.definitions import WhileLoopNode
        from visualpython2.compiler.code_generator import CodeContext

        if not isinstance(node, WhileLoopNode):
            context.errors.append(f"Expected WhileLoopNode but got {type(node).__name__}")
            return

        # Get condition value or code
        condition_var = self.get_input_value(node, "condition", context, generator.graph)

        # Determine the condition expression
        if node.condition_code:
            # Use the condition code directly
            condition_expr = node.condition_code.strip()
        elif condition_var:
            condition_expr = condition_var
        else:
            condition_expr = "False"

        # Generate iteration counter variable
        iteration_var = context.generate_variable_name("while_iteration")
        context.set_output_variable(node.id, "iteration_count", iteration_var, track_scope=False)

        context.add_line(f"# While loop: {node.name}")
        context.add_line(f"{iteration_var} = 0")

        # Add max iterations check if configured
        if node.max_iterations > 0:
            max_iter_var = context.generate_variable_name("max_iterations")
            context.add_line(f"{max_iter_var} = {node.max_iterations}")
            context.add_line(f"while ({condition_expr}) and ({iteration_var} < {max_iter_var}):")
        else:
            context.add_line(f"while {condition_expr}:")

        # Loop body - enter scope for variable tracking
        context.indentation.indent()
        context.enter_scope(CodeContext.LOOP_BODY, branch_name="while_body")

        loop_body_nodes = generator.get_flow_connected_nodes(node.id, "loop_body")
        if loop_body_nodes:
            for body_node in loop_body_nodes:
                generator.emit_node(body_node, context)
        else:
            context.add_line("pass")

        # Increment iteration counter at end of loop body
        context.add_line(f"{iteration_var} += 1")

        # Exit loop body scope
        context.exit_scope()
        context.indentation.dedent()
        context.add_blank_line()

        # Handle completed flow (nodes after the loop)
        context.mark_node_processed(node.id)


class TryCatchNodeEmitter(NodeEmitter):
    """
    Emitter for TryCatch nodes - exception handling with try/except paths.

    The TryCatchNode enables visual exception handling similar to Python's try/except
    statement. Generated code wraps the try_body in a try block and routes to
    except_path if an exception is caught.
    """

    @property
    def node_type(self) -> str:
        return "try_catch"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate code for a TryCatchNode.

        Creates a try/except structure and recursively generates code
        for each branch.
        """
        from visualpython2.nodes.definitions import TryCatchNode
        from visualpython2.compiler.code_generator import CodeContext

        if not isinstance(node, TryCatchNode):
            context.errors.append(f"Expected TryCatchNode but got {type(node).__name__}")
            return

        # Generate variable names for exception outputs
        exception_var = node.exception_variable or "e"
        exception_type_var = context.generate_variable_name("exception_type")

        # Store output variables for downstream nodes
        context.set_output_variable(node.id, "caught_exception", exception_var)
        context.set_output_variable(node.id, "exception_type_name", exception_type_var)

        context.add_line(f"# Try/Catch node: {node.name}")

        # Initialize exception tracking variables
        context.add_line(f"{exception_var} = None")
        context.add_line(f"{exception_type_var} = None")

        # Start the try block
        context.add_line("try:")

        # Try body - enter scope for variable tracking
        context.indentation.indent()
        context.enter_scope(CodeContext.IF_BRANCH, branch_name="try_body")

        try_body_nodes = generator.get_flow_connected_nodes(node.id, "try_body")
        if try_body_nodes:
            for body_node in try_body_nodes:
                self._emit_branch_flow(body_node, context, generator)
        else:
            context.add_line("pass")

        # Exit try body scope
        context.exit_scope()
        context.indentation.dedent()

        # Generate the except clause
        if node.catch_all:
            context.add_line(f"except Exception as {exception_var}:")
        else:
            # Get the exception types to catch
            exc_types = node.get_exception_type_list()
            if len(exc_types) == 1:
                context.add_line(f"except {exc_types[0]} as {exception_var}:")
            else:
                exc_tuple = ", ".join(exc_types)
                context.add_line(f"except ({exc_tuple}) as {exception_var}:")

        # Except body - enter scope for variable tracking
        context.indentation.indent()
        context.enter_scope(CodeContext.IF_BRANCH, branch_name="except_path")

        # Set the exception type name
        context.add_line(f"{exception_type_var} = type({exception_var}).__name__")

        except_path_nodes = generator.get_flow_connected_nodes(node.id, "except_path")
        if except_path_nodes:
            for except_node in except_path_nodes:
                self._emit_branch_flow(except_node, context, generator)
        else:
            context.add_line("pass")

        # Exit except body scope
        context.exit_scope()
        context.indentation.dedent()

        # Check if there's a finally block
        finally_path_nodes = generator.get_flow_connected_nodes(node.id, "finally_path")
        if finally_path_nodes:
            context.add_line("finally:")
            context.indentation.indent()
            context.enter_scope(CodeContext.IF_BRANCH, branch_name="finally_path")

            for finally_node in finally_path_nodes:
                self._emit_branch_flow(finally_node, context, generator)

            context.exit_scope()
            context.indentation.dedent()

        context.add_blank_line()
        context.mark_node_processed(node.id)

    def _emit_branch_flow(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Emit code for a branch (try body, except path, or finally path).

        Args:
            node: The starting node of the branch.
            context: The generation context.
            generator: The code generator.
        """
        if context.is_node_processed(node.id):
            return

        # Emit this node
        generator.emit_node(node, context)

        # Follow flow output to next nodes
        if node.node_type not in ("if", "for_loop", "try_catch"):
            flow_out_port = node.get_output_port("exec_out")
            if flow_out_port:
                next_nodes = generator.get_flow_connected_nodes(node.id, "exec_out")
                for next_node in next_nodes:
                    self._emit_branch_flow(next_node, context, generator)


class MergeNodeEmitter(NodeEmitter):
    """
    Emitter for Merge nodes - converge multiple execution paths.

    The MergeNode enables path convergence after branching operations like if/else
    statements. In generated code, it aggregates data from whichever input path(s)
    were executed and continues execution through a single output path.
    """

    @property
    def node_type(self) -> str:
        return "merge"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate code for a MergeNode.

        The generated code determines which input path was taken and consolidates
        the data from that path.
        """
        from visualpython2.nodes.definitions import MergeNode

        if not isinstance(node, MergeNode):
            context.errors.append(f"Expected MergeNode but got {type(node).__name__}")
            return

        # Generate output variables for the merge result
        merged_data_var = context.generate_variable_name("merged_data")
        triggered_path_var = context.generate_variable_name("triggered_path")

        context.set_output_variable(node.id, "merged_data", merged_data_var)
        context.set_output_variable(node.id, "triggered_path", triggered_path_var)

        context.add_line(f"# Merge node: {node.name}")

        # Initialize output variables
        context.add_line(f"{merged_data_var} = None")
        context.add_line(f"{triggered_path_var} = 0")

        # Check each input path for connected data
        data_inputs_found: list = []

        for i in range(1, node.num_inputs + 1):
            data_port_name = f"data_in_{i}"
            data_var = self.get_input_value(
                node, data_port_name, context, generator.graph
            )
            if data_var:
                data_inputs_found.append((i, data_var))

        if data_inputs_found:
            # Generate code to determine which path's data to use
            if len(data_inputs_found) == 1:
                # Simple case: only one data input connected
                idx, data_var = data_inputs_found[0]
                context.add_line(f"{merged_data_var} = {data_var}")
                context.add_line(f"{triggered_path_var} = {idx}")
            else:
                # Multiple data inputs connected
                first = True
                for idx, data_var in data_inputs_found:
                    var_info = context.get_variable_scope_info(
                        *self._parse_var_reference(data_var, context)
                    )
                    is_conditional = var_info.is_conditional if var_info else False

                    if is_conditional:
                        # Variable is conditionally defined, need to check existence
                        if first:
                            context.add_line(f"if '{data_var}' in dir():")
                            first = False
                        else:
                            context.add_line(f"elif '{data_var}' in dir():")
                        context.indentation.indent()
                        context.add_line(f"{merged_data_var} = {data_var}")
                        context.add_line(f"{triggered_path_var} = {idx}")
                        context.indentation.dedent()
                    else:
                        # Variable is unconditionally defined
                        if first:
                            context.add_line(f"{merged_data_var} = {data_var}")
                            context.add_line(f"{triggered_path_var} = {idx}")
                            first = False
                        else:
                            context.add_line("else:")
                            context.indentation.indent()
                            context.add_line(f"{merged_data_var} = {data_var}")
                            context.add_line(f"{triggered_path_var} = {idx}")
                            context.indentation.dedent()

        context.add_blank_line()
        context.mark_node_processed(node.id)

    def _parse_var_reference(
        self, var_name: str, context: GenerationContext
    ) -> tuple:
        """
        Parse a variable reference to find its source node and port.

        Args:
            var_name: The variable name to look up.
            context: The generation context with variable mappings.

        Returns:
            Tuple of (node_id, port_name) or (None, None) if not found.
        """
        # Reverse lookup in generated_variables
        for key, value in context.generated_variables.items():
            if value == var_name:
                parts = key.split(".", 1)
                if len(parts) == 2:
                    return parts[0], parts[1]
        return None, None
