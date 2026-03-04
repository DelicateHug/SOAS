"""
Node definitions for VisualPython2.

Ported from VisualPython (VP1) with all Qt dependencies removed.
Contains the BaseNode ABC, ExecutionState enum, Position dataclass,
and all 42 concrete node type implementations.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from functools import reduce as functools_reduce
from typing import Any, Callable, Dict, Iterator, List, Optional, TYPE_CHECKING
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from visualpython2.nodes.port_types import InputPort, OutputPort, PortType


# ---------------------------------------------------------------------------
# ExecutionState enum
# ---------------------------------------------------------------------------

class ExecutionState(Enum):
    """Represents the current execution state of a node."""

    IDLE = auto()
    """Node is not currently executing and hasn't been executed."""

    PENDING = auto()
    """Node is queued for execution, waiting for inputs."""

    RUNNING = auto()
    """Node is currently executing."""

    COMPLETED = auto()
    """Node has finished executing successfully."""

    ERROR = auto()
    """Node encountered an error during execution."""

    SKIPPED = auto()
    """Node was skipped (e.g., due to conditional branching)."""


# ---------------------------------------------------------------------------
# Position dataclass
# ---------------------------------------------------------------------------

@dataclass
class Position:
    """Represents a 2D position on the node canvas."""

    x: float = 0.0
    y: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert position to dictionary for serialization."""
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> Position:
        """Create a Position from a dictionary."""
        return cls(x=data.get("x", 0.0), y=data.get("y", 0.0))


# ---------------------------------------------------------------------------
# BaseNode ABC
# ---------------------------------------------------------------------------

class BaseNode(ABC):
    """
    Abstract base class for all node types in VisualPython2.

    Provides common properties: ID, position, connections, execution state,
    serialization support, and port management.

    Subclasses must implement _setup_ports(), execute(), and validate().
    """

    # Class-level attributes for node metadata
    node_type: str = "base"
    node_category: str = "General"
    node_color: str = "#808080"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
    ) -> None:
        self._id: str = node_id or str(uuid.uuid4())
        self._name: str = name or self._get_default_name()
        self._position: Position = position or Position()
        self._execution_state: ExecutionState = ExecutionState.IDLE
        self._error_message: Optional[str] = None
        self._execution_errors: List[str] = []
        self._custom_color: Optional[str] = None
        self._comment: str = ""
        self._input_ports: List[InputPort] = []
        self._output_ports: List[OutputPort] = []
        self._input_data: Dict[str, Any] = {}
        self._output_data: Dict[str, Any] = {}
        self._setup_ports()

    def _get_default_name(self) -> str:
        display_name = getattr(self, "display_name", None)
        if display_name:
            return display_name
        return self.node_type.replace("_", " ").title()

    @abstractmethod
    def _setup_ports(self) -> None:
        pass

    @abstractmethod
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def validate(self) -> List[str]:
        pass

    # -- Properties ----------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def position(self) -> Position:
        return self._position

    @position.setter
    def position(self, value: Position) -> None:
        self._position = value

    @property
    def execution_state(self) -> ExecutionState:
        return self._execution_state

    @execution_state.setter
    def execution_state(self, value: ExecutionState) -> None:
        self._execution_state = value
        if value != ExecutionState.ERROR:
            self._error_message = None
            self._execution_errors.clear()

    @property
    def error_message(self) -> Optional[str]:
        return self._error_message

    @error_message.setter
    def error_message(self, value: Optional[str]) -> None:
        self._error_message = value

    @property
    def execution_errors(self) -> List[str]:
        return self._execution_errors.copy()

    def add_execution_error(self, error: str) -> None:
        self._execution_errors.append(error)

    def clear_execution_errors(self) -> None:
        self._execution_errors.clear()

    def has_execution_errors(self) -> bool:
        return len(self._execution_errors) > 0

    @property
    def custom_color(self) -> Optional[str]:
        return self._custom_color

    @custom_color.setter
    def custom_color(self, value: Optional[str]) -> None:
        self._custom_color = value

    @property
    def display_color(self) -> str:
        return self._custom_color if self._custom_color else self.node_color

    @property
    def comment(self) -> str:
        return self._comment

    @comment.setter
    def comment(self, value: str) -> None:
        self._comment = value if value else ""

    @property
    def input_ports(self) -> List[InputPort]:
        return self._input_ports.copy()

    @property
    def output_ports(self) -> List[OutputPort]:
        return self._output_ports.copy()

    @property
    def input_data(self) -> Dict[str, Any]:
        return self._input_data.copy()

    @property
    def output_data(self) -> Dict[str, Any]:
        return self._output_data.copy()

    # -- Port management -----------------------------------------------------

    def add_input_port(self, port: InputPort) -> None:
        port.node = self
        self._input_ports.append(port)

    def add_output_port(self, port: OutputPort) -> None:
        port.node = self
        self._output_ports.append(port)

    def get_input_port(self, name: str) -> Optional[InputPort]:
        for port in self._input_ports:
            if port.name == name:
                return port
        return None

    def get_output_port(self, name: str) -> Optional[OutputPort]:
        for port in self._output_ports:
            if port.name == name:
                return port
        return None

    def remove_input_port(self, name: str) -> bool:
        for i, port in enumerate(self._input_ports):
            if port.name == name:
                self._input_ports.pop(i)
                return True
        return False

    def remove_output_port(self, name: str) -> bool:
        for i, port in enumerate(self._output_ports):
            if port.name == name:
                self._output_ports.pop(i)
                return True
        return False

    # -- Execution -----------------------------------------------------------

    def set_input(self, port_name: str, value: Any) -> None:
        self._input_data[port_name] = value

    def get_output(self, port_name: str) -> Any:
        return self._output_data.get(port_name)

    def clear_execution_data(self) -> None:
        self._input_data.clear()
        self._output_data.clear()

    def reset_state(self) -> None:
        self._execution_state = ExecutionState.IDLE
        self._error_message = None
        self.clear_execution_errors()
        self.clear_execution_data()

    def run(self) -> None:
        try:
            self._execution_state = ExecutionState.RUNNING
            self._output_data = self.execute(self._input_data)
            self._execution_state = ExecutionState.COMPLETED
        except Exception as e:
            self._execution_state = ExecutionState.ERROR
            self._error_message = str(e)
            raise

    def has_all_required_inputs(self) -> bool:
        for port in self._input_ports:
            if port.required and port.name not in self._input_data:
                if not port.is_connected():
                    return False
        return True

    def get_connected_input_ports(self) -> List[InputPort]:
        return [port for port in self._input_ports if port.is_connected()]

    def get_connected_output_ports(self) -> List[OutputPort]:
        return [port for port in self._output_ports if port.is_connected()]

    def get_code_preview(self) -> Optional[str]:
        return None

    # -- Serialization -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": self._id,
            "type": self.node_type,
            "name": self._name,
            "position": self._position.to_dict(),
            "input_ports": [port.to_dict() for port in self._input_ports],
            "output_ports": [port.to_dict() for port in self._output_ports],
            "properties": self._get_serializable_properties(),
        }
        if self._custom_color:
            data["custom_color"] = self._custom_color
        if self._comment:
            data["comment"] = self._comment
        return data

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BaseNode:
        position = Position.from_dict(data.get("position", {}))
        node = cls(
            node_id=data.get("id"),
            name=data.get("name"),
            position=position,
        )
        node._load_serializable_properties(data.get("properties", {}))
        for port_data in data.get("input_ports", []):
            port_name = port_data.get("name")
            inline_value = port_data.get("inline_value")
            if port_name and inline_value is not None:
                port = node.get_input_port(port_name)
                if port:
                    port.inline_value = inline_value
        if "custom_color" in data:
            node._custom_color = data["custom_color"]
        if "comment" in data:
            node._comment = data["comment"]
        return node

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        pass

    # -- String representations ----------------------------------------------

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"id='{self._id[:8]}...', "
            f"name='{self._name}', "
            f"type='{self.node_type}', "
            f"state={self._execution_state.name})"
        )

    def __str__(self) -> str:
        return f"{self._name} ({self.node_type})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseNode):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)


# ===========================================================================
# CONTROL FLOW NODES
# ===========================================================================


class StartNode(BaseNode):
    """Entry point of script execution."""

    node_type: str = "start"
    display_name: str = "Start"
    node_category: str = "Control Flow"
    node_color: str = "#00BCD4"

    # Mapping from input definition type strings to PortType enum values
    _TYPE_MAP: Dict[str, PortType] = {
        "STRING": PortType.STRING,
        "INTEGER": PortType.INTEGER,
        "FLOAT": PortType.FLOAT,
        "BOOLEAN": PortType.BOOLEAN,
        "LIST": PortType.LIST,
        "DICT": PortType.DICT,
        "ANY": PortType.ANY,
    }

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
    ) -> None:
        self._input_defs: List[Dict[str, Any]] = []
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_output_port(OutputPort(
            name="exec_out",
            port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        if self._input_defs:
            self._setup_dynamic_output_ports()

    def _setup_dynamic_output_ports(self) -> None:
        """Add output ports from the automation's input parameter definitions."""
        for defn in self._input_defs:
            port_type = self._TYPE_MAP.get(defn.get("type", "ANY"), PortType.ANY)
            self.add_output_port(OutputPort(
                name=defn["name"],
                port_type=port_type,
                description=defn.get("description", ""),
            ))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {"exec_out": None}
        for defn in self._input_defs:
            result[defn["name"]] = defn.get("default_value")
        return result

    def _get_serializable_properties(self) -> Dict[str, Any]:
        props: Dict[str, Any] = {}
        if self._input_defs:
            props["_input_defs"] = self._input_defs
        return props

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._input_defs = properties.get("_input_defs", [])
        if self._input_defs:
            self._setup_dynamic_output_ports()


class EndNode(BaseNode):
    """End of an execution path."""

    node_type: str = "end"
    display_name: str = "End"
    node_category: str = "Control Flow"
    node_color: str = "#E91E63"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
    ) -> None:
        self._result_value: Any = None
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in",
            port_type=PortType.FLOW,
            description="Execution flow input",
            required=False,
        ))
        self.add_input_port(InputPort(
            name="result",
            port_type=PortType.ANY,
            description="Optional result value",
            required=False,
        ))

    @property
    def result_value(self) -> Any:
        return self._result_value

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self._result_value = inputs.get("result")
        return {}

    def reset_state(self) -> None:
        super().reset_state()
        self._result_value = None


class IfNode(BaseNode):
    """Conditional branching node."""

    node_type: str = "if"
    display_name: str = "If"
    node_category: str = "Control Flow"
    node_color: str = "#9C27B0"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        condition_code: str = "",
    ) -> None:
        self._condition_code: str = condition_code
        self._last_result: Optional[bool] = None
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="condition", port_type=PortType.BOOLEAN,
            description="Boolean condition to evaluate", required=False, default_value=False,
        ))
        self.add_input_port(InputPort(
            name="value", port_type=PortType.ANY,
            description="Optional value input accessible in condition_code", required=False,
        ))
        self.add_output_port(OutputPort(
            name="true_branch", port_type=PortType.FLOW,
            description="Execution flow when condition is True",
        ))
        self.add_output_port(OutputPort(
            name="false_branch", port_type=PortType.FLOW,
            description="Execution flow when condition is False",
        ))
        self.add_output_port(OutputPort(
            name="result", port_type=PortType.BOOLEAN,
            description="The evaluated boolean result",
        ))

    @property
    def condition_code(self) -> str:
        return self._condition_code

    @condition_code.setter
    def condition_code(self, value: str) -> None:
        self._condition_code = value

    @property
    def last_result(self) -> Optional[bool]:
        return self._last_result

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self._condition_code:
            try:
                compile(self._condition_code, "<condition>", "eval")
            except SyntaxError as e:
                errors.append(f"Invalid condition code: {e}")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        result: bool
        if self._condition_code:
            namespace: Dict[str, Any] = {
                "inputs": inputs,
                "value": inputs.get("value"),
                "condition": inputs.get("condition", False),
            }
            try:
                result = eval(self._condition_code, {"__builtins__": {}}, namespace)
            except Exception as e:
                raise ValueError(f"Failed to evaluate condition code: {e}")
            if not isinstance(result, bool):
                result = bool(result)
        else:
            condition_value = inputs.get("condition")
            if condition_value is None:
                result = False
            elif isinstance(condition_value, bool):
                result = condition_value
            else:
                result = bool(condition_value)
        self._last_result = result
        return {"result": result}

    def get_active_branch(self) -> Optional[str]:
        if self._last_result is None:
            return None
        return "true_branch" if self._last_result else "false_branch"

    def reset_state(self) -> None:
        super().reset_state()
        self._last_result = None

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"condition_code": self._condition_code}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._condition_code = properties.get("condition_code", "")


class ForLoopNode(BaseNode):
    """Iterate over a collection."""

    node_type: str = "for_loop"
    display_name: str = "For Loop"
    node_category: str = "Control Flow"
    node_color: str = "#FF9800"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        iteration_variable: str = "item",
    ) -> None:
        self._iteration_variable: str = iteration_variable
        self._current_index: int = 0
        self._current_item: Any = None
        self._is_iterating: bool = False
        self._iteration_count: int = 0
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="iterable", port_type=PortType.ANY,
            description="The iterable collection to loop over", required=True,
        ))
        self.add_output_port(OutputPort(
            name="loop_body", port_type=PortType.FLOW,
            description="Execution flow for loop body",
        ))
        self.add_output_port(OutputPort(
            name="completed", port_type=PortType.FLOW,
            description="Execution flow when loop finishes",
        ))
        self.add_output_port(OutputPort(
            name="item", port_type=PortType.ANY,
            description="The current item in the iteration",
        ))
        self.add_output_port(OutputPort(
            name="index", port_type=PortType.INTEGER,
            description="The current iteration index (0-based)",
        ))

    @property
    def iteration_variable(self) -> str:
        return self._iteration_variable

    @iteration_variable.setter
    def iteration_variable(self, value: str) -> None:
        self._iteration_variable = value

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_item(self) -> Any:
        return self._current_item

    @property
    def is_iterating(self) -> bool:
        return self._is_iterating

    @property
    def iteration_count(self) -> int:
        return self._iteration_count

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._iteration_variable:
            errors.append("Iteration variable name cannot be empty")
        elif not self._iteration_variable.isidentifier():
            errors.append(f"Iteration variable '{self._iteration_variable}' is not a valid Python identifier")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        iterable = inputs.get("iterable")
        if iterable is None:
            raise ValueError("No iterable provided to for loop")
        try:
            iterator = iter(iterable)
        except TypeError:
            raise TypeError(f"For loop input must be iterable, got {type(iterable).__name__}")
        self._current_index = 0
        self._current_item = None
        self._is_iterating = False
        self._iteration_count = 0
        try:
            self._current_item = next(iterator)
            self._is_iterating = True
            return {"item": self._current_item, "index": self._current_index}
        except StopIteration:
            self._is_iterating = False
            return {"item": None, "index": 0}

    def iterate(self, iterable: Any) -> Iterator[Dict[str, Any]]:
        self._is_iterating = True
        self._iteration_count = 0
        try:
            for index, item in enumerate(iterable):
                self._current_index = index
                self._current_item = item
                self._iteration_count = index + 1
                yield {"item": item, "index": index}
        finally:
            self._is_iterating = False

    def reset_state(self) -> None:
        super().reset_state()
        self._current_index = 0
        self._current_item = None
        self._is_iterating = False
        self._iteration_count = 0

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"iteration_variable": self._iteration_variable}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._iteration_variable = properties.get("iteration_variable", "item")


