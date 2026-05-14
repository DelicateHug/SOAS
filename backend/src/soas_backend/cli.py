"""Small operator CLI for one-shot tasks that don't belong in the HTTP API.

Usage:
    python -m soas_backend.cli mint-bootstrap-cert <username>

Subcommands:
    mint-bootstrap-cert <username>
        Mint a fresh `web` certificate for the named user and print the
        base64-encoded .p12 + passphrase to stdout. Intended for the
        first-admin bootstrap on a fresh k8s install where there's no
        existing operator cert.

    create-admin <username> <email> <password>
        Create a local user with the admin role. Useful when seeding a
        fresh database where /auth/register is blocked because the
        mcp-bot already exists.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import secrets
import sys
from uuid import UUID

from sqlalchemy import select

from soas_backend.database import async_session


async def _mint_bootstrap_cert(username: str) -> int:
    from soas_backend.models.user import User
    from soas_backend.services.cert_authority_service import CertAuthorityService

    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"error: user '{username}' not found", file=sys.stderr)
            return 1

        svc = CertAuthorityService(db)
        issued = await svc.issue_for_user(
            user_id=user.id,
            common_name=f"user:{user.id}",
            purpose="web",
            issued_by=user.id,
        )
        await db.commit()

    print(f"common_name:        {issued.record.common_name}")
    print(f"serial:             {issued.record.serial}")
    print(f"fingerprint_sha256: {issued.record.fingerprint_sha256}")
    print(f"not_after:          {issued.record.not_after.isoformat()}")
    print(f"passphrase:         {issued.passphrase}")
    print(f"p12_base64:")
    # Wrap so it's pasteable into `echo ... | base64 -d > user.p12`
    b64 = base64.b64encode(issued.p12_bytes).decode("ascii")
    for i in range(0, len(b64), 76):
        print(b64[i : i + 76])
    print()
    print("Save the .p12 and passphrase. The private key is not retained on the server.")
    return 0


async def _create_admin(username: str, email: str, password: str) -> int:
    from soas_backend.auth.password import hash_password
    from soas_backend.models.role import Role, UserRole
    from soas_backend.models.user import User

    async with async_session() as db:
        rs = await db.execute(select(User).where(User.username == username))
        if rs.scalar_one_or_none() is not None:
            print(f"error: user '{username}' already exists", file=sys.stderr)
            return 1

        user = User(
            username=username,
            email=email,
            display_name=username.title(),
            password_hash=hash_password(password),
            is_active=True,
            auth_provider="local",
        )
        db.add(user)
        await db.flush()

        rs = await db.execute(select(Role).where(Role.name == "admin"))
        admin_role = rs.scalar_one_or_none()
        if admin_role is None:
            print("warning: 'admin' role not found; user created without role", file=sys.stderr)
        else:
            db.add(UserRole(user_id=user.id, role_id=admin_role.id))
        await db.commit()
        print(f"Created user {user.username} ({user.id}) with admin role")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="soas-cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    cert = sub.add_parser("mint-bootstrap-cert", help="Issue a .p12 cert for a user")
    cert.add_argument("username")

    admin = sub.add_parser("create-admin", help="Create a local admin user")
    admin.add_argument("username")
    admin.add_argument("email")
    admin.add_argument("password")

    args = parser.parse_args(argv)

    if args.cmd == "mint-bootstrap-cert":
        return asyncio.run(_mint_bootstrap_cert(args.username))
    if args.cmd == "create-admin":
        return asyncio.run(_create_admin(args.username, args.email, args.password))

    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
