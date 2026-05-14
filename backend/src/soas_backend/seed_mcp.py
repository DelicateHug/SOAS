"""Seed the MCP bot user + service token, and persist the raw token to disk.

The token file is written to /run/secrets/mcp_token (mounted into the MCP container).
On the host, a sibling copy is written to secrets/mcp_token so start.ps1 can show it.
This is idempotent: an existing valid token is preserved across restarts. The token is
rotated only when the previous one is revoked or the file is deleted.
"""

import logging
import os
import secrets as pysecrets
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.auth.password import hash_password
from soas_backend.models.role import Role, UserRole
from soas_backend.models.service_token import ServiceToken
from soas_backend.models.user import User
from soas_backend.services.service_token_service import ServiceTokenService

logger = logging.getLogger(__name__)

MCP_BOT_USERNAME = "mcp-bot"
MCP_BOT_EMAIL = "mcp-bot@soas.local"
MCP_BOT_DISPLAY_NAME = "MCP Service Bot"
MCP_TOKEN_NAME = "mcp-default"
MCP_TOKEN_DESCRIPTION = (
    "Auto-generated bearer token for the local MCP server. "
    "Inherits admin permissions. Rotate via the Admin > Service Tokens page."
)

# Container-internal path; mounted as a Docker secret-style file into the MCP container.
DEFAULT_TOKEN_FILE = Path(os.environ.get("MCP_TOKEN_FILE", "/run/secrets/mcp_token"))


async def _ensure_bot_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.username == MCP_BOT_USERNAME))
    bot = result.scalar_one_or_none()
    if bot is not None:
        return bot

    # Use a random throwaway password — bot logs in via service token, not password.
    bot = User(
        id=uuid4(),
        username=MCP_BOT_USERNAME,
        email=MCP_BOT_EMAIL,
        display_name=MCP_BOT_DISPLAY_NAME,
        password_hash=hash_password(pysecrets.token_urlsafe(32)),
        is_active=True,
        must_reset_password=False,
    )
    db.add(bot)
    await db.flush()
    logger.info("Created MCP bot user: %s", bot.username)
    return bot


async def _ensure_admin_role(db: AsyncSession, bot_user_id) -> None:
    role_result = await db.execute(select(Role).where(Role.name == "admin"))
    admin_role = role_result.scalar_one_or_none()
    if admin_role is None:
        logger.warning("admin role not found — bot will have no permissions until a role is assigned.")
        return

    existing = await db.execute(
        select(UserRole).where(
            UserRole.user_id == bot_user_id, UserRole.role_id == admin_role.id
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(UserRole(user_id=bot_user_id, role_id=admin_role.id))
        await db.flush()
        logger.info("Granted admin role to MCP bot.")


async def seed_mcp_bot(db: AsyncSession) -> str | None:
    """Ensure the bot user, role, and an active service token exist. Returns the raw token
    if a new one was created, otherwise None (existing token cannot be retrieved).
    """
    bot = await _ensure_bot_user(db)
    await _ensure_admin_role(db, bot.id)

    token_svc = ServiceTokenService(db)
    existing_token = await token_svc.get_by_name(MCP_TOKEN_NAME)

    # If the token is present, active, and the file exists with a non-empty value,
    # we trust it — the operator can rotate explicitly via the API if compromised.
    if (
        existing_token is not None
        and existing_token.is_active
        and existing_token.revoked_at is None
        and DEFAULT_TOKEN_FILE.exists()
        and DEFAULT_TOKEN_FILE.read_text().strip()
    ):
        logger.info("MCP service token already present, leaving it as-is.")
        return None

    # Either no token, or token has been revoked/lost — create or rotate.
    if existing_token is None:
        token, raw = await token_svc.create(
            name=MCP_TOKEN_NAME,
            user_id=bot.id,
            description=MCP_TOKEN_DESCRIPTION,
            scopes=[],  # inherit everything from admin role
            created_by=bot.id,
        )
        logger.info("Created new MCP service token (id=%s, prefix=%s).", token.id, token.token_prefix)
    else:
        rotated = await token_svc.rotate(existing_token.id)
        assert rotated is not None
        token, raw = rotated
        logger.info("Rotated MCP service token (id=%s, prefix=%s).", token.id, token.token_prefix)

    _persist_token_to_disk(raw)
    return raw


def _persist_token_to_disk(raw: str) -> None:
    """Write the token to disk so the MCP container can read it via mounted secret.

    Best-effort — failures are logged but don't break the seed flow. In typical Docker
    deployments the file path is bind-mounted and writes succeed. In bare-metal dev runs
    the path may not exist and we just skip the disk persistence — the operator can fetch
    the token via the /api/v1/service-tokens listing.
    """
    try:
        DEFAULT_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_TOKEN_FILE.write_text(raw)
        try:
            os.chmod(DEFAULT_TOKEN_FILE, 0o600)
        except OSError:
            # Windows volume mounts often reject chmod — non-fatal.
            pass
        logger.info("Wrote MCP token to %s", DEFAULT_TOKEN_FILE)
    except OSError as e:
        logger.warning("Could not persist MCP token to %s: %s", DEFAULT_TOKEN_FILE, e)
