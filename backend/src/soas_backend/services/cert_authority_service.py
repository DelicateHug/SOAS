"""Per-user client cert issuance.

Two modes, picked by env var SOAS_CA_MODE:

  - "local"   (default in dev): self-signed CA. The CA cert+key are
              persisted as encrypted app_settings on first use so dev
              restarts don't re-issue under a new root. Good for
              docker-compose + tests.
  - "k8s":    talk to cert-manager via the Kubernetes API. The backend
              pod has RBAC to create CertificateRequest resources in
              its own namespace against the `soas-user-ca` Issuer.

In both modes, the *private key* is generated server-side, bundled
into a one-time-download PKCS#12, and immediately discarded — only the
public cert + fingerprint + serial are persisted to user_certificates.
"""

from __future__ import annotations

import base64
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    pkcs12,
)
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.user_certificate import UserCertificate
from soas_backend.services.app_setting_service import AppSettingService

logger = logging.getLogger(__name__)

VALID_PURPOSES = ("web", "mcp", "cli")
CERT_TTL_DAYS = int(os.environ.get("SOAS_USER_CERT_TTL_DAYS", "365"))


@dataclass
class IssuedCert:
    """Result of issue_for_user — returned exactly once."""
    p12_bytes: bytes
    passphrase: str
    record: UserCertificate


