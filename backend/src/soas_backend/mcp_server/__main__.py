"""Python MCP sidecar entrypoint.

Run with `python -m soas_backend.mcp_server`. Listens on
MCP_PYTHON_PORT (default 8766) — distinct from the Node sidecar on
8765 so the two can run side-by-side until parity is reached.
"""

from __future__ import annotations

import logging
import os

from .client import build_client_from_env
from .tools import register

logger = logging.getLogger(__name__)


def main() -> None:
    try:
        from fastmcp import FastMCP
    except ImportError:
        raise SystemExit(
            "fastmcp is not installed; add 'fastmcp>=2.0' to backend deps and rebuild."
        )

    client = build_client_from_env()
    mcp = FastMCP("soas-python")
    register(mcp, client)

    host = os.environ.get("MCP_PYTHON_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PYTHON_PORT", "8766"))
    transport = os.environ.get("MCP_PYTHON_TRANSPORT", "http").lower()

    logger.info("Starting soas-python MCP sidecar on %s:%s (transport=%s)", host, port, transport)
    if transport == "stdio":
        mcp.run()
    else:
        # FastMCP 2.x supports `run(transport="http", host=..., port=...)`.
        mcp.run(transport=transport, host=host, port=port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
