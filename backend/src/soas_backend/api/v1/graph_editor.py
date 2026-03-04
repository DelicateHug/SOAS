"""Graph editor endpoints - node catalog, validation, and compile preview."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from soas_backend.api.deps import require_permission
from visualpython2.compiler.code_generator import CodeGenerator
from visualpython2.nodes.registry import NodeRegistry
from visualpython2.schema.graph_schema import GraphDataSchema
from visualpython2.schema.node_catalog import generate_node_catalog
from visualpython2.serialization.graph_serializer import GraphSerializer

router = APIRouter(prefix="/graph-editor", tags=["graph-editor"])


# ------------------------------------------------------------------
# Response schemas
# ------------------------------------------------------------------


class NodeCatalogResponse(BaseModel):
    """Full node catalog for the frontend editor."""

    nodes: list[dict[str, Any]]
    categories: list[str]


class ValidationErrorItem(BaseModel):
    message: str
    line: int | None = None
    column: int | None = None
    code_snippet: str | None = None


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[ValidationErrorItem] = []


class NodeMapEntry(BaseModel):
    """Source map entry linking a node to its line range in generated code."""

    type: str
    label: str
    start_line: int
    end_line: int


class CompilePreviewResponse(BaseModel):
    code: str
    valid: bool
    errors: list[ValidationErrorItem] = []
    node_map: dict[str, NodeMapEntry] = {}


class GraphInput(BaseModel):
    """Graph JSON payload from the web editor."""

    graph: dict[str, Any] = Field(..., description="Raw graph JSON from the editor")


# ------------------------------------------------------------------
# Registry helper
# ------------------------------------------------------------------


def _get_registry() -> NodeRegistry:
    """Return a freshly initialised NodeRegistry with all default nodes."""
    registry = NodeRegistry()
    registry.register_default_nodes()
    return registry


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("", response_model=NodeCatalogResponse)
@router.get("/node-catalog", response_model=NodeCatalogResponse)
async def get_node_catalog(
    _: dict = Depends(require_permission("automation", "read")),
):
    """Return all node types with ports, properties, colors, and categories."""
    registry = _get_registry()
    catalog = generate_node_catalog(registry)
    categories = registry.get_categories()

    return NodeCatalogResponse(nodes=catalog, categories=categories)


@router.post("/validate", response_model=ValidateResponse)
async def validate_graph(
    body: GraphInput,
    _: dict = Depends(require_permission("automation", "read")),
):
    """Validate graph JSON structure without saving.

    Runs Pydantic validation on the graph schema and checks that all
    referenced node types exist in the registry.
    """
    errors: list[ValidationErrorItem] = []

    # 1. Schema validation via Pydantic
    try:
        GraphDataSchema(**body.graph)
    except Exception as exc:
        errors.append(ValidationErrorItem(message=f"Schema validation failed: {exc}"))
        return ValidateResponse(valid=False, errors=errors)

    # 2. Check that all node types are known
    registry = _get_registry()
    nodes = body.graph.get("nodes", [])
    for node in nodes:
        node_type = node.get("type", "")
        if not registry.is_registered(node_type):
            errors.append(
                ValidationErrorItem(
                    message=f"Unknown node type: '{node_type}' (node id: {node.get('id', '?')})"
                )
            )

    # 3. Check connections reference valid node IDs
    node_ids = {n.get("id") for n in nodes}
    for conn in body.graph.get("connections", []):
        src = conn.get("source_node_id")
        tgt = conn.get("target_node_id")
        if src and src not in node_ids:
            errors.append(
                ValidationErrorItem(message=f"Connection references unknown source node: {src}")
            )
        if tgt and tgt not in node_ids:
            errors.append(
                ValidationErrorItem(message=f"Connection references unknown target node: {tgt}")
            )

    return ValidateResponse(valid=len(errors) == 0, errors=errors)


@router.post("/compile-preview", response_model=CompilePreviewResponse)
async def compile_preview(
    body: GraphInput,
    _: dict = Depends(require_permission("automation", "read")),
):
    """Compile graph and return generated Python code without saving.

    This endpoint deserialises the graph, walks the node tree to produce
    Python source, then validates the generated code with the AST
    validator.
    """
    errors: list[ValidationErrorItem] = []

    # Validate schema first
    try:
        GraphDataSchema(**body.graph)
    except Exception as exc:
        return CompilePreviewResponse(
            code="",
            valid=False,
            errors=[ValidationErrorItem(message=f"Schema validation failed: {exc}")],
        )

    # Deserialise into a Graph instance
    registry = _get_registry()
    serializer = GraphSerializer(registry)
    try:
        graph = serializer.deserialize(body.graph)
    except Exception as exc:
        return CompilePreviewResponse(
            code="",
            valid=False,
            errors=[ValidationErrorItem(message=f"Deserialization failed: {exc}")],
        )

    # Generate Python code from the graph using CodeGenerator
    try:
        generator = CodeGenerator(graph)
        result = generator.generate()
    except Exception as exc:
        return CompilePreviewResponse(
            code="",
            valid=False,
            errors=[ValidationErrorItem(message=f"Code generation failed: {exc}")],
        )

    if not result.success:
        for err_msg in result.errors:
            errors.append(ValidationErrorItem(message=err_msg))

    # Build node source map for code-to-node traceability
    node_map = {
        nid: NodeMapEntry(**entry)
        for nid, entry in result.node_map.items()
    } if result.node_map else {}

    return CompilePreviewResponse(
        code=result.code,
        valid=result.success and result.ast_valid,
        errors=errors,
        node_map=node_map,
    )
