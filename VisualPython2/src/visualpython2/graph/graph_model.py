"""
Core graph data model for the VisualPython2 visual programming system.

Simplified port from VisualPython with no Qt dependencies and inline
connection management (no separate ConnectionModel).  Provides the Graph
class that holds nodes and connections, with cycle detection, topological
sorting, validation, group management, and serialization.
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple, TYPE_CHECKING

from visualpython2.nodes.port_types import (
    PortType,
    InputPort,
    OutputPort,
    Connection,
    are_types_compatible,
)

if TYPE_CHECKING:
    from visualpython2.nodes.definitions import BaseNode


# ---------------------------------------------------------------------------
# Enums & dataclasses
# ---------------------------------------------------------------------------

class GraphState(Enum):
    """Represents the current state of the graph."""

    IDLE = auto()
    """Graph is not being executed."""

    EXECUTING = auto()
    """Graph is currently executing nodes."""

    PAUSED = auto()
    """Graph execution is paused."""

    COMPLETED = auto()
    """Graph execution has completed."""

    ERROR = auto()
    """Graph execution encountered an error."""


@dataclass
class GraphMetadata:
    """Metadata for a graph including name, description, and timestamps."""

    name: str = "Untitled Graph"
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    flow_entry_points: List[Dict[str, str]] = field(default_factory=list)
    flow_exit_points: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to dictionary."""
        data: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "tags": self.tags.copy(),
        }
        if self.flow_entry_points:
            data["flow_entry_points"] = [ep.copy() for ep in self.flow_entry_points]
        if self.flow_exit_points:
            data["flow_exit_points"] = [ep.copy() for ep in self.flow_exit_points]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphMetadata":
        """Deserialize metadata from dictionary."""
        return cls(
            name=data.get("name", "Untitled Graph"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            version=data.get("version", "1.0.0"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            modified_at=data.get("modified_at", datetime.now().isoformat()),
            tags=list(data.get("tags", [])),
            flow_entry_points=[ep.copy() for ep in data.get("flow_entry_points", [])],
            flow_exit_points=[ep.copy() for ep in data.get("flow_exit_points", [])],
        )


@dataclass
class GraphStatistics:
    """Statistics about the graph structure."""

    node_count: int = 0
    connection_count: int = 0
    source_node_count: int = 0
    sink_node_count: int = 0
    max_depth: int = 0
    node_types: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize statistics to dictionary."""
        return {
            "node_count": self.node_count,
            "connection_count": self.connection_count,
            "source_node_count": self.source_node_count,
            "sink_node_count": self.sink_node_count,
            "max_depth": self.max_depth,
            "node_types": self.node_types.copy(),
        }


@dataclass
class NodeGroup:
    """A lightweight container for grouping related nodes.

    Unlike the VP1 NodeGroup which had GUI-oriented bounds and collapse
    logic, this version only tracks the logical grouping for
    serialization and compiler use.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Group"
    node_ids: Set[str] = field(default_factory=set)
    description: str = ""
    color: str = "#5C6BC0"

    # ------------------------------------------------------------------

    def contains_node(self, node_id: str) -> bool:
        return node_id in self.node_ids

    def add_node(self, node_id: str) -> None:
        self.node_ids.add(node_id)

    def remove_node(self, node_id: str) -> bool:
        if node_id in self.node_ids:
            self.node_ids.discard(node_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "node_ids": sorted(self.node_ids),
            "color": self.color,
        }
        if self.description:
            data["description"] = self.description
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeGroup":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Group"),
            node_ids=set(data.get("node_ids", [])),
            description=data.get("description", ""),
            color=data.get("color", "#5C6BC0"),
        )


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class Graph:
    """Central data model for the VisualPython2 visual programming system.

    Manages collections of nodes and connections with comprehensive query
    and manipulation methods.  Connection logic is implemented directly
    (no separate ConnectionModel).
    """

    def __init__(
        self,
        graph_id: Optional[str] = None,
        name: str = "Untitled Graph",
        description: str = "",
    ) -> None:
        self._id: str = graph_id or str(uuid.uuid4())
        self._metadata: GraphMetadata = GraphMetadata(name=name, description=description)
        self._state: GraphState = GraphState.IDLE
        self._modified: bool = False

        # Core storage
        self._nodes: Dict[str, "BaseNode"] = {}
        self._connections: List[Connection] = []

        # Node groups
        self._groups: Dict[str, NodeGroup] = {}

        # Error tracking
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._metadata.name

    @name.setter
    def name(self, value: str) -> None:
        self._metadata.name = value
        self._mark_modified()

    @property
    def description(self) -> str:
        return self._metadata.description

    @description.setter
    def description(self, value: str) -> None:
        self._metadata.description = value
        self._mark_modified()

    @property
    def metadata(self) -> GraphMetadata:
        return self._metadata

    @property
    def state(self) -> GraphState:
        return self._state

    @state.setter
    def state(self, value: GraphState) -> None:
        self._state = value

    @property
    def is_modified(self) -> bool:
        return self._modified

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    @property
    def is_empty(self) -> bool:
        return len(self._nodes) == 0

    # ------------------------------------------------------------------
    # Node Management
    # ------------------------------------------------------------------

    def add_node(self, node: "BaseNode") -> None:
        """Add a node to the graph.

        Raises:
            ValueError: If a node with the same ID already exists.
        """
        if node.id in self._nodes:
            raise ValueError(f"Node with ID '{node.id}' already exists in graph")
        self._nodes[node.id] = node
        self._mark_modified()

    def remove_node(self, node_id: str) -> Optional["BaseNode"]:
        """Remove a node and all its connections from the graph."""
        node = self._nodes.pop(node_id, None)
        if node is None:
            return None
        # Remove all connections involving this node
        self._connections = [
            c for c in self._connections
            if c.source_node_id != node_id and c.target_node_id != node_id
        ]
        # Also remove from any groups
        for group in self._groups.values():
            group.remove_node(node_id)
        self._mark_modified()
        return node

    def get_node(self, node_id: str) -> Optional["BaseNode"]:
        """Get a node by its ID."""
        return self._nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    @property
    def nodes(self) -> List["BaseNode"]:
        """Get a list of all nodes in the graph."""
        return list(self._nodes.values())

    def get_nodes_by_type(self, node_type: str) -> List["BaseNode"]:
        """Get all nodes of a specific type."""
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def iter_nodes(self) -> Iterator["BaseNode"]:
        return iter(self._nodes.values())

    # ------------------------------------------------------------------
    # Connection Management (inline -- no separate ConnectionModel)
    # ------------------------------------------------------------------

    def connect(
        self,
        source_node_id: str,
        source_port_name: str,
        target_node_id: str,
        target_port_name: str,
        validate: bool = True,
    ) -> Connection:
        """Create a connection between two node ports.

        Args:
            source_node_id: ID of the source node.
            source_port_name: Name of the source output port.
            target_node_id: ID of the target node.
            target_port_name: Name of the target input port.
            validate: Whether to validate before connecting.

        Returns:
            The created Connection.

        Raises:
            ValueError: If nodes/ports are not found or validation fails.
        """
        if validate:
            ok, err = self.can_connect(
                source_node_id, source_port_name, target_node_id, target_port_name
            )
            if not ok:
                raise ValueError(err)

        conn = Connection(
            source_node_id=source_node_id,
            source_port_name=source_port_name,
            target_node_id=target_node_id,
            target_port_name=target_port_name,
        )

        # Register connection on the port objects if we can resolve them
        source_node = self._nodes.get(source_node_id)
        target_node = self._nodes.get(target_node_id)
        if source_node is not None:
            out_port = source_node.get_output_port(source_port_name)
            if out_port is not None:
                out_port.connect(conn)
        if target_node is not None:
            in_port = target_node.get_input_port(target_port_name)
            if in_port is not None:
                in_port.connect(conn)

        self._connections.append(conn)
        self._mark_modified()
        return conn

    def disconnect(
        self,
        source_node_id: str,
        source_port_name: str,
        target_node_id: str,
        target_port_name: str,
    ) -> Optional[Connection]:
        """Remove a connection between two nodes."""
        for i, c in enumerate(self._connections):
            if (
                c.source_node_id == source_node_id
                and c.source_port_name == source_port_name
                and c.target_node_id == target_node_id
                and c.target_port_name == target_port_name
            ):
                removed = self._connections.pop(i)

                # Unregister from port objects
                source_node = self._nodes.get(source_node_id)
                target_node = self._nodes.get(target_node_id)
                if source_node is not None:
                    out_port = source_node.get_output_port(source_port_name)
                    if out_port is not None:
                        out_port.disconnect(target_node_id, target_port_name)
                if target_node is not None:
                    in_port = target_node.get_input_port(target_port_name)
                    if in_port is not None:
                        in_port.disconnect()

                self._mark_modified()
                return removed
        return None

    def can_connect(
        self,
        source_node_id: str,
        source_port_name: str,
        target_node_id: str,
        target_port_name: str,
    ) -> Tuple[bool, Optional[str]]:
        """Check whether a connection can be made without creating it.

        Returns:
            (can_connect, error_message)
        """
        # Self-connection check
        if source_node_id == target_node_id:
            return False, "Cannot connect a node to itself"

        source_node = self._nodes.get(source_node_id)
        target_node = self._nodes.get(target_node_id)
        if source_node is None:
            return False, f"Source node '{source_node_id}' not found"
        if target_node is None:
            return False, f"Target node '{target_node_id}' not found"

        out_port = source_node.get_output_port(source_port_name)
        in_port = target_node.get_input_port(target_port_name)
        if out_port is None:
            return False, f"Output port '{source_port_name}' not found on node '{source_node_id}'"
        if in_port is None:
            return False, f"Input port '{target_port_name}' not found on node '{target_node_id}'"

        # Type compatibility
        if not are_types_compatible(out_port.port_type, in_port.port_type):
            return (
                False,
                f"Incompatible types: {out_port.port_type.name} -> {in_port.port_type.name}",
            )

        # Duplicate check
        for c in self._connections:
            if (
                c.source_node_id == source_node_id
                and c.source_port_name == source_port_name
                and c.target_node_id == target_node_id
                and c.target_port_name == target_port_name
            ):
                return False, "Connection already exists"

        # Input port already connected check (only one connection per input,
        # except FLOW which can have fan-in in some designs -- keep strict
        # for now).
        if in_port.is_connected():
            return False, f"Input port '{target_port_name}' is already connected"

        # Cycle check -- would adding this edge create a cycle?
        if self._would_create_cycle(source_node_id, target_node_id):
            return False, "Connection would create a cycle"

        return True, None

    @property
    def connections(self) -> List[Connection]:
        """Get a list of all connections in the graph."""
        return list(self._connections)

    def get_outgoing_connections(self, node_id: str) -> List[Connection]:
        """Get all connections where *node_id* is the source."""
        return [c for c in self._connections if c.source_node_id == node_id]

    def get_incoming_connections(self, node_id: str) -> List[Connection]:
        """Get all connections where *node_id* is the target."""
        return [c for c in self._connections if c.target_node_id == node_id]

    def get_connections_for_port(
        self, node_id: str, port_name: str, *, is_input: bool = False
    ) -> List[Connection]:
        """Get connections for a specific port on a node.

        Args:
            node_id: The node ID.
            port_name: The port name to filter by.
            is_input: If True, match target port; if False, match source port.
        """
        if is_input:
            return [
                c
                for c in self._connections
                if c.target_node_id == node_id
                and c.target_port_name == port_name
            ]
        else:
            return [
                c
                for c in self._connections
                if c.source_node_id == node_id
                and c.source_port_name == port_name
            ]

    # ------------------------------------------------------------------
    # Graph Analysis
    # ------------------------------------------------------------------

    def get_source_nodes(self) -> List["BaseNode"]:
        """Get all nodes with no incoming connections (entry points)."""
        targets = {c.target_node_id for c in self._connections}
        return [n for n in self._nodes.values() if n.id not in targets]

    def get_sink_nodes(self) -> List["BaseNode"]:
        """Get all nodes with no outgoing connections."""
        sources = {c.source_node_id for c in self._connections}
        return [n for n in self._nodes.values() if n.id not in sources]

    # ------------------------------------------------------------------
    # Cycle Detection
    # ------------------------------------------------------------------

    def has_cycle(self) -> bool:
        """Check if the graph contains any cycles using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {nid: WHITE for nid in self._nodes}

        adj = self._build_adjacency_list()

        def dfs(nid: str) -> bool:
            color[nid] = GRAY
            for neighbour in adj.get(nid, []):
                if color[neighbour] == GRAY:
                    return True
                if color[neighbour] == WHITE and dfs(neighbour):
                    return True
            color[nid] = BLACK
            return False

        for nid in self._nodes:
            if color[nid] == WHITE:
                if dfs(nid):
                    return True
        return False

    def _would_create_cycle(self, source_id: str, target_id: str) -> bool:
        """Check if adding an edge source->target would create a cycle.

        Equivalent to asking: is there already a path from *target* to
        *source* in the current graph?
        """
        visited: Set[str] = set()
        queue: deque[str] = deque([target_id])
        while queue:
            current = queue.popleft()
            if current == source_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            for c in self._connections:
                if c.source_node_id == current and c.target_node_id not in visited:
                    queue.append(c.target_node_id)
        return False

    # ------------------------------------------------------------------
    # Topological Sort
    # ------------------------------------------------------------------

    def topological_sort(self) -> Optional[List["BaseNode"]]:
        """Return nodes in topological order, or None if graph has cycles.

        Uses Kahn's algorithm.
        """
        in_degree: Dict[str, int] = {nid: 0 for nid in self._nodes}
        adj: Dict[str, List[str]] = {nid: [] for nid in self._nodes}

        for c in self._connections:
            if c.source_node_id in adj and c.target_node_id in in_degree:
                adj[c.source_node_id].append(c.target_node_id)
                in_degree[c.target_node_id] += 1

        queue: deque[str] = deque(
            nid for nid, deg in in_degree.items() if deg == 0
        )
        order: List[str] = []

        while queue:
            nid = queue.popleft()
            order.append(nid)
            for neighbour in adj[nid]:
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)

        if len(order) != len(self._nodes):
            return None  # cycle detected

        return [self._nodes[nid] for nid in order]

    def get_topological_order(self) -> Optional[List["BaseNode"]]:
        """Alias for topological_sort()."""
        return self.topological_sort()

    # ------------------------------------------------------------------
    # Execution Order
    # ------------------------------------------------------------------

    def get_execution_order(self) -> List["BaseNode"]:
        """Get nodes in execution order (topological).

        Falls back to arbitrary order if the graph has cycles.
        """
        result = self.topological_sort()
        if result is None:
            return list(self._nodes.values())
        return result

    def get_flow_execution_order(
        self,
        start_node_ids: Optional[List[str]] = None,
    ) -> List["BaseNode"]:
        """Get nodes in execution order following only FLOW connections.

        Performs a DFS along FLOW-typed output ports starting from the
        given start nodes (or auto-detected source nodes).

        Args:
            start_node_ids: Optional explicit start node IDs.  If *None*,
                all source nodes (no incoming FLOW connections) are used.

        Returns:
            List of nodes in FLOW execution order.
        """
        # Build FLOW-only adjacency list
        flow_adj: Dict[str, List[str]] = {nid: [] for nid in self._nodes}
        flow_targets: Set[str] = set()
        for c in self._connections:
            source_node = self._nodes.get(c.source_node_id)
            if source_node is None:
                continue
            out_port = source_node.get_output_port(c.source_port_name)
            if out_port is not None and out_port.port_type == PortType.FLOW:
                flow_adj.setdefault(c.source_node_id, []).append(c.target_node_id)
                flow_targets.add(c.target_node_id)

        # Determine start nodes
        if start_node_ids is not None:
            starts = [nid for nid in start_node_ids if nid in self._nodes]
        else:
            # Nodes that are never a FLOW target
            starts = [nid for nid in self._nodes if nid not in flow_targets]

        visited: Set[str] = set()
        order: List["BaseNode"] = []

        def dfs(nid: str) -> None:
            if nid in visited:
                return
            visited.add(nid)
            node = self._nodes.get(nid)
            if node is not None:
                order.append(node)
            for neighbour in flow_adj.get(nid, []):
                dfs(neighbour)

        for sid in starts:
            dfs(sid)

        return order

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> List[str]:
        """Validate the entire graph.

        Returns:
            List of validation error messages.  Empty if valid.
        """
        errors: List[str] = []

        # Validate each node
        for node in self._nodes.values():
            if hasattr(node, "validate"):
                node_errors = node.validate()
                for error in node_errors:
                    errors.append(f"{node.name}: {error}")

        # Check for dangling connections
        for c in self._connections:
            if c.source_node_id not in self._nodes:
                errors.append(
                    f"Connection references missing source node '{c.source_node_id}'"
                )
            if c.target_node_id not in self._nodes:
                errors.append(
                    f"Connection references missing target node '{c.target_node_id}'"
                )

        # Check for cycles
        if self.has_cycle():
            errors.append("Graph contains cycles which may prevent execution")

        return errors

    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    # ------------------------------------------------------------------
    # Group Management
    # ------------------------------------------------------------------

    def add_group(self, group: NodeGroup) -> None:
        if group.id in self._groups:
            raise ValueError(f"Group with ID '{group.id}' already exists")
        self._groups[group.id] = group
        self._mark_modified()

    def remove_group(self, group_id: str) -> Optional[NodeGroup]:
        group = self._groups.pop(group_id, None)
        if group is not None:
            self._mark_modified()
        return group

    def get_group(self, group_id: str) -> Optional[NodeGroup]:
        return self._groups.get(group_id)

    @property
    def groups(self) -> List[NodeGroup]:
        return list(self._groups.values())

    def get_group_for_node(self, node_id: str) -> Optional[NodeGroup]:
        for group in self._groups.values():
            if group.contains_node(node_id):
                return group
        return None

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> GraphStatistics:
        node_types: Dict[str, int] = {}
        for node in self._nodes.values():
            node_types[node.node_type] = node_types.get(node.node_type, 0) + 1

        return GraphStatistics(
            node_count=self.node_count,
            connection_count=self.connection_count,
            source_node_count=len(self.get_source_nodes()),
            sink_node_count=len(self.get_sink_nodes()),
            max_depth=self._calculate_max_depth(),
            node_types=node_types,
        )

    def _calculate_max_depth(self) -> int:
        if self.is_empty:
            return 0
        source_nodes = self.get_source_nodes()
        if not source_nodes:
            return 0

        max_depth = 0
        for source in source_nodes:
            visited: Set[str] = set()
            queue: deque[Tuple[str, int]] = deque([(source.id, 0)])
            while queue:
                node_id, depth = queue.popleft()
                if node_id in visited:
                    continue
                visited.add(node_id)
                max_depth = max(max_depth, depth)
                for conn in self.get_outgoing_connections(node_id):
                    if conn.target_node_id not in visited:
                        queue.append((conn.target_node_id, depth + 1))
        return max_depth

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the graph to a dictionary."""
        data: Dict[str, Any] = {
            "id": self._id,
            "metadata": self._metadata.to_dict(),
            "nodes": [node.to_dict() for node in self._nodes.values()],
            "connections": [conn.to_dict() for conn in self._connections],
        }
        if self._groups:
            data["groups"] = [g.to_dict() for g in self._groups.values()]
        return data

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        node_factory: Callable[[Dict[str, Any]], "BaseNode"],
    ) -> "Graph":
        """Deserialize a graph from a dictionary.

        Args:
            data: Dictionary containing serialized graph data.
            node_factory: Callable that creates a BaseNode from a dict.

        Returns:
            A new Graph instance.
        """
        graph = cls(
            graph_id=data.get("id"),
            name=data.get("metadata", {}).get("name", "Untitled Graph"),
            description=data.get("metadata", {}).get("description", ""),
        )

        # Restore full metadata
        if "metadata" in data:
            graph._metadata = GraphMetadata.from_dict(data["metadata"])

        # Restore nodes
        for node_data in data.get("nodes", []):
            node = node_factory(node_data)
            graph.add_node(node)

        # Restore connections (skip validation -- the serialized state is
        # assumed to be consistent).
        for conn_data in data.get("connections", []):
            graph.connect(
                source_node_id=conn_data["source_node_id"],
                source_port_name=conn_data["source_port_name"],
                target_node_id=conn_data["target_node_id"],
                target_port_name=conn_data["target_port_name"],
                validate=False,
            )

        # Restore groups
        for group_data in data.get("groups", []):
            group = NodeGroup.from_dict(group_data)
            graph._groups[group.id] = group

        # Reset modified flag after loading
        graph._modified = False
        return graph

    # ------------------------------------------------------------------
    # Graph Operations
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all nodes, connections, and groups."""
        self._nodes.clear()
        self._connections.clear()
        self._groups.clear()
        self._mark_modified()

    def mark_saved(self) -> None:
        """Mark the graph as saved (not modified)."""
        self._modified = False

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _build_adjacency_list(self) -> Dict[str, List[str]]:
        adj: Dict[str, List[str]] = {nid: [] for nid in self._nodes}
        for c in self._connections:
            if c.source_node_id in adj:
                adj[c.source_node_id].append(c.target_node_id)
        return adj

    def _mark_modified(self) -> None:
        self._modified = True
        self._metadata.modified_at = datetime.now().isoformat()

    # ------------------------------------------------------------------
    # Dunder Methods
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Graph(id='{self._id[:8]}...', name='{self.name}', "
            f"nodes={self.node_count}, connections={self.connection_count})"
        )

    def __str__(self) -> str:
        return (
            f"Graph '{self.name}' with {self.node_count} nodes "
            f"and {self.connection_count} connections"
        )

    def __len__(self) -> int:
        return self.node_count

    def __contains__(self, node_or_id: Any) -> bool:
        if isinstance(node_or_id, str):
            return self.has_node(node_or_id)
        if hasattr(node_or_id, "id"):
            return self.has_node(node_or_id.id)
        return False

    def __iter__(self) -> Iterator["BaseNode"]:
        return iter(self._nodes.values())
