import { useCallback, useEffect, useRef, useState } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { ToastContainer } from "@/components/ui/Toast";
import { useAuthStore } from "@/stores/authStore";
import { useTokenExpiration, type UrgencyLevel } from "@/hooks/useTokenExpiration";
import { useDeploymentMode } from "@/hooks/useDeploymentMode";
import { TeamSelector } from "@/components/ui/TeamSelector";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  AlertTriangle,
  Zap,
  Terminal,
  Users,
  ShieldCheck,
  Settings,
  LogOut,
  Shield,
  Variable,
  FileText,
  PanelLeftClose,
  PanelLeftOpen,
  Radio,
  Unplug,
  SlidersHorizontal,
  Heart,
  Code,
  Clock,
  RefreshCw,
  ClipboardList,
  CircleDot,
  BookOpen,
  Layers,
  KeyRound,
  ToggleLeft,
  ToggleRight,
  GitBranch,
  GitPullRequest,
  UsersRound,
  Tag,
} from "lucide-react";

import "./sidebar.css";

const SIDEBAR_WIDTH_KEY = "soasSidebarWidth";
const SIDEBAR_COLLAPSED_KEY = "soasSidebarCollapsed";
const SIDEBAR_DEFAULT = 228;
const SIDEBAR_MIN = 180;
const SIDEBAR_MAX = 420;

const urgencyColors: Record<UrgencyLevel, string> = {
  ok: "text-green-400",
  warning: "text-yellow-400",
  critical: "text-red-400",
  expired: "text-red-500",
};

const urgencyDotColors: Record<UrgencyLevel, string> = {
  ok: "bg-green-400",
  warning: "bg-yellow-400",
  critical: "bg-red-400 animate-pulse",
  expired: "bg-red-500 animate-pulse",
};

type NavItem = { to: string; label: string; icon: typeof LayoutDashboard };

const mainItems: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/dashboards", label: "Custom Dashboards", icon: LayoutDashboard },
  { to: "/incidents", label: "Incidents", icon: AlertTriangle },
  { to: "/cases", label: "Incident Groups", icon: Layers },
  { to: "/issues", label: "Issues", icon: CircleDot },
  { to: "/automations", label: "Automations", icon: Zap },
  { to: "/wiki", label: "Wiki", icon: BookOpen },
  { to: "/code-library", label: "Code Library", icon: Code },
  { to: "/executions", label: "Executions", icon: Terminal },
];

const workspaceItems: NavItem[] = [
  { to: "/teams", label: "Teams", icon: UsersRound },
  { to: "/team-variables", label: "Team Variables", icon: Variable },
  { to: "/my-secrets", label: "My Secrets", icon: KeyRound },
  { to: "/local-changes", label: "Local Changes", icon: GitBranch },
];

