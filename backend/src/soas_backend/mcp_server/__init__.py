"""SOAS Python MCP sidecar (Phase 9 of the case-managment port).

Mirrors case-managment's mcp_server package layout. Exposes the SOAS
surfaces added in Phases 2-8 (dashboards, saved_queries, ai_chats,
ai_actions, slas, alert_categories, assets) via FastMCP, calling back
to the SOAS REST API via a service token.

Run with: `python -m soas_backend.mcp_server`
"""

__all__ = ["server"]
