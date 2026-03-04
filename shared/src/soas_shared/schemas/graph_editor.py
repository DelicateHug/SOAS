"""Graph editor schemas for the VisualPython2 node-based automation builder."""

from typing import Any
from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseSchema


class GraphSaveRequest(BaseSchema):
    graph_data: dict[str, Any]
    name: str | None = None
    description: str | None = None
    trigger_tags: list[str] | None = None


class GraphValidateRequest(BaseSchema):
    graph_data: dict[str, Any]


class GraphValidateResponse(BaseSchema):
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class GraphCompileResponse(BaseSchema):
    success: bool
    errors: list[str] = []
    warnings: list[str] = []
    generated_code: str | None = None


class NodeCatalogEntry(BaseSchema):
    type: str
    name: str
    category: str
    color: str
    description: str
    icon: str | None = None
    input_ports: list[dict[str, Any]] = []
    output_ports: list[dict[str, Any]] = []
    properties: list[dict[str, Any]] = []


class MockIncident(BaseSchema):
    """Mock incident data for test runs."""
    title: str = "Test Incident"
    severity: str = "medium"
    status: str = "investigating"
    tags: list[str] = []
    custom_vars: dict[str, Any] = {}


class TestRunRequest(BaseSchema):
    graph_data: dict[str, Any]
    parameters: dict[str, Any] = {}
    incident_id: UUID | None = None
    mock_incident: MockIncident | None = None
    timeout_seconds: int = Field(default=60, ge=5, le=300)
