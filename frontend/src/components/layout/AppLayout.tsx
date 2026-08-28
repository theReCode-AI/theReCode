import { NavLink, Outlet } from "react-router-dom";

import { HealthStatus } from "@/components/HealthStatus";
import { useAppStore } from "@/stores/appStore";
import { useAuthStore } from "@/stores/authStore";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", end: true },
  { to: "/projects", label: "Projects" },
  { to: "/settings", label: "Settings" },
];

export function AppLayout() {
  const sidebarOpen = useAppStore((state) => state.sidebarOpen);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);
  const user = useAuthStore((state) => state.user);
  const clearSession = useAuthStore((state) => state.clearSession);

  return (
    <div className={`app-shell ${sidebarOpen ? "sidebar-open" : "sidebar-collapsed"}`}>
      <aside className="app-sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">CT</span>
          <div>
            <strong>CodeThera</strong>
            <small>Autonomous Engineer</small>
          </div>
        </div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <HealthStatus />
        </div>
      </aside>

      <div className="app-main">
        <header className="app-topbar">
          <button type="button" className="ghost-button" onClick={toggleSidebar}>
            Menu
          </button>
          <div className="topbar-user">
            <span>{user?.full_name ?? user?.email}</span>
            <button type="button" className="ghost-button" onClick={clearSession}>
              Sign out
            </button>
          </div>
        </header>
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
