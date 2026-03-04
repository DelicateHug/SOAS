"""
Base emitter abstract class for node-specific code generation.

All node emitters must inherit from NodeEmitter and implement
the emit() method to generate Python code for their node type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from visualpython2.compiler.code_generator import CodeGenerator, GenerationContext
    from visualpython2.graph.graph_model import Graph


class NodeEmitter(ABC):
    """
    Abstract base class for node-specific code emitters.

    Each node type has its own emitter that knows how to generate
    the appropriate Python code for that node's behavior.
    """

    @property
    @abstractmethod
    def node_type(self) -> str:
        """Return the node type this emitter handles."""
        pass

    @abstractmethod
    def emit(
        self,
        node: object,
        context: GenerationContext,
        generator: CodeGenerator,
    ) -> None:
        """
        Generate code for the given node.

        Args:
            node: The node to generate code for.
            context: The current generation context.
            generator: The parent code generator.
        """
        pass

    def get_input_value(
        self,
        node: object,
        port_name: str,
        context: GenerationContext,
        graph: Graph,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get the variable name or value for an input port.

        Args:
            node: The node containing the input port.
            port_name: The name of the input port.
            context: The current generation context.
            graph: The graph being processed.
            default: Default value if not connected.

        Returns:
            The variable name or literal value, or None if not available.
        """
        port = node.get_input_port(port_name)
        if port is None:
            return default

        if port.is_connected() and port.connection:
            # Get the variable from the source node's output
            source_node_id = port.connection.source_node_id
            source_port_name = port.connection.source_port_name
            var_name = context.get_output_variable(source_node_id, source_port_name)
            if var_name:
                return var_name

        # Use inline value if available (set by user in the editor)
        if hasattr(port, "inline_value") and port.inline_value is not None:
            return repr(port.inline_value)

        # Use default value if available
        if port.default_value is not None:
            return repr(port.default_value)

        return default
