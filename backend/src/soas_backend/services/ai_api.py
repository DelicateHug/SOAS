"""ai_api — direct Anthropic SDK wrapper for worker-driven AI.

Used by Celery tasks (scheduled jobs, batch ops, automation agent
nodes). API key is read from an encrypted user secret or app setting.
Token usage is captured directly from the SDK response.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.services.token_usage_service import TokenUsageService

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 180
DEFAULT_MAX_TOKENS = 4096

MODEL_ALIASES = {
    "opus": "claude-opus-4-7",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5",
}


class AnthropicAPIError(RuntimeError):
    """Raised when SDK call fails or returns no content."""


class AnthropicAPIRunner:
    """Wrapper around the Anthropic Python SDK.

    Use:
        runner = AnthropicAPIRunner(db, api_key="sk-...")
        result = await runner.run(prompt="...", model="sonnet", caller="automation_agent_node")
    """

    def __init__(self, db: AsyncSession, api_key: str):
        if not api_key:
            raise AnthropicAPIError("Anthropic API key is required")
        self.db = db
        self.api_key = api_key
        self.token_svc = TokenUsageService(db)

    async def run(
        self,
        *,
        prompt: str,
        model: str = "sonnet",
        caller: str,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        user_id: UUID | None = None,
        target_id: UUID | None = None,
        target_kind: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Invoke the Anthropic Messages API and return {"content": str, "usage": dict, ...}."""
        # Late import so this module is light when AI features are unused.
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise AnthropicAPIError(
                "Anthropic SDK not installed. Add 'anthropic>=0.40' to backend dependencies."
            ) from e

        resolved_model = MODEL_ALIASES.get(model, model)
        client = AsyncAnthropic(
            api_key=self.api_key,
            timeout=timeout_s,
            default_headers=extra_headers or {},
        )

        start = time.monotonic()
        try:
            message = await client.messages.create(
                model=resolved_model,
                max_tokens=max_tokens,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise AnthropicAPIError(f"Anthropic SDK error: {e}") from e

        duration_ms = int((time.monotonic() - start) * 1000)

        # Extract text content. Messages API returns a list of content blocks.
        parts: list[str] = []
        for block in message.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        content = "".join(parts)

        usage = getattr(message, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
        cache_create = int(getattr(usage, "cache_creation_input_tokens", 0) or 0) if usage else 0
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0) if usage else 0

        await self.token_svc.record(
            source="api",
            caller=caller,
            model=resolved_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_create_tokens=cache_create,
            cache_read_tokens=cache_read,
            cost_usd=None,  # Let the service estimate from the pricing table.
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
            },
            "model": resolved_model,
            "duration_ms": duration_ms,
            "stop_reason": getattr(message, "stop_reason", None),
        }
