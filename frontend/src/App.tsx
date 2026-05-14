import { lazy, Suspense } from "react";
import { Routes, Route, Navigate, useParams } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { DashboardLayout } from "@/components/layout/DashboardLayout";

// Auth pages kept eager (small, needed immediately)
import { LoginPage } from "@/pages/auth/LoginPage";
import { RegisterPage } from "@/pages/auth/RegisterPage";
import { ChangePasswordPage } from "@/pages/auth/ChangePasswordPage";

// Lazy-loaded pages — only fetched when the route is visited
const DashboardPage = lazy(() => import("@/pages/dashboard/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const DashboardListPage = lazy(() => import("@/pages/dashboards/DashboardListPage").then((m) => ({ default: m.DashboardListPage })));
const DashboardDetailPage = lazy(() => import("@/pages/dashboards/DashboardDetailPage").then((m) => ({ default: m.DashboardDetailPage })));
const DashboardEditPage = lazy(() => import("@/pages/dashboards/DashboardEditPage").then((m) => ({ default: m.DashboardEditPage })));
const AdminAlertCategoriesPage = lazy(() => import("@/pages/admin/AdminAlertCategoriesPage").then((m) => ({ default: m.AdminAlertCategoriesPage })));
const SavedQueriesPage = lazy(() => import("@/pages/saved-queries/SavedQueriesPage").then((m) => ({ default: m.SavedQueriesPage })));
const AdminSLAPage = lazy(() => import("@/pages/admin/AdminSLAPage").then((m) => ({ default: m.AdminSLAPage })));
const IncidentListPage = lazy(() => import("@/pages/incidents/IncidentListPage").then((m) => ({ default: m.IncidentListPage })));
const IncidentDetailPage = lazy(() => import("@/pages/incidents/IncidentDetailPage").then((m) => ({ default: m.IncidentDetailPage })));
const CreateIncidentPage = lazy(() => import("@/pages/incidents/CreateIncidentPage").then((m) => ({ default: m.CreateIncidentPage })));
const CaseListPage = lazy(() => import("@/pages/cases/CaseListPage").then((m) => ({ default: m.CaseListPage })));
const CaseDetailPage = lazy(() => import("@/pages/cases/CaseDetailPage").then((m) => ({ default: m.CaseDetailPage })));
const AutomationListPage = lazy(() => import("@/pages/automations/AutomationListPage").then((m) => ({ default: m.AutomationListPage })));
const AutomationDetailPage = lazy(() => import("@/pages/automations/AutomationDetailPage").then((m) => ({ default: m.AutomationDetailPage })));
const UploadAutomationPage = lazy(() => import("@/pages/automations/UploadAutomationPage").then((m) => ({ default: m.UploadAutomationPage })));
const GraphEditorPage = lazy(() => import("@/pages/automations/GraphEditorPage").then((m) => ({ default: m.GraphEditorPage })));
const DependencyGraphPage = lazy(() => import("@/pages/automations/DependencyGraphPage").then((m) => ({ default: m.DependencyGraphPage })));
const ExecutionListPage = lazy(() => import("@/pages/executions/ExecutionListPage").then((m) => ({ default: m.ExecutionListPage })));
const ExecutionDetailPage = lazy(() => import("@/pages/executions/ExecutionDetailPage").then((m) => ({ default: m.ExecutionDetailPage })));
const MonitoringDashboardPage = lazy(() => import("@/pages/monitoring/MonitoringDashboardPage").then((m) => ({ default: m.MonitoringDashboardPage })));
const CodeLibraryPage = lazy(() => import("@/pages/code-library/CodeLibraryPage").then((m) => ({ default: m.CodeLibraryPage })));
const AdminUsersPage = lazy(() => import("@/pages/admin/AdminUsersPage").then((m) => ({ default: m.AdminUsersPage })));
const AdminRolesPage = lazy(() => import("@/pages/admin/AdminRolesPage").then((m) => ({ default: m.AdminRolesPage })));
const AdminSettingsPage = lazy(() => import("@/pages/admin/AdminSettingsPage").then((m) => ({ default: m.AdminSettingsPage })));
const IncidentVariablesPage = lazy(() => import("@/pages/admin/IncidentVariablesPage").then((m) => ({ default: m.IncidentVariablesPage })));
const SOASVariablesPage = lazy(() => import("@/pages/admin/SOASVariablesPage").then((m) => ({ default: m.SOASVariablesPage })));
const WebhooksPage = lazy(() => import("@/pages/admin/WebhooksPage").then((m) => ({ default: m.WebhooksPage })));
const NormalizationEditorPage = lazy(() => import("@/pages/admin/NormalizationEditorPage").then((m) => ({ default: m.NormalizationEditorPage })));
const WebhookSourcesPage = lazy(() => import("@/pages/admin/WebhookSourcesPage").then((m) => ({ default: m.WebhookSourcesPage })));
const FormDefinitionsPage = lazy(() => import("@/pages/admin/FormDefinitionsPage").then((m) => ({ default: m.FormDefinitionsPage })));
const IssueListPage = lazy(() => import("@/pages/issues/IssueListPage").then((m) => ({ default: m.IssueListPage })));
const IssueDetailPage = lazy(() => import("@/pages/issues/IssueDetailPage").then((m) => ({ default: m.IssueDetailPage })));
const CreateIssuePage = lazy(() => import("@/pages/issues/CreateIssuePage").then((m) => ({ default: m.CreateIssuePage })));
const WikiListPage = lazy(() => import("@/pages/wiki/WikiListPage").then((m) => ({ default: m.WikiListPage })));
const WikiPageView = lazy(() => import("@/pages/wiki/WikiPageView").then((m) => ({ default: m.WikiPageView })));
const WikiPageEditor = lazy(() => import("@/pages/wiki/WikiPageEditor").then((m) => ({ default: m.WikiPageEditor })));
const WikiVersionHistory = lazy(() => import("@/pages/wiki/WikiVersionHistory").then((m) => ({ default: m.WikiVersionHistory })));
const UserSecretsPage = lazy(() => import("@/pages/UserSecretsPage").then((m) => ({ default: m.UserSecretsPage })));
const AdminUserSecretsPage = lazy(() => import("@/pages/admin/AdminUserSecretsPage").then((m) => ({ default: m.AdminUserSecretsPage })));
const LocalChangesPage = lazy(() => import("@/pages/LocalChangesPage").then((m) => ({ default: m.LocalChangesPage })));
const ReviewChangesPage = lazy(() => import("@/pages/admin/ReviewChangesPage").then((m) => ({ default: m.ReviewChangesPage })));
const TeamsPage = lazy(() => import("@/pages/teams/TeamsPage").then((m) => ({ default: m.TeamsPage })));
const TeamDetailPage = lazy(() => import("@/pages/teams/TeamDetailPage").then((m) => ({ default: m.TeamDetailPage })));
const TeamVariablesPage = lazy(() => import("@/pages/teams/TeamVariablesPage").then((m) => ({ default: m.TeamVariablesPage })));

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const mustResetPassword = useAuthStore((s) => s.mustResetPassword);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (mustResetPassword) return <Navigate to="/change-password" replace />;
  return <>{children}</>;
}

function PageFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  );
}

