"""
Python code generator for converting visual node graphs to executable Python scripts.

This module provides the core CodeGenerator class that traverses a graph of nodes
and generates equivalent Python source code. It handles control flow structures,
variable management, and proper code indentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from visualpython2.compiler.ast_validator import validate_generated_code
from visualpython2.compiler.variable_scope import (
    VariableScopeManager,
    ScopeType,
    VariableInfo,
)

if TYPE_CHECKING:
    from visualpython2.graph.graph_model import Graph
    from visualpython2.nodes.port_types import Connection

# Import the base emitter class
from visualpython2.compiler.emitters.base import NodeEmitter


class GenerationError(Exception):
    """Exception raised when code generation fails."""

    def __init__(self, message: str, node_id: Optional[str] = None) -> None:
        """
        Initialize a generation error.

        Args:
            message: Error description.
            node_id: Optional ID of the node that caused the error.
        """
        self.node_id = node_id
        super().__init__(message)


class CodeContext(Enum):
    """Represents the current code generation context."""

    GLOBAL = auto()
    """Top-level script code."""

    FUNCTION = auto()
    """Inside a function definition."""

    IF_BRANCH = auto()
    """Inside an if/else branch."""

    LOOP_BODY = auto()
    """Inside a loop body."""


@dataclass
class IndentationManager:
    """Manages code indentation levels."""

    indent_string: str = "    "
    """The string used for one level of indentation (default: 4 spaces)."""

    _current_level: int = 0
    """Current indentation level."""

    @property
    def current_level(self) -> int:
        """Get the current indentation level."""
        return self._current_level

    def indent(self) -> None:
        """Increase indentation by one level."""
        self._current_level += 1

    def dedent(self) -> None:
        """Decrease indentation by one level."""
        if self._current_level > 0:
            self._current_level -= 1

    def get_indent(self) -> str:
        """Get the current indentation string."""
        return self.indent_string * self._current_level

    def indent_code(self, code: str) -> str:
        """
        Apply current indentation to a code block.

        Args:
            code: The code to indent.

        Returns:
            The indented code.
        """
        if not code:
            return code

        indent = self.get_indent()
        lines = code.split("\n")
        indented_lines = [f"{indent}{line}" if line.strip() else line for line in lines]
        return "\n".join(indented_lines)

    def reset(self) -> None:
        """Reset indentation to zero."""
        self._current_level = 0


@dataclass
class NodeSourceSpan:
    """Records the line range in generated code for a single node."""

    node_id: str
    node_type: str
    node_label: str
    start_line: int
    end_line: int


@dataclass
class GenerationContext:
    """
    Holds state information during code generation.

    This context is passed through the generation process to track:
    - Variable declarations and assignments
    - Current scope and indentation
    - Generated code sections
    - Node processing state
    - Variable scope management for safe variable accessibility
    """

    indentation: IndentationManager = field(default_factory=IndentationManager)
    """Manages code indentation."""

    context_stack: List[CodeContext] = field(default_factory=list)
    """Stack of code contexts for nested structures."""

    generated_variables: Dict[str, str] = field(default_factory=dict)
    """Maps node output port keys to generated variable names."""

    processed_nodes: Set[str] = field(default_factory=set)
    """Set of node IDs that have been processed."""

    code_lines: List[str] = field(default_factory=list)
    """Accumulated generated code lines."""

    imports: Set[str] = field(default_factory=set)
    """Required import statements."""

    errors: List[str] = field(default_factory=list)
    """Any errors encountered during generation."""

    warnings: List[str] = field(default_factory=list)
    """Warnings about potential issues (e.g., conditional variable access)."""

    _variable_counter: int = 0
    """Counter for generating unique variable names."""

    _scope_manager: Optional[VariableScopeManager] = field(default=None)
    """Manages variable scopes for safe code generation."""

    thread_variables: Dict[str, str] = field(default_factory=dict)
    """Maps thread node IDs to their threads list variable names for join synchronization."""

    subgraph_inline_stack: Set[str] = field(default_factory=set)
    """Tracks subgraph file paths currently being inlined, to detect circular references."""

    node_source_map: Dict[str, "NodeSourceSpan"] = field(default_factory=dict)
    """Maps node IDs to their line ranges in generated code for traceability."""

    def __post_init__(self) -> None:
        """Initialize the scope manager after dataclass init."""
        if self._scope_manager is None:
            self._scope_manager = VariableScopeManager()

    @property
    def scope_manager(self) -> VariableScopeManager:
        """Get the variable scope manager."""
        if self._scope_manager is None:
            self._scope_manager = VariableScopeManager()
        return self._scope_manager

    def push_context(self, context: CodeContext) -> None:
        """Push a new code context onto the stack."""
        self.context_stack.append(context)

    def pop_context(self) -> Optional[CodeContext]:
        """Pop the current code context from the stack."""
        if self.context_stack:
            return self.context_stack.pop()
        return None

    @property
    def current_context(self) -> CodeContext:
        """Get the current code context."""
        if self.context_stack:
            return self.context_stack[-1]
        return CodeContext.GLOBAL

    def enter_scope(
        self,
        context: CodeContext,
        branch_name: Optional[str] = None,
    ) -> None:
        """
        Enter a new scope for variable tracking.

        This method combines pushing the code context and entering a scope
        for variable management.

        Args:
            context: The code context being entered.
            branch_name: Optional name for conditional branches (e.g., 'true_branch').
        """
        self.push_context(context)

        # Map CodeContext to ScopeType
        scope_type_map = {
            CodeContext.GLOBAL: ScopeType.GLOBAL,
            CodeContext.FUNCTION: ScopeType.FUNCTION,
            CodeContext.IF_BRANCH: ScopeType.IF_BRANCH,
            CodeContext.LOOP_BODY: ScopeType.LOOP_BODY,
        }
        scope_type = scope_type_map.get(context, ScopeType.GLOBAL)
        self.scope_manager.enter_scope(scope_type, branch_name)

    def exit_scope(self) -> Optional[CodeContext]:
        """
        Exit the current scope.

        This method combines popping the code context and exiting the scope
        for variable management.

        Returns:
            The code context that was exited.
        """
        self.scope_manager.exit_scope()
        return self.pop_context()

    def generate_variable_name(self, prefix: str = "var") -> str:
        """
        Generate a unique variable name.

        Args:
            prefix: Prefix for the variable name.

        Returns:
            A unique variable name.
        """
        self._variable_counter += 1
        return f"{prefix}_{self._variable_counter}"

    def add_line(self, line: str) -> None:
        """
        Add an indented line of code.

        Args:
            line: The line of code to add.
        """
        if line.strip():
            self.code_lines.append(self.indentation.indent_code(line))
        else:
            self.code_lines.append("")

    def add_lines(self, lines: List[str]) -> None:
        """
        Add multiple indented lines of code.

        Args:
            lines: The lines of code to add.
        """
        for line in lines:
            self.add_line(line)

    def add_blank_line(self) -> None:
        """Add a blank line to the generated code."""
        self.code_lines.append("")

    def get_output_variable(self, node_id: str, port_name: str) -> Optional[str]:
        """
        Get the variable name for a node's output port.

        Args:
            node_id: The node ID.
            port_name: The output port name.

        Returns:
            The variable name if it exists, None otherwise.
        """
        key = f"{node_id}.{port_name}"
        return self.generated_variables.get(key)

    def set_output_variable(
        self,
        node_id: str,
        port_name: str,
        var_name: str,
        track_scope: bool = True,
    ) -> None:
        """
        Set the variable name for a node's output port.

        Args:
            node_id: The node ID.
            port_name: The output port name.
            var_name: The variable name to associate.
            track_scope: Whether to track this variable in the scope manager.
        """
        key = f"{node_id}.{port_name}"
        self.generated_variables[key] = var_name

        # Also track in the scope manager for scope-aware access checking
        # Only if there's an active scope (during actual code generation)
        if track_scope and self.scope_manager.current_scope is not None:
            self.scope_manager.define_variable(node_id, port_name, var_name)

    def get_output_variable_with_scope_check(
        self,
        node_id: str,
        port_name: str,
        accessing_node_id: str,
    ) -> Optional[str]:
        """
        Get a variable name with scope safety checking.

        This method retrieves a variable and checks if it's safely accessible
        from the current scope. If the variable is only conditionally defined,
        a warning is added.

        Args:
            node_id: The source node ID.
            port_name: The source port name.
            accessing_node_id: The ID of the node trying to access the variable.

        Returns:
            The variable name if it exists, None otherwise.
        """
        var_name = self.get_output_variable(node_id, port_name)

        if var_name:
            # Check for scope access issues
            access_warnings = self.scope_manager.check_variable_access(
                node_id, port_name, accessing_node_id
            )
            self.warnings.extend(access_warnings)

        return var_name

    def get_variable_scope_info(
        self,
        node_id: str,
        port_name: str,
    ) -> Optional[VariableInfo]:
        """
        Get detailed scope information about a variable.

        Args:
            node_id: The source node ID.
            port_name: The source port name.

        Returns:
            VariableInfo if the variable exists, None otherwise.
        """
        return self.scope_manager.get_variable(node_id, port_name)

    def is_variable_conditional(self, node_id: str, port_name: str) -> bool:
        """
        Check if a variable is only conditionally defined.

        Args:
            node_id: The source node ID.
            port_name: The source port name.

        Returns:
            True if the variable is only defined in some code paths.
        """
        var_info = self.scope_manager.get_variable(node_id, port_name)
        return var_info.is_conditional if var_info else False

    def is_node_processed(self, node_id: str) -> bool:
        """Check if a node has been processed."""
        return node_id in self.processed_nodes

    def mark_node_processed(self, node_id: str) -> None:
        """Mark a node as processed."""
        self.processed_nodes.add(node_id)

    def record_node_span(
        self,
        node_id: str,
        node_type: str,
        node_label: str,
        start_line: int,
        end_line: int,
    ) -> None:
        """Record the source mapping for a node's generated code."""
        self.node_source_map[node_id] = NodeSourceSpan(
            node_id=node_id,
            node_type=node_type,
            node_label=node_label,
            start_line=start_line,
            end_line=end_line,
        )

    def get_conditional_variable_initializations(self) -> List[str]:
        """
        Get initialization statements for conditional variables.

        Returns:
            List of initialization statements to prevent undefined variable errors.
        """
        return self.scope_manager.generate_initialization_code()

    def get_generated_code(self) -> str:
        """Get the complete generated code as a string."""
        parts: List[str] = []

        # Add imports if any
        if self.imports:
            for imp in sorted(self.imports):
                parts.append(imp)
            parts.append("")

        # Add main code
        parts.extend(self.code_lines)

        return "\n".join(parts)

    def get_scope_warnings(self) -> List[str]:
        """
        Get all warnings related to variable scopes.

        Returns:
            Combined list of context warnings and scope manager warnings.
        """
        return self.warnings + self.scope_manager.warnings

    def reset(self) -> None:
        """Reset the context for a fresh generation."""
        self.indentation.reset()
        self.context_stack.clear()
        self.generated_variables.clear()
        self.processed_nodes.clear()
        self.code_lines.clear()
        self.imports.clear()
        self.errors.clear()
        self.warnings.clear()
        self._variable_counter = 0
        self.scope_manager.reset()
        self.thread_variables.clear()
        self.node_source_map.clear()