class WhileLoopNode(BaseNode):
    """Iterate while condition is true."""

    node_type: str = "while_loop"
    display_name: str = "While Loop"
    node_category: str = "Control Flow"
    node_color: str = "#FF9800"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        condition_code: str = "",
        max_iterations: int = 10000,
    ) -> None:
        self._condition_code: str = condition_code
        self._max_iterations: int = max_iterations
        self._current_iteration: int = 0
        self._is_iterating: bool = False
        self._last_condition_result: Optional[bool] = None
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="condition", port_type=PortType.BOOLEAN,
            description="Boolean condition to evaluate", required=False, default_value=False,
        ))
        self.add_input_port(InputPort(
            name="value", port_type=PortType.ANY,
            description="Optional value input accessible in condition_code", required=False,
        ))
        self.add_output_port(OutputPort(
            name="loop_body", port_type=PortType.FLOW,
            description="Execution flow for loop body",
        ))
        self.add_output_port(OutputPort(
            name="completed", port_type=PortType.FLOW,
            description="Execution flow when loop finishes",
        ))
        self.add_output_port(OutputPort(
            name="iteration_count", port_type=PortType.INTEGER,
            description="The current iteration count",
        ))

    @property
    def condition_code(self) -> str:
        return self._condition_code

    @condition_code.setter
    def condition_code(self, value: str) -> None:
        self._condition_code = value

    @property
    def max_iterations(self) -> int:
        return self._max_iterations

    @max_iterations.setter
    def max_iterations(self, value: int) -> None:
        self._max_iterations = max(0, value)

    @property
    def current_iteration(self) -> int:
        return self._current_iteration

    @property
    def is_iterating(self) -> bool:
        return self._is_iterating

    @property
    def last_condition_result(self) -> Optional[bool]:
        return self._last_condition_result

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self._condition_code:
            try:
                compile(self._condition_code, "<condition>", "eval")
            except SyntaxError as e:
                errors.append(f"Invalid condition code: {e}")
        if self._max_iterations < 0:
            errors.append("max_iterations must be non-negative")
        return errors

    def _evaluate_condition(self, inputs: Dict[str, Any]) -> bool:
        if self._condition_code:
            namespace: Dict[str, Any] = {
                "inputs": inputs,
                "value": inputs.get("value"),
                "condition": inputs.get("condition", False),
                "iteration": self._current_iteration,
            }
            try:
                result = eval(self._condition_code, {"__builtins__": {}}, namespace)
            except Exception as e:
                raise ValueError(f"Failed to evaluate condition code: {e}")
            if not isinstance(result, bool):
                result = bool(result)
            return result
        else:
            condition_value = inputs.get("condition")
            if condition_value is None:
                return False
            elif isinstance(condition_value, bool):
                return condition_value
            else:
                return bool(condition_value)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self._current_iteration = 0
        self._is_iterating = False
        self._last_condition_result = None
        try:
            condition_result = self._evaluate_condition(inputs)
            self._last_condition_result = condition_result
        except Exception:
            self._is_iterating = False
            raise
        if condition_result:
            self._is_iterating = True
        return {"iteration_count": self._current_iteration}

    def iterate(self, inputs: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        self._is_iterating = True
        self._current_iteration = 0
        try:
            while True:
                if self._max_iterations > 0 and self._current_iteration >= self._max_iterations:
                    raise RuntimeError(
                        f"While loop exceeded maximum iterations ({self._max_iterations})."
                    )
                condition_result = self._evaluate_condition(inputs)
                self._last_condition_result = condition_result
                if not condition_result:
                    break
                yield {"iteration_count": self._current_iteration}
                self._current_iteration += 1
        finally:
            self._is_iterating = False

    def reset_state(self) -> None:
        super().reset_state()
        self._current_iteration = 0
        self._is_iterating = False
        self._last_condition_result = None

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"condition_code": self._condition_code, "max_iterations": self._max_iterations}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._condition_code = properties.get("condition_code", "")
        self._max_iterations = properties.get("max_iterations", 10000)


class MergeNode(BaseNode):
    """Converge multiple execution paths."""

    node_type: str = "merge"
    display_name: str = "Merge"
    node_category: str = "Control Flow"
    node_color: str = "#607D8B"

    MIN_INPUTS: int = 2
    MAX_INPUTS: int = 8

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        merge_strategy: str = "first_in",
        num_inputs: int = 2,
    ) -> None:
        self._merge_strategy: str = merge_strategy
        self._num_inputs: int = max(self.MIN_INPUTS, min(self.MAX_INPUTS, num_inputs))
        self._triggered_inputs: set = set()
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        for i in range(1, self._num_inputs + 1):
            self.add_input_port(InputPort(
                name=f"exec_in_{i}", port_type=PortType.FLOW,
                description=f"Execution flow input {i}", required=False,
            ))
        for i in range(1, self._num_inputs + 1):
            self.add_input_port(InputPort(
                name=f"data_in_{i}", port_type=PortType.ANY,
                description=f"Optional data input from path {i}", required=False,
            ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output after merge",
        ))
        self.add_output_port(OutputPort(
            name="merged_data", port_type=PortType.ANY,
            description="Data from the triggered input path",
        ))
        self.add_output_port(OutputPort(
            name="triggered_path", port_type=PortType.INTEGER,
            description="Index of the path that triggered (1-based)",
        ))

    @property
    def merge_strategy(self) -> str:
        return self._merge_strategy

    @merge_strategy.setter
    def merge_strategy(self, value: str) -> None:
        if value not in ("first_in", "wait_all"):
            raise ValueError(f"Invalid merge strategy: {value}")
        self._merge_strategy = value

    @property
    def num_inputs(self) -> int:
        return self._num_inputs

    @property
    def triggered_inputs(self) -> set:
        return self._triggered_inputs.copy()

    def add_input_path(self) -> bool:
        if self._num_inputs >= self.MAX_INPUTS:
            return False
        self._num_inputs += 1
        idx = self._num_inputs
        self.add_input_port(InputPort(
            name=f"exec_in_{idx}", port_type=PortType.FLOW,
            description=f"Execution flow input {idx}", required=False,
        ))
        self.add_input_port(InputPort(
            name=f"data_in_{idx}", port_type=PortType.ANY,
            description=f"Optional data input from path {idx}", required=False,
        ))
        return True

    def remove_input_path(self) -> bool:
        if self._num_inputs <= self.MIN_INPUTS:
            return False
        idx = self._num_inputs
        self.remove_input_port(f"exec_in_{idx}")
        self.remove_input_port(f"data_in_{idx}")
        self._num_inputs -= 1
        return True

    def trigger_input(self, input_name: str) -> None:
        if input_name.startswith("exec_in_"):
            self._triggered_inputs.add(input_name)

    def is_ready_to_execute(self) -> bool:
        if self._merge_strategy == "first_in":
            return len(self._triggered_inputs) > 0
        else:
            for i in range(1, self._num_inputs + 1):
                port = self.get_input_port(f"exec_in_{i}")
                if port and port.is_connected():
                    if f"exec_in_{i}" not in self._triggered_inputs:
                        return False
            return len(self._triggered_inputs) > 0

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self._merge_strategy not in ("first_in", "wait_all"):
            errors.append(f"Invalid merge strategy: {self._merge_strategy}")
        if self._num_inputs < self.MIN_INPUTS or self._num_inputs > self.MAX_INPUTS:
            errors.append(f"Number of inputs must be between {self.MIN_INPUTS} and {self.MAX_INPUTS}")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        merged_data: Any = None
        triggered_path: int = 0
        for i in range(1, self._num_inputs + 1):
            exec_port_name = f"exec_in_{i}"
            data_port_name = f"data_in_{i}"
            if exec_port_name in self._triggered_inputs:
                triggered_path = i
                merged_data = inputs.get(data_port_name)
                if self._merge_strategy == "first_in":
                    break
        return {"merged_data": merged_data, "triggered_path": triggered_path}

    def reset_state(self) -> None:
        super().reset_state()
        self._triggered_inputs.clear()

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"merge_strategy": self._merge_strategy, "num_inputs": self._num_inputs}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._merge_strategy = properties.get("merge_strategy", "first_in")
        new_num = properties.get("num_inputs", 2)
        while self._num_inputs < new_num and self._num_inputs < self.MAX_INPUTS:
            self.add_input_path()
        while self._num_inputs > new_num and self._num_inputs > self.MIN_INPUTS:
            self.remove_input_path()


class ThreadNode(BaseNode):
    """Spawn parallel threads."""

    node_type: str = "thread"
    display_name: str = "Thread"
    node_category: str = "Control Flow"
    node_color: str = "#9C27B0"

    MIN_THREADS: int = 2
    MAX_THREADS: int = 8

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        num_threads: int = 2,
        wait_for_all: bool = True,
    ) -> None:
        self._num_threads: int = max(self.MIN_THREADS, min(self.MAX_THREADS, num_threads))
        self._wait_for_all: bool = wait_for_all
        self._thread_results: Dict[int, Any] = {}
        self._completed_threads: set = set()
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=True,
        ))
        self.add_input_port(InputPort(
            name="data_in", port_type=PortType.ANY,
            description="Optional data to pass to all threads", required=False,
        ))
        for i in range(1, self._num_threads + 1):
            self.add_output_port(OutputPort(
                name=f"thread_out_{i}", port_type=PortType.FLOW,
                description=f"Thread {i} execution output",
            ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output after threads complete",
        ))
        self.add_output_port(OutputPort(
            name="thread_results", port_type=PortType.DICT,
            description="Results from each thread",
        ))
        self.add_output_port(OutputPort(
            name="data_out", port_type=PortType.ANY,
            description="Pass-through of input data",
        ))

    @property
    def num_threads(self) -> int:
        return self._num_threads

    @property
    def wait_for_all(self) -> bool:
        return self._wait_for_all

    @wait_for_all.setter
    def wait_for_all(self, value: bool) -> None:
        self._wait_for_all = value

    @property
    def thread_results(self) -> Dict[int, Any]:
        return self._thread_results.copy()

    @property
    def completed_threads(self) -> set:
        return self._completed_threads.copy()

    def add_thread(self) -> bool:
        if self._num_threads >= self.MAX_THREADS:
            return False
        self._num_threads += 1
        self.add_output_port(OutputPort(
            name=f"thread_out_{self._num_threads}", port_type=PortType.FLOW,
            description=f"Thread {self._num_threads} execution output",
        ))
        return True

    def remove_thread(self) -> bool:
        if self._num_threads <= self.MIN_THREADS:
            return False
        self.remove_output_port(f"thread_out_{self._num_threads}")
        self._num_threads -= 1
        return True

    def get_connected_thread_count(self) -> int:
        count = 0
        for i in range(1, self._num_threads + 1):
            port = self.get_output_port(f"thread_out_{i}")
            if port and port.is_connected():
                count += 1
        return count

    def mark_thread_completed(self, thread_index: int, result: Any = None) -> None:
        if 1 <= thread_index <= self._num_threads:
            self._completed_threads.add(thread_index)
            self._thread_results[thread_index] = result

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self._num_threads < self.MIN_THREADS or self._num_threads > self.MAX_THREADS:
            errors.append(f"Number of threads must be between {self.MIN_THREADS} and {self.MAX_THREADS}")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        data_in = inputs.get("data_in")
        return {"data_out": data_in, "thread_results": self._thread_results.copy()}

    def reset_state(self) -> None:
        super().reset_state()
        self._thread_results.clear()
        self._completed_threads.clear()

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"num_threads": self._num_threads, "wait_for_all": self._wait_for_all}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._wait_for_all = properties.get("wait_for_all", True)
        new_num = properties.get("num_threads", 2)
        while self._num_threads < new_num and self._num_threads < self.MAX_THREADS:
            self.add_thread()
        while self._num_threads > new_num and self._num_threads > self.MIN_THREADS:
            self.remove_thread()


