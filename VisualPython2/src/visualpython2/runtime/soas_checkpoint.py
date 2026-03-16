"""Runtime checkpoint helpers for split-at-Input-node execution.

Provides save_checkpoint() and load_checkpoint() which serialize/restore
all live variable state to Redis between segments.  When an Input node
is reached the subprocess saves state and exits with code 42.  The
orchestrator (worker) then waits for user input, stores the response,
and launches a new subprocess that loads the checkpoint and continues.

Uses pickle for broad type coverage + HMAC for integrity.
"""

import hashlib
import hmac
import json
import os
import pickle
import sys
import uuid

_EXECUTION_ID = os.environ.get("SOAS_EXECUTION_ID", "")
_REDIS_URL = os.environ.get("REDIS_URL", "")
_INTERACTIVE = os.environ.get("SOAS_INTERACTIVE", "0") == "1"
_HMAC_KEY = os.environ.get("SOAS_EXECUTION_ID", "fallback").encode()

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(_REDIS_URL)
    return _redis_client


def _sign(data: bytes) -> str:
    return hmac.new(_HMAC_KEY, data, hashlib.sha256).hexdigest()


def save_checkpoint(
    segment_index: int,
    state: dict,
    node_id: str,
    prompt: str,
    default: str = "",
    timeout: int = 120,
) -> None:
    """Save variable state to Redis, publish input_request, and sys.exit(42).

    This function NEVER returns — it terminates the subprocess.

    Args:
        segment_index: The ordinal of the current segment (0-based).
        state: Dict of {variable_name: value} to preserve.
        node_id: The Input node ID (for tracking).
        prompt: The prompt text to display.
        default: Default value if input is cancelled/timed out.
        timeout: Seconds before the input request expires.
    """
    if not _INTERACTIVE or not _EXECUTION_ID or not _REDIS_URL:
        # Non-interactive: return default immediately.
        # We can't split in non-interactive mode, so just set the values
        # in the caller's namespace and continue.  This path is handled
        # by the emitter: it falls back to a non-interactive stub.
        return

    try:
        r = _get_redis()

        # Pickle the state
        pickled = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
        sig = _sign(pickled)

        state_key = f"execution:{_EXECUTION_ID}:checkpoint_state"
        meta_key = f"execution:{_EXECUTION_ID}:checkpoint_meta"
        pending_key = f"execution:{_EXECUTION_ID}:pending_input"
        pubsub_channel = f"execution:{_EXECUTION_ID}:output"

        ttl = max(timeout + 300, 600)  # At least 10 min

        # Store state + metadata
        r.set(state_key, pickled, ex=ttl)
        meta = json.dumps({
            "segment_index": segment_index,
            "node_id": node_id,
            "signature": sig,
            "variable_names": list(state.keys()),
        })
        r.set(meta_key, meta, ex=ttl)

        # Build input request (same format as the old soas_input)
        request_id = str(uuid.uuid4())
        request_payload = json.dumps({
            "type": "input_request",
            "request_id": request_id,
            "node_id": node_id,
            "prompt": prompt,
            "default": default,
            "segment_index": segment_index,
        })

        # Store pending input info (includes request_id for response routing)
        pending_data = json.dumps({
            "request_id": request_id,
            "node_id": node_id,
            "segment_index": segment_index,
            "prompt": prompt,
            "default": default,
        })
        r.set(pending_key, request_payload, ex=ttl)
        r.sadd("executions:pending_input", _EXECUTION_ID)

        # Publish the request to the frontend
        r.publish(pubsub_channel, request_payload)

    except Exception as exc:
        print(f"[soas_checkpoint] save error: {exc}", file=sys.stderr)

    # Always exit with 42 to signal "waiting for input"
    sys.exit(42)


def load_checkpoint() -> dict:
    """Load the checkpoint state from Redis.

    Called at the start of a resumed segment.  Returns the restored
    variable dict (including ``__input_value__`` and ``__input_cancelled__``
    injected by the orchestrator before resume).

    Returns:
        Dict of {variable_name: value}.
    """
    if not _EXECUTION_ID or not _REDIS_URL:
        return {}

    try:
        r = _get_redis()

        state_key = f"execution:{_EXECUTION_ID}:checkpoint_state"
        meta_key = f"execution:{_EXECUTION_ID}:checkpoint_meta"

        pickled = r.get(state_key)
        meta_raw = r.get(meta_key)

        if not pickled or not meta_raw:
            print("[soas_checkpoint] no checkpoint found", file=sys.stderr)
            return {}

        if isinstance(meta_raw, bytes):
            meta_raw = meta_raw.decode("utf-8")
        meta = json.loads(meta_raw)

        # Verify HMAC signature
        expected_sig = meta.get("signature", "")
        actual_sig = _sign(pickled)
        if not hmac.compare_digest(expected_sig, actual_sig):
            print("[soas_checkpoint] signature mismatch — state may be tampered", file=sys.stderr)
            return {}

        state = pickle.loads(pickled)

        # Clean up checkpoint keys (they're consumed)
        r.delete(state_key, meta_key)

        return state

    except Exception as exc:
        print(f"[soas_checkpoint] load error: {exc}", file=sys.stderr)
        return {}
