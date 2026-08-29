import { useQuery } from "@tanstack/react-query";
import { Card, Label, Select } from "flowbite-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { listProjects } from "@/api/projects";
import { listRuns } from "@/api/runs";
import { RunChatPanel } from "@/components/chat/RunChatPanel";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { useAuthStore } from "@/stores/authStore";

export function ChatPage() {
  const token = useAuthStore((state) => state.token);
  const [searchParams, setSearchParams] = useSearchParams();
  const [projectId, setProjectId] = useState(searchParams.get("projectId") ?? "");
  const [runId, setRunId] = useState(searchParams.get("runId") ?? "");

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => listProjects(token!),
    enabled: Boolean(token),
  });

  const runsQuery = useQuery({
    queryKey: ["runs", projectId],
    queryFn: () => listRuns(projectId, token!),
    enabled: Boolean(token && projectId),
  });

  const selectedProject = useMemo(
    () => projectsQuery.data?.find((project) => project.id === projectId) ?? null,
    [projectsQuery.data, projectId],
  );

  useEffect(() => {
    const next = new URLSearchParams();
    if (projectId) {
      next.set("projectId", projectId);
    }
    if (runId) {
      next.set("runId", runId);
    }
    setSearchParams(next, { replace: true });
  }, [projectId, runId, setSearchParams]);

  useEffect(() => {
    if (!projectId) {
      setRunId("");
      return;
    }
    if (!runsQuery.data) {
      return;
    }
    const exists = runsQuery.data.some((run) => run.id === runId);
    if (!exists) {
      setRunId(runsQuery.data[0]?.id ?? "");
    }
  }, [projectId, runId, runsQuery.data]);

  if (projectsQuery.isLoading) {
    return <LoadingState />;
  }

  if (projectsQuery.isError) {
    return <ErrorState message="Unable to load projects." />;
  }

  const projects = projectsQuery.data ?? [];

  return (
    <section className="w-full max-w-none">
      <PageHeader
        title="Chat"
        subtitle="Select a project, then a run, and ask Gemini about that run’s findings and status."
      />

      <Card className="mb-4 w-full">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="chatProject">Project</Label>
            <Select
              id="chatProject"
              value={projectId}
              onChange={(event) => {
                setProjectId(event.target.value);
                setRunId("");
              }}
            >
              <option value="">Select a project</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="chatRun">Run</Label>
            <Select
              id="chatRun"
              value={runId}
              disabled={!projectId || runsQuery.isLoading}
              onChange={(event) => setRunId(event.target.value)}
            >
              <option value="">
                {!projectId
                  ? "Select a project first"
                  : runsQuery.isLoading
                    ? "Loading runs…"
                    : "Select a run"}
              </option>
              {(runsQuery.data ?? []).map((run) => (
                <option key={run.id} value={run.id}>
                  {run.id.slice(-8)} · {run.status}
                </option>
              ))}
            </Select>
          </div>
        </div>
        {projectId && runsQuery.isError ? (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">Unable to load runs.</p>
        ) : null}
        {projectId && !runsQuery.isLoading && (runsQuery.data?.length ?? 0) === 0 ? (
          <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
            No runs for this project yet.{" "}
            <Link to={`/projects/${projectId}`} className="text-blue-600 hover:underline">
              Create a run
            </Link>
            .
          </p>
        ) : null}
      </Card>

      {!projectId || !runId ? (
        <Card className="w-full">
          <EmptyState message="Choose a project and run to start the conversation." />
        </Card>
      ) : (
        <RunChatPanel runId={runId} projectLabel={selectedProject?.name} />
      )}
    </section>
  );
}
