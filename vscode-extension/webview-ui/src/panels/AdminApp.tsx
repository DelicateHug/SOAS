/**
 * Admin webview panel app.
 * Renders the appropriate admin page based on adminPanel type.
 * Each admin section is a self-contained CRUD interface.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useDeploymentMode } from "@/hooks/useDeploymentMode";

interface Props {
  adminPanel: string;
}

export function AdminApp({ adminPanel }: Props) {
  switch (adminPanel) {
    case "adminUsers":
      return <UsersAdmin />;
    case "adminRoles":
      return <RolesAdmin />;
    case "adminSoasVariables":
      return <VariablesAdmin endpoint="/soas-variables" title="SOAS Variables" />;
    case "adminIncidentVariables":
      return <VariablesAdmin endpoint="/incident-variables" title="Incident Variables" />;
    case "adminFormDefinitions":
      return <FormDefinitionsAdmin />;
    case "adminWebhooks":
      return <WebhooksAdmin />;
    case "adminWebhookSources":
      return <GenericListAdmin endpoint="/webhook-sources" title="Webhook Sources" />;
    case "adminNormalization":
      return <GenericListAdmin endpoint="/normalization/groups" title="Normalization Groups" />;
    case "adminUserSecrets":
      return <GenericListAdmin endpoint="/user-secrets/admin/all" title="User Secrets (Admin)" />;
    case "adminReviewChanges":
      return <ReviewChangesAdmin />;
    case "adminSettings":
      return <SettingsAdmin />;
    default:
      return <div style={styles.container}><p>Unknown admin panel: {adminPanel}</p></div>;
  }
}

// ---------- Shared styles ----------

const styles = {
  container: {
    padding: 24,
    color: "var(--vscode-foreground)",
    background: "var(--vscode-editor-background)",
    minHeight: "100vh",
  } as React.CSSProperties,
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 24,
  } as React.CSSProperties,
  title: { fontSize: 24, fontWeight: 600 } as React.CSSProperties,
  table: { width: "100%", borderCollapse: "collapse" as const, fontSize: 13 },
  th: {
    textAlign: "left" as const,
    padding: "8px 12px",
    borderBottom: "1px solid var(--vscode-panel-border)",
    color: "var(--vscode-descriptionForeground)",
    fontWeight: 500,
    fontSize: 12,
  },
  td: {
    padding: "8px 12px",
    borderBottom: "1px solid var(--vscode-panel-border)",
  },
  btn: {
    padding: "6px 14px",
    background: "var(--vscode-button-background)",
    color: "var(--vscode-button-foreground)",
    border: "none",
    borderRadius: 4,
    cursor: "pointer",
    fontSize: 12,
  } as React.CSSProperties,
  btnSmall: {
    padding: "3px 8px",
    background: "var(--vscode-button-secondaryBackground)",
    color: "var(--vscode-button-secondaryForeground)",
    border: "none",
    borderRadius: 3,
    cursor: "pointer",
    fontSize: 11,
    marginRight: 4,
  } as React.CSSProperties,
  input: {
    padding: "6px 8px",
    background: "var(--vscode-input-background)",
    color: "var(--vscode-input-foreground)",
    border: "1px solid var(--vscode-input-border, transparent)",
    borderRadius: 2,
    fontSize: 13,
    width: "100%",
    boxSizing: "border-box" as const,
  },
  badge: (color: string) => ({
    display: "inline-block",
    padding: "1px 6px",
    borderRadius: 3,
    fontSize: 11,
    fontWeight: 600,
    background: color,
    color: "#fff",
  }),
};

// ---------- Users Admin ----------

interface User {
  id: string;
  username: string;
  display_name: string;
  email: string;
  is_active: boolean;
  is_mfa_enabled: boolean;
  roles: string[];
  last_login_at?: string;
  created_at: string;
}

interface AdminUserCreateResponse extends User {
  temporary_password: string;
}

function UsersAdmin() {
  const { isProduction } = useDeploymentMode();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ username: "", email: "", display_name: "" });
  const [createError, setCreateError] = useState("");
  const [createdUser, setCreatedUser] = useState<AdminUserCreateResponse | null>(null);
  const [resetResult, setResetResult] = useState<{ user: User; password: string } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api.get<{ data: User[]; meta: { total: number } }>("/admin/users?per_page=100"),
  });

  const createMutation = useMutation({
    mutationFn: (form: { username: string; email: string; display_name: string }) =>
      api.post<AdminUserCreateResponse>("/admin/users", form),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setCreatedUser(data);
      setCreateError("");
    },
    onError: (err: { detail?: string }) => {
      setCreateError(err.detail || "Failed to create user");
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: (user: User) =>
      user.is_active
        ? api.delete(`/admin/users/${user.id}`)
        : api.patch(`/admin/users/${user.id}`, { is_active: true }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const resetPasswordMutation = useMutation({
    mutationFn: (user: User) =>
      api.post<{ temporary_password: string }>(`/admin/users/${user.id}/reset-password`),
    onSuccess: (data, user) => setResetResult({ user, password: data.temporary_password }),
  });

  const handleCloseCreate = () => {
    setShowCreate(false);
    setCreateForm({ username: "", email: "", display_name: "" });
    setCreateError("");
    setCreatedUser(null);
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Users</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "var(--vscode-descriptionForeground)" }}>
            {data?.meta.total ?? 0} users
          </span>
          {!isProduction && (
            <button style={styles.btn} onClick={() => setShowCreate(true)}>
              + Add User
            </button>
          )}
        </div>
      </div>

      {/* Create User Modal */}
      {showCreate && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
          <div style={{ background: "var(--vscode-editor-background)", border: "1px solid var(--vscode-panel-border)", borderRadius: 8, padding: 24, width: 400, maxWidth: "90vw" }}>
            {createdUser ? (
              <>
                <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>User Created</h2>
                <p style={{ fontSize: 13, marginBottom: 4 }}>Username: <strong>{createdUser.username}</strong></p>
                <p style={{ fontSize: 13, marginBottom: 12 }}>Email: <strong>{createdUser.email}</strong></p>
                <div style={{ padding: 12, background: "var(--vscode-inputValidation-warningBackground, rgba(255,200,0,0.1))", border: "1px solid var(--vscode-inputValidation-warningBorder, orange)", borderRadius: 4, marginBottom: 12 }}>
                  <p style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Temporary Password</p>
                  <code style={{ fontSize: 13, fontFamily: "var(--vscode-editor-font-family)", wordBreak: "break-all" }}>
                    {createdUser.temporary_password}
                  </code>
                  <p style={{ fontSize: 11, marginTop: 8, color: "var(--vscode-descriptionForeground)" }}>
                    The user must change this on first login. Copy it now — it cannot be retrieved later.
                  </p>
                </div>
                <button style={styles.btn} onClick={handleCloseCreate}>Done</button>
              </>
            ) : (
              <>
                <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Add New User</h2>
                {createError && (
                  <div style={{ padding: 8, marginBottom: 12, background: "var(--vscode-inputValidation-errorBackground, rgba(255,0,0,0.1))", borderRadius: 4, fontSize: 13, color: "var(--vscode-errorForeground)" }}>
                    {createError}
                  </div>
                )}
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div>
                    <label style={{ display: "block", fontSize: 12, marginBottom: 2 }}>Username *</label>
                    <input style={styles.input} value={createForm.username} onChange={(e) => setCreateForm((f) => ({ ...f, username: e.target.value }))} />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: 12, marginBottom: 2 }}>Email *</label>
                    <input style={styles.input} type="email" value={createForm.email} onChange={(e) => setCreateForm((f) => ({ ...f, email: e.target.value }))} />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: 12, marginBottom: 2 }}>Display Name *</label>
                    <input style={styles.input} value={createForm.display_name} onChange={(e) => setCreateForm((f) => ({ ...f, display_name: e.target.value }))} />
                  </div>
                  <p style={{ fontSize: 11, color: "var(--vscode-descriptionForeground)" }}>
                    A secure password will be auto-generated. The user must change it on first login.
                  </p>
                  <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                    <button style={{ ...styles.btn, flex: 1, background: "var(--vscode-button-secondaryBackground)", color: "var(--vscode-button-secondaryForeground)" }} onClick={handleCloseCreate}>Cancel</button>
                    <button style={{ ...styles.btn, flex: 1 }} onClick={() => createMutation.mutate(createForm)} disabled={!createForm.username || !createForm.email || !createForm.display_name || createMutation.isPending}>
                      {createMutation.isPending ? "Creating..." : "Create User"}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Reset Password Result Modal */}
      {resetResult && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
          <div style={{ background: "var(--vscode-editor-background)", border: "1px solid var(--vscode-panel-border)", borderRadius: 8, padding: 24, width: 400, maxWidth: "90vw" }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Password Reset</h2>
            <p style={{ fontSize: 13, marginBottom: 12 }}>New temporary password for <strong>{resetResult.user.display_name}</strong>:</p>
            <div style={{ padding: 12, background: "var(--vscode-inputValidation-warningBackground, rgba(255,200,0,0.1))", border: "1px solid var(--vscode-inputValidation-warningBorder, orange)", borderRadius: 4, marginBottom: 12 }}>
              <code style={{ fontSize: 13, fontFamily: "var(--vscode-editor-font-family)", wordBreak: "break-all" }}>
                {resetResult.password}
              </code>
              <p style={{ fontSize: 11, marginTop: 8, color: "var(--vscode-descriptionForeground)" }}>
                Copy this now — it cannot be retrieved later.
              </p>
            </div>
            <button style={styles.btn} onClick={() => setResetResult(null)}>Done</button>
          </div>
        </div>
      )}

      {isLoading ? <p>Loading...</p> : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Username</th>
              <th style={styles.th}>Display Name</th>
              <th style={styles.th}>Email</th>
              <th style={styles.th}>Roles</th>
              <th style={styles.th}>MFA</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Last Login</th>
              {!isProduction && <th style={styles.th}>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {data?.data.map((user) => (
              <tr key={user.id}>
                <td style={styles.td}>{user.username}</td>
                <td style={styles.td}>{user.display_name}</td>
                <td style={styles.td}>{user.email}</td>
                <td style={styles.td}>
                  {(user.roles ?? []).map((roleName) => (
                    <span key={roleName} style={{ ...styles.badge("var(--vscode-badge-background)"), color: "var(--vscode-badge-foreground)", marginRight: 4 }}>
                      {roleName}
                    </span>
                  ))}
                </td>
                <td style={styles.td}>
                  <span style={{ fontSize: 12, color: user.is_mfa_enabled ? "var(--vscode-charts-green)" : "var(--vscode-descriptionForeground)" }}>
                    {user.is_mfa_enabled ? "Enabled" : "Off"}
                  </span>
                </td>
                <td style={styles.td}>
                  <span style={styles.badge(user.is_active ? "var(--vscode-charts-green)" : "var(--vscode-charts-red)")}>
                    {user.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td style={{ ...styles.td, fontSize: 12, color: "var(--vscode-descriptionForeground)" }}>
                  {user.last_login_at ? new Date(user.last_login_at).toLocaleDateString() : "Never"}
                </td>
                {!isProduction && (
                  <td style={styles.td}>
                    <button
                      style={{ ...styles.btnSmall, marginRight: 4 }}
                      onClick={() => resetPasswordMutation.mutate(user)}
                      title="Reset password"
                    >
                      Reset PW
                    </button>
                    <button
                      style={{ ...styles.btnSmall, color: user.is_active ? "var(--vscode-charts-red)" : "var(--vscode-charts-green)" }}
                      onClick={() => toggleActiveMutation.mutate(user)}
                      title={user.is_active ? "Deactivate user" : "Activate user"}
                    >
                      {user.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------- Roles Admin ----------

interface RolePermission {
  id: string;
  resource: string;
  action: string;
  description?: string;
}

interface Role {
  id: string;
  name: string;
  display_name: string;
  description: string;
  is_system?: boolean;
  permissions: RolePermission[];
}

function RolesAdmin() {
  // API returns Role[] directly (not wrapped in { data: ... })
  const { data: roles, isLoading } = useQuery({
    queryKey: ["admin-roles"],
    queryFn: () => api.get<Role[]>("/roles"),
  });

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Roles & Permissions</h1>
      </div>
      {isLoading ? <p>Loading...</p> : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {(roles ?? []).map((role) => (
            <div key={role.id} style={{
              padding: 16,
              background: "var(--vscode-editor-inactiveSelectionBackground)",
              borderRadius: 6,
              border: "1px solid var(--vscode-panel-border)",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontWeight: 600, fontSize: 14 }}>{role.display_name || role.name}</span>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {role.is_system && (
                    <span style={{ ...styles.badge("var(--vscode-charts-blue)"), fontSize: 10 }}>System</span>
                  )}
                  <span style={{ fontSize: 12, color: "var(--vscode-descriptionForeground)" }}>{role.name}</span>
                </div>
              </div>
              {role.description && (
                <p style={{ fontSize: 12, color: "var(--vscode-descriptionForeground)", marginBottom: 8 }}>{role.description}</p>
              )}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {(role.permissions ?? []).map((p) => (
                  <span key={p.id} style={{ ...styles.badge("var(--vscode-badge-background)"), color: "var(--vscode-badge-foreground)", fontWeight: 400 }}>
                    {p.resource}:{p.action}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------- Variables Admin (SOAS + Incident) ----------

interface Variable {
  id: string;
  key: string;
  value: string;
  description?: string;
  is_secret?: boolean;
  created_at: string;
}

function VariablesAdmin({ endpoint, title }: { endpoint: string; title: string }) {
  const { isProduction } = useDeploymentMode();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newDescription, setNewDescription] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-variables", endpoint],
    queryFn: () => api.get<{ data: Variable[] }>(`${endpoint}?per_page=100`),
  });

  const createMutation = useMutation({
    mutationFn: () => api.post(endpoint, { key: newKey, value: newValue, description: newDescription }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-variables", endpoint] });
      setShowCreate(false);
      setNewKey("");
      setNewValue("");
      setNewDescription("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`${endpoint}/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-variables", endpoint] }),
  });

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>{title}</h1>
        {!isProduction && (
          <button style={styles.btn} onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? "Cancel" : "+ Add Variable"}
          </button>
        )}
      </div>

      {showCreate && !isProduction && (
        <div style={{ padding: 16, marginBottom: 16, background: "var(--vscode-editor-inactiveSelectionBackground)", borderRadius: 6, display: "flex", flexDirection: "column", gap: 8 }}>
          <input style={styles.input} placeholder="Key" value={newKey} onChange={(e) => setNewKey(e.target.value)} />
          <input style={styles.input} placeholder="Value" value={newValue} onChange={(e) => setNewValue(e.target.value)} />
          <input style={styles.input} placeholder="Description (optional)" value={newDescription} onChange={(e) => setNewDescription(e.target.value)} />
          <button style={styles.btn} onClick={() => createMutation.mutate()} disabled={!newKey || !newValue}>
            Create
          </button>
        </div>
      )}

      {isLoading ? <p>Loading...</p> : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Key</th>
              <th style={styles.th}>Value</th>
              <th style={styles.th}>Description</th>
              {!isProduction && <th style={styles.th}>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {data?.data.map((v) => (
              <tr key={v.id}>
                <td style={{ ...styles.td, fontFamily: "var(--vscode-editor-font-family)" }}>{v.key}</td>
                <td style={{ ...styles.td, fontFamily: "var(--vscode-editor-font-family)", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {v.is_secret ? "••••••" : v.value}
                </td>
                <td style={{ ...styles.td, color: "var(--vscode-descriptionForeground)" }}>{v.description}</td>
                {!isProduction && (
                  <td style={styles.td}>
                    <button style={{ ...styles.btnSmall, color: "var(--vscode-charts-red)" }} onClick={() => deleteMutation.mutate(v.id)}>
                      Delete
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------- Form Definitions Admin ----------

interface FormDefinition {
  id: string;
  name: string;
  description: string;
  fields: Array<{ key: string; label: string; type: string; required: boolean }>;
  created_at: string;
}

function FormDefinitionsAdmin() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-form-definitions"],
    queryFn: () => api.get<{ data: FormDefinition[] }>("/form-definitions?per_page=100"),
  });

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Form Definitions</h1>
      </div>
      {isLoading ? <p>Loading...</p> : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {data?.data.map((form) => (
            <div key={form.id} style={{
              padding: 16,
              background: "var(--vscode-editor-inactiveSelectionBackground)",
              borderRadius: 6,
              border: "1px solid var(--vscode-panel-border)",
            }}>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{form.name}</div>
              {form.description && <p style={{ fontSize: 12, color: "var(--vscode-descriptionForeground)", marginBottom: 8 }}>{form.description}</p>}
              <div style={{ fontSize: 12, color: "var(--vscode-descriptionForeground)" }}>
                {form.fields.length} field{form.fields.length !== 1 ? "s" : ""}: {form.fields.map((f) => f.label).join(", ")}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------- Webhooks Admin ----------

interface Webhook {
  id: string;
  name: string;
  path: string;
  is_active: boolean;
  source_name?: string;
  created_at: string;
}

function WebhooksAdmin() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-webhooks"],
    queryFn: () => api.get<{ data: Webhook[] }>("/webhooks?per_page=100"),
  });

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Webhooks</h1>
      </div>
      {isLoading ? <p>Loading...</p> : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Name</th>
              <th style={styles.th}>Path</th>
              <th style={styles.th}>Source</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Created</th>
            </tr>
          </thead>
          <tbody>
            {data?.data.map((wh) => (
              <tr key={wh.id}>
                <td style={styles.td}>{wh.name}</td>
                <td style={{ ...styles.td, fontFamily: "var(--vscode-editor-font-family)" }}>{wh.path}</td>
                <td style={styles.td}>{wh.source_name || "—"}</td>
                <td style={styles.td}>
                  <span style={styles.badge(wh.is_active ? "var(--vscode-charts-green)" : "var(--vscode-charts-red)")}>
                    {wh.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td style={styles.td}>{new Date(wh.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------- Review Changes Admin ----------

interface ChangeRequest {
  id: string;
  entity_type: string;
  entity_name: string;
  action: string;
  status: string;
  submitted_by?: { display_name: string };
  created_at: string;
}

function ReviewChangesAdmin() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["admin-review-changes"],
    queryFn: () => api.get<{ data: ChangeRequest[] }>("/change-requests/pending"),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => api.post(`/change-requests/${id}/approve`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-review-changes"] }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => api.post(`/change-requests/${id}/reject`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-review-changes"] }),
  });

  const STATUS_COLORS: Record<string, string> = {
    submitted: "var(--vscode-charts-yellow)",
    approved: "var(--vscode-charts-green)",
    rejected: "var(--vscode-charts-red)",
    draft: "var(--vscode-descriptionForeground)",
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Review Changes</h1>
      </div>
      {isLoading ? <p>Loading...</p> : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Entity</th>
              <th style={styles.th}>Action</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Submitted By</th>
              <th style={styles.th}>Date</th>
              <th style={styles.th}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data?.data.map((cr) => (
              <tr key={cr.id}>
                <td style={styles.td}>
                  <span style={{ fontSize: 11, color: "var(--vscode-descriptionForeground)" }}>{cr.entity_type}/</span>
                  {cr.entity_name}
                </td>
                <td style={styles.td}>{cr.action}</td>
                <td style={styles.td}>
                  <span style={styles.badge(STATUS_COLORS[cr.status] || "gray")}>{cr.status}</span>
                </td>
                <td style={styles.td}>{cr.submitted_by?.display_name || "—"}</td>
                <td style={styles.td}>{new Date(cr.created_at).toLocaleDateString()}</td>
                <td style={styles.td}>
                  {cr.status === "submitted" && (
                    <>
                      <button style={{ ...styles.btnSmall, background: "var(--vscode-charts-green)", color: "#fff" }} onClick={() => approveMutation.mutate(cr.id)}>
                        Approve
                      </button>
                      <button style={{ ...styles.btnSmall, background: "var(--vscode-charts-red)", color: "#fff" }} onClick={() => rejectMutation.mutate(cr.id)}>
                        Reject
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {(!data?.data || data.data.length === 0) && (
              <tr>
                <td colSpan={6} style={{ ...styles.td, textAlign: "center", color: "var(--vscode-descriptionForeground)" }}>
                  No pending changes to review
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------- Settings Admin ----------

interface Setting {
  key: string;
  value: string;
  description?: string;
}

function SettingsAdmin() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-settings"],
    queryFn: () => api.get<{ data: Setting[] }>("/settings"),
  });

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>System Settings</h1>
      </div>
      {isLoading ? <p>Loading...</p> : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Setting</th>
              <th style={styles.th}>Value</th>
              <th style={styles.th}>Description</th>
            </tr>
          </thead>
          <tbody>
            {data?.data.map((s) => (
              <tr key={s.key}>
                <td style={{ ...styles.td, fontFamily: "var(--vscode-editor-font-family)" }}>{s.key}</td>
                <td style={{ ...styles.td, fontFamily: "var(--vscode-editor-font-family)" }}>{s.value}</td>
                <td style={{ ...styles.td, color: "var(--vscode-descriptionForeground)" }}>{s.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------- Generic List Admin ----------

function GenericListAdmin({ endpoint, title }: { endpoint: string; title: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-generic", endpoint],
    queryFn: () => api.get<{ data: Array<Record<string, unknown>> }>(endpoint),
  });

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>{title}</h1>
      </div>
      {isLoading ? <p>Loading...</p> : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {data?.data.map((item, i) => (
            <div key={i} style={{
              padding: 12,
              background: "var(--vscode-editor-inactiveSelectionBackground)",
              borderRadius: 4,
              fontSize: 13,
              fontFamily: "var(--vscode-editor-font-family)",
            }}>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                {JSON.stringify(item, null, 2)}
              </pre>
            </div>
          ))}
          {(!data?.data || data.data.length === 0) && (
            <p style={{ color: "var(--vscode-descriptionForeground)" }}>No items found</p>
          )}
        </div>
      )}
    </div>
  );
}