class ThreadJoinNode(BaseNode):
    """Wait for thread completion."""

    node_type: str = "thread_join"
    display_name: str = "Thread Join"
    node_category: str = "Control Flow"
    node_color: str = "#673AB7"

    MIN_INPUTS: int = 2
    MAX_INPUTS: int = 8

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        num_inputs: int = 2,
        wait_for_all: bool = True,
        timeout_ms: int = 0,
    ) -> None:
        self._num_inputs: int = max(self.MIN_INPUTS, min(self.MAX_INPUTS, num_inputs))
        self._wait_for_all: bool = wait_for_all
        self._timeout_ms: int = max(0, timeout_ms)
        self._completed_threads: set = set()
        self._thread_data: Dict[int, Any] = {}
        self._completion_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=True,
        ))
        for i in range(1, self._num_inputs + 1):
            self.add_input_port(InputPort(
                name=f"thread_in_{i}", port_type=PortType.FLOW,
                description=f"Thread {i} completion input", required=False,
            ))
        for i in range(1, self._num_inputs + 1):
            self.add_input_port(InputPort(
                name=f"data_in_{i}", port_type=PortType.ANY,
                description=f"Optional data input from thread {i}", required=False,
            ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output after synchronization",
        ))
        self.add_output_port(OutputPort(
            name="all_completed", port_type=PortType.BOOLEAN,
            description="True if all connected threads completed",
        ))
        self.add_output_port(OutputPort(
            name="completed_count", port_type=PortType.INTEGER,
            description="Number of threads that completed",
        ))
        self.add_output_port(OutputPort(
            name="thread_data", port_type=PortType.DICT,
            description="Data from each thread",
        ))

    @property
    def num_inputs(self) -> int:
        return self._num_inputs

    @property
    def wait_for_all(self) -> bool:
        return self._wait_for_all

    @wait_for_all.setter
    def wait_for_all(self, value: bool) -> None:
        self._wait_for_all = value

    @property
    def timeout_ms(self) -> int:
        return self._timeout_ms

    @timeout_ms.setter
    def timeout_ms(self, value: int) -> None:
        self._timeout_ms = max(0, value)

    @property
    def completed_threads(self) -> set:
        with self._lock:
            return self._completed_threads.copy()

    @property
    def thread_data(self) -> Dict[int, Any]:
        with self._lock:
            return self._thread_data.copy()

    def add_input(self) -> bool:
        if self._num_inputs >= self.MAX_INPUTS:
            return False
        self._num_inputs += 1
        idx = self._num_inputs
        self.add_input_port(InputPort(
            name=f"thread_in_{idx}", port_type=PortType.FLOW,
            description=f"Thread {idx} completion input", required=False,
        ))
        self.add_input_port(InputPort(
            name=f"data_in_{idx}", port_type=PortType.ANY,
            description=f"Optional data input from thread {idx}", required=False,
        ))
        return True

    def remove_input(self) -> bool:
        if self._num_inputs <= self.MIN_INPUTS:
            return False
        idx = self._num_inputs
        self.remove_input_port(f"thread_in_{idx}")
        self.remove_input_port(f"data_in_{idx}")
        self._num_inputs -= 1
        return True

    def get_connected_input_indices(self) -> List[int]:
        indices = []
        for i in range(1, self._num_inputs + 1):
            port = self.get_input_port(f"thread_in_{i}")
            if port and port.is_connected():
                indices.append(i)
        return indices

    def mark_thread_completed(self, thread_index: int, data: Any = None) -> None:
        with self._lock:
            if 1 <= thread_index <= self._num_inputs:
                self._completed_threads.add(thread_index)
                self._thread_data[thread_index] = data
                connected = self.get_connected_input_indices()
                if not connected or (
                    self._wait_for_all and all(idx in self._completed_threads for idx in connected)
                ) or (
                    not self._wait_for_all and any(idx in self._completed_threads for idx in connected)
                ):
                    self._completion_event.set()

    def wait_for_completion(self) -> bool:
        if self._timeout_ms > 0:
            return self._completion_event.wait(timeout=self._timeout_ms / 1000.0)
        else:
            self._completion_event.wait()
            return True

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self._num_inputs < self.MIN_INPUTS or self._num_inputs > self.MAX_INPUTS:
            errors.append(f"Number of inputs must be between {self.MIN_INPUTS} and {self.MAX_INPUTS}")
        if self._timeout_ms < 0:
            errors.append("Timeout cannot be negative")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            for i in range(1, self._num_inputs + 1):
                data_key = f"data_in_{i}"
                if data_key in inputs:
                    self._thread_data[i] = inputs[data_key]
        connected_indices = self.get_connected_input_indices()
        all_completed = all(idx in self._completed_threads for idx in connected_indices)
        return {
            "all_completed": all_completed,
            "completed_count": len(self._completed_threads),
            "thread_data": self._thread_data.copy(),
        }

    def reset_state(self) -> None:
        super().reset_state()
        with self._lock:
            self._completed_threads.clear()
            self._thread_data.clear()
            self._completion_event.clear()

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {
            "num_inputs": self._num_inputs,
            "wait_for_all": self._wait_for_all,
            "timeout_ms": self._timeout_ms,
        }

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._wait_for_all = properties.get("wait_for_all", True)
        self._timeout_ms = properties.get("timeout_ms", 0)
        new_num = properties.get("num_inputs", 2)
        while self._num_inputs < new_num and self._num_inputs < self.MAX_INPUTS:
            self.add_input()
        while self._num_inputs > new_num and self._num_inputs > self.MIN_INPUTS:
            self.remove_input()


class TryCatchNode(BaseNode):
    """Exception handling node."""

    node_type: str = "try_catch"
    display_name: str = "Try Catch"
    node_category: str = "Control Flow"
    node_color: str = "#E91E63"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        exception_types: str = "Exception",
        catch_all: bool = False,
        exception_variable: str = "e",
    ) -> None:
        self._exception_types: str = exception_types
        self._catch_all: bool = catch_all
        self._exception_variable: str = exception_variable
        self._last_exception: Optional[BaseException] = None
        self._last_exception_type: Optional[str] = None
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_output_port(OutputPort(
            name="try_body", port_type=PortType.FLOW,
            description="Execution flow for try block",
        ))
        self.add_output_port(OutputPort(
            name="except_path", port_type=PortType.FLOW,
            description="Execution flow when exception is caught",
        ))
        self.add_output_port(OutputPort(
            name="finally_path", port_type=PortType.FLOW,
            description="Execution flow that always runs",
        ))
        self.add_output_port(OutputPort(
            name="caught_exception", port_type=PortType.ANY,
            description="The caught exception object",
        ))
        self.add_output_port(OutputPort(
            name="exception_type_name", port_type=PortType.STRING,
            description="The name of the caught exception type",
        ))

    @property
    def exception_types(self) -> str:
        return self._exception_types

    @exception_types.setter
    def exception_types(self, value: str) -> None:
        self._exception_types = value

    @property
    def catch_all(self) -> bool:
        return self._catch_all

    @catch_all.setter
    def catch_all(self, value: bool) -> None:
        self._catch_all = value

    @property
    def exception_variable(self) -> str:
        return self._exception_variable

    @exception_variable.setter
    def exception_variable(self, value: str) -> None:
        self._exception_variable = value if value else "e"

    @property
    def last_exception(self) -> Optional[BaseException]:
        return self._last_exception

    @property
    def last_exception_type(self) -> Optional[str]:
        return self._last_exception_type

    def get_exception_type_list(self) -> List[str]:
        if not self._exception_types:
            return ["Exception"]
        types = [t.strip() for t in self._exception_types.split(",") if t.strip()]
        return types if types else ["Exception"]

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._catch_all and self._exception_types:
            for exc_type in self.get_exception_type_list():
                if not exc_type.isidentifier():
                    errors.append(f"Invalid exception type name: {exc_type}")
        if self._exception_variable and not self._exception_variable.isidentifier():
            errors.append(f"Invalid exception variable name: {self._exception_variable}")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self._last_exception = None
        self._last_exception_type = None
        return {"caught_exception": None, "exception_type_name": None}

    def set_caught_exception(self, exception: BaseException) -> None:
        self._last_exception = exception
        self._last_exception_type = type(exception).__name__

    def get_active_branch(self) -> Optional[str]:
        if self._last_exception is not None:
            return "except_path"
        return "try_body"

    def reset_state(self) -> None:
        super().reset_state()
        self._last_exception = None
        self._last_exception_type = None

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {
            "exception_types": self._exception_types,
            "catch_all": self._catch_all,
            "exception_variable": self._exception_variable,
        }

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._exception_types = properties.get("exception_types", "Exception")
        self._catch_all = properties.get("catch_all", False)
        self._exception_variable = properties.get("exception_variable", "e")


# ===========================================================================
# CUSTOM CODE NODE
# ===========================================================================


class CodeNode(BaseNode):
    """Execute custom Python code."""

    node_type: str = "code"
    display_name: str = "Code"
    node_category: str = "Custom Code"
    node_color: str = "#4CAF50"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        code: str = "",
    ) -> None:
        self._code: str = code
        self._is_code_valid: bool = True
        self._validation_errors: List[str] = []
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        self.add_input_port(InputPort(
            name="value", port_type=PortType.ANY,
            description="Input value accessible as inputs['value']", required=False,
        ))
        self.add_output_port(OutputPort(
            name="result", port_type=PortType.ANY,
            description="Output value set as outputs['result']",
        ))

    @property
    def code(self) -> str:
        return self._code

    @code.setter
    def code(self, value: str) -> None:
        self._code = value

    @property
    def is_code_valid(self) -> bool:
        return self._is_code_valid

    @property
    def validation_errors(self) -> List[str]:
        return self._validation_errors.copy()

    def set_validation_state(self, is_valid: bool, errors: List[str]) -> None:
        self._is_code_valid = is_valid
        self._validation_errors = errors.copy() if errors else []

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._code or not self._code.strip():
            errors.append("Code cannot be empty")
            return errors
        try:
            compile(self._code, "<code_node>", "exec")
        except SyntaxError as e:
            errors.append(f"Syntax error: {e}")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self._code or not self._code.strip():
            raise ValueError("Cannot execute empty code")
        try:
            compile(self._code, "<code_node>", "exec")
        except SyntaxError as e:
            raise SyntaxError(str(e))
        outputs: Dict[str, Any] = {}
        namespace: Dict[str, Any] = {
            "inputs": inputs,
            "outputs": outputs,
        }
        exec(self._code, namespace)
        return outputs

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"code": self._code}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._code = properties.get("code", "")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeNode":
        """Override to add custom ports from graph data.

        _setup_ports() creates the default ports (exec_in, value, exec_out,
        result). This override adds any additional ports that were defined
        via the code library's custom port builder, so the compiler can
        correctly wire all inputs/outputs.
        """
        node = super().from_dict(data)

        # Add custom input ports not already created by _setup_ports()
        for port_data in data.get("input_ports", []):
            port_name = port_data.get("name")
            if port_name and not node.get_input_port(port_name):
                node.add_input_port(InputPort(
                    name=port_name,
                    port_type=PortType[port_data.get("type", "ANY")],
                    description=port_data.get("description", ""),
                    required=port_data.get("required", False),
                ))

        # Add custom output ports not already created by _setup_ports()
        for port_data in data.get("output_ports", []):
            port_name = port_data.get("name")
            if port_name and not node.get_output_port(port_name):
                node.add_output_port(OutputPort(
                    name=port_name,
                    port_type=PortType[port_data.get("type", "ANY")],
                    description=port_data.get("description", ""),
                ))

        return node


# ===========================================================================
# VARIABLE NODES
# ===========================================================================


class GetVariableNode(BaseNode):
    """Get a global variable value."""

    node_type: str = "get_variable"
    display_name: str = "Get Global Variable"
    node_category: str = "Variables"
    node_color: str = "#2196F3"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        variable_name: str = "",
        default_value: Any = None,
    ) -> None:
        self._variable_name: str = variable_name
        self._default_value: Any = default_value
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        self.add_input_port(InputPort(
            name="variable_name", port_type=PortType.STRING,
            description="Name of the variable to retrieve", required=False,
        ))
        self.add_output_port(OutputPort(
            name="value", port_type=PortType.ANY,
            description="The variable value",
        ))
        self.add_output_port(OutputPort(
            name="exists", port_type=PortType.BOOLEAN,
            description="Whether the variable exists",
        ))

    @property
    def variable_name(self) -> str:
        return self._variable_name

    @variable_name.setter
    def variable_name(self, value: str) -> None:
        self._variable_name = value

    @property
    def default_value(self) -> Any:
        return self._default_value

    @default_value.setter
    def default_value(self, value: Any) -> None:
        self._default_value = value

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._variable_name:
            var_name_port = self.get_input_port("variable_name")
            if var_name_port and not var_name_port.is_connected():
                errors.append("Variable name must be configured or provided via input port")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        var_name = inputs.get("variable_name", self._variable_name)
        if not var_name:
            raise ValueError("No variable name specified")
        # In VP2 the execution engine provides the variable store via context.
        # The node returns a placeholder; the engine resolves the actual value.
        return {"value": self._default_value, "exists": False}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"variable_name": self._variable_name, "default_value": self._default_value}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._variable_name = properties.get("variable_name", "")
        self._default_value = properties.get("default_value", None)


class SetVariableNode(BaseNode):
    """Set a global variable value."""

    node_type: str = "set_variable"
    display_name: str = "Set Global Variable"
    node_category: str = "Variables"
    node_color: str = "#2196F3"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        variable_name: str = "",
        validate_type: bool = True,
        expected_type: Optional[PortType] = None,
    ) -> None:
        self._variable_name: str = variable_name
        self._validate_type: bool = validate_type
        self._expected_type: Optional[PortType] = expected_type
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        self.add_input_port(InputPort(
            name="variable_name", port_type=PortType.STRING,
            description="Name of the variable to set", required=False,
        ))
        self.add_input_port(InputPort(
            name="value", port_type=PortType.ANY,
            description="The value to store", required=False,
        ))
        self.add_output_port(OutputPort(
            name="success", port_type=PortType.BOOLEAN,
            description="Whether the variable was successfully set",
        ))

    @property
    def variable_name(self) -> str:
        return self._variable_name

    @variable_name.setter
    def variable_name(self, value: str) -> None:
        self._variable_name = value

    @property
    def validate_type(self) -> bool:
        return self._validate_type

    @validate_type.setter
    def validate_type(self, value: bool) -> None:
        self._validate_type = value

    @property
    def expected_type(self) -> Optional[PortType]:
        return self._expected_type

    @expected_type.setter
    def expected_type(self, value: Optional[PortType]) -> None:
        self._expected_type = value

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._variable_name:
            var_name_port = self.get_input_port("variable_name")
            if var_name_port and not var_name_port.is_connected():
                errors.append("Variable name must be configured or provided via input port")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        var_name = inputs.get("variable_name", self._variable_name)
        if not var_name:
            raise ValueError("No variable name specified")
        # In VP2 the execution engine handles actual storage.
        return {"success": True}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "variable_name": self._variable_name,
            "validate_type": self._validate_type,
        }
        if self._expected_type is not None:
            result["expected_type"] = self._expected_type.name
        return result

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._variable_name = properties.get("variable_name", "")
        self._validate_type = properties.get("validate_type", True)
        expected_type_name = properties.get("expected_type")
        if expected_type_name:
            self._expected_type = PortType[expected_type_name]
        else:
            self._expected_type = None


class GetCaseVariableNode(BaseNode):
    """Get a per-execution case variable."""

    node_type: str = "get_case_variable"
    display_name: str = "Get Variable"
    node_category: str = "Variables"
    node_color: str = "#9C27B0"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        default_variable_name: str = "",
        default_value: Any = None,
    ) -> None:
        self._default_variable_name: str = default_variable_name
        self._default_value: Any = default_value
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="variable_name", port_type=PortType.STRING,
            description="Name of the variable to retrieve", required=True,
            default_value=self._default_variable_name,
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        self.add_output_port(OutputPort(
            name="value", port_type=PortType.ANY,
            description="The retrieved variable value",
        ))

    @property
    def default_variable_name(self) -> str:
        return self._default_variable_name

    @default_variable_name.setter
    def default_variable_name(self, value: str) -> None:
        self._default_variable_name = value
        port = self.get_input_port("variable_name")
        if port:
            port.default_value = value

    @property
    def default_value(self) -> Any:
        return self._default_value

    @default_value.setter
    def default_value(self, value: Any) -> None:
        self._default_value = value

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self._default_variable_name:
            if not self._default_variable_name.isidentifier():
                errors.append(f"Default variable name '{self._default_variable_name}' is not a valid Python identifier")
            import keyword
            if keyword.iskeyword(self._default_variable_name):
                errors.append(f"Default variable name '{self._default_variable_name}' is a Python keyword")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        variable_name = inputs.get("variable_name", self._default_variable_name)
        if not variable_name:
            raise ValueError("Variable name is required")
        # In VP2 the execution engine resolves case variables.
        return {"value": self._default_value}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"default_variable_name": self._default_variable_name, "default_value": self._default_value}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._default_variable_name = properties.get("default_variable_name", "")
        self._default_value = properties.get("default_value", None)


