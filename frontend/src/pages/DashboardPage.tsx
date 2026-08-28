import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listProjects } from "@/api/projects";
import { listRuns } from "@/api/runs";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { useAuthStore } from "@/stores/authStore";
import type { Run } from "@/types/run";
import { formatDateTime } from "@/utils/runStages";

async function loadDashboardRuns(token: string): Promise<Run[]> {
  const projects = await listProjects(token);
  const runsByProject = await Promise.all(
    projects.map((project) => listRuns(project.id, token)),
  );
  return runsByProject
    .flat()
    .sort(
      (left, right) =>
        new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime(),
    )
    .slice(0, 8);
}

export function DashboardPage() {
  const token = useAuthStore((state) => state.token);

  const { data: projects, isLoading: projectsLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => listProjects(token!),
    enabled: Boolean(token),
  });

  const {
    data: recentRuns,
    isLoading: runsLoading,
    isError,
  } = useQuery({
    queryKey: ["dashboard-runs"],
    queryFn: () => loadDashboardRuns(token!),
    enabled: Boolean(token),
  });

  if (projectsLoading || runsLoading) {
    return <LoadingState />;
  }

  if (isError) {
    return <ErrorState message="Unable to load dashboard data." />;
  }

  const activeRuns =
    recentRuns?.filter((run) => !["COMPLETED", "FAILED", "CANCELLED"].includes(run.status))
      .length ?? 0;

  return (
    <section>
      <PageHeader
        title="Dashboard"
        subtitle="Track autonomous runs, projects, and agent progress."
      />

      <div className="summary-grid dashboard-summary">
        <article className="summary-card">
          <span className="summary-label">Projects</span>
          <strong className="summary-value">{projects?.length ?? 0}</strong>
        </article>
        <article className="summary-card">
          <span className="summary-label">Active runs</span>
          <strong className="summary-value">{activeRuns}</strong>
        </article>
        <article className="summary-card">
          <span className="summary-label">Recent runs</span>
          <strong className="summary-value">{recentRuns?.length ?? 0}</strong>
        </article>
      </div>

      <section className="panel">
        <div className="panel-header">
          <h2>Recent runs</h2>
          <Link to="/projects" className="text-link">
            View projects
          </Link>
        </div>
        {!recentRuns || recentRuns.length === 0 ? (
          <EmptyState message="No runs yet. Create a project and start an autonomous run." />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <Link to={`/runs/${run.id}`}>{run.id.slice(-8)}</Link>
                    </td>
                    <td>
                      <RunStatusBadge status={run.status} />
                    </td>
                    <td>{formatDateTime(run.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}
