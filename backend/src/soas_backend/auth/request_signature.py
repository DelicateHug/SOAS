"""Per-request HMAC signature scheme.

The client and server agree on a session key at login time. Every request the client makes
must include two headers:

  X-SOAS-Timestamp: <unix seconds>
  X-SOAS-Signature: <hex hmac-sha256 of canonical string>

The canonical string is newline-joined:

  METHOD\n
  PATH\n
  QUERY_STRING_SORTED\n
  TIMESTAMP\n
  SHA256_HEX(BODY)

The server recomputes the HMAC from the wrapped session key and compares with
hmac.compare_digest. A 60s timestamp window stops replay attacks.

Why HMAC rather than encrypting the body: TLS already protects body secrecy in transit.
The threat we add coverage for is token theft / cookie theft → the attacker still cannot
sign a request without the session key (which never leaves browser memory).
"""

import hashlib
import hmac
import time
from urllib.parse import parse_qsl, urlencode

# Maximum tolerated drift between client clock and server clock, in seconds.
TIMESTAMP_WINDOW_SECONDS = 60

TIMESTAMP_HEADER = "x-soas-timestamp"
SIGNATURE_HEADER = "x-soas-signature"


def _canonical_query(query_string: str) -> str:
    """Sort the query string alphabetically so client and server agree on order."""
    if not query_string:
        return ""
    pairs = parse_qsl(query_string, keep_blank_values=True)
    pairs.sort()
    return urlencode(pairs)


def build_canonical_string(
    *, method: str, path: str, query_string: str, timestamp: str, body: bytes
) -> str:
    body_hash = hashlib.sha256(body or b"").hexdigest()
    return "\n".join(
        [
            method.upper(),
            path,
            _canonical_query(query_string),
            str(timestamp),
            body_hash,
        ]
    )


def sign(canonical: str, key: bytes) -> str:
    return hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def verify(*, presented: str, expected: str) -> bool:
    """Constant-time comparison so attackers can't time-out the signature."""
    if not presented or not expected:
        return False
    return hmac.compare_digest(presented, expected)


def timestamp_in_window(timestamp: str, *, now: float | None = None) -> bool:
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    now_s = now if now is not None else time.time()
    return abs(now_s - ts) <= TIMESTAMP_WINDOW_SECONDS
