"""
Graph serialization for saving and loading VisualPython2 graphs to JSON.

Accepts three input formats:
  - v1 format  (format_version "1.0.0", file_type "visualpython_project")
  - v2 format  (format_version "2.0.0", file_type "visualpython2_project")
  - raw graph  (a plain dict with "nodes" and "connections" keys, no wrapper)

Always serializes *out* in v2 format.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from visualpython2.graph.graph_model import Graph
from visualpython2.nodes.registry import NodeRegistry


class SerializationError(Exception):
    """Raised when serialization or deserialization fails."""


class GraphSerializer:
    """Handles serialization and deserialization of VisualPython2 graphs.

    Reads v1 projects, v2 projects, and raw graph dicts.  Always writes
    v2 format.

    Example::

        serializer = GraphSerializer()
        serializer.save(graph, "my_project.vpy2")
        loaded = serializer.load("my_project.vpy2")
    """

    V1_FORMAT_VERSION = "1.0.0"
    V2_FORMAT_VERSION = "2.0.0"

    V1_FILE_TYPE = "visualpython_project"
    V2_FILE_TYPE = "visualpython2_project"

    def __init__(self, registry: Optional[NodeRegistry] = None) -> None:
        """
        Args:
            registry: Optional NodeRegistry used for creating nodes during
                deserialization.  If not provided, creates a new one with
                default nodes registered.
        """
        if registry is None:
            registry = NodeRegistry()
            registry.register_default_nodes()
        self._registry: NodeRegistry = registry

    # ------------------------------------------------------------------
    # Public API -- file-level convenience
    # ------------------------------------------------------------------

    def save(
        self,
        graph: Graph,
        file_path: Union[str, Path],
        pretty: bool = True,
    ) -> None:
        """Save a graph to a JSON file in v2 format.

        Auto-increments the workflow version and updates ``modified_at``.

        Args:
            graph: The graph to save.
            file_path: Destination file path.
            pretty: If *True*, format with indentation.

        Raises:
            SerializationError: If the file cannot be written.
        """
        try:
            graph.metadata.version = self._increment_version(graph.metadata.version)
            graph.metadata.modified_at = datetime.now().isoformat()

            # Auto-detect flow entry points from Start nodes
            if not graph.metadata.flow_entry_points:
                for node in graph.nodes:
                    if node.node_type == "start":
                        graph.metadata.flow_entry_points = [{"node_id": node.id}]
                        break

            data = self.serialize(graph)
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                if pretty:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(data, f, ensure_ascii=False)

            graph.mark_saved()

        except (OSError, IOError) as exc:
            raise SerializationError(
                f"Failed to save project to '{file_path}': {exc}"
            ) from exc

    def load(self, file_path: Union[str, Path]) -> Graph:
        """Load a graph from a JSON file (v1, v2, or raw).

        Args:
            file_path: Path to the input file.

        Returns:
            The loaded Graph.

        Raises:
            SerializationError: If the file cannot be read or parsed.
        """
        try:
            path = Path(file_path)
            with open(path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
            return self.deserialize(data)
        except json.JSONDecodeError as exc:
            raise SerializationError(
                f"Invalid JSON in '{file_path}': {exc}"
            ) from exc
        except (OSError, IOError) as exc:
            raise SerializationError(
                f"Failed to load project from '{file_path}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Core serialize / deserialize
    # ------------------------------------------------------------------

    def serialize(self, graph: Graph) -> Dict[str, Any]:
        """Serialize a graph to a v2 wrapper dict.

        Args:
            graph: The graph to serialize.

        Returns:
            A dict with ``format_version``, ``file_type``, and ``graph`` keys.
        """
        return {
            "format_version": self.V2_FORMAT_VERSION,
            "file_type": self.V2_FILE_TYPE,
            "graph": graph.to_dict(),
        }

    def deserialize(self, data: Dict[str, Any]) -> Graph:
        """Deserialize a graph from a dict.

        Accepts:
          1. **v2 format** -- ``file_type == "visualpython2_project"``
          2. **v1 format** -- ``file_type == "visualpython_project"``
          3. **Legacy / no file_type** -- has a ``"graph"`` key
          4. **Raw graph** -- has ``"nodes"`` and ``"connections"`` keys

        Args:
            data: The dict to deserialize.

        Returns:
            A fully populated Graph instance.

        Raises:
            SerializationError: If the data cannot be understood.
        """
        fmt = self._detect_format(data)

        if fmt == "v2":
            self._check_version_compatibility(
                data.get("format_version", self.V2_FORMAT_VERSION),
                expected_major=2,
            )
            graph_data = data.get("graph")
            if graph_data is None:
                raise SerializationError("Missing 'graph' field in v2 project data")

        elif fmt == "v1":
            self._check_version_compatibility(
                data.get("format_version", self.V1_FORMAT_VERSION),
                expected_major=1,
            )
            graph_data = data.get("graph")
            if graph_data is None:
                raise SerializationError("Missing 'graph' field in v1 project data")

        elif fmt == "legacy_wrapper":
            # Has a "graph" key but no recognized file_type -- treat as valid
            graph_data = data.get("graph")
            if graph_data is None:
                raise SerializationError("Missing 'graph' field in legacy project data")

        elif fmt == "raw":
            # The dict itself *is* the graph data
            graph_data = data

        else:
            raise SerializationError(
                f"Unrecognised project format. Keys present: {sorted(data.keys())}"
            )

        return Graph.from_dict(graph_data, self._create_node_from_dict)

    # ------------------------------------------------------------------
    # Format detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_format(data: Dict[str, Any]) -> str:
        """Return one of 'v2', 'v1', 'legacy_wrapper', 'raw', or 'unknown'."""
        file_type = data.get("file_type")

        if file_type == "visualpython2_project":
            return "v2"

        if file_type == "visualpython_project":
            return "v1"

        # No file_type but has a graph wrapper
        if "graph" in data:
            return "legacy_wrapper"

        # Raw graph dict (nodes + connections at top level)
        if "nodes" in data and "connections" in data:
            return "raw"

        return "unknown"

    # ------------------------------------------------------------------
    # Version compatibility
    # ------------------------------------------------------------------

    @staticmethod
    def _check_version_compatibility(
        version: str,
        expected_major: int,
    ) -> None:
        """Validate that *version* is compatible with *expected_major*.

        Only the major component must match; minor/patch differences are
        tolerated.

        Raises:
            SerializationError: If the major version is wrong or the
                string cannot be parsed.
        """
        try:
            major, _minor, _patch = (int(p) for p in version.split("."))
        except (ValueError, AttributeError) as exc:
            raise SerializationError(
                f"Invalid format version string: '{version}'"
            ) from exc

        if major != expected_major:
            raise SerializationError(
                f"Incompatible format version: {version}. "
                f"Expected major version {expected_major}."
            )

    # ------------------------------------------------------------------
    # Node factory
    # ------------------------------------------------------------------

    def _create_node_from_dict(self, node_data: Dict[str, Any]) -> Any:
        """Create a node instance from serialized data.

        Uses the node registry to look up the class, then delegates to
        that class's ``from_dict`` method.

        Args:
            node_data: Dict with at least a ``"type"`` key.

        Returns:
            A BaseNode subclass instance.

        Raises:
            SerializationError: If the node type is missing or unknown.
        """
        node_type = node_data.get("type")
        if not node_type:
            raise SerializationError("Node data missing 'type' field")

        node_type_info = self._registry.get_node_type(node_type)
        if node_type_info is None:
            raise SerializationError(f"Unknown node type: '{node_type}'")

        node_class = node_type_info.node_class
        return node_class.from_dict(node_data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _increment_version(version_str: str) -> str:
        """Increment the patch component of a semver version string."""
        try:
            parts = version_str.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            return ".".join(parts)
        except (ValueError, IndexError):
            return "1.0.1"


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

def save_graph(
    graph: Graph,
    file_path: Union[str, Path],
    pretty: bool = True,
    registry: Optional[NodeRegistry] = None,
) -> None:
    """Save a graph to a JSON file (v2 format).

    Args:
        graph: The graph to save.
        file_path: Destination file path.
        pretty: If *True*, format with indentation.
        registry: Optional NodeRegistry.

    Raises:
        SerializationError: If the file cannot be written.
    """
    serializer = GraphSerializer(registry)
    serializer.save(graph, file_path, pretty)


def load_graph(
    file_path: Union[str, Path],
    registry: Optional[NodeRegistry] = None,
) -> Graph:
    """Load a graph from a JSON file (v1, v2, or raw format).

    Args:
        file_path: Path to the input file.
        registry: Optional NodeRegistry.

    Returns:
        The loaded Graph.

    Raises:
        SerializationError: If the file cannot be read or parsed.
    """
    serializer = GraphSerializer(registry)
    return serializer.load(file_path)
