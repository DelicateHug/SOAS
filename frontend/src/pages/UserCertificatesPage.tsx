/**
 * Self-service certificate page.
 *
 * Lists the current user's active certs and lets them mint a new one.
 * On issue, a modal shows the one-time .p12 download button + the
 * passphrase. Closing the modal triggers an explicit confirmation since
 * neither is recoverable.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, Download, Copy, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { DataTable, Th, Tr, Td } from "@/components/ui/DataTable";

interface CertRead {
  id: string;
  purpose: string;
  serial: string;
  fingerprint_sha256: string;
  common_name: string;
  not_before: string;
  not_after: string;
  issued_at: string;
  downloaded_at: string | null;
  revoked_at: string | null;
  revocation_reason: string | null;
}

interface IssueResponse {
  cert: CertRead;
  download_token: string;
  download_expires_at: string;
}

const PURPOSES = [
  { value: "web", label: "Browser (web)" },
  { value: "mcp", label: "Claude Code / IDE (mcp)" },
  { value: "cli", label: "CLI / scripts (cli)" },
];

export function UserCertificatesPage() {
  const qc = useQueryClient();
  const [purpose, setPurpose] = useState("web");
  const [issued, setIssued] = useState<IssueResponse | null>(null);
  const [passphrase, setPassphrase] = useState<string | null>(null);
  const [showRevoked, setShowRevoked] = useState(false);

  const { data: certs = [] } = useQuery({
    queryKey: ["my-certificates", showRevoked],
    queryFn: () =>
      api.get<CertRead[]>(
        `/me/certificates${showRevoked ? "?include_revoked=true" : ""}`,
      ),
  });

  const issue = useMutation({
    mutationFn: (body: { purpose: string }) =>
      api.post<IssueResponse>("/me/certificates", body),
    onSuccess: (resp) => {
      setIssued(resp);
      qc.invalidateQueries({ queryKey: ["my-certificates"] });
      // Eagerly fetch the .p12 + passphrase so the user has it on screen.
      downloadIssued(resp.download_token).then(setPassphrase);
    },
  });

  async function downloadIssued(token: string): Promise<string | null> {
    // Use a direct fetch to read the X-Cert-Passphrase header.
    const res = await fetch(`/api/v1/me/certificates/download/${token}`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
      },
    });
    if (!res.ok) {
      return null;
    }
    const phrase = res.headers.get("x-cert-passphrase");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `soas-${purpose}.p12`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return phrase;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <ShieldCheck size={18} /> My Certificates
        </h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
          Client certificates authenticate your browser, Claude Code MCP client, or scripts to SOAS
          at the gateway. Each cert is good for a year. You can issue a new one any time — the old
          one stays valid until you revoke it.
        </p>
      </div>

      <Card>
        <CardBody>
          <div className="flex items-end gap-2">
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
                Purpose
              </label>
              <select
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                className="px-2 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
              >
                {PURPOSES.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <button
              onClick={() => issue.mutate({ purpose })}
              disabled={issue.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
            >
              <Download size={14} /> Issue + download
            </button>
            <label className="ml-auto inline-flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
              <input type="checkbox" checked={showRevoked} onChange={(e) => setShowRevoked(e.target.checked)} />
              Show revoked
            </label>
          </div>
        </CardBody>
      </Card>

      {issued && (
        <Card>
          <CardBody>
            <div className="flex items-start gap-3">
              <AlertTriangle size={18} className="text-[var(--color-warning)] mt-0.5" />
              <div className="flex-1">
                <div className="text-sm font-semibold mb-1">Your .p12 has been downloaded.</div>
                <p className="text-xs text-[var(--color-text-muted)] mb-2">
                  The passphrase is shown <strong>once</strong> below. Note it down — it's not
                  recoverable. The download URL also expires in 5 minutes.
                </p>
                {passphrase ? (
                  <div className="inline-flex items-center gap-2">
                    <code className="font-mono text-xs px-2 py-1 bg-[var(--color-surface-2)] rounded select-all">
                      {passphrase}
                    </code>
                    <button
                      onClick={() => navigator.clipboard.writeText(passphrase)}
                      className="inline-flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                    >
                      <Copy size={11} /> Copy
                    </button>
                  </div>
                ) : (
                  <div className="text-xs text-[var(--color-text-muted)]">Waiting for download…</div>
                )}
                <div className="mt-3">
                  <button
                    onClick={() => {
                      if (confirm("Have you saved the passphrase? It cannot be retrieved later.")) {
                        setIssued(null);
                        setPassphrase(null);
                      }
                    }}
                    className="px-3 py-1 text-xs rounded border border-[var(--color-border)]"
                  >
                    I've saved it
                  </button>
                </div>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardBody>
          <DataTable>
            <thead>
              <tr>
                <Th>Purpose</Th>
                <Th>Common name</Th>
                <Th>Serial</Th>
                <Th>Fingerprint (sha256)</Th>
                <Th>Not before</Th>
                <Th>Not after</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {certs.map((c) => (
                <Tr key={c.id}>
                  <Td className="font-mono text-xs">{c.purpose}</Td>
                  <Td className="font-mono text-xs">{c.common_name}</Td>
                  <Td className="font-mono text-xs">{c.serial}</Td>
                  <Td className="font-mono text-[10px]">{c.fingerprint_sha256.slice(0, 24)}…</Td>
                  <Td className="font-mono text-xs">{new Date(c.not_before).toLocaleDateString()}</Td>
                  <Td className="font-mono text-xs">{new Date(c.not_after).toLocaleDateString()}</Td>
                  <Td>
                    {c.revoked_at ? (
                      <span className="text-xs text-[var(--color-danger)]">
                        revoked · {c.revocation_reason}
                      </span>
                    ) : (
                      <span className="text-xs text-[var(--color-success)]">active</span>
                    )}
                  </Td>
                </Tr>
              ))}
              {certs.length === 0 && (
                <Tr>
                  <Td>
                    <div className="text-xs text-[var(--color-text-muted)] py-4 text-center">
                      No certificates yet. Issue one above.
                    </div>
                  </Td>
                </Tr>
              )}
            </tbody>
          </DataTable>
        </CardBody>
      </Card>
    </div>
  );
}
