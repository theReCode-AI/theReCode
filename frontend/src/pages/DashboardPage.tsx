import { useQuery } from "@tanstack/react-query";
import { Card, Table, TableBody, TableCell, TableHead, TableHeadCell, TableRow } from "flowbite-react";
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

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-sm text-gray-500">Projects</p>
          <p className="text-3xl font-bold text-gray-900">{projects?.length ?? 0}</p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Active runs</p>
          <p className="text-3xl font-bold text-gray-900">{activeRuns}</p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Recent runs</p>
          <p className="text-3xl font-bold text-gray-900">{recentRuns?.length ?? 0}</p>
        </Card>
      </div>

      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Recent runs</h2>
          <Link to="/projects" className="text-sm font-medium text-blue-600 hover:underline">
            View projects
          </Link>
        </div>
        {!recentRuns || recentRuns.length === 0 ? (
          <EmptyState message="No runs yet. Create a project and start an autonomous run." />
        ) : (
          <div className="overflow-x-auto">
            <Table hoverable>
              <TableHead>
                <TableRow>
                  <TableHeadCell>Run</TableHeadCell>
                  <TableHeadCell>Status</TableHeadCell>
                  <TableHeadCell>Updated</TableHeadCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {recentRuns.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>
                      <Link to={`/runs/${run.id}`} className="font-medium text-blue-600 hover:underline">
                        {run.id.slice(-8)}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <RunStatusBadge status={run.status} />
                    </TableCell>
                    <TableCell>{formatDateTime(run.updated_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Card>
    </section>
  );
}
