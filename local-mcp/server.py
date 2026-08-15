"""Local-only MCP server for SOAS.

Spawned by Claude Code as a stdio subprocess. No network listener of its own — Claude
talks to it over stdin/stdout, and this process talks to the SOAS proxy over HTTPS.

Auth model (post-security-rework):

  * `python -m local_mcp login` does the full SOAS login flow (password, MFA if enabled,
    or OIDC redirect) and stores the resulting app-session cookie + HMAC session key in
    ~/.soas/session.json.  The file is `chmod 600`.
  * Every tool call below loads that session and signs the outbound request with the
    same canonical-string HMAC the browser uses. The SOAS backend treats the call as
    "the analyst" and applies their tier permissions.
  * If the session expired or the IP changed (the backend revokes on IP mismatch),
    tools return a helpful error pointing the user back at `login`.

Unlike the Docker mcp/, this server:
  * Has no network listener; only runs as a subprocess of `claude`.
  * Inherits the analyst's tier RBAC exactly. No service-token blanket access.
  * Talks to the SOAS proxy over HTTPS (default https://localhost), trusting the
    SOAS internal CA from secrets/mtls/ca/ca.crt or the system trust store.
"""

from __future__ import annotations

import asyncio
import base64
import getpass
import hashlib
import hmac
import json
import logging
import os
import ssl
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx
from mcp.server.fastmcp import FastMCP

SESSION_PATH = Path(os.path.expanduser("~/.soas/session.json"))
# Default points at the Caddy proxy on the local machine. Override with SOAS_BASE_URL
# for staging / prod endpoints (e.g. SOAS_BASE_URL=https://soas.example.com).
BASE_URL = os.environ.get("SOAS_BASE_URL", "https://localhost")
# Optional path to the SOAS internal CA so we don't have to disable cert validation.
# Defaults to the repo's secrets dir; override if your CA bundle lives elsewhere.
CA_PATH = os.environ.get(
    "SOAS_CA_CERT",
    str(Path(__file__).resolve().parent.parent / "secrets" / "mtls" / "ca" / "ca.crt"),
)
# Last-resort env var if you trust your network and don't want to wire up the CA file.
INSECURE = os.environ.get("SOAS_INSECURE", "").lower() in ("1", "true", "yes")

logger = logging.getLogger("soas.local-mcp")
mcp = FastMCP("soas-local")


# ─── Session storage ────────────────────────────────────────────────────────

class SessionExpired(RuntimeError):
    pass


def _load_session() -> dict:
    if not SESSION_PATH.exists():
        raise SessionExpired(
            f"No session at {SESSION_PATH}. Run: python -m local_mcp login"
        )
    data = json.loads(SESSION_PATH.read_text())
    exp = data.get("expires_at_unix")
    if isinstance(exp, (int, float)) and exp <= time.time():
        raise SessionExpired(
            f"Session expired (at {SESSION_PATH}). Run: python -m local_mcp login"
        )
    return data


def _save_session(session_id: str, session_key_b64: str, expires_at_iso: str) -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Convert ISO 8601 to unix seconds so the TTL check above is timezone-safe.
    import datetime as _dt
    try:
        exp_dt = _dt.datetime.fromisoformat(expires_at_iso.replace("Z", "+00:00"))
        exp_unix = exp_dt.timestamp()
    except Exception:
        exp_unix = time.time() + 6 * 3600
    SESSION_PATH.write_text(
        json.dumps(
            {
                "session_id": session_id,
                "session_key_b64": session_key_b64,
                "expires_at_unix": exp_unix,
                "base_url": BASE_URL,
            },
            indent=2,
        )
    )
    try:
        SESSION_PATH.chmod(0o600)
    except Exception:
        pass


# ─── HMAC request signing (mirrors backend/auth/request_signature.py) ───────

def _canonical_query(query_string: str) -> str:
    if not query_string:
        return ""
    pairs = [tuple(p.split("=", 1)) if "=" in p else (p, "") for p in query_string.split("&")]
    pairs.sort()
    return urlencode(pairs)


def _canonical_string(method: str, path: str, query: str, ts: str, body: bytes) -> str:
    body_hash = hashlib.sha256(body or b"").hexdigest()
    return "\n".join([method.upper(), path, _canonical_query(query), ts, body_hash])


