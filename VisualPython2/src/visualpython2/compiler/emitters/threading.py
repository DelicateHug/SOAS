"""
Threading emitters for Thread and ThreadJoin nodes.

These emitters handle parallel execution paths by generating Python
threading code for concurrent execution and synchronization.
"""

from __future__ import annotations

from typing import List, Set, TYPE_CHECKING

from visualpython2.compiler.emitters.base import NodeEmitter

if TYPE_CHECKING:
    from visualpython2.compiler.code_generator import CodeGenerator, GenerationContext


class ThreadNodeEmitter(NodeEmitter):
    """
    Emitter for Thread nodes - spawn parallel execution paths.

    The ThreadNode enables concurrent processing by generating Python threading code
    that executes connected downstream paths in separate threads. Each thread output
    port becomes a separate thread function that runs in parallel.

    Generated code pattern:
    1. Define a thread function for each connected thread output
    2. Create threading.Thread instances for each function
    3. Start all threads
    4. If wait_for_all is True, join all threads before continuing

    Thread-safe data sharing is handled through the global _global_vars dictionary.
    """

    @property
    def node_type(self) -> str:
        return "thread"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate Python threading code for parallel execution.

        Creates thread functions for each connected thread output, starts them,
        and optionally waits for completion based on the node's configuration.
        """
        from visualpython2.nodes.definitions import ThreadNode
        from visualpython2.compiler.code_generator import CodeContext

        if not isinstance(node, ThreadNode):
            context.errors.append(f"Expected ThreadNode but got {type(node).__name__}")
            return

        # Add threading import
        context.imports.add("import threading")

        # Get input data to pass to threads
        data_var = self.get_input_value(node, "data_in", context, generator.graph)

        # Generate variables for tracking threads
        threads_list_var = context.generate_variable_name("threads")
        results_var = context.generate_variable_name("thread_results")
        lock_var = context.generate_variable_name("thread_lock")

        context.set_output_variable(node.id, "thread_results", results_var)
        context.set_output_variable(node.id, "data_out", data_var if data_var else "None")

        context.add_line(f"# Thread node: {node.name}")
        context.add_line(f"{threads_list_var} = []")
        context.add_line(f"{results_var} = {{}}")
        context.add_line(f"{lock_var} = threading.Lock()")
        context.add_blank_line()

        # Store thread variables in context for ThreadJoinNode to use
        context.thread_variables[node.id] = threads_list_var

        # Get connected thread outputs and generate functions for each
        connected_indices = node.get_connected_thread_indices()

        for idx in connected_indices:
            port_name = f"thread_out_{idx}"
            func_name = context.generate_variable_name(f"thread_func_{idx}")

            # Generate thread function
            context.add_line(f"def {func_name}():")
            context.indentation.indent()

            # Provide access to shared data in thread
            if data_var:
                context.add_line(f"_thread_data = {data_var}")
            else:
                context.add_line("_thread_data = None")

            # Enter a new scope for thread body (similar to loop body)
            context.enter_scope(CodeContext.FUNCTION, branch_name=f"thread_{idx}")

            # Get nodes connected to this thread output and emit them
            thread_nodes = generator.get_flow_connected_nodes(node.id, port_name)
            if thread_nodes:
                for thread_node in thread_nodes:
                    # Recursively emit the thread body
                    self._emit_thread_body(thread_node, context, generator, idx, results_var, lock_var)
            else:
                context.add_line("pass  # Empty thread body")

            # Exit thread scope
            context.exit_scope()
            context.indentation.dedent()
            context.add_blank_line()

            # Create and add thread to list
            context.add_line(f"_t_{idx} = threading.Thread(target={func_name}, name='thread_{idx}')")
            context.add_line(f"{threads_list_var}.append(_t_{idx})")

        # Mark thread output nodes as processed (they're handled inside thread functions)
        for idx in connected_indices:
            port_name = f"thread_out_{idx}"
            thread_nodes = generator.get_flow_connected_nodes(node.id, port_name)
            for thread_node in thread_nodes:
                self._mark_thread_nodes_processed(thread_node, context, generator)

        context.add_blank_line()

        # Start all threads
        context.add_line(f"# Start all threads")
        context.add_line(f"for _t in {threads_list_var}:")
        context.indentation.indent()
        context.add_line("_t.start()")
        context.indentation.dedent()
        context.add_blank_line()

        # Wait for all threads if configured
        if node.wait_for_all:
            context.add_line(f"# Wait for all threads to complete")
            context.add_line(f"for _t in {threads_list_var}:")
            context.indentation.indent()
            context.add_line("_t.join()")
            context.indentation.dedent()
            context.add_blank_line()

        context.mark_node_processed(node.id)

    def _emit_thread_body(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
        thread_idx: int,
        results_var: str,
        lock_var: str,
    ) -> None:
        """
        Emit code for nodes within a thread body.

        Args:
            node: The node to emit code for.
            context: The generation context.
            generator: The code generator.
            thread_idx: The index of the current thread.
            results_var: Variable name for thread results dictionary.
            lock_var: Variable name for the thread lock.
        """
        if context.is_node_processed(node.id):
            return

        # Check if this node is a ThreadJoinNode - stop here
        if node.node_type == "thread_join":
            return

        # Emit this node
        generator.emit_node(node, context)

        # Follow flow output to next nodes
        if node.node_type not in ("if", "for_loop"):
            next_nodes = generator.get_flow_connected_nodes(node.id, "exec_out")
            for next_node in next_nodes:
                self._emit_thread_body(next_node, context, generator, thread_idx, results_var, lock_var)

    def _mark_thread_nodes_processed(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Mark all nodes in a thread body as processed.

        This prevents the main traversal from re-emitting nodes that
        have already been emitted inside thread functions.
        """
        if context.is_node_processed(node.id):
            return

        # Stop at thread join nodes
        if node.node_type == "thread_join":
            return

        context.mark_node_processed(node.id)

        # Follow flow output to next nodes
        if node.node_type not in ("if", "for_loop"):
            next_nodes = generator.get_flow_connected_nodes(node.id, "exec_out")
            for next_node in next_nodes:
                self._mark_thread_nodes_processed(next_node, context, generator)