@dataclass
class GenerationResult:
    """
    Result of code generation.

    Attributes:
        success: Whether generation completed without errors.
        code: The generated Python code.
        errors: List of error messages if any.
        warnings: List of warning messages if any.
        ast_valid: Whether the generated code passed AST validation.
    """

    success: bool
    code: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    ast_valid: bool = False
    node_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    """Maps node IDs to metadata and line ranges for source tracing."""


class CodeGenerator:
    """
    Main code generator class that orchestrates the graph traversal
    and code generation process.

    The CodeGenerator:
    1. Validates the graph structure
    2. Traverses nodes in execution order
    3. Delegates code generation to node-specific emitters
    4. Combines generated code into a complete Python script

    Example:
        >>> graph = Graph()
        >>> # ... build graph ...
        >>> generator = CodeGenerator(graph)
        >>> result = generator.generate()
        >>> if result.success:
        ...     print(result.code)
    """

    # Node types that manage their own indentation/control flow.
    # These should NOT be wrapped in debug try/except.
    _CONTROL_FLOW_NODES = frozenset({
        "if", "for_loop", "while_loop", "try_catch",
        "thread", "thread_join", "subgraph",
    })

    def __init__(self, graph: Graph, debug_mode: bool = False) -> None:
        """
        Initialize the code generator.

        Args:
            graph: The graph to generate code from.
            debug_mode: When True, inject per-node I/O tracing code.
        """
        self._graph = graph
        self._debug_mode = debug_mode
        self._debug_counter = 0
        self._debug_pre_vars: Dict[str, Set[str]] = {}
        self._emitters: Dict[str, NodeEmitter] = {}
        self._context = GenerationContext()

        # Register default emitters
        self._register_default_emitters()

    def _register_default_emitters(self) -> None:
        """Register the built-in node emitters."""
        # Import emitters from modular files
        from visualpython2.compiler.emitters.control_flow import (
            StartNodeEmitter,
            EndNodeEmitter,
            IfNodeEmitter,
            ForLoopNodeEmitter,
            WhileLoopNodeEmitter,
            TryCatchNodeEmitter,
            MergeNodeEmitter,
        )
        from visualpython2.compiler.emitters.variables import (
            GetVariableNodeEmitter,
            SetVariableNodeEmitter,
            GetIncidentVarNodeEmitter,
            SetIncidentVarNodeEmitter,
            GetIncidentDataNodeEmitter,
            GetSOASVarNodeEmitter,
            SetSOASVarNodeEmitter,
            GetUserSecretNodeEmitter,
        )
        from visualpython2.compiler.emitters.code import CodeNodeEmitter
        from visualpython2.compiler.emitters.threading import (
            ThreadNodeEmitter,
            ThreadJoinNodeEmitter,
        )
        from visualpython2.compiler.emitters.data import (
            DatabaseQueryNodeEmitter,
            RegexMatchNodeEmitter,
            RegexReplaceNodeEmitter,
            SubgraphNodeEmitter,
            SubgraphInputNodeEmitter,
            SubgraphOutputNodeEmitter,
            RunAutomationNodeEmitter,
        )
        from visualpython2.compiler.emitters.io import (
            PrintNodeEmitter,
            InputNodeEmitter,
            FileReadNodeEmitter,
            FileWriteNodeEmitter,
            HttpRequestNodeEmitter,
        )
        from visualpython2.compiler.emitters.utility import (
            AddNodeEmitter,
            SubtractNodeEmitter,
            MultiplyNodeEmitter,
            DivideNodeEmitter,
            ModuloNodeEmitter,
            PowerNodeEmitter,
            StringConcatNodeEmitter,
            StringSplitNodeEmitter,
            StringReplaceNodeEmitter,
            StringFormatNodeEmitter,
            ListAppendNodeEmitter,
            ListFilterNodeEmitter,
            ListMapNodeEmitter,
            ListReduceNodeEmitter,
            JsonParseNodeEmitter,
            JsonStringifyNodeEmitter,
            DataAggregationNodeEmitter,
            BreakpointNodeEmitter,
        )

        emitters: List[NodeEmitter] = [
            StartNodeEmitter(),
            EndNodeEmitter(),
            CodeNodeEmitter(),
            IfNodeEmitter(),
            ForLoopNodeEmitter(),
            WhileLoopNodeEmitter(),
            GetVariableNodeEmitter(),
            SetVariableNodeEmitter(),
            GetIncidentVarNodeEmitter(),
            SetIncidentVarNodeEmitter(),
            GetIncidentDataNodeEmitter(),
            GetSOASVarNodeEmitter(),
            SetSOASVarNodeEmitter(),
            GetUserSecretNodeEmitter(),
            MergeNodeEmitter(),
            ThreadNodeEmitter(),
            ThreadJoinNodeEmitter(),
            TryCatchNodeEmitter(),
            DatabaseQueryNodeEmitter(),
            RegexMatchNodeEmitter(),
            RegexReplaceNodeEmitter(),
            SubgraphNodeEmitter(),
            SubgraphInputNodeEmitter(),
            SubgraphOutputNodeEmitter(),
            RunAutomationNodeEmitter(),
            # IO emitters
            PrintNodeEmitter(),
            InputNodeEmitter(),
            FileReadNodeEmitter(),
            FileWriteNodeEmitter(),
            HttpRequestNodeEmitter(),
            # Utility emitters
            AddNodeEmitter(),
            SubtractNodeEmitter(),
            MultiplyNodeEmitter(),
            DivideNodeEmitter(),
            ModuloNodeEmitter(),
            PowerNodeEmitter(),
            StringConcatNodeEmitter(),
            StringSplitNodeEmitter(),
            StringReplaceNodeEmitter(),
            StringFormatNodeEmitter(),
            ListAppendNodeEmitter(),
            ListFilterNodeEmitter(),
            ListMapNodeEmitter(),
            ListReduceNodeEmitter(),
            JsonParseNodeEmitter(),
            JsonStringifyNodeEmitter(),
            DataAggregationNodeEmitter(),
            BreakpointNodeEmitter(),
        ]

        for emitter in emitters:
            self._emitters[emitter.node_type] = emitter

    @property
    def graph(self) -> Graph:
        """Get the graph being processed."""
        return self._graph

    def register_emitter(self, emitter: NodeEmitter) -> None:
        """
        Register a custom node emitter.

        Args:
            emitter: The emitter to register.
        """
        self._emitters[emitter.node_type] = emitter

    def get_emitter(self, node_type: str) -> Optional[NodeEmitter]:
        """
        Get the emitter for a node type.

        Args:
            node_type: The node type.

        Returns:
            The emitter if registered, None otherwise.
        """
        return self._emitters.get(node_type)

    def get_flow_connected_nodes(self, node_id: str, port_name: str) -> List:
        """
        Get nodes connected to a flow output port.

        Args:
            node_id: The source node ID.
            port_name: The flow output port name.

        Returns:
            List of connected nodes in connection order.
        """
        connections = self._graph.get_connections_for_port(node_id, port_name, is_input=False)
        nodes: list = []

        for conn in connections:
            target_node = self._graph.get_node(conn.target_node_id)
            if target_node and not self._context.is_node_processed(target_node.id):
                nodes.append(target_node)

        return nodes

    def emit_node(self, node: object, context: GenerationContext) -> None:
        """
        Emit code for a single node.

        Before emitting, resolves data dependencies: if this node has data
        inputs connected to unprocessed nodes (not in the exec flow), those
        source nodes are emitted first so their output variables exist.

        Args:
            node: The node to generate code for.
            context: The generation context.
        """
        if context.is_node_processed(node.id):
            return

        # Resolve data dependencies: emit unprocessed source nodes first
        self._resolve_data_dependencies(node, context)

        emitter = self.get_emitter(node.node_type)
        if emitter is None:
            context.errors.append(f"No emitter registered for node type: {node.node_type}")
            context.add_line(f"# Unsupported node type: {node.node_type}")
            context.mark_node_processed(node.id)
            return

        # Record line position and emit tracing comment for code-to-node traceability
        start_line = len(context.code_lines)
        node_label = getattr(node, "name", None) or node.node_type
        context.add_line(f"# [node:{node.id}] {node.node_type}: {node_label}")

        # Debug instrumentation: capture node inputs before emitting
        counter = None
        if self._debug_mode:
            counter = self._debug_counter
            self._debug_counter += 1
            self._emit_debug_pre(node, context, counter)

        emitter.emit(node, context, self)

        # Debug instrumentation: capture node outputs after emitting
        if self._debug_mode and counter is not None:
            self._emit_debug_post(node, context, counter)

        # Record the source span so the node_map can reference line ranges
        end_line = len(context.code_lines)
        context.record_node_span(node.id, node.node_type, node_label, start_line, end_line)

    def _emit_debug_pre(
        self, node: object, context: GenerationContext, counter: int
    ) -> None:
        """Emit debug code before a node runs: record metadata and capture inputs."""
        from visualpython2.nodes.port_types import PortType

        node_id = node.id
        node_type = node.node_type
        node_label = getattr(node, "name", None) or node_type

        # Snapshot generated_variables keys so we can diff for outputs later
        self._debug_pre_vars[node_id] = set(context.generated_variables.keys())

        # Build input capture expressions
        input_parts: List[str] = []
        for port in node.input_ports:
            if port.port_type == PortType.FLOW:
                continue
            if port.is_connected() and port.connection:
                source_var = context.get_output_variable(
                    port.connection.source_node_id,
                    port.connection.source_port_name,
                )
                if source_var:
                    input_parts.append(f"'{port.name}': _safe_repr({source_var})")
            elif hasattr(port, "inline_value") and port.inline_value is not None:
                # Static inline value — embed as a string literal
                val_repr = repr(str(port.inline_value))
                if len(val_repr) > 200:
                    val_repr = val_repr[:200] + "...'"
                input_parts.append(f"'{port.name}': {val_repr}")

        inputs_expr = "{" + ", ".join(input_parts) + "}" if input_parts else "{}"

        # Emit the pre-node debug code
        safe_label = node_label.replace("'", "\\'")
        context.add_line(
            f"_node_debug.setdefault('{node_id}', "
            f"{{'type': '{node_type}', 'label': '{safe_label}', 'executions': []}})"
        )
        context.add_line(f"_dbg_inputs_{counter} = {inputs_expr}")
        context.add_line(f"_dbg_start_{counter} = _dbg_time.perf_counter()")

    def _emit_debug_post(
        self, node: object, context: GenerationContext, counter: int
    ) -> None:
        """Emit debug code after a node runs: capture outputs and record trace."""
        node_id = node.id

        # Diff generated_variables to find new output variables
        pre_keys = self._debug_pre_vars.get(node_id, set())
        post_keys = set(context.generated_variables.keys())
        new_keys = post_keys - pre_keys

        output_parts: List[str] = []
        for key in sorted(new_keys):
            if key.startswith(f"{node_id}."):
                port_name = key[len(node_id) + 1 :]
                var_name = context.generated_variables[key]
                output_parts.append(f"'{port_name}': _safe_repr({var_name})")

        outputs_expr = "{" + ", ".join(output_parts) + "}" if output_parts else "{}"

        # Emit the post-node debug code
        context.add_line(f"_dbg_outputs_{counter} = {outputs_expr}")
        context.add_line(
            f"if len(_node_debug['{node_id}']['executions']) < _MAX_DBG_EXECS:"
        )
        context.indentation.indent()
        context.add_line("with _dbg_lock:")
        context.indentation.indent()
        context.add_line(
            f"_node_debug['{node_id}']['executions'].append({{"
            f"'inputs': _dbg_inputs_{counter}, "
            f"'outputs': _dbg_outputs_{counter}, "
            f"'duration_ms': (_dbg_time.perf_counter() - _dbg_start_{counter}) * 1000, "
            f"'status': 'completed'"
            f"}})"
        )
        context.indentation.dedent()
        context.indentation.dedent()

    def _resolve_data_dependencies(
        self, node: object, context: GenerationContext
    ) -> None:
        """
        Recursively emit any unprocessed nodes that feed data into this node.

        This allows "data-only" nodes (not connected via exec flow) to have
        their code generated before the node that consumes their output.
        """
        from visualpython2.nodes.port_types import PortType

        for port in node.input_ports:
            # Skip flow ports — those are handled by _emit_flow_from_node
            if port.port_type == PortType.FLOW:
                continue
            if port.is_connected() and port.connection:
                source_node_id = port.connection.source_node_id
                if not context.is_node_processed(source_node_id):
                    source_node = self._graph.get_node(source_node_id)
                    if source_node:
                        # Recursive call handles chains of data-only nodes
                        self.emit_node(source_node, context)

    def _generate_preamble(self, context: GenerationContext) -> None:
        """Generate the script preamble (comments, setup code)."""
        context.add_line('"""')
        context.add_line(f"Generated Python script from: {self._graph.name}")
        context.add_line(f"Description: {self._graph.description}")
        context.add_line('"""')
        context.add_blank_line()
        context.add_line("import json as _json, os as _os")
        context.add_blank_line()
        context.add_line("# Global variable storage")
        context.add_line("_global_vars = {}")
        context.add_blank_line()
        context.add_line("# Subgraph inputs from parent automation (via SOAS_PARAMS env var)")
        context.add_line("_subgraph_inputs = _json.loads(_os.environ.get('SOAS_PARAMS', '{}'))")
        context.add_blank_line()

        if self._debug_mode:
            self._generate_debug_preamble(context)

    def _generate_debug_preamble(self, context: GenerationContext) -> None:
        """Generate debug trace infrastructure code in the preamble."""
        debug_lines = [
            "# --- Debug trace infrastructure ---",
            "import time as _dbg_time, threading as _dbg_threading",
            "_node_debug = {}",
            "_dbg_lock = _dbg_threading.Lock()",
            "_MAX_DBG_EXECS = 100",
            "",
            "def _safe_repr(v):",
            "    try:",
            "        r = repr(v)",
            "        return r[:1000] if len(r) > 1000 else r",
            "    except Exception:",
            "        return '<repr failed>'",
            "",
            "def _flush_debug():",
            "    import json as _dj, os as _do",
            "    _p = _do.environ.get('SOAS_DEBUG_FILE', '')",
            "    if _p:",
            "        try:",
            "            with open(_p, 'w') as _f:",
            "                _dj.dump(_node_debug, _f)",
            "        except Exception:",
            "            pass",
            "",
            "import atexit as _dbg_atexit",
            "_dbg_atexit.register(_flush_debug)",
            "",
            "import signal as _dbg_signal",
            "def _dbg_sig_handler(signum, frame):",
            "    _flush_debug()",
            "    raise SystemExit(1)",
            "try:",
            "    _dbg_signal.signal(_dbg_signal.SIGTERM, _dbg_sig_handler)",
            "except (OSError, ValueError):",
            "    pass  # Signal handling not available in this context",
            "# --- End debug infrastructure ---",
            "",
        ]
        for line in debug_lines:
            context.code_lines.append(line)

    def _validate_graph(self) -> List[str]:
        """
        Validate the graph before generation.

        Returns:
            List of validation errors.
        """
        errors: List[str] = []

        # Check for cycles
        if self._graph.has_cycle():
            errors.append("Graph contains cycles - cannot generate sequential code")

        # Check for start node
        start_nodes = self._graph.get_nodes_by_type("start")
        if not start_nodes:
            errors.append("Graph must have at least one Start node")

        # Validate all nodes
        graph_errors = self._graph.validate()
        errors.extend(graph_errors)

        return errors

    def generate(self) -> GenerationResult:
        """
        Generate Python code from the graph.

        Uses AST validation to verify the generated code syntax before
        returning. This catches compilation errors early in the process.
        Tracks variable scopes to detect potential undefined variable errors.

        Returns:
            GenerationResult containing the generated code and any errors.
        """
        # Reset context
        self._context.reset()
        self._debug_counter = 0
        self._debug_pre_vars.clear()

        # Initialize global scope for variable tracking
        self._context.scope_manager.enter_scope(ScopeType.GLOBAL)

        # Validate graph
        validation_errors = self._validate_graph()
        if validation_errors:
            return GenerationResult(
                success=False,
                code="",
                errors=validation_errors,
                ast_valid=False,
            )

        # Generate preamble
        self._generate_preamble(self._context)

        # Get execution order using flow-based traversal from start nodes
        start_nodes = self._graph.get_nodes_by_type("start")

        # Process each start node and follow the flow
        for start_node in start_nodes:
            self._emit_flow_from_node(start_node, self._context)

        # Debug epilogue: flush debug data at end of script
        if self._debug_mode:
            self._context.add_blank_line()
            self._context.add_line("# --- Flush debug trace ---")
            self._context.add_line("_flush_debug()")

        # Check for any generation errors
        if self._context.errors:
            return GenerationResult(
                success=False,
                code=self._context.get_generated_code(),
                errors=self._context.errors,
                ast_valid=False,
            )

        # Validate generated code using AST
        generated_code = self._context.get_generated_code()
        ast_result = validate_generated_code(generated_code)

        if not ast_result.valid:
            # Add AST validation errors to the result
            ast_errors = [f"Generated code syntax error: {e}" for e in ast_result.error_messages]
            return GenerationResult(
                success=False,
                code=generated_code,
                errors=ast_errors,
                ast_valid=False,
            )

        # Collect scope-related warnings
        scope_warnings = self._context.get_scope_warnings()

        # Build node-to-line source map for traceability.
        # Imports are prepended by get_generated_code(), so offset line numbers.
        import_line_count = len(self._context.imports) + (1 if self._context.imports else 0)
        node_map: Dict[str, Dict[str, Any]] = {}
        for nid, span in self._context.node_source_map.items():
            node_map[nid] = {
                "type": span.node_type,
                "label": span.node_label,
                "start_line": span.start_line + import_line_count,
                "end_line": span.end_line + import_line_count,
            }

        return GenerationResult(
            success=True,
            code=generated_code,
            errors=[],
            warnings=scope_warnings,
            ast_valid=True,
            node_map=node_map,
        )

    def _emit_flow_from_node(self, node: object, context: GenerationContext) -> None:
        """
        Emit code following the execution flow from a node.

        Args:
            node: The starting node.
            context: The generation context.
        """
        if context.is_node_processed(node.id):
            return

        # Emit this node
        self.emit_node(node, context)

        # Follow flow output to next nodes (unless this is a control flow node)
        # Control flow nodes (if, for, while, try_catch) handle their own flow traversal
        if node.node_type not in ("if", "for_loop", "while_loop", "try_catch"):
            # Get flow output port and follow connections
            flow_out_port = node.get_output_port("exec_out")
            if flow_out_port:
                next_nodes = self.get_flow_connected_nodes(node.id, "exec_out")
                for next_node in next_nodes:
                    self._emit_flow_from_node(next_node, context)

        # For loop nodes: handle the 'completed' flow (code that runs after the loop)
        if node.node_type == "for_loop":
            completed_nodes = self.get_flow_connected_nodes(node.id, "completed")
            for completed_node in completed_nodes:
                self._emit_flow_from_node(completed_node, context)

        # While loop nodes: handle the 'completed' flow (code that runs after the loop)
        if node.node_type == "while_loop":
            completed_nodes = self.get_flow_connected_nodes(node.id, "completed")
            for completed_node in completed_nodes:
                self._emit_flow_from_node(completed_node, context)