class SetCaseVariableNode(BaseNode):
    """Set a per-execution case variable."""

    node_type: str = "set_case_variable"
    display_name: str = "Set Variable"
    node_category: str = "Variables"
    node_color: str = "#9C27B0"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        default_variable_name: str = "",
    ) -> None:
        self._default_variable_name: str = default_variable_name
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="variable_name", port_type=PortType.STRING,
            description="Name of the variable to set", required=True,
            default_value=self._default_variable_name,
        ))
        self.add_input_port(InputPort(
            name="value", port_type=PortType.ANY,
            description="Value to store", required=True,
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))

    @property
    def default_variable_name(self) -> str:
        return self._default_variable_name

    @default_variable_name.setter
    def default_variable_name(self, value: str) -> None:
        self._default_variable_name = value
        port = self.get_input_port("variable_name")
        if port:
            port.default_value = value

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self._default_variable_name:
            if not self._default_variable_name.isidentifier():
                errors.append(f"Default variable name '{self._default_variable_name}' is not a valid Python identifier")
            import keyword
            if keyword.iskeyword(self._default_variable_name):
                errors.append(f"Default variable name '{self._default_variable_name}' is a Python keyword")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        variable_name = inputs.get("variable_name", self._default_variable_name)
        if not variable_name:
            raise ValueError("Variable name is required")
        # In VP2 the execution engine handles case variable storage.
        return {}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"default_variable_name": self._default_variable_name}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._default_variable_name = properties.get("default_variable_name", "")


# ===========================================================================
# INPUT/OUTPUT NODES
# ===========================================================================


class PrintNode(BaseNode):
    """Print messages to output."""

    node_type: str = "print"
    display_name: str = "Print"
    node_category: str = "Input/Output"
    node_color: str = "#4CAF50"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        message: str = "",
        prefix: str = "",
        add_timestamp: bool = False,
        add_newline: bool = True,
    ) -> None:
        self._message: str = message
        self._prefix: str = prefix
        self._add_timestamp: bool = add_timestamp
        self._add_newline: bool = add_newline
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="message", port_type=PortType.ANY,
            description="The message to print", required=False,
        ))
        self.add_input_port(InputPort(
            name="prefix", port_type=PortType.STRING,
            description="Optional prefix for the message", required=False,
        ))
        self.add_input_port(InputPort(
            name="add_timestamp", port_type=PortType.BOOLEAN,
            description="Whether to add a timestamp", required=False, default_value=False,
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        self.add_output_port(OutputPort(
            name="printed_message", port_type=PortType.STRING,
            description="The fully formatted printed message",
        ))

    @property
    def message(self) -> str:
        return self._message

    @message.setter
    def message(self, value: str) -> None:
        self._message = value

    @property
    def prefix(self) -> str:
        return self._prefix

    @prefix.setter
    def prefix(self, value: str) -> None:
        self._prefix = value

    @property
    def add_timestamp(self) -> bool:
        return self._add_timestamp

    @add_timestamp.setter
    def add_timestamp(self, value: bool) -> None:
        self._add_timestamp = value

    @property
    def add_newline(self) -> bool:
        return self._add_newline

    @add_newline.setter
    def add_newline(self, value: bool) -> None:
        self._add_newline = value

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        msg = inputs.get("message", self._message)
        if msg is None:
            msg = ""
        msg = str(msg)
        pfx = inputs.get("prefix", self._prefix)
        use_timestamp = inputs.get("add_timestamp", self._add_timestamp)
        parts: List[str] = []
        if use_timestamp:
            parts.append(f"[{datetime.now().strftime('%H:%M:%S')}]")
        if pfx:
            parts.append(str(pfx))
        parts.append(msg)
        formatted = " ".join(parts) if len(parts) > 1 else msg
        print(formatted, end="\n" if self._add_newline else "")
        return {"printed_message": formatted}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {
            "message": self._message, "prefix": self._prefix,
            "add_timestamp": self._add_timestamp, "add_newline": self._add_newline,
        }

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._message = properties.get("message", "")
        self._prefix = properties.get("prefix", "")
        self._add_timestamp = properties.get("add_timestamp", False)
        self._add_newline = properties.get("add_newline", True)


class InputNode(BaseNode):
    """Prompt for user input (non-blocking placeholder in VP2)."""

    node_type: str = "input"
    display_name: str = "Input"
    node_category: str = "Input/Output"
    node_color: str = "#FF6B6B"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        prompt_text: str = "Enter value:",
        variable_name: str = "",
        default_value: str = "",
    ) -> None:
        self._prompt_text: str = prompt_text
        self._variable_name: str = variable_name
        self._default_value: str = default_value
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="prompt_text", port_type=PortType.STRING,
            description="The prompt to display", required=False,
            default_value="Enter value:",
        ))
        self.add_input_port(InputPort(
            name="default_value", port_type=PortType.STRING,
            description="Default value if input is cancelled", required=False,
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        self.add_output_port(OutputPort(
            name="value", port_type=PortType.STRING,
            description="The user input value",
        ))
        self.add_output_port(OutputPort(
            name="cancelled", port_type=PortType.BOOLEAN,
            description="Whether input was cancelled",
        ))

    @property
    def prompt_text(self) -> str:
        return self._prompt_text

    @prompt_text.setter
    def prompt_text(self, value: str) -> None:
        self._prompt_text = value

    @property
    def variable_name(self) -> str:
        return self._variable_name

    @variable_name.setter
    def variable_name(self, value: str) -> None:
        self._variable_name = value

    @property
    def default_value(self) -> str:
        return self._default_value

    @default_value.setter
    def default_value(self, value: str) -> None:
        self._default_value = value

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # In VP2 web environment, input is handled by the frontend.
        # This returns the default value as a placeholder.
        default = inputs.get("default_value", self._default_value)
        return {"value": default, "cancelled": False}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {
            "prompt_text": self._prompt_text,
            "variable_name": self._variable_name,
            "default_value": self._default_value,
        }

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._prompt_text = properties.get("prompt_text", "Enter value:")
        self._variable_name = properties.get("variable_name", "")
        self._default_value = properties.get("default_value", "")


class BreakpointNode(BaseNode):
    """Pause for debugging."""

    node_type: str = "breakpoint"
    display_name: str = "Breakpoint"
    node_category: str = "Debugging"
    node_color: str = "#FF5722"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        enabled: bool = True,
        message: str = "",
    ) -> None:
        self._enabled: bool = enabled
        self._message: str = message
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="condition", port_type=PortType.BOOLEAN,
            description="Conditional breakpoint (pause only when True)", required=False,
            default_value=True,
        ))
        self.add_input_port(InputPort(
            name="inspect_data", port_type=PortType.ANY,
            description="Data to inspect when paused", required=False,
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        self.add_output_port(OutputPort(
            name="data_out", port_type=PortType.ANY,
            description="Pass-through of inspect data",
        ))
        self.add_output_port(OutputPort(
            name="was_paused", port_type=PortType.BOOLEAN,
            description="Whether execution was paused",
        ))

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def message(self) -> str:
        return self._message

    @message.setter
    def message(self, value: str) -> None:
        self._message = value

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        condition = inputs.get("condition", True)
        inspect_data = inputs.get("inspect_data")
        should_pause = self._enabled and bool(condition)
        # In VP2 the execution engine handles actual pausing.
        return {"data_out": inspect_data, "was_paused": should_pause}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"enabled": self._enabled, "message": self._message}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._enabled = properties.get("enabled", True)
        self._message = properties.get("message", "")


# ===========================================================================
# FILE I/O NODES
# ===========================================================================


class FileReadNode(BaseNode):
    """Read content from a file."""

    node_type: str = "file_read"
    display_name: str = "File Read"
    node_category: str = "File I/O"
    node_color: str = "#4CAF50"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
    ) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="file_path", port_type=PortType.STRING,
            description="Path to the file to read", required=True,
        ))
        self.add_input_port(InputPort(
            name="encoding", port_type=PortType.STRING,
            description="File encoding", required=False, default_value="utf-8",
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        self.add_output_port(OutputPort(
            name="content", port_type=PortType.STRING,
            description="File content",
        ))
        self.add_output_port(OutputPort(
            name="success", port_type=PortType.BOOLEAN,
            description="Whether the read succeeded",
        ))
        self.add_output_port(OutputPort(
            name="bytes_read", port_type=PortType.INTEGER,
            description="Number of bytes read",
        ))
        self.add_output_port(OutputPort(
            name="error_message", port_type=PortType.STRING,
            description="Error message if read failed",
        ))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        file_path = inputs.get("file_path", "")
        encoding = inputs.get("encoding", "utf-8")
        if not file_path:
            return {"content": "", "success": False, "bytes_read": 0, "error_message": "No file path specified"}
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            return {"content": content, "success": True, "bytes_read": len(content.encode(encoding)), "error_message": ""}
        except Exception as e:
            return {"content": "", "success": False, "bytes_read": 0, "error_message": str(e)}


class FileWriteNode(BaseNode):
    """Write content to a file."""

    node_type: str = "file_write"
    display_name: str = "File Write"
    node_category: str = "File I/O"
    node_color: str = "#FF5722"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
    ) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="file_path", port_type=PortType.STRING,
            description="Path to the file to write", required=True,
        ))
        self.add_input_port(InputPort(
            name="content", port_type=PortType.STRING,
            description="Content to write", required=True,
        ))
        self.add_input_port(InputPort(
            name="append", port_type=PortType.BOOLEAN,
            description="Whether to append instead of overwrite", required=False, default_value=False,
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        self.add_output_port(OutputPort(
            name="success", port_type=PortType.BOOLEAN,
            description="Whether the write succeeded",
        ))
        self.add_output_port(OutputPort(
            name="bytes_written", port_type=PortType.INTEGER,
            description="Number of bytes written",
        ))
        self.add_output_port(OutputPort(
            name="error_message", port_type=PortType.STRING,
            description="Error message if write failed",
        ))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        file_path = inputs.get("file_path", "")
        content = inputs.get("content", "")
        append = inputs.get("append", False)
        if not file_path:
            return {"success": False, "bytes_written": 0, "error_message": "No file path specified"}
        try:
            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(str(content))
            return {"success": True, "bytes_written": len(str(content).encode("utf-8")), "error_message": ""}
        except Exception as e:
            return {"success": False, "bytes_written": 0, "error_message": str(e)}


# ===========================================================================
# NETWORK NODES
# ===========================================================================


class HTTPRequestNode(BaseNode):
    """Make HTTP requests."""

    node_type: str = "http_request"
    display_name: str = "HTTP Request"
    node_category: str = "Network"
    node_color: str = "#2196F3"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
    ) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="url", port_type=PortType.STRING,
            description="The URL to request", required=True,
        ))
        self.add_input_port(InputPort(
            name="method", port_type=PortType.STRING,
            description="HTTP method (GET, POST, PUT, DELETE, etc.)", required=False,
            default_value="GET",
        ))
        self.add_input_port(InputPort(
            name="headers", port_type=PortType.DICT,
            description="Request headers", required=False,
        ))
        self.add_input_port(InputPort(
            name="body", port_type=PortType.STRING,
            description="Request body", required=False,
        ))
        self.add_input_port(InputPort(
            name="timeout", port_type=PortType.FLOAT,
            description="Request timeout in seconds", required=False, default_value=30.0,
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        self.add_output_port(OutputPort(
            name="response_body", port_type=PortType.STRING,
            description="Response body",
        ))
        self.add_output_port(OutputPort(
            name="status_code", port_type=PortType.INTEGER,
            description="HTTP status code",
        ))
        self.add_output_port(OutputPort(
            name="response_headers", port_type=PortType.DICT,
            description="Response headers",
        ))
        self.add_output_port(OutputPort(
            name="success", port_type=PortType.BOOLEAN,
            description="Whether the request succeeded",
        ))
        self.add_output_port(OutputPort(
            name="error_message", port_type=PortType.STRING,
            description="Error message if request failed",
        ))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        url = inputs.get("url", "")
        method = inputs.get("method", "GET").upper()
        headers = inputs.get("headers") or {}
        body = inputs.get("body")
        timeout = inputs.get("timeout", 30.0)
        if not url:
            return {
                "response_body": "", "status_code": 0, "response_headers": {},
                "success": False, "error_message": "No URL specified",
            }
        try:
            data = body.encode("utf-8") if body else None
            req = urllib_request.Request(url, data=data, headers=headers, method=method)
            with urllib_request.urlopen(req, timeout=timeout) as response:
                resp_body = response.read().decode("utf-8", errors="replace")
                resp_headers = dict(response.headers)
                status = response.status
            return {
                "response_body": resp_body, "status_code": status,
                "response_headers": resp_headers, "success": True, "error_message": "",
            }
        except HTTPError as e:
            resp_body = ""
            try:
                resp_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return {
                "response_body": resp_body, "status_code": e.code,
                "response_headers": dict(e.headers), "success": False, "error_message": str(e),
            }
        except Exception as e:
            return {
                "response_body": "", "status_code": 0, "response_headers": {},
                "success": False, "error_message": str(e),
            }


# ===========================================================================
# DATABASE NODE
# ===========================================================================


class DatabaseType(Enum):
    """Supported database types."""
    SQLITE = "sqlite"
    GENERIC = "generic"


class DatabaseQueryNode(BaseNode):
    """Execute SQL queries."""

    node_type: str = "database_query"
    display_name: str = "Database Query"
    node_category: str = "Database"
    node_color: str = "#FF9800"

    def __init__(
        self,
        node_id: Optional[str] = None,
        name: Optional[str] = None,
        position: Optional[Position] = None,
        database_type: str = "sqlite",
    ) -> None:
        self._database_type: str = database_type
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(
            name="exec_in", port_type=PortType.FLOW,
            description="Execution flow input", required=False,
        ))
        self.add_input_port(InputPort(
            name="connection_string", port_type=PortType.STRING,
            description="Database connection string or file path", required=True,
        ))
        self.add_input_port(InputPort(
            name="query", port_type=PortType.STRING,
            description="SQL query to execute", required=True,
        ))
        self.add_input_port(InputPort(
            name="parameters", port_type=PortType.DICT,
            description="Query parameters", required=False,
        ))
        self.add_input_port(InputPort(
            name="timeout", port_type=PortType.FLOAT,
            description="Query timeout in seconds", required=False, default_value=30.0,
        ))
        self.add_output_port(OutputPort(
            name="exec_out", port_type=PortType.FLOW,
            description="Execution flow output",
        ))
        self.add_output_port(OutputPort(name="rows", port_type=PortType.LIST, description="Query result rows"))
        self.add_output_port(OutputPort(name="row_count", port_type=PortType.INTEGER, description="Number of rows"))
        self.add_output_port(OutputPort(name="columns", port_type=PortType.LIST, description="Column names"))
        self.add_output_port(OutputPort(name="success", port_type=PortType.BOOLEAN, description="Whether query succeeded"))
        self.add_output_port(OutputPort(name="error_message", port_type=PortType.STRING, description="Error message"))
        self.add_output_port(OutputPort(name="last_insert_id", port_type=PortType.INTEGER, description="Last insert row ID"))
        self.add_output_port(OutputPort(name="rows_affected", port_type=PortType.INTEGER, description="Number of rows affected"))

    @property
    def database_type(self) -> str:
        return self._database_type

    @database_type.setter
    def database_type(self, value: str) -> None:
        self._database_type = value

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        conn_str = inputs.get("connection_string", "")
        query = inputs.get("query", "")
        params = inputs.get("parameters")
        if not conn_str or not query:
            return {
                "rows": [], "row_count": 0, "columns": [], "success": False,
                "error_message": "Connection string and query are required",
                "last_insert_id": 0, "rows_affected": 0,
            }
        try:
            conn = sqlite3.connect(conn_str)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if params:
                if isinstance(params, dict):
                    cursor.execute(query, params)
                elif isinstance(params, (list, tuple)):
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
            else:
                cursor.execute(query)
            columns: List[str] = []
            rows: List[Dict[str, Any]] = []
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(row) for row in cursor.fetchall()]
            last_insert_id = cursor.lastrowid or 0
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            return {
                "rows": rows, "row_count": len(rows), "columns": columns,
                "success": True, "error_message": "",
                "last_insert_id": last_insert_id, "rows_affected": rows_affected,
            }
        except Exception as e:
            return {
                "rows": [], "row_count": 0, "columns": [], "success": False,
                "error_message": str(e), "last_insert_id": 0, "rows_affected": 0,
            }

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"database_type": self._database_type}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._database_type = properties.get("database_type", "sqlite")


