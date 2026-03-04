"""Runtime helper for interactive user input in automation scripts.

Provides soas_input() which handles both interactive (test run) and
non-interactive (incident/job) execution contexts.  In interactive mode
it publishes an input request via Redis pub/sub and blocks until the
frontend responds.  In non-interactive mode it returns the default value
immediately.

Uses only stdlib + redis so it works in sandboxed subprocesses.
"""

import json
import os
import sys
import uuid

_INTERACTIVE = os.environ.get("SOAS_INTERACTIVE", "0") == "1"
_EXECUTION_ID = os.environ.get("SOAS_EXECUTION_ID", "")
_REDIS_URL = os.environ.get("REDIS_URL", "")

_redis_client = None


def _get_redis():
    """Lazily connect to Redis (only when interactive mode needs it)."""
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(_REDIS_URL)
    return _redis_client


def soas_input(
    node_id: str,
    prompt: str,
    default: str = "",
    timeout: int = 120,
) -> tuple:
    """Request user input, blocking until a response arrives or timeout.

    Args:
        node_id: The graph node ID (used for tracking).
        prompt: The prompt text to display to the user.
        default: Default value returned on timeout or in non-interactive mode.
        timeout: Seconds to wait for a response (interactive mode only).

    Returns:
        (value, cancelled) tuple.  *cancelled* is True when the user
        explicitly cancelled or the request timed out.
    """
    if not _INTERACTIVE or not _EXECUTION_ID or not _REDIS_URL:
        return (default, False)

    request_id = str(uuid.uuid4())
    pubsub_channel = f"execution:{_EXECUTION_ID}:output"
    response_key = f"execution:{_EXECUTION_ID}:input:{request_id}"

    pending_key = f"execution:{_EXECUTION_ID}:pending_input"

    try:
        r = _get_redis()

        request_payload = json.dumps({
            "type": "input_request",
            "request_id": request_id,
            "node_id": node_id,
            "prompt": prompt,
            "default": default,
        })

        # Store the request in a Redis key so the WebSocket can recover it
        # even if it subscribes after the pubsub message was published.
        r.set(pending_key, request_payload, ex=timeout + 30)
        r.sadd("executions:pending_input", _EXECUTION_ID)

        # Publish the input request so the frontend displays a prompt
        r.publish(pubsub_channel, request_payload)

        # Block until the frontend pushes a response or we time out
        result = r.blpop(response_key, timeout=timeout)

        if result is None:
            # Timeout — no response from the frontend
            return (default, True)

        # result is (key, value) from BLPOP
        _, raw = result
        data = json.loads(raw)

        if data.get("cancelled", False):
            return (default, True)

        return (data.get("value", default), False)

    except Exception as exc:
        # Redis unavailable or other error — fall back to default
        print(f"[soas_input] error: {exc}", file=sys.stderr)
        return (default, True)
    finally:
        # Clean up Redis keys
        try:
            r = _get_redis()
            r.delete(response_key, pending_key)
            r.srem("executions:pending_input", _EXECUTION_ID)
        except Exception:
            pass
