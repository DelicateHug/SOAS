import { useState } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { useTokenExpiration, type UrgencyLevel } from "@/hooks/useTokenExpiration";
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
} from "lucide-react";

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

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/incidents", label: "Incidents", icon: AlertTriangle },
  { to: "/cases", label: "Incident Groups", icon: Layers },
  { to: "/issues", label: "Issues", icon: CircleDot },
  { to: "/automations", label: "Automations", icon: Zap },
  { to: "/wiki", label: "Wiki", icon: BookOpen },
  { to: "/code-library", label: "Code Library", icon: Code },
  { to: "/executions", label: "Executions", icon: Terminal },
];

const adminItems = [
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/roles", label: "Roles", icon: ShieldCheck },
  { to: "/admin/soas-variables", label: "SOAS Variables", icon: Variable },
  { to: "/admin/incident-variables", label: "Incident Variables", icon: FileText },
  { to: "/admin/form-definitions", label: "Forms", icon: ClipboardList },
  { to: "/admin/webhooks", label: "Webhooks", icon: Radio },
  { to: "/admin/webhook-sources", label: "Webhook Sources", icon: Unplug },
  { to: "/admin/normalization", label: "Normalization", icon: SlidersHorizontal },
  { to: "/monitoring", label: "Monitoring", icon: Heart },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function DashboardLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout, hasPermission, refreshSession, isRefreshing } = useAuthStore();
  const { remainingText, urgency } = useTokenExpiration();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const showAdmin = hasPermission("user:read") || hasPermission("role:read");

  return (
    <div className="flex h-screen bg-[hsl(var(--background))]">
      {/* Sidebar */}
      <aside
        className={`${
          collapsed ? "w-16" : "w-64"
        } shrink-0 border-r border-[hsl(var(--border))] flex flex-col transition-all duration-200`}
      >
        <div className="p-4 border-b border-[hsl(var(--border))] flex items-center justify-between">
          <div className={`flex items-center gap-2 ${collapsed ? "justify-center w-full" : ""}`}>
            <Shield className="w-6 h-6 text-[hsl(var(--primary))] shrink-0" />
            {!collapsed && (
              <div>
                <span className="font-bold text-lg">SOAS</span>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
                  SOC on a Stick
                </p>
              </div>
            )}
          </div>
          {!collapsed && (
            <button
              onClick={() => setCollapsed(true)}
              className="p-1 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
              title="Collapse sidebar"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          )}
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {collapsed && (
            <button
              onClick={() => setCollapsed(false)}
              className="flex items-center justify-center w-full py-2 rounded-md text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] hover:bg-[hsl(var(--accent))] mb-2"
              title="Expand sidebar"
            >
              <PanelLeftOpen className="w-4 h-4" />
            </button>
          )}
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              title={label}
              className={({ isActive }) =>
                `flex items-center ${collapsed ? "justify-center" : "gap-3"} px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                    : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))] hover:text-[hsl(var(--accent-foreground))]"
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              {!collapsed && label}
            </NavLink>
          ))}

          {showAdmin && (
            <>
              <div className={`pt-4 pb-1 ${collapsed ? "flex justify-center" : "px-3"}`}>
                {collapsed ? (
                  <div className="w-6 border-t border-[hsl(var(--border))]" />
                ) : (
                  <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider">
                    Admin
                  </p>
                )}
              </div>
              {adminItems.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  title={label}
                  className={({ isActive }) =>
                    `flex items-center ${collapsed ? "justify-center" : "gap-3"} px-3 py-2 rounded-md text-sm transition-colors ${
                      isActive
                        ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                        : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))] hover:text-[hsl(var(--accent-foreground))]"
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  {!collapsed && label}
                </NavLink>
              ))}
            </>
          )}
        </nav>

        <div className="p-3 border-t border-[hsl(var(--border))]">
          {!collapsed && (
            <div className="flex items-center justify-between px-3 py-1.5 mb-1">
              <div className={`flex items-center gap-1.5 text-xs ${urgencyColors[urgency]}`}>
                <Clock className="w-3 h-3" />
                <span>Session: {remainingText}</span>
              </div>
              <button
                onClick={refreshSession}
                disabled={isRefreshing}
                className="p-1 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] disabled:opacity-50"
                title="Refresh session"
              >
                <RefreshCw className={`w-3 h-3 ${isRefreshing ? "animate-spin" : ""}`} />
              </button>
            </div>
          )}

          <div className={`flex items-center ${collapsed ? "justify-center" : "gap-3"} px-3 py-2`}>
            <div className="relative shrink-0">
              <div className="w-8 h-8 rounded-full bg-[hsl(var(--primary))] flex items-center justify-center text-[hsl(var(--primary-foreground))] text-sm font-medium">
                {user?.display_name?.charAt(0).toUpperCase() || "U"}
              </div>
              {collapsed && (
                <span
                  className={`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-[hsl(var(--background))] ${urgencyDotColors[urgency]}`}
                  title={`Session: ${remainingText}`}
                />
              )}
            </div>
            {!collapsed && (
              <>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{user?.display_name}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] truncate">
                    {user?.roles?.[0] || "User"}
                  </p>
                </div>
                <button
                  onClick={handleLogout}
                  className="p-1 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                  title="Logout"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 overflow-auto">
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
