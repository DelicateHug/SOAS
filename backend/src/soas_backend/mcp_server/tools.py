"""Tool registry — mirrors case-managment's mcp_server/tools/* split, but
collapsed into a single module for compactness.

Each tool is a thin pass-through to the SOAS REST API via SoasClient.
"""

from __future__ import annotations

from typing import Any

from .client import SoasClient


def register(mcp, client: SoasClient) -> None:
    """Attach every tool to the FastMCP instance."""

    # ------------------- Dashboards -------------------

    @mcp.tool()
    async def soas_list_dashboards() -> list[dict[str, Any]]:
        """List dashboards visible to the calling service token."""
        return await client.get("/dashboards")

    @mcp.tool()
    async def soas_get_dashboard(dashboard_id: str) -> dict[str, Any]:
        """Get a dashboard with all its widgets."""
        return await client.get(f"/dashboards/{dashboard_id}")

    @mcp.tool()
    async def soas_render_widget(widget_type: str, config: dict[str, Any], title: str = "Preview") -> dict[str, Any]:
        """Run a widget query without persisting (live preview)."""
        return await client.post(
            "/dashboards/render-widget",
            json={"title": title, "widget_type": widget_type, "config": config},
        )

    # ------------------- Saved queries -------------------

    @mcp.tool()
    async def soas_list_saved_queries(only_mine: bool = False, favorited: bool = False) -> list[dict[str, Any]]:
        """List saved queries."""
        return await client.get("/saved-queries", only_mine=only_mine, favorited=favorited)

    @mcp.tool()
    async def soas_get_saved_query(query_id: str) -> dict[str, Any]:
        return await client.get(f"/saved-queries/{query_id}")

    @mcp.tool()
    async def soas_execute_saved_query(query_id: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a saved query with parameters."""
        return await client.post(
            f"/saved-queries/{query_id}/execute",
            json={"parameters": parameters or {}},
        )

    # ------------------- Alert categories -------------------

    @mcp.tool()
    async def soas_list_alert_categories() -> list[dict[str, Any]]:
        return await client.get("/alert-categories")

    # ------------------- SLAs -------------------

    @mcp.tool()
    async def soas_list_slas() -> list[dict[str, Any]]:
        return await client.get("/slas")

    @mcp.tool()
    async def soas_get_sla_snapshots(sla_key: str | None = None, days: int = 30) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"days": days}
        if sla_key:
            params["sla_key"] = sla_key
        return await client.get("/slas/snapshots", **params)

    # ------------------- Assets -------------------

    @mcp.tool()
    async def soas_list_assets(asset_type: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if asset_type:
            params["asset_type"] = asset_type
        return await client.get("/assets", **params)

    @mcp.tool()
    async def soas_detect_asset(asset_id: str, timeframe: str = "last_30d") -> dict[str, Any]:
        """Find recent incidents that reference this asset."""
        return await client.get(f"/assets/{asset_id}/detect", timeframe=timeframe)

    # ------------------- AI chats -------------------

    @mcp.tool()
    async def soas_list_ai_chats(case_id: str | None = None, incident_id: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if case_id:
            params["case_id"] = case_id
        if incident_id:
            params["incident_id"] = incident_id
        return await client.get("/ai/chats", **params)

    @mcp.tool()
    async def soas_create_ai_chat(name: str, case_id: str | None = None, incident_id: str | None = None) -> dict[str, Any]:
        return await client.post(
            "/ai/chats",
            json={"name": name, "case_id": case_id, "incident_id": incident_id},
        )

    @mcp.tool()
    async def soas_send_ai_chat_message(chat_id: str, content: str, model: str | None = None) -> dict[str, Any]:
        return await client.post(
            f"/ai/chats/{chat_id}/send",
            json={"content": content, "model": model},
        )

    @mcp.tool()
    async def soas_list_ai_actions(page_key: str) -> list[dict[str, Any]]:
        return await client.get("/ai/actions", page_key=page_key)

    @mcp.tool()
    async def soas_execute_ai_action(action_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return await client.post(
            f"/ai/actions/{action_id}/execute",
            json={"context": context or {}},
        )

    # ------------------- Token usage / job ticks (read-only) -------------------

    @mcp.tool()
    async def soas_get_job_ticks(job_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Scheduler decision audit for a scheduled job."""
        return await client.get(f"/jobs/{job_id}/ticks", limit=limit)
