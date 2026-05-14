# SOAS on Kubernetes

This document covers a from-scratch deployment of SOAS to a Kubernetes
cluster with Istio service mesh, cert-manager, and Microsoft Entra
OIDC.

## Architecture

- **Mesh**: Istio in `STRICT` PeerAuthentication mode for the `soas`
  namespace. Every pod-to-pod call is wrapped in mesh-mTLS by the
  envoy sidecar. No app code changes needed.
- **PKI**: two cert-manager `ClusterIssuer`s. `soas-internal-ca` signs
  the gateway's server cert + (optionally) postgres TLS. `soas-user-ca`
  signs per-user client certs (PKCS#12 bundles distributed via the
  SOAS admin UI).
- **Edge**: a user-facing Istio gateway on 443 requires both a client
  cert (signed by `soas-user-ca`) and a bearer JWT. A separate webhook
  gateway on 8443 terminates server-side TLS only — external SIEMs
  POST to `/api/v1/webhooks/ingest/<token>` with no cert.
- **Identity**: hybrid — the cert proves the device is allowed to talk
  to SOAS; the JWT proves who's using it. The backend's
  `get_authenticated_user` dep binds the two: cert.CN must match
  JWT.sub.
- **OIDC + CAE**: Microsoft Entra is supported as a parallel login
  path. Every authenticated request runs a Continuous Access
  Evaluation check (cached 30s) so revocations propagate quickly.

## Bootstrap

### Prerequisites

```bash
# Local cluster (kind/k3d works fine for dev)
kind create cluster

# cert-manager
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --version v1.15 --namespace cert-manager --create-namespace \
  --set installCRDs=true

# Istio
curl -L https://istio.io/downloadIstio | sh -
./istio-*/bin/istioctl install -y --set profile=demo
kubectl label namespace istio-system name=istio-system
```

### Apply SOAS

```bash
# Dev overlay (1 replica per deployment)
kubectl apply -k deploy/k8s/overlays/dev

# Wait for migration to complete
kubectl logs -n soas deploy/backend --tail=50 | grep "Running upgrade"
```

### Bootstrap the first admin user

There's no operator-out-of-band cert injection in dev mode. Use the
provided CLI to mint the first cert from inside the backend pod:

```bash
kubectl exec -n soas deploy/backend -- \
  python -m soas_backend.cli mint-bootstrap-cert admin
```

The .p12 + passphrase are printed once. Import the .p12 into your
browser (Chrome: Settings → Privacy → Manage certificates → Import).
Then sign in at https://soas.example.com.

## Enabling OIDC

1. Register an app in Entra. Single-tenant or multi-tenant both work.
2. Add a Web redirect URI: `https://soas.example.com/api/v1/auth/oidc/callback`.
3. In the Entra portal, **API permissions** → add Microsoft Graph
   `User.Read` and `openid profile email offline_access`. Grant admin
   consent for your tenant if required.
4. **Certificates & secrets** → create a client secret. Note the value;
   you won't see it again.
5. Hit SOAS at /admin/danger-zone → Authentication panel:
   - paste tenant id, client id, redirect URI
   - paste the client secret
   - flip "Enable Microsoft Entra (OIDC) login" on
6. (Optional) Map Entra group object-ids to SOAS roles via the
   `auth_oidc_group_mappings` JSON setting:
   ```json
   {"abcd1234-...": "soc_manager", "efgh5678-...": "analyst"}
   ```
7. Sign out, refresh /login — you'll see "Sign in with Microsoft".

## CAE (Continuous Access Evaluation)

Every request runs `CAEService.evaluate()` after the JWT signature
check. Three signals invalidate a session:

- An admin posts to `/admin/users/{id}/revoke-sessions` (writes the
  user-id to a Redis kill-switch set)
- An admin revokes a user's cert (publishes on the
  `auth:revocation` channel)
- A user logs out (their jti is added to the revoked set with TTL)

The frontend handles `401 X-Cae-Revoked: true` by redirecting to
`/login?reason=revoked`. Open WebSockets (incident chat, monitoring)
also close on the next pubsub tick.

## Rotating a leaked user cert

1. Admin → Users → click user → Certificates tab
2. Revoke the affected cert
3. Click Issue, hand the user the new .p12 + passphrase
4. Within ~30s the mesh refresh propagates and the old cert is
   rejected at the gateway

## Switching to an org CA

The bootstrap CA is self-signed. To swap for your org root:

1. Create a `Secret` containing the org root + key in `cert-manager`.
2. Replace `soas-bootstrap-selfsigned` with a `CA` issuer pointing at
   the secret.
3. The two ClusterIssuers (`soas-internal-ca`, `soas-user-ca`) continue
   to issue leaf certs as before; everything downstream keeps working.
