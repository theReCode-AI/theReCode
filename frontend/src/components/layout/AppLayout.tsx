import { Button, Navbar, Sidebar, SidebarItemGroup, SidebarItems } from "flowbite-react";
import { NavLink, Outlet } from "react-router-dom";

import { MenuIcon } from "@/components/common/MenuIcon";
import {
  DashboardIcon,
  ProjectsIcon,
  SettingsIcon,
} from "@/components/common/SidebarNavIcons";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import { UserAvatar } from "@/components/common/UserAvatar";
import { AppFooter } from "@/components/layout/AppFooter";
import { HealthStatus } from "@/components/HealthStatus";
import { useAppStore } from "@/stores/appStore";
import { useAuthStore } from "@/stores/authStore";

const BRAND_LOGO = "/codethera-hero.png";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", end: true, icon: DashboardIcon },
  { to: "/projects", label: "Projects", icon: ProjectsIcon },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

const sidebarTheme = {
  root: {
    inner:
      "flex h-full flex-col overflow-y-auto bg-gray-900 px-3 py-4 dark:bg-gray-950",
  },
  itemGroup: {
    base: "mt-4 space-y-1 first:mt-0",
  },
};

export function AppLayout() {
  const sidebarOpen = useAppStore((state) => state.sidebarOpen);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);
  const user = useAuthStore((state) => state.user);
  const clearSession = useAuthStore((state) => state.clearSession);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-gray-900">
      {sidebarOpen ? (
        <Sidebar
          aria-label="CodeThera sidebar"
          className="sticky top-0 h-screen w-64 shrink-0"
          theme={sidebarTheme}
        >
          <div className="mb-6 px-2">
            <img
              src={BRAND_LOGO}
              alt="CodeThera"
              className="h-[120px] w-[250px] object-contain"
            />
          </div>
          <SidebarItems>
            <SidebarItemGroup>
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.to} className="list-none">
                    <NavLink
                      to={item.to}
                      end={item.end}
                      className={({ isActive }) =>
                        `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                          isActive
                            ? "bg-gray-700 text-white"
                            : "text-gray-300 hover:bg-gray-700 hover:text-white"
                        }`
                      }
                    >
                      <Icon className="h-5 w-5 shrink-0" />
                      {item.label}
                    </NavLink>
                  </li>
                );
              })}
            </SidebarItemGroup>
          </SidebarItems>
          <div className="mt-auto px-2 pt-6 text-sm text-gray-400">
            <HealthStatus />
          </div>
        </Sidebar>
      ) : null}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <Navbar
          fluid
          className="shrink-0 border-b border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800"
        >
          <div className="flex w-full items-center justify-between">
            <Button color="light" size="sm" onClick={toggleSidebar} aria-label="Toggle menu">
              <MenuIcon />
            </Button>
            <div className="flex items-center gap-3">
              <ThemeToggle />
              <UserAvatar fullName={user?.full_name} email={user?.email} />
              <Button color="light" size="sm" onClick={clearSession}>
                Sign out
              </Button>
            </div>
          </div>
        </Navbar>
        <main className="mx-auto w-full max-w-6xl flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
        <AppFooter />
      </div>
    </div>
  );
}