# ===========================================================================
# JSON PROCESSING NODES
# ===========================================================================


class JSONParseNode(BaseNode):
    """Parse JSON strings."""

    node_type: str = "json_parse"
    display_name: str = "JSON Parse"
    node_category: str = "Data Processing"
    node_color: str = "#FF6B00"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="json_string", port_type=PortType.STRING, description="JSON string to parse", required=True))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="data", port_type=PortType.ANY, description="Parsed data"))
        self.add_output_port(OutputPort(name="success", port_type=PortType.BOOLEAN, description="Whether parsing succeeded"))
        self.add_output_port(OutputPort(name="error_message", port_type=PortType.STRING, description="Error message"))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        json_string = inputs.get("json_string", "")
        if not json_string:
            return {"data": None, "success": False, "error_message": "No JSON string provided"}
        try:
            data = json.loads(json_string)
            return {"data": data, "success": True, "error_message": ""}
        except Exception as e:
            return {"data": None, "success": False, "error_message": str(e)}


class JSONStringifyNode(BaseNode):
    """Convert to JSON strings."""

    node_type: str = "json_stringify"
    display_name: str = "JSON Stringify"
    node_category: str = "Data Processing"
    node_color: str = "#FF6B00"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="data", port_type=PortType.ANY, description="Data to stringify", required=True))
        self.add_input_port(InputPort(name="indent", port_type=PortType.INTEGER, description="Indentation level", required=False, default_value=2))
        self.add_input_port(InputPort(name="sort_keys", port_type=PortType.BOOLEAN, description="Whether to sort keys", required=False, default_value=False))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="json_string", port_type=PortType.STRING, description="JSON string"))
        self.add_output_port(OutputPort(name="success", port_type=PortType.BOOLEAN, description="Whether stringify succeeded"))
        self.add_output_port(OutputPort(name="error_message", port_type=PortType.STRING, description="Error message"))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        data = inputs.get("data")
        indent = inputs.get("indent", 2)
        sort_keys = inputs.get("sort_keys", False)
        try:
            json_string = json.dumps(data, indent=indent, sort_keys=sort_keys, default=str)
            return {"json_string": json_string, "success": True, "error_message": ""}
        except Exception as e:
            return {"json_string": "", "success": False, "error_message": str(e)}


# ===========================================================================
# MATH OPERATION NODES
# ===========================================================================


class AddNode(BaseNode):
    """Add two numbers."""

    node_type: str = "add"
    display_name: str = "Add"
    node_category: str = "Math Operations"
    node_color: str = "#FF9800"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="a", port_type=PortType.FLOAT, description="First operand", required=False, default_value=0))
        self.add_input_port(InputPort(name="b", port_type=PortType.FLOAT, description="Second operand", required=False, default_value=0))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.FLOAT, description="Sum of a + b"))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        a = inputs.get("a", 0)
        b = inputs.get("b", 0)
        return {"result": a + b}


class SubtractNode(BaseNode):
    """Subtract numbers."""

    node_type: str = "subtract"
    display_name: str = "Subtract"
    node_category: str = "Math Operations"
    node_color: str = "#FF9800"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="a", port_type=PortType.FLOAT, description="First operand", required=False, default_value=0))
        self.add_input_port(InputPort(name="b", port_type=PortType.FLOAT, description="Second operand", required=False, default_value=0))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.FLOAT, description="Difference of a - b"))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        a = inputs.get("a", 0)
        b = inputs.get("b", 0)
        return {"result": a - b}


class MultiplyNode(BaseNode):
    """Multiply numbers."""

    node_type: str = "multiply"
    display_name: str = "Multiply"
    node_category: str = "Math Operations"
    node_color: str = "#FF9800"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="a", port_type=PortType.FLOAT, description="First operand", required=False, default_value=1))
        self.add_input_port(InputPort(name="b", port_type=PortType.FLOAT, description="Second operand", required=False, default_value=1))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.FLOAT, description="Product of a * b"))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        a = inputs.get("a", 1)
        b = inputs.get("b", 1)
        return {"result": a * b}


class DivideNode(BaseNode):
    """Divide numbers."""

    node_type: str = "divide"
    display_name: str = "Divide"
    node_category: str = "Math Operations"
    node_color: str = "#FF9800"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, integer_division: bool = False) -> None:
        self._integer_division: bool = integer_division
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="a", port_type=PortType.FLOAT, description="Dividend", required=False, default_value=0))
        self.add_input_port(InputPort(name="b", port_type=PortType.FLOAT, description="Divisor", required=False, default_value=1))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.FLOAT, description="Quotient of a / b"))

    @property
    def integer_division(self) -> bool:
        return self._integer_division

    @integer_division.setter
    def integer_division(self, value: bool) -> None:
        self._integer_division = value

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        a = inputs.get("a", 0)
        b = inputs.get("b", 1)
        if b == 0:
            raise ZeroDivisionError("Division by zero")
        if self._integer_division:
            return {"result": a // b}
        return {"result": a / b}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"integer_division": self._integer_division}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._integer_division = properties.get("integer_division", False)


class ModuloNode(BaseNode):
    """Modulo operation."""

    node_type: str = "modulo"
    display_name: str = "Modulo"
    node_category: str = "Math Operations"
    node_color: str = "#FF9800"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="a", port_type=PortType.FLOAT, description="Dividend", required=False, default_value=0))
        self.add_input_port(InputPort(name="b", port_type=PortType.FLOAT, description="Divisor", required=False, default_value=1))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.FLOAT, description="Remainder of a % b"))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        a = inputs.get("a", 0)
        b = inputs.get("b", 1)
        if b == 0:
            raise ZeroDivisionError("Modulo by zero")
        return {"result": a % b}


class PowerNode(BaseNode):
    """Exponentiation."""

    node_type: str = "power"
    display_name: str = "Power"
    node_category: str = "Math Operations"
    node_color: str = "#FF9800"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="base", port_type=PortType.FLOAT, description="Base number", required=False, default_value=0))
        self.add_input_port(InputPort(name="exponent", port_type=PortType.FLOAT, description="Exponent", required=False, default_value=1))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.FLOAT, description="Result of base ** exponent"))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        base = inputs.get("base", 0)
        exponent = inputs.get("exponent", 1)
        return {"result": base ** exponent}


# ===========================================================================
# STRING OPERATION NODES
# ===========================================================================


class StringConcatNode(BaseNode):
    """Concatenate strings."""

    node_type: str = "string_concat"
    display_name: str = "String Concat"
    node_category: str = "String Operations"
    node_color: str = "#2196F3"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="str1", port_type=PortType.STRING, description="First string", required=False, default_value=""))
        self.add_input_port(InputPort(name="str2", port_type=PortType.STRING, description="Second string", required=False, default_value=""))
        self.add_input_port(InputPort(name="str3", port_type=PortType.STRING, description="Third string (optional)", required=False))
        self.add_input_port(InputPort(name="str4", port_type=PortType.STRING, description="Fourth string (optional)", required=False))
        self.add_input_port(InputPort(name="separator", port_type=PortType.STRING, description="Separator between strings", required=False, default_value=""))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.STRING, description="Concatenated result"))
        self.add_output_port(OutputPort(name="length", port_type=PortType.INTEGER, description="Length of result"))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        parts: List[str] = []
        for key in ("str1", "str2", "str3", "str4"):
            val = inputs.get(key)
            if val is not None:
                parts.append(str(val))
        separator = inputs.get("separator", "")
        if separator is None:
            separator = ""
        result = separator.join(parts)
        return {"result": result, "length": len(result)}


class StringSplitNode(BaseNode):
    """Split strings."""

    node_type: str = "string_split"
    display_name: str = "String Split"
    node_category: str = "String Operations"
    node_color: str = "#2196F3"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, default_delimiter: str = "",
                 max_splits: int = -1) -> None:
        self._default_delimiter: str = default_delimiter
        self._max_splits: int = max_splits
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="text", port_type=PortType.STRING, description="Text to split", required=True))
        self.add_input_port(InputPort(name="delimiter", port_type=PortType.STRING, description="Delimiter to split on", required=False, default_value=""))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="parts", port_type=PortType.LIST, description="List of parts"))
        self.add_output_port(OutputPort(name="count", port_type=PortType.INTEGER, description="Number of parts"))
        self.add_output_port(OutputPort(name="first", port_type=PortType.STRING, description="First part"))
        self.add_output_port(OutputPort(name="last", port_type=PortType.STRING, description="Last part"))

    @property
    def default_delimiter(self) -> str:
        return self._default_delimiter

    @default_delimiter.setter
    def default_delimiter(self, value: str) -> None:
        self._default_delimiter = value

    @property
    def max_splits(self) -> int:
        return self._max_splits

    @max_splits.setter
    def max_splits(self, value: int) -> None:
        self._max_splits = value

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        text = inputs.get("text", "")
        delimiter = inputs.get("delimiter", self._default_delimiter)
        if not text:
            return {"parts": [], "count": 0, "first": "", "last": ""}
        if delimiter:
            if self._max_splits >= 0:
                parts = str(text).split(delimiter, self._max_splits)
            else:
                parts = str(text).split(delimiter)
        else:
            if self._max_splits >= 0:
                parts = str(text).split(None, self._max_splits)
            else:
                parts = str(text).split()
        return {
            "parts": parts, "count": len(parts),
            "first": parts[0] if parts else "",
            "last": parts[-1] if parts else "",
        }

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"default_delimiter": self._default_delimiter, "max_splits": self._max_splits}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._default_delimiter = properties.get("default_delimiter", "")
        self._max_splits = properties.get("max_splits", -1)


class StringReplaceNode(BaseNode):
    """Find and replace in strings."""

    node_type: str = "string_replace"
    display_name: str = "String Replace"
    node_category: str = "String Operations"
    node_color: str = "#2196F3"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, default_search: str = "",
                 default_replacement: str = "", max_replacements: int = -1,
                 case_sensitive: bool = True) -> None:
        self._default_search: str = default_search
        self._default_replacement: str = default_replacement
        self._max_replacements: int = max_replacements
        self._case_sensitive: bool = case_sensitive
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="text", port_type=PortType.STRING, description="Text to search in", required=True))
        self.add_input_port(InputPort(name="search", port_type=PortType.STRING, description="Text to find", required=False))
        self.add_input_port(InputPort(name="replacement", port_type=PortType.STRING, description="Replacement text", required=False))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.STRING, description="Resulting text"))
        self.add_output_port(OutputPort(name="replacement_count", port_type=PortType.INTEGER, description="Number of replacements"))
        self.add_output_port(OutputPort(name="original_text", port_type=PortType.STRING, description="Original text"))
        self.add_output_port(OutputPort(name="changed", port_type=PortType.BOOLEAN, description="Whether text was changed"))

    @property
    def default_search(self) -> str:
        return self._default_search

    @default_search.setter
    def default_search(self, value: str) -> None:
        self._default_search = value

    @property
    def default_replacement(self) -> str:
        return self._default_replacement

    @default_replacement.setter
    def default_replacement(self, value: str) -> None:
        self._default_replacement = value

    @property
    def max_replacements(self) -> int:
        return self._max_replacements

    @max_replacements.setter
    def max_replacements(self, value: int) -> None:
        self._max_replacements = value

    @property
    def case_sensitive(self) -> bool:
        return self._case_sensitive

    @case_sensitive.setter
    def case_sensitive(self, value: bool) -> None:
        self._case_sensitive = value

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        text = str(inputs.get("text", ""))
        search = inputs.get("search", self._default_search)
        replacement = inputs.get("replacement", self._default_replacement)
        if not search:
            return {"result": text, "replacement_count": 0, "original_text": text, "changed": False}
        if self._case_sensitive:
            if self._max_replacements >= 0:
                result = text.replace(search, replacement, self._max_replacements)
            else:
                result = text.replace(search, replacement)
            count = text.count(search)
            if self._max_replacements >= 0:
                count = min(count, self._max_replacements)
        else:
            pattern = re.compile(re.escape(search), re.IGNORECASE)
            count_val = len(pattern.findall(text))
            if self._max_replacements >= 0:
                result = pattern.sub(replacement, text, count=self._max_replacements)
                count = min(count_val, self._max_replacements)
            else:
                result = pattern.sub(replacement, text)
                count = count_val
        return {"result": result, "replacement_count": count, "original_text": text, "changed": result != text}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {
            "default_search": self._default_search, "default_replacement": self._default_replacement,
            "max_replacements": self._max_replacements, "case_sensitive": self._case_sensitive,
        }

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._default_search = properties.get("default_search", "")
        self._default_replacement = properties.get("default_replacement", "")
        self._max_replacements = properties.get("max_replacements", -1)
        self._case_sensitive = properties.get("case_sensitive", True)


class StringFormatNode(BaseNode):
    """Format strings with templates."""

    node_type: str = "string_format"
    display_name: str = "String Format"
    node_category: str = "String Operations"
    node_color: str = "#2196F3"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None) -> None:
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="template", port_type=PortType.STRING, description="Format template string", required=True))
        self.add_input_port(InputPort(name="arg1", port_type=PortType.ANY, description="First argument ({0} or {arg1})", required=False))
        self.add_input_port(InputPort(name="arg2", port_type=PortType.ANY, description="Second argument ({1} or {arg2})", required=False))
        self.add_input_port(InputPort(name="arg3", port_type=PortType.ANY, description="Third argument ({2} or {arg3})", required=False))
        self.add_input_port(InputPort(name="arg4", port_type=PortType.ANY, description="Fourth argument ({3} or {arg4})", required=False))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.STRING, description="Formatted string"))
        self.add_output_port(OutputPort(name="success", port_type=PortType.BOOLEAN, description="Whether formatting succeeded"))
        self.add_output_port(OutputPort(name="error_message", port_type=PortType.STRING, description="Error message"))

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        template = inputs.get("template", "")
        if not template:
            return {"result": "", "success": False, "error_message": "No template provided"}
        args = []
        kwargs: Dict[str, Any] = {}
        for i in range(1, 5):
            key = f"arg{i}"
            val = inputs.get(key)
            if val is not None:
                args.append(val)
                kwargs[key] = val
        try:
            result = template.format(*args, **kwargs)
            return {"result": result, "success": True, "error_message": ""}
        except (IndexError, KeyError):
            # Fallback: simple regex replacement
            result = template
            for i, val in enumerate(args):
                result = result.replace(f"{{{i}}}", str(val))
            for k, v in kwargs.items():
                result = result.replace(f"{{{k}}}", str(v))
            return {"result": result, "success": True, "error_message": ""}
        except Exception as e:
            return {"result": "", "success": False, "error_message": str(e)}