def _sign(canonical: str, key_b64: str) -> str:
    pad = "=" * (-len(key_b64) % 4)
    raw_key = base64.urlsafe_b64decode(key_b64 + pad)
    return hmac.new(raw_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


# ─── httpx client factory ───────────────────────────────────────────────────

def _ssl_context() -> ssl.SSLContext | bool:
    """Trust the SOAS CA if its file exists; otherwise fall back to the default trust
    store. SOAS_INSECURE=1 skips verification entirely (use only for dev)."""
    if INSECURE:
        return False  # httpx: don't verify
    if Path(CA_PATH).exists():
        ctx = ssl.create_default_context(cafile=CA_PATH)
        return ctx
    return True  # default system trust store


async def _call(method: str, path: str, *, params: dict | None = None, body: dict | None = None) -> dict | list:
    """Make a single signed HTTP request against the SOAS API."""
    session = _load_session()
    base = session.get("base_url") or BASE_URL
    full_path = f"/api/v1{path}"
    query_string = urlencode(params or {})
    body_bytes = b"" if body is None else json.dumps(body).encode("utf-8")
    ts = str(int(time.time()))
    canonical = _canonical_string(method, full_path, query_string, ts, body_bytes)
    sig = _sign(canonical, session["session_key_b64"])

    cookies = {"soas_session": f"{session['session_id']}.{session['session_key_b64']}"}
    headers = {
        "X-SOAS-Timestamp": ts,
        "X-SOAS-Signature": sig,
        "Content-Type": "application/json",
    }
    url = base.rstrip("/") + full_path
    if query_string:
        url += "?" + query_string

    async with httpx.AsyncClient(verify=_ssl_context(), timeout=30.0) as c:
        r = await c.request(method, url, headers=headers, cookies=cookies, content=body_bytes or None)
        if r.status_code == 401:
            # Session is dead. Wipe the cached file so the next `login` is clean.
            try:
                SESSION_PATH.unlink()
            except FileNotFoundError:
                pass
            raise SessionExpired(
                f"SOAS rejected the session ({r.status_code} {r.reason_phrase}). "
                f"Run: python -m local_mcp login"
            )
        r.raise_for_status()
        if r.status_code == 204 or not r.content:
            return {}
        return r.json()


def _tool_response(result) -> str:
    try:
        return json.dumps(result, indent=2)
    except (TypeError, ValueError):
        return str(result)


# ─── MCP tools ──────────────────────────────────────────────────────────────

@mcp.tool()
async def list_incidents(limit: int = 25) -> str:
    """List recent incidents (newest first). Returns JSON."""
    return _tool_response(await _call("GET", "/incidents", params={"per_page": limit}))


@mcp.tool()
async def get_incident(incident_id: str) -> str:
    """Get a single incident by id. Returns JSON."""
    return _tool_response(await _call("GET", f"/incidents/{incident_id}"))


@mcp.tool()
async def list_cases(limit: int = 25) -> str:
    """List recent cases (newest first). Returns JSON."""
    return _tool_response(await _call("GET", "/cases", params={"per_page": limit}))


@mcp.tool()
async def get_case(case_id: str) -> str:
    """Get a single case by id. Returns JSON."""
    return _tool_response(await _call("GET", f"/cases/{case_id}"))


@mcp.tool()
async def list_automations(limit: int = 25) -> str:
    """List automations. Returns JSON."""
    return _tool_response(await _call("GET", "/automations", params={"per_page": limit}))


@mcp.tool()
async def search_wiki(query: str, limit: int = 10) -> str:
    """Search wiki pages. Returns JSON list of hits."""
    return _tool_response(await _call("GET", "/wiki/search", params={"q": query, "limit": limit}))


@mcp.tool()
async def run_saved_query(query_id: str) -> str:
    """Run a saved query by id. Returns rows as JSON."""
    return _tool_response(await _call("POST", f"/saved-queries/{query_id}/run", body={}))


@mcp.tool()
async def session_info() -> str:
    """Show metadata about the current session (id, expiry, base URL). No secrets."""
    try:
        s = _load_session()
        return _tool_response({
            "session_id": s.get("session_id"),
            "base_url": s.get("base_url"),
            "expires_at_unix": s.get("expires_at_unix"),
            "expires_in_seconds": max(0, int(s.get("expires_at_unix", 0) - time.time())),
        })
    except SessionExpired as e:
        return str(e)


# ─── login bootstrap ────────────────────────────────────────────────────────

async def _login(base_url: str, username: str) -> None:
    """Interactive login: prompt for password, hit /auth/login, then bootstrap.

    The cookie SOAS sets is httpOnly, so we read it from the response Set-Cookie header
    and stash it ourselves. We then call /auth/session/bootstrap to get the HMAC key.
    """
    password = getpass.getpass(f"password for {username}: ")
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=15.0, verify=_ssl_context()) as c:
        r = await c.post("/api/v1/auth/login", json={"username": username, "password": password})
        if r.status_code != 200:
            raise RuntimeError(f"Login failed: {r.status_code} {r.text}")
        data = r.json()
        if data.get("mfa_required"):
            mfa_token = data["mfa_token"]
            totp = input("TOTP code: ").strip()
            r2 = await c.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "totp_code": totp})
            if r2.status_code != 200:
                raise RuntimeError(f"MFA verification failed: {r2.status_code} {r2.text}")
            r = r2  # use the MFA response for cookies

        # Extract the soas_session cookie that the server just set.
        cookie_value: str | None = None
        for k, v in c.cookies.items():
            if k == "soas_session":
                cookie_value = v
                break
        if not cookie_value or "." not in cookie_value:
            raise RuntimeError("Login succeeded but no soas_session cookie was returned.")
        sid, _, key_b64 = cookie_value.partition(".")

        # Call /auth/session/bootstrap to confirm and get the canonical expiry.
        boot = await c.get("/api/v1/auth/session/bootstrap")
        if boot.status_code != 200:
            raise RuntimeError(f"Bootstrap call failed: {boot.status_code} {boot.text}")
        bdata = boot.json()
        _save_session(sid, bdata.get("session_key", key_b64), bdata.get("expires_at", ""))
        print(f"Logged in. Session at {SESSION_PATH} (expires {bdata.get('expires_at')}).")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        argv = sys.argv[2:]
        base = BASE_URL
        user = None
        i = 0
        while i < len(argv):
            if argv[i] == "--base-url" and i + 1 < len(argv):
                base = argv[i + 1]; i += 2
            elif argv[i] == "--username" and i + 1 < len(argv):
                user = argv[i + 1]; i += 2
            else:
                i += 1
        if not user:
            user = input("username: ").strip()
        asyncio.run(_login(base, user))
        return 0

    if len(sys.argv) > 1 and sys.argv[1] == "logout":
        try:
            SESSION_PATH.unlink()
            print(f"Removed {SESSION_PATH}")
        except FileNotFoundError:
            print("No session to remove.")
        return 0

    # Default: stdio MCP server (what Claude Code expects when spawning this binary)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    logger.info("Starting local SOAS MCP (base_url=%s)", BASE_URL)
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
