"""ai_subprocess — shell out to the local `claude` CLI.

Used by user-driven AI features (Case Chat, AI Actions, Query Builder,
Widget Builder). The CLI reuses the analyst's own Claude Code auth so no
API key plumbing is needed. Token usage is parsed from --output-format
json and persisted via TokenUsageService.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import tempfile
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.services.token_usage_service import TokenUsageService

logger = logging.getLogger(__name__)

# Default timeout for any single CLI invocation
DEFAULT_TIMEOUT_S = 180

# Model aliases mapping: short name → CLI argument. Pinned IDs go through as-is.
MODEL_ALIASES = {
    "opus": "claude-opus-4-7",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5",
}


class ClaudeCLIError(RuntimeError):
    """Raised when the CLI returns a non-zero exit or unparseable output."""


class ClaudeCLIRunner:
    """Lightweight wrapper around the `claude` CLI.

    Use:
        runner = ClaudeCLIRunner(db)
        result = await runner.run(prompt="...", model="sonnet", caller="case_chat")
        # result = {"content": "...", "usage": {...}}
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.token_svc = TokenUsageService(db)

    async def run(
        self,
        *,
        prompt: str,
        model: str = "sonnet",
        caller: str,
        system: str | None = None,
        allowed_tools: list[str] | None = None,
        mcp_config_path: str | None = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        user_id: UUID | None = None,
        target_id: UUID | None = None,
        target_kind: str | None = None,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Invoke the CLI and return {"content": str, "usage": dict, "model": str, "raw": dict}."""
        cli_binary = os.environ.get("CLAUDE_CLI_BINARY", "claude")
        resolved_model = MODEL_ALIASES.get(model, model)

        # Build CLI argv. Using --output-format json gives us a structured envelope
        # with content + usage metadata.
        argv = [
            cli_binary,
            "--print",
            "--output-format",
            "json",
            "--model",
            resolved_model,
        ]
        if system:
            argv.extend(["--system-prompt", system])
        if allowed_tools is not None:
            argv.extend(["--allowed-tools", ",".join(allowed_tools)])
        if mcp_config_path:
            argv.extend(["--mcp-config", mcp_config_path])

        start = time.monotonic()
        logger.info("claude_cli: caller=%s model=%s argv=%s", caller, resolved_model, shlex.join(argv))
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        except FileNotFoundError as e:
            raise ClaudeCLIError(
                f"Claude CLI not found at '{cli_binary}'. Install Claude Code or set CLAUDE_CLI_BINARY."
            ) from e

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(prompt.encode("utf-8")),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError as e:
            proc.kill()
            raise ClaudeCLIError(f"Claude CLI timed out after {timeout_s}s") from e

        duration_ms = int((time.monotonic() - start) * 1000)

        if proc.returncode != 0:
            err = stderr_bytes.decode("utf-8", errors="replace").strip()
            raise ClaudeCLIError(
                f"Claude CLI exited {proc.returncode}: {err[:1000]}"
            )

        raw = stdout_bytes.decode("utf-8", errors="replace").strip()
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ClaudeCLIError(f"Claude CLI returned non-JSON output: {raw[:500]}") from e

        # CLI envelope shape (current): { "type": "result", "result": "...", "usage": {...},
        # "total_cost_usd": 0.0123, "session_id": "..." }.
        content = envelope.get("result") or envelope.get("content") or ""
        usage = envelope.get("usage") or {}
        cost_usd = envelope.get("total_cost_usd")

        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        cache_create = int(usage.get("cache_creation_input_tokens") or 0)
        cache_read = int(usage.get("cache_read_input_tokens") or 0)

        # Best-effort token usage row. Never blocks the response.
        await self.token_svc.record(
            source="cli",
            caller=caller,
            model=resolved_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_create_tokens=cache_create,
            cache_read_tokens=cache_read,
            cost_usd=float(cost_usd) if cost_usd is not None else None,
            user_id=user_id,
            target_id=target_id,
            target_kind=target_kind,
            duration_ms=duration_ms,
        )

        return {
            "content": content,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_create_tokens": cache_create,
                "cache_read_tokens": cache_read,
                "cost_usd": float(cost_usd) if cost_usd is not None else None,
            },
            "model": resolved_model,
            "duration_ms": duration_ms,
            "raw": envelope,
        }


def write_mcp_config(servers: dict[str, dict[str, Any]]) -> str:
    """Write a temp MCP config file the CLI can consume via --mcp-config.

    Returns the path. Caller is responsible for cleanup via Path(...).unlink().
    """
    fd, path = tempfile.mkstemp(prefix="soas_mcp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"mcpServers": servers}, f)
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    return path
