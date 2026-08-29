import { useQuery } from "@tanstack/react-query";
import { Card, Table, TableBody, TableCell, TableHead, TableHeadCell, TableRow } from "flowbite-react";
import type { ComponentType, SVGProps } from "react";
import { Link } from "react-router-dom";

import { listProjects } from "@/api/projects";
import { listRuns } from "@/api/runs";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import {
  ActiveRunsStatIcon,
  ProjectsStatIcon,
  RecentRunsStatIcon,
} from "@/components/common/SidebarNavIcons";
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

interface StatCardProps {
  label: string;
  value: number;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  iconClassName: string;
  iconWrapClassName: string;
}

function StatCard({
  label,
  value,
  icon: Icon,
  iconClassName,
  iconWrapClassName,
}: StatCardProps) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{label}</p>
          <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{value}</p>
        </div>
        <span
          className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${iconWrapClassName}`}
        >
          <Icon className={`h-6 w-6 ${iconClassName}`} />
        </span>
      </div>
    </Card>
  );
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
        <StatCard
          label="Projects"
          value={projects?.length ?? 0}
          icon={ProjectsStatIcon}
          iconWrapClassName="bg-blue-100 dark:bg-blue-900/40"
          iconClassName="text-blue-600 dark:text-blue-400"
        />
        <StatCard
          label="Active runs"
          value={activeRuns}
          icon={ActiveRunsStatIcon}
          iconWrapClassName="bg-emerald-100 dark:bg-emerald-900/40"
          iconClassName="text-emerald-600 dark:text-emerald-400"
        />
        <StatCard
          label="Recent runs"
          value={recentRuns?.length ?? 0}
          icon={RecentRunsStatIcon}
          iconWrapClassName="bg-violet-100 dark:bg-violet-900/40"
          iconClassName="text-violet-600 dark:text-violet-400"
        />
      </div>

      <Card>
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RecentRunsStatIcon className="h-5 w-5 text-violet-600 dark:text-violet-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Recent runs</h2>
          </div>
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
                      <Link
                        to={`/runs/${run.id}`}
                        className="font-medium text-blue-600 hover:underline"
                      >
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
