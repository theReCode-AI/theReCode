import { Navigate, Outlet, useLocation } from "react-router-dom";

import { LoadingState } from "@/components/common/LoadingState";
import { useAuthStore } from "@/stores/authStore";

export function ProtectedRoute() {
  const location = useLocation();
  const token = useAuthStore((state) => state.token);
  const isHydrated = useAuthStore((state) => state.isHydrated);

  if (!isHydrated) {
    return <LoadingState message="Restoring session..." />;
  }

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}

export function PublicOnlyRoute() {
  const token = useAuthStore((state) => state.token);
  const isHydrated = useAuthStore((state) => state.isHydrated);

  if (!isHydrated) {
    return <LoadingState message="Loading..." />;
  }

  if (token) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