const adminItems: NavItem[] = [
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/roles", label: "Roles", icon: ShieldCheck },
  { to: "/admin/soas-variables", label: "SOAS Variables", icon: Variable },
  { to: "/admin/incident-variables", label: "Incident Variables", icon: FileText },
  { to: "/admin/form-definitions", label: "Forms", icon: ClipboardList },
  { to: "/admin/webhooks", label: "Webhooks", icon: Radio },
  { to: "/admin/webhook-sources", label: "Webhook Sources", icon: Unplug },
  { to: "/admin/normalization", label: "Normalization", icon: SlidersHorizontal },
  { to: "/admin/alert-categories", label: "Alert Categories", icon: Tag },
  { to: "/admin/user-secrets", label: "User Secrets", icon: KeyRound },
  { to: "/admin/review-changes", label: "Review Changes", icon: GitPullRequest },
  { to: "/monitoring", label: "Monitoring", icon: Heart },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function DashboardLayout() {
  const { user, logout, hasPermission, refreshSession, isRefreshing } = useAuthStore();
  const { remainingText, urgency } = useTokenExpiration();
  const { isDevMode, isProduction, canToggle, toggleDevMode } = useDeploymentMode();
  const navigate = useNavigate();

  // Width state: read from localStorage once on mount.
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [width, setWidth] = useState<number>(() => {
    try {
      const stored = parseInt(localStorage.getItem(SIDEBAR_WIDTH_KEY) ?? "", 10);
      if (Number.isFinite(stored) && stored >= SIDEBAR_MIN && stored <= SIDEBAR_MAX) {
        return stored;
      }
    } catch {
      /* ignore */
    }
    return SIDEBAR_DEFAULT;
  });

  // Drag-resize state.
  const draggingRef = useRef(false);
  const onMouseMove = useCallback((event: MouseEvent) => {
    if (!draggingRef.current) return;
    const next = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, event.clientX));
    setWidth(next);
  }, []);
  const onMouseUp = useCallback(() => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    document.documentElement.classList.remove("xs-sidebar-dragging");
    try {
      localStorage.setItem(SIDEBAR_WIDTH_KEY, String(width));
    } catch {
      /* ignore */
    }
  }, [width]);
  useEffect(() => {
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [onMouseMove, onMouseUp]);
  const startDrag = useCallback(() => {
    draggingRef.current = true;
    document.documentElement.classList.add("xs-sidebar-dragging");
  }, []);

  // Push width + collapsed state into CSS via inline style on the root element.
  const rootStyle = {
    "--sidebar-width": collapsed ? `var(--sidebar-width-collapsed)` : `${width}px`,
  } as React.CSSProperties;

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, next ? "1" : "0");
    } catch {
      /* ignore */
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const showAdmin = hasPermission("user:read") || hasPermission("role:read");

  const userInitial = user?.display_name?.charAt(0).toUpperCase() ?? "U";
  const userRole = user?.roles?.[0] ?? "User";

  return (
    <div
      className={cn("xs-shell", collapsed && "xs-sidebar-collapsed")}
      style={rootStyle}
    >
      <aside className="xs-sidebar">
        <button
          type="button"
          className="xs-sidebar-toggle"
          onClick={toggleCollapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen size={12} /> : <PanelLeftClose size={12} />}
        </button>

        <a href="/dashboard" className="xs-brand">
          <span className="xs-brand-mark">SOAS</span>
          <span className="xs-brand-text">
            <span className="t">SOC on a Stick</span>
            <span className="s">Security Ops Platform</span>
          </span>
        </a>

        {/* Team selector — only render expanded; collapsed it's a no-op visually */}
        <div style={{ padding: collapsed ? "8px 0" : "10px 14px 0" }}>
          <TeamSelector collapsed={collapsed} />
        </div>

        {/* Deployment mode toggle */}
        <div style={{ padding: collapsed ? "6px 0" : "8px 14px 4px", display: "flex", justifyContent: collapsed ? "center" : "flex-start" }}>
          {canToggle ? (
            <button
              onClick={toggleDevMode}
              className={cn(
                "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wide transition-colors",
                isDevMode
                  ? "bg-[rgba(0,195,137,0.15)] text-[var(--color-sidebar-accent)] border border-[rgba(0,195,137,0.35)]"
                  : "bg-[rgba(124,138,160,0.15)] text-[var(--color-sidebar-fg-muted)] border border-[rgba(124,138,160,0.25)]",
              )}
              title={
                isDevMode
                  ? "Click to switch to production mode (read-only)"
                  : "Click to switch to development mode (editing enabled)"
              }
            >
              {isDevMode ? <ToggleRight size={12} /> : <ToggleLeft size={12} />}
              {!collapsed && (isDevMode ? "DEV" : "PROD")}
            </button>
          ) : (
            <div
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wide bg-[rgba(124,138,160,0.15)] text-[var(--color-sidebar-fg-muted)] border border-[rgba(124,138,160,0.25)]"
              title="Production mode — you don't have permission to enable development mode"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-sidebar-fg-muted)]" />
              {!collapsed && "PROD"}
            </div>
          )}
        </div>

        <nav>
          <div className="xs-nav-section">Workspace</div>
          <ul className="xs-nav">
            {mainItems.map(({ to, label, icon: Icon }) => (
              <li key={to}>
                <NavLink to={to} title={label} className={({ isActive }) => (isActive ? "active" : "")}>
                  <Icon className="xs-nav-icon" />
                  <span className="xs-nav-label">{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>

          <div className="xs-nav-section">Configuration</div>
          <ul className="xs-nav">
            {workspaceItems.map(({ to, label, icon: Icon }) => (
              <li key={to}>
                <NavLink to={to} title={label} className={({ isActive }) => (isActive ? "active" : "")}>
                  <Icon className="xs-nav-icon" />
                  <span className="xs-nav-label">{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>

          {showAdmin && (
            <>
              <div className="xs-nav-section">Admin</div>
              <ul className="xs-nav">
                {adminItems.map(({ to, label, icon: Icon }) => (
                  <li key={to}>
                    <NavLink to={to} title={label} className={({ isActive }) => (isActive ? "active" : "")}>
                      <Icon className="xs-nav-icon" />
                      <span className="xs-nav-label">{label}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </>
          )}
        </nav>

        <div className="xs-user-block">
          <div className="relative shrink-0">
            <div className="xs-user-avatar">{userInitial}</div>
            {collapsed && (
              <span
                className={cn(
                  "absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2",
                  urgencyDotColors[urgency],
                )}
                style={{ borderColor: "var(--color-sidebar-bg)" }}
                title={`Session: ${remainingText}`}
              />
            )}
          </div>
          {!collapsed && (
            <>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="xs-user-name" title={user?.display_name ?? ""}>
                  {user?.display_name ?? "Unknown"}
                </div>
                <div className={cn("xs-user-role flex items-center gap-1", urgencyColors[urgency])}>
                  <Clock size={10} />
                  <span>{userRole} · {remainingText}</span>
                </div>
              </div>
              <div className="xs-user-actions inline-flex items-center gap-1">
                <button
                  onClick={refreshSession}
                  disabled={isRefreshing}
                  className="p-1 text-[var(--color-sidebar-fg-muted)] hover:text-white disabled:opacity-50"
                  title="Refresh session"
                >
                  <RefreshCw size={12} className={isRefreshing ? "animate-spin" : ""} />
                </button>
                <button
                  onClick={handleLogout}
                  className="p-1 text-[var(--color-sidebar-fg-muted)] hover:text-white"
                  title="Logout"
                >
                  <LogOut size={12} />
                </button>
              </div>
            </>
          )}
        </div>
      </aside>

      {!collapsed && (
        <div
          className="xs-sidebar-resize"
          onMouseDown={(e) => {
            e.preventDefault();
            startDrag();
          }}
          role="separator"
          aria-orientation="vertical"
        />
      )}

      <main className="xs-main">
        {isProduction && (
          <div className="xs-prod-banner">
            <Shield size={14} className="shrink-0" />
            <span>
              Production mode — editing is restricted.{" "}
              {canToggle
                ? "Switch to development mode to make changes."
                : "Contact an admin for development mode access."}
            </span>
          </div>
        )}
        <div className="xs-workspace">
          <Outlet />
        </div>
      </main>

      <ToastContainer />
    </div>
  );
}