function WikiSlugRouter() {
  const { "*": slugPath = "" } = useParams();
  if (slugPath.endsWith("/edit")) return <WikiPageEditor />;
  if (slugPath.endsWith("/history")) return <WikiVersionHistory />;
  return <WikiPageView />;
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/change-password" element={<ChangePasswordPage />} />

        {/* Protected routes */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />

          {/* Custom dashboards (Phase 2) */}
          <Route path="dashboards" element={<DashboardListPage />} />
          <Route path="dashboards/:id" element={<DashboardDetailPage />} />
          <Route path="dashboards/:id/edit" element={<DashboardEditPage />} />

          {/* Saved queries (Phase 4) */}
          <Route path="saved-queries" element={<SavedQueriesPage />} />

          {/* Incidents */}
          <Route path="incidents" element={<IncidentListPage />} />
          <Route path="incidents/new" element={<CreateIncidentPage />} />
          <Route path="incidents/:id" element={<IncidentDetailPage />} />

          {/* Incident Groups (formerly Cases) */}
          <Route path="cases" element={<CaseListPage />} />
          <Route path="cases/:id" element={<CaseDetailPage />} />

          {/* Issues */}
          <Route path="issues" element={<IssueListPage />} />
          <Route path="issues/new" element={<CreateIssuePage />} />
          <Route path="issues/:id" element={<IssueDetailPage />} />

          {/* Automations */}
          <Route path="automations" element={<AutomationListPage />} />
          <Route path="automations/new" element={<GraphEditorPage />} />
          <Route path="automations/upload" element={<UploadAutomationPage />} />
          <Route path="automations/:id" element={<AutomationDetailPage />} />
          <Route path="automations/:id/dependencies" element={<DependencyGraphPage />} />
          <Route path="automations/:id/editor" element={<GraphEditorPage />} />

          {/* Wiki */}
          <Route path="wiki" element={<WikiListPage />} />
          <Route path="wiki/new" element={<WikiPageEditor />} />
          <Route path="wiki/*" element={<WikiSlugRouter />} />

          {/* Code Library */}
          <Route path="code-library" element={<CodeLibraryPage />} />

          {/* Jobs — redirect to executions page with jobs tab */}
          <Route path="jobs" element={<Navigate to="/executions?tab=jobs" replace />} />

          {/* Teams */}
          <Route path="teams" element={<TeamsPage />} />
          <Route path="teams/:id" element={<TeamDetailPage />} />
          <Route path="team-variables" element={<TeamVariablesPage />} />

          {/* My Secrets */}
          <Route path="my-secrets" element={<UserSecretsPage />} />

          {/* Local Changes */}
          <Route path="local-changes" element={<LocalChangesPage />} />

          {/* Executions */}
          <Route path="executions" element={<ExecutionListPage />} />
          <Route path="executions/:id" element={<ExecutionDetailPage />} />

          {/* Monitoring */}
          <Route path="monitoring" element={<MonitoringDashboardPage />} />

          {/* Admin */}
          <Route path="admin/users" element={<AdminUsersPage />} />
          <Route path="admin/roles" element={<AdminRolesPage />} />
          <Route path="admin/alert-categories" element={<AdminAlertCategoriesPage />} />
          <Route path="admin/slas" element={<AdminSLAPage />} />
          <Route path="admin/soas-variables" element={<SOASVariablesPage />} />
          <Route path="admin/incident-variables" element={<IncidentVariablesPage />} />
          <Route path="admin/form-definitions" element={<FormDefinitionsPage />} />
          <Route path="admin/webhooks" element={<WebhooksPage />} />
          <Route path="admin/webhook-sources" element={<WebhookSourcesPage />} />
          <Route path="admin/normalization" element={<NormalizationEditorPage />} />
          <Route path="admin/user-secrets" element={<AdminUserSecretsPage />} />
          <Route path="admin/review-changes" element={<ReviewChangesPage />} />
          <Route path="settings" element={<AdminSettingsPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
