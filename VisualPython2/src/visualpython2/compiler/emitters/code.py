"""
Code node emitter for inline Python code execution.

This emitter handles CodeNode instances that contain user-written Python code
and embeds them into the generated script with proper namespace setup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from visualpython2.compiler.emitters.base import NodeEmitter
from visualpython2.nodes.port_types import PortType

if TYPE_CHECKING:
    from visualpython2.compiler.code_generator import CodeGenerator, GenerationContext


class CodeNodeEmitter(NodeEmitter):
    """
    Emitter for Code nodes - inline Python code execution.

    This emitter extracts Python code from CodeNode instances and inserts it
    into the generated script. The user's code has access to:
    - 'inputs': A dictionary containing values from connected input ports
    - 'outputs': A dictionary where the code should set output values
    - 'globals': A dictionary (_global_vars) for persistent state across nodes

    The emitter handles:
    - Proper indentation within control flow structures (if/for)
    - Variable tracking for connecting outputs to downstream nodes
    - Empty code node handling
    - Multi-line code preservation
    - Dynamic multi-port code blocks with custom input/output ports
    """

    @property
    def node_type(self) -> str:
        return "code"

    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate code for a CodeNode.

        The CodeNode's code is embedded directly into the generated script,
        wrapped with proper namespace setup for inputs, outputs, and globals.
        The code maintains its original formatting and indentation relative
        to the current context.

        Supports dynamic multi-port code blocks: iterates all non-FLOW input
        ports to build the inputs dict, and all non-FLOW output ports to
        extract values from the outputs dict.

        Args:
            node: The CodeNode to generate code for.
            context: The current generation context with indentation state.
            generator: The parent code generator for graph access.
        """
        from visualpython2.nodes.definitions import CodeNode

        if not isinstance(node, CodeNode):
            context.errors.append(f"Expected CodeNode but got {type(node).__name__}")
            return

        code = node.code
        if not code or not code.strip():
            context.add_line("pass  # Empty code node")
            context.mark_node_processed(node.id)
            return

        # Add comment header for the code block
        context.add_line(f"# Code node: {node.name}")

        # Build inputs dict from all connected non-FLOW input ports
        input_parts: list[str] = []
        for port in node.input_ports:
            if port.port_type == PortType.FLOW:
                continue
            var = self.get_input_value(node, port.name, context, generator.graph)
            if var:
                input_parts.append(f"'{port.name}': {var}")

        if input_parts:
            context.add_line(f"inputs = {{{', '.join(input_parts)}}}")
        else:
            context.add_line("inputs = {}")

        # Create outputs dict for user code to populate
        context.add_line("outputs = {}")

        # Provide access to globals (the global variable store)
        # This allows user code to use: globals.get('key'), globals['key'] = value
        context.add_line("globals = _global_vars")

        # Emit the user's Python code
        # Each line is added with proper indentation for the current context
        code_lines = code.strip().split("\n")
        for line in code_lines:
            context.add_line(line)

        # Extract results from outputs dict for all non-FLOW output ports
        for port in node.output_ports:
            if port.port_type == PortType.FLOW:
                continue
            var = context.generate_variable_name(port.name)
            context.set_output_variable(node.id, port.name, var)
            context.add_line(f"{var} = outputs.get('{port.name}')")

        context.add_blank_line()
        context.mark_node_processed(node.id)