# ===========================================================================
# REGEX NODES
# ===========================================================================


class RegexMatchNode(BaseNode):
    """Find regex matches in text."""

    node_type: str = "regex_match"
    display_name: str = "Regex Match"
    node_category: str = "String Operations"
    node_color: str = "#2196F3"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, default_pattern: str = "",
                 case_insensitive: bool = False, multiline: bool = False,
                 dot_all: bool = False) -> None:
        self._default_pattern: str = default_pattern
        self._case_insensitive: bool = case_insensitive
        self._multiline: bool = multiline
        self._dot_all: bool = dot_all
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="text", port_type=PortType.STRING, description="Text to search", required=True))
        self.add_input_port(InputPort(name="pattern", port_type=PortType.STRING, description="Regex pattern", required=False))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="matches", port_type=PortType.LIST, description="All matches"))
        self.add_output_port(OutputPort(name="match_found", port_type=PortType.BOOLEAN, description="Whether a match was found"))
        self.add_output_port(OutputPort(name="first_match", port_type=PortType.STRING, description="First match"))
        self.add_output_port(OutputPort(name="match_count", port_type=PortType.INTEGER, description="Number of matches"))
        self.add_output_port(OutputPort(name="groups", port_type=PortType.LIST, description="Capture groups from first match"))
        self.add_output_port(OutputPort(name="error_message", port_type=PortType.STRING, description="Error message"))

    @property
    def default_pattern(self) -> str:
        return self._default_pattern

    @default_pattern.setter
    def default_pattern(self, value: str) -> None:
        self._default_pattern = value

    @property
    def case_insensitive(self) -> bool:
        return self._case_insensitive

    @case_insensitive.setter
    def case_insensitive(self, value: bool) -> None:
        self._case_insensitive = value

    @property
    def multiline(self) -> bool:
        return self._multiline

    @multiline.setter
    def multiline(self, value: bool) -> None:
        self._multiline = value

    @property
    def dot_all(self) -> bool:
        return self._dot_all

    @dot_all.setter
    def dot_all(self, value: bool) -> None:
        self._dot_all = value

    def _get_flags(self) -> int:
        flags = 0
        if self._case_insensitive:
            flags |= re.IGNORECASE
        if self._multiline:
            flags |= re.MULTILINE
        if self._dot_all:
            flags |= re.DOTALL
        return flags

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self._default_pattern:
            try:
                re.compile(self._default_pattern)
            except re.error as e:
                errors.append(f"Invalid regex pattern: {e}")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        text = str(inputs.get("text", ""))
        pattern = inputs.get("pattern", self._default_pattern)
        if not pattern:
            return {"matches": [], "match_found": False, "first_match": "", "match_count": 0, "groups": [], "error_message": "No pattern specified"}
        try:
            flags = self._get_flags()
            compiled = re.compile(pattern, flags)
            all_matches = compiled.findall(text)
            first = compiled.search(text)
            groups: List[str] = []
            first_match = ""
            if first:
                first_match = first.group(0)
                groups = list(first.groups()) if first.groups() else []
            return {
                "matches": all_matches, "match_found": len(all_matches) > 0,
                "first_match": first_match, "match_count": len(all_matches),
                "groups": groups, "error_message": "",
            }
        except re.error as e:
            return {"matches": [], "match_found": False, "first_match": "", "match_count": 0, "groups": [], "error_message": str(e)}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {
            "default_pattern": self._default_pattern, "case_insensitive": self._case_insensitive,
            "multiline": self._multiline, "dot_all": self._dot_all,
        }

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._default_pattern = properties.get("default_pattern", "")
        self._case_insensitive = properties.get("case_insensitive", False)
        self._multiline = properties.get("multiline", False)
        self._dot_all = properties.get("dot_all", False)


class RegexReplaceNode(BaseNode):
    """Regex find and replace."""

    node_type: str = "regex_replace"
    display_name: str = "Regex Replace"
    node_category: str = "String Operations"
    node_color: str = "#2196F3"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, default_pattern: str = "",
                 default_replacement: str = "", max_replacements: int = 0,
                 case_insensitive: bool = False, multiline: bool = False,
                 dot_all: bool = False) -> None:
        self._default_pattern: str = default_pattern
        self._default_replacement: str = default_replacement
        self._max_replacements: int = max_replacements
        self._case_insensitive: bool = case_insensitive
        self._multiline: bool = multiline
        self._dot_all: bool = dot_all
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="text", port_type=PortType.STRING, description="Text to search", required=True))
        self.add_input_port(InputPort(name="pattern", port_type=PortType.STRING, description="Regex pattern", required=False))
        self.add_input_port(InputPort(name="replacement", port_type=PortType.STRING, description="Replacement text", required=False))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.STRING, description="Resulting text"))
        self.add_output_port(OutputPort(name="replacement_count", port_type=PortType.INTEGER, description="Number of replacements"))
        self.add_output_port(OutputPort(name="original_text", port_type=PortType.STRING, description="Original text"))
        self.add_output_port(OutputPort(name="changed", port_type=PortType.BOOLEAN, description="Whether text was changed"))
        self.add_output_port(OutputPort(name="error_message", port_type=PortType.STRING, description="Error message"))

    def _get_flags(self) -> int:
        flags = 0
        if self._case_insensitive:
            flags |= re.IGNORECASE
        if self._multiline:
            flags |= re.MULTILINE
        if self._dot_all:
            flags |= re.DOTALL
        return flags

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self._default_pattern:
            try:
                re.compile(self._default_pattern)
            except re.error as e:
                errors.append(f"Invalid regex pattern: {e}")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        text = str(inputs.get("text", ""))
        pattern = inputs.get("pattern", self._default_pattern)
        replacement = inputs.get("replacement", self._default_replacement)
        if not pattern:
            return {"result": text, "replacement_count": 0, "original_text": text, "changed": False, "error_message": "No pattern specified"}
        try:
            flags = self._get_flags()
            compiled = re.compile(pattern, flags)
            count_matches = len(compiled.findall(text))
            count = self._max_replacements if self._max_replacements > 0 else 0
            result = compiled.sub(replacement, text, count=count)
            actual_replacements = min(count_matches, self._max_replacements) if self._max_replacements > 0 else count_matches
            return {
                "result": result, "replacement_count": actual_replacements,
                "original_text": text, "changed": result != text, "error_message": "",
            }
        except re.error as e:
            return {"result": text, "replacement_count": 0, "original_text": text, "changed": False, "error_message": str(e)}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {
            "default_pattern": self._default_pattern, "default_replacement": self._default_replacement,
            "max_replacements": self._max_replacements, "case_insensitive": self._case_insensitive,
            "multiline": self._multiline, "dot_all": self._dot_all,
        }

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._default_pattern = properties.get("default_pattern", "")
        self._default_replacement = properties.get("default_replacement", "")
        self._max_replacements = properties.get("max_replacements", 0)
        self._case_insensitive = properties.get("case_insensitive", False)
        self._multiline = properties.get("multiline", False)
        self._dot_all = properties.get("dot_all", False)


# ===========================================================================
# LIST OPERATION NODES
# ===========================================================================


class ListAppendNode(BaseNode):
    """Append elements to a list."""

    node_type: str = "list_append"
    display_name: str = "List Append"
    node_category: str = "List Operations"
    node_color: str = "#2196F3"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, extend_mode: bool = False,
                 create_new_list: bool = True) -> None:
        self._extend_mode: bool = extend_mode
        self._create_new_list: bool = create_new_list
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="list", port_type=PortType.LIST, description="The source list", required=True))
        self.add_input_port(InputPort(name="element", port_type=PortType.ANY, description="Element to append", required=True))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.LIST, description="The resulting list"))
        self.add_output_port(OutputPort(name="length", port_type=PortType.INTEGER, description="Length of resulting list"))

    @property
    def extend_mode(self) -> bool:
        return self._extend_mode

    @extend_mode.setter
    def extend_mode(self, value: bool) -> None:
        self._extend_mode = value

    @property
    def create_new_list(self) -> bool:
        return self._create_new_list

    @create_new_list.setter
    def create_new_list(self, value: bool) -> None:
        self._create_new_list = value

    def validate(self) -> List[str]:
        return []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        source = inputs.get("list")
        element = inputs.get("element")
        if source is None:
            source = []
        if not isinstance(source, list):
            raise TypeError(f"Expected list, got {type(source).__name__}")
        result = list(source) if self._create_new_list else source
        if self._extend_mode and isinstance(element, (list, tuple)):
            result.extend(element)
        else:
            result.append(element)
        return {"result": result, "length": len(result)}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"extend_mode": self._extend_mode, "create_new_list": self._create_new_list}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._extend_mode = properties.get("extend_mode", False)
        self._create_new_list = properties.get("create_new_list", True)


class FilterCondition(Enum):
    TRUTHY = "truthy"
    FALSY = "falsy"
    NOT_NONE = "not_none"
    IS_STRING = "is_string"
    IS_NUMBER = "is_number"
    IS_POSITIVE = "is_positive"
    IS_NEGATIVE = "is_negative"
    IS_EVEN = "is_even"
    IS_ODD = "is_odd"
    CUSTOM = "custom"


class ListFilterNode(BaseNode):
    """Filter list elements."""

    node_type: str = "list_filter"
    display_name: str = "List Filter"
    node_category: str = "List Operations"
    node_color: str = "#2196F3"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, filter_condition: str = "truthy",
                 custom_expression: str = "", variable_name: str = "x") -> None:
        self._filter_condition: str = filter_condition
        self._custom_expression: str = custom_expression
        self._variable_name: str = variable_name
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="list", port_type=PortType.LIST, description="The source list to filter", required=True))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.LIST, description="Filtered list"))
        self.add_output_port(OutputPort(name="rejected", port_type=PortType.LIST, description="Rejected elements"))
        self.add_output_port(OutputPort(name="count", port_type=PortType.INTEGER, description="Number that passed"))

    @property
    def filter_condition(self) -> str:
        return self._filter_condition

    @filter_condition.setter
    def filter_condition(self, value: str) -> None:
        self._filter_condition = value

    @property
    def custom_expression(self) -> str:
        return self._custom_expression

    @custom_expression.setter
    def custom_expression(self, value: str) -> None:
        self._custom_expression = value

    @property
    def variable_name(self) -> str:
        return self._variable_name

    @variable_name.setter
    def variable_name(self, value: str) -> None:
        self._variable_name = value

    def _get_filter_function(self) -> Callable[[Any], bool]:
        cond = self._filter_condition
        if cond == "truthy": return lambda x: bool(x)
        elif cond == "falsy": return lambda x: not bool(x)
        elif cond == "not_none": return lambda x: x is not None
        elif cond == "is_string": return lambda x: isinstance(x, str)
        elif cond == "is_number": return lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)
        elif cond == "is_positive": return lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0
        elif cond == "is_negative": return lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and x < 0
        elif cond == "is_even": return lambda x: isinstance(x, int) and not isinstance(x, bool) and x % 2 == 0
        elif cond == "is_odd": return lambda x: isinstance(x, int) and not isinstance(x, bool) and x % 2 != 0
        elif cond == "custom":
            if not self._custom_expression: return lambda x: True
            try:
                compiled = compile(self._custom_expression, "<filter>", "eval")
                def custom_filter(x: Any) -> bool:
                    try: return bool(eval(compiled, {"__builtins__": {}}, {self._variable_name: x}))
                    except Exception: return False
                return custom_filter
            except SyntaxError: return lambda x: False
        return lambda x: bool(x)

    def validate(self) -> List[str]:
        errors: List[str] = []
        valid = [c.value for c in FilterCondition]
        if self._filter_condition not in valid:
            errors.append(f"Invalid filter condition: {self._filter_condition}")
        if self._filter_condition == "custom" and self._custom_expression:
            try: compile(self._custom_expression, "<filter>", "eval")
            except SyntaxError as e: errors.append(f"Invalid custom expression: {e}")
        if not self._variable_name.isidentifier():
            errors.append(f"Invalid variable name: {self._variable_name}")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        source_list = inputs.get("list")
        if source_list is None: raise ValueError("No list provided")
        if not isinstance(source_list, list): raise TypeError(f"Expected list, got {type(source_list).__name__}")
        ff = self._get_filter_function()
        passed: List[Any] = []
        rejected: List[Any] = []
        for item in source_list:
            try:
                (passed if ff(item) else rejected).append(item)
            except Exception:
                rejected.append(item)
        return {"result": passed, "rejected": rejected, "count": len(passed)}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"filter_condition": self._filter_condition, "custom_expression": self._custom_expression, "variable_name": self._variable_name}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._filter_condition = properties.get("filter_condition", "truthy")
        self._custom_expression = properties.get("custom_expression", "")
        self._variable_name = properties.get("variable_name", "x")


class MapTransformation(Enum):
    TO_STRING = "to_string"; TO_INT = "to_int"; TO_FLOAT = "to_float"; TO_BOOL = "to_bool"
    TO_UPPER = "to_upper"; TO_LOWER = "to_lower"; STRIP = "strip"; ABS = "abs"
    NEGATE = "negate"; DOUBLE = "double"; SQUARE = "square"; LENGTH = "length"; CUSTOM = "custom"