class CertAuthorityService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.mode = os.environ.get("SOAS_CA_MODE", "local").lower()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def issue_for_user(
        self,
        *,
        user_id: UUID,
        common_name: str,
        purpose: str,
        issued_by: UUID | None,
    ) -> IssuedCert:
        """Issue a fresh cert. Revokes any prior active cert for the same
        (user, purpose) tuple."""
        if purpose not in VALID_PURPOSES:
            raise ValueError(f"purpose must be one of {VALID_PURPOSES}")

        # Revoke prior active certs of the same purpose
        rs = await self.db.execute(
            select(UserCertificate).where(
                and_(
                    UserCertificate.user_id == user_id,
                    UserCertificate.purpose == purpose,
                    UserCertificate.revoked_at.is_(None),
                )
            )
        )
        for prior in rs.scalars().all():
            prior.revoked_at = datetime.now(timezone.utc)
            prior.revocation_reason = "replaced by re-issue"

        # Generate keypair
        priv = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        san_uri = f"spiffe://soas/user/{user_id}/{purpose}"

        if self.mode == "k8s":
            cert = await self._sign_via_cert_manager(priv, common_name, san_uri)
        else:
            cert = await self._sign_local(priv, common_name, san_uri)

        # Persist public metadata only
        der = cert.public_bytes(serialization.Encoding.DER)
        fingerprint = hashes.Hash(hashes.SHA256())
        fingerprint.update(der)
        fp_hex = fingerprint.finalize().hex()

        record = UserCertificate(
            user_id=user_id,
            purpose=purpose,
            serial=format(cert.serial_number, "x"),
            fingerprint_sha256=fp_hex,
            common_name=common_name,
            cert_pem=cert.public_bytes(serialization.Encoding.PEM).decode("ascii"),
            not_before=_aware(cert.not_valid_before_utc),
            not_after=_aware(cert.not_valid_after_utc),
            issued_by=issued_by,
        )
        self.db.add(record)
        await self.db.flush()

        # Bundle PKCS#12 with a one-time passphrase
        passphrase = secrets.token_urlsafe(24)
        p12 = pkcs12.serialize_key_and_certificates(
            name=common_name.encode("utf-8"),
            key=priv,
            cert=cert,
            cas=None,
            encryption_algorithm=BestAvailableEncryption(passphrase.encode("utf-8")),
        )
        # priv goes out of scope here; we never persist it.
        del priv

        return IssuedCert(p12_bytes=p12, passphrase=passphrase, record=record)

    async def revoke(
        self,
        *,
        cert_id: UUID,
        actor_id: UUID | None,
        reason: str | None = None,
    ) -> UserCertificate | None:
        rs = await self.db.execute(
            select(UserCertificate).where(UserCertificate.id == cert_id)
        )
        cert = rs.scalar_one_or_none()
        if cert is None:
            return None
        if cert.revoked_at is None:
            cert.revoked_at = datetime.now(timezone.utc)
            cert.revocation_reason = reason or "revoked"
            await self.db.flush()
        return cert

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        include_revoked: bool = False,
    ) -> list[UserCertificate]:
        q = select(UserCertificate).where(UserCertificate.user_id == user_id)
        if not include_revoked:
            q = q.where(UserCertificate.revoked_at.is_(None))
        q = q.order_by(UserCertificate.issued_at.desc())
        rs = await self.db.execute(q)
        return list(rs.scalars().all())

    async def lookup_by_fingerprint(self, fingerprint_hex: str) -> UserCertificate | None:
        rs = await self.db.execute(
            select(UserCertificate).where(
                UserCertificate.fingerprint_sha256 == fingerprint_hex
            )
        )
        return rs.scalar_one_or_none()

    async def mark_downloaded(self, cert_id: UUID) -> None:
        rs = await self.db.execute(
            select(UserCertificate).where(UserCertificate.id == cert_id)
        )
        cert = rs.scalar_one_or_none()
        if cert and cert.downloaded_at is None:
            cert.downloaded_at = datetime.now(timezone.utc)
            await self.db.flush()

    # ------------------------------------------------------------------
    # Local-mode CA
    # ------------------------------------------------------------------

    async def _load_or_create_local_ca(self) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
        """Lazy-load the dev CA from app_settings; create one if absent."""
        settings = AppSettingService(self.db)
        ca_cert_pem = await settings.get_value("soas_local_ca_cert_pem")
        ca_key_pem = await settings.get_value("soas_local_ca_key_pem")
        if ca_cert_pem and ca_key_pem:
            ca_cert = x509.load_pem_x509_certificate(ca_cert_pem.encode("ascii"))
            ca_key = serialization.load_pem_private_key(
                ca_key_pem.encode("ascii"), password=None
            )
            return ca_key, ca_cert

        # Mint a fresh CA
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SOC on a Stick"),
                x509.NameAttribute(NameOID.COMMON_NAME, "SOAS User CA"),
            ]
        )
        now = datetime.now(timezone.utc)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(ca_key, hashes.SHA256())
        )

        cert_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
        key_pem = ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")
        await settings.set("soas_local_ca_cert_pem", cert_pem)
        await settings.set("soas_local_ca_key_pem", key_pem)
        await self.db.flush()
        logger.info("cert_authority: created local SOAS User CA (dev mode)")
        return ca_key, ca_cert

    async def _sign_local(
        self,
        priv: rsa.RSAPrivateKey,
        common_name: str,
        san_uri: str,
    ) -> x509.Certificate:
        ca_key, ca_cert = await self._load_or_create_local_ca()
        now = datetime.now(timezone.utc)
        builder = (
            x509.CertificateBuilder()
            .subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
            )
            .issuer_name(ca_cert.subject)
            .public_key(priv.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=CERT_TTL_DAYS))
            .add_extension(
                x509.SubjectAlternativeName([x509.UniformResourceIdentifier(san_uri)]),
                critical=False,
            )
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
                critical=False,
            )
        )
        return builder.sign(ca_key, hashes.SHA256())

    # ------------------------------------------------------------------
    # k8s-mode CA via cert-manager
    # ------------------------------------------------------------------

    async def _sign_via_cert_manager(
        self,
        priv: rsa.RSAPrivateKey,
        common_name: str,
        san_uri: str,
    ) -> x509.Certificate:
        """Submit a CertificateRequest to cert-manager and wait for it
        to be signed by the soas-user-ca Issuer."""
        try:
            from kubernetes import client, config
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "k8s mode requires the `kubernetes` python package"
            ) from exc

        try:
            config.load_incluster_config()
        except Exception:
            config.load_kube_config()
        api = client.CustomObjectsApi()

        # Build CSR
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
            )
            .add_extension(
                x509.SubjectAlternativeName([x509.UniformResourceIdentifier(san_uri)]),
                critical=False,
            )
            .sign(priv, hashes.SHA256())
        )
        csr_pem = csr.public_bytes(serialization.Encoding.PEM)
        csr_b64 = base64.b64encode(csr_pem).decode("ascii")

        namespace = os.environ.get("SOAS_NAMESPACE", "soas")
        name = f"soas-user-{secrets.token_hex(6)}"
        body = {
            "apiVersion": "cert-manager.io/v1",
            "kind": "CertificateRequest",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "request": csr_b64,
                "isCA": False,
                "duration": f"{CERT_TTL_DAYS * 24}h",
                "usages": ["client auth", "digital signature", "key encipherment"],
                "issuerRef": {
                    "name": "soas-user-ca",
                    "kind": "ClusterIssuer",
                },
            },
        }
        api.create_namespaced_custom_object(
            group="cert-manager.io",
            version="v1",
            namespace=namespace,
            plural="certificaterequests",
            body=body,
        )

        # Poll for the signed cert (cert-manager usually completes inside a second)
        import asyncio

        for _ in range(30):
            await asyncio.sleep(0.5)
            cr = api.get_namespaced_custom_object(
                group="cert-manager.io",
                version="v1",
                namespace=namespace,
                plural="certificaterequests",
                name=name,
            )
            status = cr.get("status") or {}
            cert_b64 = status.get("certificate")
            if cert_b64:
                cert_pem = base64.b64decode(cert_b64)
                return x509.load_pem_x509_certificate(cert_pem)
            conds = status.get("conditions") or []
            failed = next(
                (c for c in conds if c.get("type") == "Ready" and c.get("status") == "False"),
                None,
            )
            if failed:
                raise RuntimeError(
                    f"cert-manager refused to sign: {failed.get('reason')} — "
                    f"{failed.get('message')}"
                )
        raise RuntimeError("cert-manager did not sign within 15s")


def _aware(dt: datetime) -> datetime:
    """cert-manager and cryptography return tz-naive datetimes for some
    fields; normalize to UTC-aware so storage stays consistent."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
