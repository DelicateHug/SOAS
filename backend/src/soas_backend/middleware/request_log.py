"""In-memory request and error log store.

Two ring buffers:
  - requests: stores recent request summaries (method, path, status, request_id)
  - errors:   stores requests that resulted in 4xx/5xx responses

A periodic cleanup task checks every few minutes. If no errors exist,
both buffers are cleared. This keeps memory bounded while retaining
context when errors are present for debugging.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class RequestRecord:
    request_id: str
    method: str
    path: str
    status_code: int
    duration_ms: float
    timestamp: float = field(default_factory=time.time)
    detail: str | None = None  # error detail if available


# Max entries per buffer - keeps memory usage predictable
MAX_REQUESTS = 2000
MAX_ERRORS = 500

_lock = threading.Lock()
_requests: deque[RequestRecord] = deque(maxlen=MAX_REQUESTS)
_errors: deque[RequestRecord] = deque(maxlen=MAX_ERRORS)


def record_request(rec: RequestRecord) -> None:
    """Store a request record. If status >= 400, also store in errors."""
    with _lock:
        _requests.append(rec)
        if rec.status_code >= 400:
            _errors.append(rec)


def get_requests() -> list[RequestRecord]:
    with _lock:
        return list(_requests)


def get_errors() -> list[RequestRecord]:
    with _lock:
        return list(_errors)


def get_stats() -> dict:
    """Return summary counts without copying full lists."""
    with _lock:
        return {
            "request_count": len(_requests),
            "error_count": len(_errors),
            "max_requests": MAX_REQUESTS,
            "max_errors": MAX_ERRORS,
        }


def cleanup_if_healthy() -> bool:
    """Clear both buffers if there are no errors. Returns True if cleared."""
    with _lock:
        if len(_errors) == 0:
            _requests.clear()
            return True
        return False
