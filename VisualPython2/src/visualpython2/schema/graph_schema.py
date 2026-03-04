"""Pydantic models for validating graph JSON from the frontend."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class PortConnectionSchema(BaseModel):
    source_node_id: str
    source_port_name: str
    target_node_id: str
    target_port_name: str


class InputPortSchema(BaseModel):
    name: str
    type: str
    description: str = ""
    required: bool = False
    default_value: Any = None
    inline_value: Any = None
    connection: Optional[PortConnectionSchema] = None


class OutputPortSchema(BaseModel):
    name: str
    type: str
    description: str = ""
    connections: list[PortConnectionSchema] = []


class NodeSchema(BaseModel):
    id: str
    type: str
    name: str
    position: dict[str, float]
    input_ports: list[InputPortSchema] = []
    output_ports: list[OutputPortSchema] = []
    properties: dict[str, Any] = {}
    custom_color: Optional[str] = None
    comment: Optional[str] = None


class GraphMetadataSchema(BaseModel):
    name: str = "Untitled Graph"
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    tags: list[str] = []
    trigger_tags: list[str] = []
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    flow_entry_points: list[dict[str, str]] = []
    flow_exit_points: list[dict[str, str]] = []


class ConnectionSchema(BaseModel):
    source_node_id: str
    source_port_name: str
    target_node_id: str
    target_port_name: str


class GraphDataSchema(BaseModel):
    id: str
    metadata: GraphMetadataSchema = Field(default_factory=GraphMetadataSchema)
    nodes: list[NodeSchema] = []
    connections: list[ConnectionSchema] = []
    groups: list[dict[str, Any]] = []


class VisualPython2ProjectSchema(BaseModel):
    """Top-level schema for a VP2 project file."""
    format_version: str = "2.0.0"
    file_type: str = "visualpython2_project"
    graph: GraphDataSchema


class VisualPython1ProjectSchema(BaseModel):
    """Top-level schema for a VP1 project file (for backward compat)."""
    format_version: str = "1.0.0"
    file_type: str = "visualpython_project"
    graph: GraphDataSchema
