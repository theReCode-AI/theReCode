import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { PublicOnlyRoute, ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { AppLayout } from "@/components/layout/AppLayout";
import { DashboardPage } from "@/pages/DashboardPage";
import { ChatPage } from "@/pages/ChatPage";
import { LoginPage } from "@/pages/LoginPage";
import { ProjectDetailPage } from "@/pages/ProjectDetailPage";
import { ProjectsPage } from "@/pages/ProjectsPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { RunApprovalsPage } from "@/pages/RunApprovalsPage";
import { RunChatPage } from "@/pages/RunChatPage";
import { RunDetailPage } from "@/pages/RunDetailPage";
import { RunDiffPage } from "@/pages/RunDiffPage";
import { RunFindingsPage } from "@/pages/RunFindingsPage";
import { RunOverviewPage } from "@/pages/RunOverviewPage";
import { RunReportsPage } from "@/pages/RunReportsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { useAuthStore } from "@/stores/authStore";

export function AppRoutes() {
  const loadUser = useAuthStore((state) => state.loadUser);
  const token = useAuthStore((state) => state.token);

  useEffect(() => {
    if (token) {
      void loadUser();
    }
  }, [loadUser, token]);

  return (
    <Routes>
      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />}>
            <Route index element={<RunOverviewPage />} />
            <Route path="findings" element={<RunFindingsPage />} />
            <Route path="diff" element={<RunDiffPage />} />
            <Route path="approvals" element={<RunApprovalsPage />} />
            <Route path="reports" element={<RunReportsPage />} />
            <Route path="chat" element={<RunChatPage />} />
          </Route>
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
