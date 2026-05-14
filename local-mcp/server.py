"""Local-only MCP server for SOAS.

Runs on the analyst's host machine, binds to 127.0.0.1:8766, and exposes a
curated set of SOAS read-tools to whatever `claude` CLI is also on the host.

Unlike the production MCP at mcp/ (Node, service-token-authenticated, listens on
all interfaces), this server:

  * Binds only to 127.0.0.1 (loopback). It is not reachable from the network.
  * Uses the analyst's own JWT (stored at ~/.soas/token) for SOAS API calls,
    so it inherits the analyst's exact RBAC. No service-token plumbing.
  * Provides the read-only surface that Claude Code most often needs:
    list incidents, get incident, list cases, get case, search wiki,
    run saved query, list automations.

Start it with:

    python -m local_mcp

or via the helper script `local-mcp.ps1` / `local-mcp.sh` in this directory.

Token bootstrap:

    # one-shot login (writes ~/.soas/token):
    python -m local_mcp login --base-url http://localhost:8000 --username admin
"""

from __future__ import annotations

import asyncio
import getpass
import json
import logging
import os
import sys
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

TOKEN_PATH = Path(os.path.expanduser("~/.soas/token"))
BASE_URL = os.environ.get("SOAS_BASE_URL", "http://localhost:8000")

logger = logging.getLogger("soas.local-mcp")
mcp = FastMCP("soas-local")


def _read_token() -> str:
    if not TOKEN_PATH.exists():
        raise RuntimeError(
            f"No token at {TOKEN_PATH}. Run: python -m local_mcp login"
        )
    return TOKEN_PATH.read_text().strip()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=BASE_URL.rstrip("/") + "/api/v1",
        headers={"Authorization": f"Bearer {_read_token()}"},
        timeout=15.0,
    )


@mcp.tool()
async def list_incidents(limit: int = 25) -> str:
    """List recent incidents (newest first). Returns JSON."""
    async with _client() as c:
        r = await c.get("/incidents", params={"per_page": limit})
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def get_incident(incident_id: str) -> str:
    """Get a single incident by id. Returns JSON."""
    async with _client() as c:
        r = await c.get(f"/incidents/{incident_id}")
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def list_cases(limit: int = 25) -> str:
    """List recent cases (newest first). Returns JSON."""
    async with _client() as c:
        r = await c.get("/cases", params={"per_page": limit})
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def get_case(case_id: str) -> str:
    """Get a single case by id. Returns JSON."""
    async with _client() as c:
        r = await c.get(f"/cases/{case_id}")
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def list_automations(limit: int = 25) -> str:
    """List automations. Returns JSON."""
    async with _client() as c:
        r = await c.get("/automations", params={"per_page": limit})
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def search_wiki(query: str, limit: int = 10) -> str:
    """Search wiki pages. Returns JSON list of hits."""
    async with _client() as c:
        r = await c.get("/wiki/search", params={"q": query, "limit": limit})
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def run_saved_query(query_id: str) -> str:
    """Run a saved query by id. Returns rows as JSON."""
    async with _client() as c:
        r = await c.post(f"/saved-queries/{query_id}/run", json={})
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


async def _login(base_url: str, username: str) -> None:
    """Bootstrap helper: log in once, write the JWT to ~/.soas/token."""
    password = getpass.getpass(f"password for {username}: ")
    async with httpx.AsyncClient(base_url=base_url.rstrip("/") + "/api/v1", timeout=15.0) as c:
        r = await c.post("/auth/login", json={"username": username, "password": password})
        r.raise_for_status()
        token = r.json()["access_token"]
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token)
    try:
        TOKEN_PATH.chmod(0o600)
    except Exception:
        pass
    print(f"Wrote token to {TOKEN_PATH}")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        # Usage: python -m local_mcp login [--base-url URL] [--username NAME]
        argv = sys.argv[2:]
        base = BASE_URL
        user = None
        i = 0
        while i < len(argv):
            if argv[i] == "--base-url" and i + 1 < len(argv):
                base = argv[i + 1]
                i += 2
            elif argv[i] == "--username" and i + 1 < len(argv):
                user = argv[i + 1]
                i += 2
            else:
                i += 1
        if not user:
            user = input("username: ").strip()
        asyncio.run(_login(base, user))
        return 0

    # Default: run the MCP server over stdio (what Claude Code expects)
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting local SOAS MCP (base_url=%s)", BASE_URL)
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
