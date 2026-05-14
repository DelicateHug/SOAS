"""Parse client certs forwarded by the Istio gateway.

Istio terminates mTLS at the gateway and forwards verified peer
certificates downstream via the `X-Forwarded-Client-Cert` (XFCC) header.
Each cert in the chain is encoded as a semicolon-separated list of
`key="value"` pairs; we care about `Hash=` (sha256 of the cert) and
`URI=` (the SAN). The full PEM may be available under `Cert=` if the
gateway is configured with `forwardClientCertDetails: APPEND_FORWARD`.

We DO NOT trust the header without the gateway in front of us — see
the SOAS_TRUST_XFCC env knob. When unset (the dev default), the parser
returns None and the auth dep falls back to JWT-only.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from urllib.parse import unquote
from uuid import UUID

from cryptography import x509

logger = logging.getLogger(__name__)


@dataclass
class XfccPeer:
    """One parsed peer cert from the XFCC header."""
    fingerprint_sha256: str  # hex, lower
    subject_cn: str | None
    san_uris: list[str]
    user_id: UUID | None  # parsed out of CN or SAN if it matches our scheme


def trust_enabled() -> bool:
    """Whether the deployment is configured to honor XFCC headers.

    Set SOAS_TRUST_XFCC=true on the backend pod only when there is a
    cert-validating gateway in front (Istio gateway with
    `MUTUAL` TLS). In docker-compose dev, leave it off — the auth dep
    will silently fall back to JWT-only, matching previous behavior.
    """
    return os.environ.get("SOAS_TRUST_XFCC", "").lower() in ("1", "true", "yes")


def parse_xfcc_header(value: str | None) -> list[XfccPeer]:
    """Parse the X-Forwarded-Client-Cert value into 0..N peer records.

    Multiple certs are comma-separated. Within each cert, fields are
    `Key="value"` pairs separated by ';'. Values containing commas or
    semicolons are URL-encoded by the gateway.
    """
    if not value:
        return []
    peers: list[XfccPeer] = []
    for entry in _split_top_level(value, ","):
        fields = _parse_fields(entry)
        fp = (fields.get("hash") or "").lower()
        cn = None
        san_uris: list[str] = []

        # Prefer the embedded PEM if the gateway includes it — it's
        # authoritative. Some Istio configurations send `Cert=`.
        pem = fields.get("cert")
        if pem:
            try:
                cert = x509.load_pem_x509_certificate(pem.encode("ascii"))
                cn = _first_cn(cert)
                san_uris = _extract_san_uris(cert)
                if not fp:
                    from cryptography.hazmat.primitives import hashes

                    digest = hashes.Hash(hashes.SHA256())
                    digest.update(cert.public_bytes(serialization_encoding_der()))
                    fp = digest.finalize().hex()
            except Exception:
                logger.debug("xfcc: failed to parse embedded cert; will rely on Hash/URI")

        # Fall back to top-level `Subject=` and `URI=` keys.
        if cn is None and "subject" in fields:
            cn = _cn_from_subject(fields["subject"])
        if not san_uris and "uri" in fields:
            san_uris = [fields["uri"]]

        if not fp:
            continue  # Useless entry without a fingerprint
        peers.append(
            XfccPeer(
                fingerprint_sha256=fp,
                subject_cn=cn,
                san_uris=san_uris,
                user_id=_extract_user_id(cn, san_uris),
            )
        )
    return peers


def _split_top_level(s: str, sep: str) -> list[str]:
    """Split `s` on `sep` but ignore separators inside double-quotes."""
    out: list[str] = []
    buf: list[str] = []
    in_quotes = False
    for ch in s:
        if ch == '"':
            in_quotes = not in_quotes
            buf.append(ch)
        elif ch == sep and not in_quotes:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf).strip())
    return [p for p in out if p]


def _parse_fields(entry: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for pair in _split_top_level(entry, ";"):
        if "=" not in pair:
            continue
        key, _, val = pair.partition("=")
        v = val.strip()
        if v.startswith('"') and v.endswith('"') and len(v) >= 2:
            v = v[1:-1]
        fields[key.strip().lower()] = unquote(v)
    return fields


def _cn_from_subject(subject: str) -> str | None:
    # Subject may be RFC 2253 ("CN=user:abc,O=SOAS") or freeform
    for part in subject.split(","):
        p = part.strip()
        if p.lower().startswith("cn="):
            return p[3:]
    return None


def _first_cn(cert: x509.Certificate) -> str | None:
    try:
        attrs = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        return attrs[0].value if attrs else None
    except Exception:
        return None


def _extract_san_uris(cert: x509.Certificate) -> list[str]:
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        return [u for u in ext.value.get_values_for_type(x509.UniformResourceIdentifier)]
    except x509.ExtensionNotFound:
        return []


def _extract_user_id(cn: str | None, sans: list[str]) -> UUID | None:
    """Pull a SOAS user UUID out of a CN or SAN if it follows our scheme.

    Issued certs use CN=`user:<uuid>` and SAN URI =
    `spiffe://soas/user/<uuid>/<purpose>`.
    """
    candidates: list[str] = []
    if cn and cn.startswith("user:"):
        candidates.append(cn[len("user:"):])
    for s in sans:
        if s.startswith("spiffe://soas/user/"):
            parts = s.split("/")
            # spiffe:, '', soas, user, <uuid>, <purpose>
            if len(parts) >= 5:
                candidates.append(parts[4])
    for c in candidates:
        try:
            return UUID(c)
        except (ValueError, AttributeError):
            continue
    return None


def serialization_encoding_der():
    """Tiny helper to avoid pulling serialization at import time of cert.py."""
    from cryptography.hazmat.primitives import serialization

    return serialization.Encoding.DER