class ListMapNode(BaseNode):
    """Transform list elements."""

    node_type: str = "list_map"
    display_name: str = "List Map"
    node_category: str = "List Operations"
    node_color: str = "#2196F3"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, transformation: str = "to_string",
                 custom_expression: str = "", variable_name: str = "x",
                 skip_errors: bool = False) -> None:
        self._transformation: str = transformation
        self._custom_expression: str = custom_expression
        self._variable_name: str = variable_name
        self._skip_errors: bool = skip_errors
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="list", port_type=PortType.LIST, description="The source list", required=True))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.LIST, description="Transformed list"))
        self.add_output_port(OutputPort(name="errors", port_type=PortType.LIST, description="Failed elements"))
        self.add_output_port(OutputPort(name="count", port_type=PortType.INTEGER, description="Number transformed"))

    @property
    def transformation(self) -> str: return self._transformation
    @transformation.setter
    def transformation(self, value: str) -> None: self._transformation = value
    @property
    def custom_expression(self) -> str: return self._custom_expression
    @custom_expression.setter
    def custom_expression(self, value: str) -> None: self._custom_expression = value
    @property
    def variable_name(self) -> str: return self._variable_name
    @variable_name.setter
    def variable_name(self, value: str) -> None: self._variable_name = value
    @property
    def skip_errors(self) -> bool: return self._skip_errors
    @skip_errors.setter
    def skip_errors(self, value: bool) -> None: self._skip_errors = value

    def _get_transform_function(self) -> Callable[[Any], Any]:
        t = self._transformation
        mapping: Dict[str, Callable] = {
            "to_string": str, "to_int": int, "to_float": float, "to_bool": bool,
            "to_upper": lambda x: str(x).upper(), "to_lower": lambda x: str(x).lower(),
            "strip": lambda x: str(x).strip(), "abs": abs, "negate": lambda x: -x,
            "double": lambda x: x * 2, "square": lambda x: x * x, "length": len,
        }
        if t in mapping: return mapping[t]
        if t == "custom":
            if not self._custom_expression: return lambda x: x
            try:
                compiled = compile(self._custom_expression, "<map>", "eval")
                def custom_transform(x: Any) -> Any:
                    return eval(compiled, {"__builtins__": {}}, {self._variable_name: x})
                return custom_transform
            except SyntaxError: return lambda x: x
        return lambda x: x

    def validate(self) -> List[str]:
        errors: List[str] = []
        valid = [t.value for t in MapTransformation]
        if self._transformation not in valid: errors.append(f"Invalid transformation: {self._transformation}")
        if self._transformation == "custom" and self._custom_expression:
            try: compile(self._custom_expression, "<map>", "eval")
            except SyntaxError as e: errors.append(f"Invalid custom expression: {e}")
        if not self._variable_name.isidentifier(): errors.append(f"Invalid variable name: {self._variable_name}")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        source_list = inputs.get("list")
        if source_list is None: raise ValueError("No list provided")
        if not isinstance(source_list, list): raise TypeError(f"Expected list, got {type(source_list).__name__}")
        tf = self._get_transform_function()
        result_list: List[Any] = []
        error_list: List[Any] = []
        for item in source_list:
            try: result_list.append(tf(item))
            except Exception as e:
                if self._skip_errors: error_list.append(item)
                else: raise ValueError(f"Failed to transform '{item}': {e}") from e
        return {"result": result_list, "errors": error_list, "count": len(result_list)}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"transformation": self._transformation, "custom_expression": self._custom_expression,
                "variable_name": self._variable_name, "skip_errors": self._skip_errors}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._transformation = properties.get("transformation", "to_string")
        self._custom_expression = properties.get("custom_expression", "")
        self._variable_name = properties.get("variable_name", "x")
        self._skip_errors = properties.get("skip_errors", False)


class ReduceOperation(Enum):
    SUM = "sum"; PRODUCT = "product"; MIN = "min"; MAX = "max"; COUNT = "count"
    AVERAGE = "average"; JOIN = "join"; FIRST = "first"; LAST = "last"
    ALL = "all"; ANY = "any"; CONCAT = "concat"; CUSTOM = "custom"


class ListReduceNode(BaseNode):
    """Reduce a list to a single value."""

    node_type: str = "list_reduce"
    display_name: str = "List Reduce"
    node_category: str = "List Operations"
    node_color: str = "#2196F3"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, reduce_operation: str = "sum",
                 custom_expression: str = "", accumulator_name: str = "acc",
                 element_name: str = "x", initial_value: Optional[Any] = None,
                 join_separator: str = "") -> None:
        self._reduce_operation: str = reduce_operation
        self._custom_expression: str = custom_expression
        self._accumulator_name: str = accumulator_name
        self._element_name: str = element_name
        self._initial_value: Optional[Any] = initial_value
        self._join_separator: str = join_separator
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="list", port_type=PortType.LIST, description="The source list", required=True))
        self.add_input_port(InputPort(name="initial", port_type=PortType.ANY, description="Optional initial value", required=False))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.ANY, description="Reduced result"))
        self.add_output_port(OutputPort(name="count", port_type=PortType.INTEGER, description="Number of elements"))

    @property
    def reduce_operation(self) -> str: return self._reduce_operation
    @reduce_operation.setter
    def reduce_operation(self, value: str) -> None: self._reduce_operation = value
    @property
    def custom_expression(self) -> str: return self._custom_expression
    @custom_expression.setter
    def custom_expression(self, value: str) -> None: self._custom_expression = value
    @property
    def accumulator_name(self) -> str: return self._accumulator_name
    @accumulator_name.setter
    def accumulator_name(self, value: str) -> None: self._accumulator_name = value
    @property
    def element_name(self) -> str: return self._element_name
    @element_name.setter
    def element_name(self, value: str) -> None: self._element_name = value
    @property
    def initial_value(self) -> Optional[Any]: return self._initial_value
    @initial_value.setter
    def initial_value(self, value: Optional[Any]) -> None: self._initial_value = value
    @property
    def join_separator(self) -> str: return self._join_separator
    @join_separator.setter
    def join_separator(self, value: str) -> None: self._join_separator = value

    def _execute_reduction(self, sl: List[Any], init: Optional[Any]) -> Any:
        op = self._reduce_operation
        if op == "sum": return sum(sl, init) if init is not None else sum(sl)
        elif op == "product":
            r = init if init is not None else 1
            for i in sl: r *= i
            return r
        elif op == "min": return min(sl) if sl else init
        elif op == "max": return max(sl) if sl else init
        elif op == "count": return len(sl)
        elif op == "average": return sum(sl) / len(sl) if sl else (init if init is not None else 0)
        elif op == "join": return self._join_separator.join(str(i) for i in sl)
        elif op == "first": return sl[0] if sl else init
        elif op == "last": return sl[-1] if sl else init
        elif op == "all": return all(sl)
        elif op == "any": return any(sl)
        elif op == "concat":
            rl: List[Any] = list(init) if init and isinstance(init, list) else []
            for i in sl:
                if isinstance(i, list): rl.extend(i)
                else: rl.append(i)
            return rl
        elif op == "custom":
            if not self._custom_expression:
                return init if init is not None else (sl[0] if sl else None)
            try:
                compiled = compile(self._custom_expression, "<reduce>", "eval")
                def reducer(acc: Any, x: Any) -> Any:
                    return eval(compiled, {"__builtins__": {}}, {self._accumulator_name: acc, self._element_name: x})
                if init is not None: return functools_reduce(reducer, sl, init)
                elif sl: return functools_reduce(reducer, sl)
                else: return None
            except (SyntaxError, TypeError): return init
        return sum(sl) if sl else (init if init is not None else 0)

    def validate(self) -> List[str]:
        errors: List[str] = []
        valid = [op.value for op in ReduceOperation]
        if self._reduce_operation not in valid: errors.append(f"Invalid operation: {self._reduce_operation}")
        if self._reduce_operation == "custom" and self._custom_expression:
            try: compile(self._custom_expression, "<reduce>", "eval")
            except SyntaxError as e: errors.append(f"Invalid custom expression: {e}")
        if not self._accumulator_name.isidentifier(): errors.append(f"Invalid accumulator name: {self._accumulator_name}")
        if not self._element_name.isidentifier(): errors.append(f"Invalid element name: {self._element_name}")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        sl = inputs.get("list")
        init = inputs.get("initial", self._initial_value)
        if sl is None: raise ValueError("No list provided")
        if not isinstance(sl, list): raise TypeError(f"Expected list, got {type(sl).__name__}")
        return {"result": self._execute_reduction(sl, init), "count": len(sl)}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"reduce_operation": self._reduce_operation, "custom_expression": self._custom_expression,
                "accumulator_name": self._accumulator_name, "element_name": self._element_name,
                "initial_value": self._initial_value, "join_separator": self._join_separator}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._reduce_operation = properties.get("reduce_operation", "sum")
        self._custom_expression = properties.get("custom_expression", "")
        self._accumulator_name = properties.get("accumulator_name", "acc")
        self._element_name = properties.get("element_name", "x")
        self._initial_value = properties.get("initial_value")
        self._join_separator = properties.get("join_separator", "")


# ===========================================================================
# DATA AGGREGATION NODE
# ===========================================================================

class AggregationStrategy(Enum):
    COLLECT_LIST = "collect_list"; MERGE_DICTS = "merge_dicts"; MERGE_DICTS_DEEP = "merge_dicts_deep"
    CONCATENATE_STRINGS = "concatenate_strings"; SUM_NUMBERS = "sum_numbers"
    FIRST_NON_NULL = "first_non_null"; LAST_NON_NULL = "last_non_null"


class DataAggregationNode(BaseNode):
    """Combine data from multiple sources."""

    node_type: str = "data_aggregation"
    display_name: str = "Data Aggregation"
    node_category: str = "Data Processing"
    node_color: str = "#9C27B0"
    MIN_INPUTS: int = 2
    MAX_INPUTS: int = 8

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, aggregation_strategy: str = "collect_list",
                 num_inputs: int = 2, separator: str = "", skip_none: bool = True) -> None:
        self._aggregation_strategy: str = aggregation_strategy
        self._num_inputs: int = max(self.MIN_INPUTS, min(self.MAX_INPUTS, num_inputs))
        self._separator: str = separator
        self._skip_none: bool = skip_none
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        for i in range(1, self._num_inputs + 1):
            self.add_input_port(InputPort(name=f"data_in_{i}", port_type=PortType.ANY, description=f"Data input {i}", required=False))
        self.add_input_port(InputPort(name="separator", port_type=PortType.STRING, description="Separator for concatenation", required=False, default_value=""))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="result", port_type=PortType.ANY, description="Aggregated result"))
        self.add_output_port(OutputPort(name="count", port_type=PortType.INTEGER, description="Number aggregated"))

    @property
    def aggregation_strategy(self) -> str: return self._aggregation_strategy
    @aggregation_strategy.setter
    def aggregation_strategy(self, value: str) -> None:
        valid = [s.value for s in AggregationStrategy]
        if value not in valid: raise ValueError(f"Invalid strategy: {value}")
        self._aggregation_strategy = value
    @property
    def num_inputs(self) -> int: return self._num_inputs
    @property
    def separator(self) -> str: return self._separator
    @separator.setter
    def separator(self, value: str) -> None: self._separator = value
    @property
    def skip_none(self) -> bool: return self._skip_none
    @skip_none.setter
    def skip_none(self, value: bool) -> None: self._skip_none = value

    def add_input_slot(self) -> bool:
        if self._num_inputs >= self.MAX_INPUTS: return False
        self._num_inputs += 1
        self.add_input_port(InputPort(name=f"data_in_{self._num_inputs}", port_type=PortType.ANY, description=f"Data input {self._num_inputs}", required=False))
        return True

    def remove_input_slot(self) -> bool:
        if self._num_inputs <= self.MIN_INPUTS: return False
        self.remove_input_port(f"data_in_{self._num_inputs}")
        self._num_inputs -= 1
        return True

    def _collect_inputs(self, inputs: Dict[str, Any]) -> List[Any]:
        values = []
        for i in range(1, self._num_inputs + 1):
            pn = f"data_in_{i}"
            if pn in inputs:
                v = inputs[pn]
                if not self._skip_none or v is not None: values.append(v)
        return values

    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        result = base.copy()
        for k, v in update.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else: result[k] = v
        return result

    def validate(self) -> List[str]:
        errors: List[str] = []
        valid = [s.value for s in AggregationStrategy]
        if self._aggregation_strategy not in valid: errors.append(f"Invalid strategy: {self._aggregation_strategy}")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        values = self._collect_inputs(inputs)
        sep = inputs.get("separator", self._separator) or ""
        s = self._aggregation_strategy
        result: Any = None
        count = len(values)
        if s == "collect_list": result = values
        elif s == "merge_dicts":
            result = {}
            for v in values:
                if isinstance(v, dict): result.update(v)
        elif s == "merge_dicts_deep":
            result = {}
            for v in values:
                if isinstance(v, dict): result = self._deep_merge(result, v)
        elif s == "concatenate_strings": result = sep.join(str(v) for v in values if v is not None)
        elif s == "sum_numbers": result = sum(v for v in values if v is not None)
        elif s == "first_non_null":
            result = next((v for v in values if v is not None), None)
            count = 1 if result is not None else 0
        elif s == "last_non_null":
            result = None
            for v in values:
                if v is not None: result = v
            count = 1 if result is not None else 0
        return {"result": result, "count": count}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"aggregation_strategy": self._aggregation_strategy, "num_inputs": self._num_inputs,
                "separator": self._separator, "skip_none": self._skip_none}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._aggregation_strategy = properties.get("aggregation_strategy", "collect_list")
        self._separator = properties.get("separator", "")
        self._skip_none = properties.get("skip_none", True)
        new_n = properties.get("num_inputs", 2)
        while self._num_inputs < new_n and self._num_inputs < self.MAX_INPUTS: self.add_input_slot()
        while self._num_inputs > new_n and self._num_inputs > self.MIN_INPUTS: self.remove_input_slot()


# ===========================================================================
# SUBGRAPH NODES
# ===========================================================================

class SubgraphNode(BaseNode):
    """Reusable subgraph (simplified for VP2)."""
    node_type: str = "subgraph"
    display_name: str = "Subgraph"
    node_category: str = "Subgraphs"
    node_color: str = "#00BCD4"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, subgraph_id: str = "",
                 subgraph_name: str = "", subgraph_description: str = "") -> None:
        self._subgraph_id: str = subgraph_id
        self._subgraph_name: str = subgraph_name
        self._subgraph_description: str = subgraph_description
        self._subgraph_data: Optional[Dict[str, Any]] = None
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))

    @property
    def subgraph_id(self) -> str: return self._subgraph_id
    @subgraph_id.setter
    def subgraph_id(self, value: str) -> None: self._subgraph_id = value
    @property
    def subgraph_name(self) -> str: return self._subgraph_name
    @subgraph_name.setter
    def subgraph_name(self, value: str) -> None: self._subgraph_name = value
    @property
    def subgraph_description(self) -> str: return self._subgraph_description
    @subgraph_description.setter
    def subgraph_description(self, value: str) -> None: self._subgraph_description = value
    @property
    def subgraph_data(self) -> Optional[Dict[str, Any]]: return self._subgraph_data
    @subgraph_data.setter
    def subgraph_data(self, value: Optional[Dict[str, Any]]) -> None: self._subgraph_data = value

    def add_dynamic_input(self, port_name: str, port_type: PortType = PortType.ANY, description: str = "") -> None:
        self.add_input_port(InputPort(name=port_name, port_type=port_type, description=description, required=False))

    def add_dynamic_output(self, port_name: str, port_type: PortType = PortType.ANY, description: str = "") -> None:
        self.add_output_port(OutputPort(name=port_name, port_type=port_type, description=description))

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._subgraph_id and not self._subgraph_data:
            errors.append("Subgraph must have an ID or embedded graph data")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        r: Dict[str, Any] = {"subgraph_id": self._subgraph_id, "subgraph_name": self._subgraph_name, "subgraph_description": self._subgraph_description}
        if self._subgraph_data: r["subgraph_data"] = self._subgraph_data
        return r

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._subgraph_id = properties.get("subgraph_id", "")
        self._subgraph_name = properties.get("subgraph_name", "")
        self._subgraph_description = properties.get("subgraph_description", "")
        self._subgraph_data = properties.get("subgraph_data")


