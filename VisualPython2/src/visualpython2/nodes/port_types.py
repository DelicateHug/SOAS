"""Port types and connection model for VisualPython2.

Ported from VisualPython with Qt dependencies removed.
Defines the type system for node connections.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from visualpython2.nodes.definitions import BaseNode


class PortType(Enum):
    """Defines the type of data a port can accept or produce."""
    ANY = auto()
    FLOW = auto()
    STRING = auto()
    INTEGER = auto()
    FLOAT = auto()
    BOOLEAN = auto()
    LIST = auto()
    DICT = auto()
    OBJECT = auto()


TYPE_COMPATIBILITY: Dict[PortType, List[PortType]] = {
    PortType.ANY: list(PortType),
    PortType.FLOW: [PortType.FLOW],
    PortType.STRING: [PortType.STRING, PortType.ANY],
    PortType.INTEGER: [PortType.INTEGER, PortType.FLOAT, PortType.ANY],
    PortType.FLOAT: [PortType.FLOAT, PortType.INTEGER, PortType.ANY],
    PortType.BOOLEAN: [PortType.BOOLEAN, PortType.ANY],
    PortType.LIST: [PortType.LIST, PortType.ANY],
    PortType.DICT: [PortType.DICT, PortType.ANY],
    PortType.OBJECT: [PortType.OBJECT, PortType.ANY],
}


def are_types_compatible(source_type: PortType, target_type: PortType) -> bool:
    if target_type == PortType.ANY or source_type == PortType.ANY:
        return True
    compatible_types = TYPE_COMPATIBILITY.get(target_type, [])
    return source_type in compatible_types


@dataclass
class Connection:
    source_node_id: str
    source_port_name: str
    target_node_id: str
    target_port_name: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "source_node_id": self.source_node_id,
            "source_port_name": self.source_port_name,
            "target_node_id": self.target_node_id,
            "target_port_name": self.target_port_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> Connection:
        return cls(
            source_node_id=data["source_node_id"],
            source_port_name=data["source_port_name"],
            target_node_id=data["target_node_id"],
            target_port_name=data["target_port_name"],
        )


class BasePort(ABC):
    def __init__(self, name: str, port_type: PortType = PortType.ANY, description: str = "") -> None:
        self._name = name
        self._port_type = port_type
        self._description = description
        self._node: Optional[BaseNode] = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def port_type(self) -> PortType:
        return self._port_type

    @property
    def description(self) -> str:
        return self._description

    @property
    def node(self) -> Optional[BaseNode]:
        return self._node

    @node.setter
    def node(self, value: Optional[BaseNode]) -> None:
        self._node = value

    def is_connected(self) -> bool:
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self._name,
            "type": self._port_type.name,
            "description": self._description,
        }


class InputPort(BasePort):
    def __init__(
        self,
        name: str,
        port_type: PortType = PortType.ANY,
        description: str = "",
        required: bool = True,
        default_value: Any = None,
        inline_value: Any = None,
    ) -> None:
        super().__init__(name, port_type, description)
        self._required = required
        self._default_value = default_value
        self._inline_value = inline_value
        self._connection: Optional[Connection] = None

    @property
    def required(self) -> bool:
        return self._required

    @property
    def default_value(self) -> Any:
        return self._default_value

    @default_value.setter
    def default_value(self, value: Any) -> None:
        self._default_value = value

    @property
    def inline_value(self) -> Any:
        return self._inline_value

    @inline_value.setter
    def inline_value(self, value: Any) -> None:
        self._inline_value = value

    def get_effective_value(self) -> Any:
        if self._inline_value is not None:
            return self._inline_value
        return self._default_value

    @property
    def connection(self) -> Optional[Connection]:
        return self._connection

    def is_connected(self) -> bool:
        return self._connection is not None

    def connect(self, connection: Connection) -> None:
        self._connection = connection

    def disconnect(self) -> Optional[Connection]:
        old = self._connection
        self._connection = None
        return old

    def can_accept_type(self, source_type: PortType) -> bool:
        if self._port_type == PortType.ANY:
            return True
        compatible = TYPE_COMPATIBILITY.get(self._port_type, [])
        return source_type in compatible or source_type == PortType.ANY

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "required": self._required,
            "default_value": self._default_value,
            "inline_value": self._inline_value,
            "connection": self._connection.to_dict() if self._connection else None,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> InputPort:
        port = cls(
            name=data["name"],
            port_type=PortType[data["type"]],
            description=data.get("description", ""),
            required=data.get("required", True),
            default_value=data.get("default_value"),
            inline_value=data.get("inline_value"),
        )
        if data.get("connection"):
            port._connection = Connection.from_dict(data["connection"])
        return port


class OutputPort(BasePort):
    def __init__(self, name: str, port_type: PortType = PortType.ANY, description: str = "") -> None:
        super().__init__(name, port_type, description)
        self._connections: List[Connection] = []

    @property
    def connections(self) -> List[Connection]:
        return self._connections.copy()

    def is_connected(self) -> bool:
        return len(self._connections) > 0

    def connect(self, connection: Connection) -> None:
        for existing in self._connections:
            if (existing.target_node_id == connection.target_node_id and
                    existing.target_port_name == connection.target_port_name):
                return
        self._connections.append(connection)

    def disconnect(self, target_node_id: str, target_port_name: str) -> Optional[Connection]:
        for i, conn in enumerate(self._connections):
            if conn.target_node_id == target_node_id and conn.target_port_name == target_port_name:
                return self._connections.pop(i)
        return None

    def disconnect_all(self) -> List[Connection]:
        connections = self._connections.copy()
        self._connections.clear()
        return connections

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["connections"] = [conn.to_dict() for conn in self._connections]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OutputPort:
        port = cls(
            name=data["name"],
            port_type=PortType[data["type"]],
            description=data.get("description", ""),
        )
        for conn_data in data.get("connections", []):
            port._connections.append(Connection.from_dict(conn_data))
        return port