class ThreadJoinNodeEmitter(NodeEmitter):
    """
    Emitter for ThreadJoin nodes - synchronization point for parallel threads.

    The ThreadJoinNode waits for specified threads to complete before allowing
    execution to continue. This provides synchronization points in parallel workflows.
    """

    @property
    def node_type(self) -> str:
        return "thread_join"

    def _find_source_thread_nodes(
        self,
        node: object,
        generator: CodeGenerator,
    ) -> List[str]:
        """
        Find the ThreadNode IDs that feed into this ThreadJoinNode.

        Traces back through the graph from thread_in_N ports to find
        the source ThreadNode(s).
        """
        from visualpython2.nodes.definitions import ThreadJoinNode

        if not isinstance(node, ThreadJoinNode):
            return []

        thread_node_ids: List[str] = []
        visited: Set[str] = set()

        def trace_back(current_node_id: str) -> None:
            """Recursively trace back to find ThreadNodes."""
            if current_node_id in visited:
                return
            visited.add(current_node_id)

            current_node = generator.graph.get_node(current_node_id)
            if current_node is None:
                return

            # Check if this is a ThreadNode
            if current_node.node_type == "thread":
                if current_node_id not in thread_node_ids:
                    thread_node_ids.append(current_node_id)
                return

            # Trace back through flow inputs
            for port in current_node.input_ports:
                if port.is_connected() and port.connection:
                    source_node_id = port.connection.source_node_id
                    trace_back(source_node_id)

        # Start tracing from thread_in_N ports
        for i in range(1, node.num_inputs + 1):
            port = node.get_input_port(f"thread_in_{i}")
            if port and port.is_connected() and port.connection:
                source_node_id = port.connection.source_node_id
                trace_back(source_node_id)

        return thread_node_ids

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate synchronization code for thread joining.

        Generates explicit thread.join() calls to wait for thread completion,
        with optional timeout support based on the node's configuration.
        """
        from visualpython2.nodes.definitions import ThreadJoinNode

        if not isinstance(node, ThreadJoinNode):
            context.errors.append(f"Expected ThreadJoinNode but got {type(node).__name__}")
            return

        # Add threading import (may already be added by ThreadNodeEmitter)
        context.imports.add("import threading")

        # Generate output variables
        all_completed_var = context.generate_variable_name("all_completed")
        completed_count_var = context.generate_variable_name("completed_count")
        thread_data_var = context.generate_variable_name("thread_data")

        context.set_output_variable(node.id, "all_completed", all_completed_var)
        context.set_output_variable(node.id, "completed_count", completed_count_var)
        context.set_output_variable(node.id, "thread_data", thread_data_var)

        context.add_line(f"# Thread join node: {node.name}")

        # Find source ThreadNode(s) and their thread list variables
        source_thread_node_ids = self._find_source_thread_nodes(node, generator)
        threads_to_join: List[str] = []

        for thread_node_id in source_thread_node_ids:
            threads_list_var = context.thread_variables.get(thread_node_id)
            if threads_list_var:
                threads_to_join.append(threads_list_var)

        # Generate thread.join() calls for synchronization
        if threads_to_join:
            context.add_line(f"# Wait for threads to complete")

            # Handle timeout configuration
            timeout_seconds = node.timeout_ms / 1000.0 if node.timeout_ms > 0 else None

            if node.wait_for_all:
                # Wait for all threads from all source ThreadNodes
                for threads_list_var in threads_to_join:
                    context.add_line(f"for _thread in {threads_list_var}:")
                    context.indentation.indent()
                    if timeout_seconds is not None:
                        context.add_line(f"_thread.join(timeout={timeout_seconds})")
                    else:
                        context.add_line("_thread.join()")
                    context.indentation.dedent()
            else:
                # Wait for any thread to complete (join with short poll intervals)
                context.add_line(f"_all_threads = []")
                for threads_list_var in threads_to_join:
                    context.add_line(f"_all_threads.extend({threads_list_var})")

                if timeout_seconds is not None:
                    context.add_line(f"_join_timeout = {timeout_seconds}")
                    context.add_line(f"_poll_interval = min(0.1, _join_timeout / 10)")
                    context.add_line(f"_elapsed = 0.0")
                    context.add_line(f"while _elapsed < _join_timeout:")
                    context.indentation.indent()
                    context.add_line(f"for _thread in _all_threads:")
                    context.indentation.indent()
                    context.add_line(f"if not _thread.is_alive():")
                    context.indentation.indent()
                    context.add_line(f"break")
                    context.indentation.dedent()
                    context.indentation.dedent()
                    context.add_line(f"else:")
                    context.indentation.indent()
                    context.add_line(f"import time")
                    context.add_line(f"time.sleep(_poll_interval)")
                    context.add_line(f"_elapsed += _poll_interval")
                    context.add_line(f"continue")
                    context.indentation.dedent()
                    context.add_line(f"break")
                    context.indentation.dedent()
                else:
                    # No timeout - just join all threads
                    context.add_line(f"for _thread in _all_threads:")
                    context.indentation.indent()
                    context.add_line("_thread.join()")
                    context.indentation.dedent()

            context.add_blank_line()

        # Collect data from connected thread inputs
        data_inputs: List[tuple] = []
        for i in range(1, node.num_inputs + 1):
            data_port_name = f"data_in_{i}"
            data_var = self.get_input_value(node, data_port_name, context, generator.graph)
            if data_var:
                data_inputs.append((i, data_var))

        # Initialize thread data dictionary
        context.add_line(f"{thread_data_var} = {{}}")

        # Collect data from inputs
        for idx, data_var in data_inputs:
            context.add_line(f"{thread_data_var}[{idx}] = {data_var}")

        # Calculate completion status based on threads still alive
        if threads_to_join:
            context.add_line(f"# Calculate completion status")
            context.add_line(f"_alive_count = 0")
            for threads_list_var in threads_to_join:
                context.add_line(f"for _t in {threads_list_var}:")
                context.indentation.indent()
                context.add_line(f"if _t.is_alive():")
                context.indentation.indent()
                context.add_line(f"_alive_count += 1")
                context.indentation.dedent()
                context.indentation.dedent()
            context.add_line(f"_total_threads = sum(len(_tl) for _tl in [{', '.join(threads_to_join)}])")
            context.add_line(f"{completed_count_var} = _total_threads - _alive_count")
            context.add_line(f"{all_completed_var} = _alive_count == 0")
        else:
            # No threads found, use data inputs to determine completion
            context.add_line(f"{completed_count_var} = len({thread_data_var})")
            expected_count = len(data_inputs) if data_inputs else node.num_inputs
            context.add_line(f"{all_completed_var} = {completed_count_var} >= {expected_count}")

        context.add_blank_line()
        context.mark_node_processed(node.id)