class SubgraphInputNode(BaseNode):
    """Subgraph input parameter."""
    node_type: str = "subgraph_input"
    display_name: str = "Subgraph Input"
    node_category: str = "Subgraphs"
    node_color: str = "#4CAF50"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, port_name: str = "input",
                 port_type_setting: str = "ANY", description: str = "",
                 default_value: Any = None) -> None:
        self._port_name: str = port_name
        self._port_type_setting: str = port_type_setting
        self._description: str = description
        self._default_value_setting: Any = default_value
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        pt = PortType[self._port_type_setting] if self._port_type_setting in PortType.__members__ else PortType.ANY
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="value", port_type=pt, description=self._description or "Subgraph input value"))

    @property
    def port_name(self) -> str: return self._port_name
    @port_name.setter
    def port_name(self, value: str) -> None: self._port_name = value
    @property
    def port_type_setting(self) -> str: return self._port_type_setting
    @port_type_setting.setter
    def port_type_setting(self, value: str) -> None: self._port_type_setting = value
    @property
    def default_value(self) -> Any: return self._default_value_setting
    @property
    def default_value_setting(self) -> Any: return self._default_value_setting
    @default_value_setting.setter
    def default_value_setting(self, value: Any) -> None: self._default_value_setting = value

    def validate(self) -> List[str]:
        return [("Port name is required")] if not self._port_name else []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"value": self._default_value_setting}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"port_name": self._port_name, "port_type_setting": self._port_type_setting,
                "description": self._description, "default_value": self._default_value_setting}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._port_name = properties.get("port_name", "input")
        self._port_type_setting = properties.get("port_type_setting", "ANY")
        self._description = properties.get("description", "")
        self._default_value_setting = properties.get("default_value")


class SubgraphOutputNode(BaseNode):
    """Subgraph output parameter."""
    node_type: str = "subgraph_output"
    display_name: str = "Subgraph Output"
    node_category: str = "Subgraphs"
    node_color: str = "#F44336"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, port_name: str = "output",
                 port_type_setting: str = "ANY", description: str = "") -> None:
        self._port_name: str = port_name
        self._port_type_setting: str = port_type_setting
        self._description: str = description
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        pt = PortType[self._port_type_setting] if self._port_type_setting in PortType.__members__ else PortType.ANY
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="value", port_type=pt, description=self._description or "Subgraph output value", required=False))

    @property
    def port_name(self) -> str: return self._port_name
    @port_name.setter
    def port_name(self, value: str) -> None: self._port_name = value
    @property
    def port_type_setting(self) -> str: return self._port_type_setting
    @port_type_setting.setter
    def port_type_setting(self, value: str) -> None: self._port_type_setting = value

    def validate(self) -> List[str]:
        return ["Port name is required"] if not self._port_name else []

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"value": inputs.get("value")}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"port_name": self._port_name, "port_type_setting": self._port_type_setting, "description": self._description}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._port_name = properties.get("port_name", "output")
        self._port_type_setting = properties.get("port_type_setting", "ANY")
        self._description = properties.get("description", "")


# ===========================================================================
# RUN AUTOMATION NODE
# ===========================================================================

class RunAutomationNode(BaseNode):
    """Run another automation as a sub-automation."""
    node_type: str = "run_automation"
    display_name: str = "Run Automation"
    node_category: str = "Subgraphs"
    node_color: str = "#00897B"

    # Mapping from input definition type strings to PortType enum values
    _TYPE_MAP: Dict[str, PortType] = {
        "STRING": PortType.STRING,
        "INTEGER": PortType.INTEGER,
        "FLOAT": PortType.FLOAT,
        "BOOLEAN": PortType.BOOLEAN,
        "LIST": PortType.LIST,
        "DICT": PortType.DICT,
        "ANY": PortType.ANY,
    }

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, automation_id: str = "",
                 automation_name: str = "", synchronous: bool = True) -> None:
        self._automation_id: str = automation_id
        self._automation_name: str = automation_name
        self._synchronous: bool = synchronous
        self._input_defs: List[Dict[str, Any]] = []
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        # Only add the generic parameters port if no input definitions are set
        if not self._input_defs:
            self.add_input_port(InputPort(name="parameters", port_type=PortType.DICT, description="Parameters to pass to the automation", required=False))
        else:
            self._setup_dynamic_ports()
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="execution_id", port_type=PortType.STRING, description="Execution ID of the child automation"))
        self.add_output_port(OutputPort(name="success", port_type=PortType.BOOLEAN, description="Whether the child automation succeeded (sync only)"))
        self.add_output_port(OutputPort(name="output", port_type=PortType.STRING, description="Captured stdout from the child automation (sync only)"))
        self.add_output_port(OutputPort(name="error", port_type=PortType.STRING, description="Error message if the child automation failed"))

    def _setup_dynamic_ports(self) -> None:
        """Add individual typed input ports from the target automation's input definitions."""
        for defn in self._input_defs:
            port_type = self._TYPE_MAP.get(defn.get("type", "ANY"), PortType.ANY)
            self.add_input_port(InputPort(
                name=defn["name"],
                port_type=port_type,
                description=defn.get("description", ""),
                required=defn.get("required", True),
                default_value=defn.get("default_value"),
            ))

    @property
    def automation_id(self) -> str: return self._automation_id
    @automation_id.setter
    def automation_id(self, value: str) -> None: self._automation_id = value
    @property
    def automation_name(self) -> str: return self._automation_name
    @automation_name.setter
    def automation_name(self, value: str) -> None: self._automation_name = value
    @property
    def synchronous(self) -> bool: return self._synchronous
    @synchronous.setter
    def synchronous(self, value: bool) -> None: self._synchronous = value

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._automation_id:
            errors.append("Target automation must be selected")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        props: Dict[str, Any] = {
            "automation_id": self._automation_id,
            "automation_name": self._automation_name,
            "synchronous": self._synchronous,
        }
        if self._input_defs:
            props["_input_defs"] = self._input_defs
        return props

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._automation_id = properties.get("automation_id", "")
        self._automation_name = properties.get("automation_name", "")
        self._synchronous = properties.get("synchronous", True)
        self._input_defs = properties.get("_input_defs", [])
        # Rebuild ports if we have input definitions
        if self._input_defs:
            self.remove_input_port("parameters")
            self._setup_dynamic_ports()


# ===========================================================================
# INCIDENT VARIABLE NODES (NEW FOR VP2)
# ===========================================================================

class GetIncidentVarNode(BaseNode):
    """Get an incident variable from the runtime context."""
    node_type: str = "get_incident_var"
    display_name: str = "Get Incident Var"
    node_category: str = "Incident"
    node_color: str = "#E91E63"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, variable_name: str = "",
                 default_value: Any = None) -> None:
        self._variable_name: str = variable_name
        self._default_value: Any = default_value
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="variable_name", port_type=PortType.STRING, description="Incident variable name", required=False))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="value", port_type=PortType.ANY, description="The variable value"))
        self.add_output_port(OutputPort(name="exists", port_type=PortType.BOOLEAN, description="Whether the variable exists"))

    @property
    def variable_name(self) -> str: return self._variable_name
    @variable_name.setter
    def variable_name(self, value: str) -> None: self._variable_name = value
    @property
    def default_value(self) -> Any: return self._default_value
    @default_value.setter
    def default_value(self, value: Any) -> None: self._default_value = value

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._variable_name:
            p = self.get_input_port("variable_name")
            if p and not p.is_connected(): errors.append("Incident variable name must be configured or provided via input")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        vn = inputs.get("variable_name", self._variable_name)
        if not vn: raise ValueError("No incident variable name specified")
        return {"value": self._default_value, "exists": False}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"variable_name": self._variable_name, "default_value": self._default_value}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._variable_name = properties.get("variable_name", "")
        self._default_value = properties.get("default_value", None)


class SetIncidentVarNode(BaseNode):
    """Set an incident variable in the runtime context."""
    node_type: str = "set_incident_var"
    display_name: str = "Set Incident Var"
    node_category: str = "Incident"
    node_color: str = "#E91E63"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, variable_name: str = "") -> None:
        self._variable_name: str = variable_name
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="variable_name", port_type=PortType.STRING, description="Incident variable name", required=False))
        self.add_input_port(InputPort(name="value", port_type=PortType.ANY, description="Value to store", required=True))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="success", port_type=PortType.BOOLEAN, description="Whether set succeeded"))

    @property
    def variable_name(self) -> str: return self._variable_name
    @variable_name.setter
    def variable_name(self, value: str) -> None: self._variable_name = value

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._variable_name:
            p = self.get_input_port("variable_name")
            if p and not p.is_connected(): errors.append("Incident variable name must be configured or provided via input")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        vn = inputs.get("variable_name", self._variable_name)
        if not vn: raise ValueError("No incident variable name specified")
        return {"success": True}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"variable_name": self._variable_name}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._variable_name = properties.get("variable_name", "")


class GetIncidentDataNode(BaseNode):
    """Get all incident data from the runtime context."""
    node_type: str = "get_incident_data"
    display_name: str = "Get Incident Data"
    node_category: str = "Incident"
    node_color: str = "#E91E63"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, incident_id: str = "") -> None:
        self._incident_id: str = incident_id
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="incident_id", port_type=PortType.STRING, description="Incident identifier", required=False))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="data", port_type=PortType.DICT, description="Full incident data"))
        self.add_output_port(OutputPort(name="exists", port_type=PortType.BOOLEAN, description="Whether the incident exists"))

    @property
    def incident_id(self) -> str: return self._incident_id
    @incident_id.setter
    def incident_id(self, value: str) -> None: self._incident_id = value

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._incident_id:
            p = self.get_input_port("incident_id")
            if p and not p.is_connected(): errors.append("Incident ID must be configured or provided via input")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        iid = inputs.get("incident_id", self._incident_id)
        if not iid: raise ValueError("No incident ID specified")
        return {"data": {}, "exists": False}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"incident_id": self._incident_id}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._incident_id = properties.get("incident_id", "")


# ===========================================================================
# SOAS APPLICATION-LEVEL VARIABLE NODES (NEW)
# ===========================================================================

class GetSOASVarNode(BaseNode):
    """Get an application-level SOAS variable (permission-restricted)."""
    node_type: str = "get_soas_var"
    display_name: str = "Get SOAS Var"
    node_category: str = "SOAS"
    node_color: str = "#9C27B0"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, variable_name: str = "",
                 default_value: Any = None) -> None:
        self._variable_name: str = variable_name
        self._default_value: Any = default_value
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="variable_name", port_type=PortType.STRING, description="SOAS variable name", required=False))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="value", port_type=PortType.ANY, description="The variable value"))
        self.add_output_port(OutputPort(name="exists", port_type=PortType.BOOLEAN, description="Whether the variable exists"))

    @property
    def variable_name(self) -> str: return self._variable_name
    @variable_name.setter
    def variable_name(self, value: str) -> None: self._variable_name = value
    @property
    def default_value(self) -> Any: return self._default_value
    @default_value.setter
    def default_value(self, value: Any) -> None: self._default_value = value

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._variable_name:
            p = self.get_input_port("variable_name")
            if p and not p.is_connected(): errors.append("SOAS variable name must be configured or provided via input")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        vn = inputs.get("variable_name", self._variable_name)
        if not vn: raise ValueError("No SOAS variable name specified")
        return {"value": self._default_value, "exists": False}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"variable_name": self._variable_name, "default_value": self._default_value}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._variable_name = properties.get("variable_name", "")
        self._default_value = properties.get("default_value", None)


class SetSOASVarNode(BaseNode):
    """Set an application-level SOAS variable (permission-restricted)."""
    node_type: str = "set_soas_var"
    display_name: str = "Set SOAS Var"
    node_category: str = "SOAS"
    node_color: str = "#9C27B0"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, variable_name: str = "") -> None:
        self._variable_name: str = variable_name
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="variable_name", port_type=PortType.STRING, description="SOAS variable name", required=False))
        self.add_input_port(InputPort(name="value", port_type=PortType.ANY, description="Value to store", required=True))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="success", port_type=PortType.BOOLEAN, description="Whether set succeeded"))

    @property
    def variable_name(self) -> str: return self._variable_name
    @variable_name.setter
    def variable_name(self, value: str) -> None: self._variable_name = value

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._variable_name:
            p = self.get_input_port("variable_name")
            if p and not p.is_connected(): errors.append("SOAS variable name must be configured or provided via input")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        vn = inputs.get("variable_name", self._variable_name)
        if not vn: raise ValueError("No SOAS variable name specified")
        return {"success": True}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"variable_name": self._variable_name}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._variable_name = properties.get("variable_name", "")


# ===========================================================================
# USER SECRET NODES
# ===========================================================================


class GetUserSecretNode(BaseNode):
    """Get a per-user secret value (read-only)."""
    node_type: str = "get_user_secret"
    display_name: str = "Get User Secret"
    node_category: str = "SOAS"
    node_color: str = "#E91E63"

    def __init__(self, node_id: Optional[str] = None, name: Optional[str] = None,
                 position: Optional[Position] = None, secret_name: str = "",
                 default_value: Any = None) -> None:
        self._secret_name: str = secret_name
        self._default_value: Any = default_value
        super().__init__(node_id, name, position)

    def _setup_ports(self) -> None:
        self.add_input_port(InputPort(name="exec_in", port_type=PortType.FLOW, description="Execution flow input", required=False))
        self.add_input_port(InputPort(name="secret_name", port_type=PortType.STRING, description="User secret name", required=False))
        self.add_output_port(OutputPort(name="exec_out", port_type=PortType.FLOW, description="Execution flow output"))
        self.add_output_port(OutputPort(name="value", port_type=PortType.ANY, description="The secret value"))
        self.add_output_port(OutputPort(name="exists", port_type=PortType.BOOLEAN, description="Whether the secret exists"))

    @property
    def secret_name(self) -> str: return self._secret_name
    @secret_name.setter
    def secret_name(self, value: str) -> None: self._secret_name = value
    @property
    def default_value(self) -> Any: return self._default_value
    @default_value.setter
    def default_value(self, value: Any) -> None: self._default_value = value

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self._secret_name:
            p = self.get_input_port("secret_name")
            if p and not p.is_connected(): errors.append("User secret name must be configured or provided via input")
        return errors

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        sn = inputs.get("secret_name", self._secret_name)
        if not sn: raise ValueError("No user secret name specified")
        return {"value": self._default_value, "exists": False}

    def _get_serializable_properties(self) -> Dict[str, Any]:
        return {"secret_name": self._secret_name, "default_value": self._default_value}

    def _load_serializable_properties(self, properties: Dict[str, Any]) -> None:
        self._secret_name = properties.get("secret_name", "")
        self._default_value = properties.get("default_value", None)
