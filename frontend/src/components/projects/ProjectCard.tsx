import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listRepositories } from "@/api/projects";
import { listRuns } from "@/api/runs";
import {
  ActiveRunsStatIcon,
  ChevronRightIcon,
  ProjectsStatIcon,
  RecentRunsStatIcon,
  RepositoriesStatIcon,
} from "@/components/common/SidebarNavIcons";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { useAuthStore } from "@/stores/authStore";
import type { Project } from "@/types/project";
import type { RunStatus } from "@/types/run";
import { formatDateTime } from "@/utils/runStages";

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

interface ProjectInsight {
  repositoryCount: number;
  runCount: number;
  activeRunCount: number;
  latestStatus: RunStatus | null;
  latestUpdatedAt: string | null;
}

async function loadProjectInsight(projectId: string, token: string): Promise<ProjectInsight> {
  const [repositories, runs] = await Promise.all([
    listRepositories(projectId, token),
    listRuns(projectId, token),
  ]);

  const sortedRuns = [...runs].sort(
    (left, right) =>
      new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime(),
  );
  const latest = sortedRuns[0] ?? null;

  return {
    repositoryCount: repositories.length,
    runCount: runs.length,
    activeRunCount: runs.filter((run) => !TERMINAL_STATUSES.has(run.status)).length,
    latestStatus: latest?.status ?? null,
    latestUpdatedAt: latest?.updated_at ?? null,
  };
}

interface ProjectCardProps {
  project: Project;
}

export function ProjectCard({ project }: ProjectCardProps) {
  const token = useAuthStore((state) => state.token);

  const insightQuery = useQuery({
    queryKey: ["project-insight", project.id],
    queryFn: () => loadProjectInsight(project.id, token!),
    enabled: Boolean(token && project.id),
  });

  const insight = insightQuery.data;

  return (
    <Link
      to={`/projects/${project.id}`}
      className="group block rounded-xl border border-gray-200 bg-gray-50 p-4 transition hover:border-blue-300 hover:bg-blue-50 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-blue-600 dark:hover:bg-gray-800"
    >
      <div className="flex items-start gap-3">
        <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/40">
          <ProjectsStatIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h3 className="truncate font-semibold text-gray-900 dark:text-white">{project.name}</h3>
            <ChevronRightIcon className="h-4 w-4 shrink-0 text-gray-400 transition group-hover:text-blue-600 dark:group-hover:text-blue-400" />
          </div>
          <p className="mt-1 line-clamp-2 text-sm text-gray-600 dark:text-gray-400">
            {project.description ?? "No description"}
          </p>

          <div className="mt-3 grid grid-cols-3 gap-2 border-t border-gray-200 pt-3 dark:border-gray-700">
            <InsightStat
              icon={RepositoriesStatIcon}
              label="Repos"
              value={insightQuery.isLoading ? "…" : String(insight?.repositoryCount ?? 0)}
              tone="blue"
            />
            <InsightStat
              icon={RecentRunsStatIcon}
              label="Runs"
              value={insightQuery.isLoading ? "…" : String(insight?.runCount ?? 0)}
              tone="violet"
            />
            <InsightStat
              icon={ActiveRunsStatIcon}
              label="Active"
              value={insightQuery.isLoading ? "…" : String(insight?.activeRunCount ?? 0)}
              tone="emerald"
            />
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            {insight?.latestStatus ? (
              <>
                <span>Latest</span>
                <RunStatusBadge status={insight.latestStatus} />
                {insight.latestUpdatedAt ? (
                  <span className="text-gray-400 dark:text-gray-500">
                    · {formatDateTime(insight.latestUpdatedAt)}
                  </span>
                ) : null}
              </>
            ) : (
              <span>Updated {formatDateTime(project.updated_at)}</span>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}

function InsightStat({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof RepositoriesStatIcon;
  label: string;
  value: string;
  tone: "blue" | "violet" | "emerald";
}) {
  const tones = {
    blue: "text-blue-600 dark:text-blue-400",
    violet: "text-violet-600 dark:text-violet-400",
    emerald: "text-emerald-600 dark:text-emerald-400",
  };

  return (
    <div className="min-w-0">
      <div className={`mb-0.5 flex items-center gap-1 ${tones[tone]}`}>
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate text-[10px] font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-sm font-semibold text-gray-900 dark:text-white">{value}</p>
    </div>
  );
}
