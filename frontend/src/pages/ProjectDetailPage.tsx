import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  createRepository,
  getProject,
  listRepositories,
} from "@/api/projects";
import { createRun, listRuns } from "@/api/runs";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { useAuthStore } from "@/stores/authStore";
import type { GitProvider } from "@/types/project";
import { formatDateTime } from "@/utils/runStages";

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();

  const [provider, setProvider] = useState<GitProvider>("github");
  const [fullName, setFullName] = useState("");
  const [defaultBranch, setDefaultBranch] = useState("main");
  const [selectedRepositoryId, setSelectedRepositoryId] = useState("");

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId, token!),
    enabled: Boolean(token && projectId),
  });

  const repositoriesQuery = useQuery({
    queryKey: ["repositories", projectId],
    queryFn: () => listRepositories(projectId, token!),
    enabled: Boolean(token && projectId),
  });

  const runsQuery = useQuery({
    queryKey: ["runs", projectId],
    queryFn: () => listRuns(projectId, token!),
    enabled: Boolean(token && projectId),
  });

  const createRepositoryMutation = useMutation({
    mutationFn: () =>
      createRepository(
        projectId,
        { provider, full_name: fullName, default_branch: defaultBranch },
        token!,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repositories", projectId] });
      setFullName("");
    },
  });

  const createRunMutation = useMutation({
    mutationFn: () =>
      createRun(
        {
          project_id: projectId,
          repository_id: selectedRepositoryId || undefined,
        },
        token!,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs", projectId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-runs"] });
    },
  });

  function handleRepositorySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createRepositoryMutation.mutate();
  }

  if (projectQuery.isLoading || repositoriesQuery.isLoading || runsQuery.isLoading) {
    return <LoadingState />;
  }

  if (projectQuery.isError || !projectQuery.data) {
    return <ErrorState message="Unable to load project." />;
  }

  const repositories = repositoriesQuery.data ?? [];
  const runs = runsQuery.data ?? [];

  return (
    <section>
      <PageHeader
        title={projectQuery.data.name}
        subtitle={projectQuery.data.description ?? "Project workspace"}
        actions={
          <Link to="/projects" className="text-link">
            Back to projects
          </Link>
        }
      />

      <form className="panel form-panel" onSubmit={handleRepositorySubmit}>
        <h2>Link repository</h2>
        <div className="form-grid">
          <label>
            Provider
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value as GitProvider)}
            >
              <option value="github">GitHub</option>
              <option value="gitlab">GitLab</option>
            </select>
          </label>
            <label>
            Repository
            <input
              placeholder="owner/repo or https://github.com/owner/repo"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
            />
          </label>
          <label>
            Default branch
            <input
              value={defaultBranch}
              onChange={(event) => setDefaultBranch(event.target.value)}
              required
            />
          </label>
        </div>
        <button
          type="submit"
          className="primary-button"
          disabled={createRepositoryMutation.isPending}
        >
          {createRepositoryMutation.isPending ? "Linking..." : "Link repository"}
        </button>
      </form>

      <section className="panel">
        <div className="panel-header">
          <h2>Start run</h2>
        </div>
        <p className="run-meta">
          Select a linked repository, then create a run. Open the run and use{" "}
          <strong>Clone repository</strong> on the Overview tab to pull the code. Save your Git token
          under Settings first.
        </p>
        <div className="form-grid">
          <label>
            Repository
            <select
              value={selectedRepositoryId}
              onChange={(event) => setSelectedRepositoryId(event.target.value)}
            >
              <option value="">No repository selected</option>
              {repositories.map((repository) => (
                <option key={repository.id} value={repository.id}>
                  {repository.full_name} ({repository.default_branch})
                </option>
              ))}
            </select>
          </label>
        </div>
        <button
          type="button"
          className="primary-button"
          disabled={createRunMutation.isPending || !selectedRepositoryId}
          onClick={() => createRunMutation.mutate()}
        >
          {createRunMutation.isPending ? "Creating run..." : "Create run"}
        </button>
      </section>

      <section className="panel">
        <h2>Linked repositories</h2>
        {repositories.length === 0 ? (
          <EmptyState message="No repositories linked yet." />
        ) : (
          <ul className="simple-list">
            {repositories.map((repository) => (
              <li key={repository.id}>
                <strong>{repository.full_name}</strong> · {repository.provider} ·{" "}
                {repository.default_branch}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <h2>Runs</h2>
        {runs.length === 0 ? (
          <EmptyState message="No runs for this project yet." />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Report</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <Link to={`/runs/${run.id}`}>{run.id.slice(-8)}</Link>
                    </td>
                    <td>
                      <RunStatusBadge status={run.status} />
                    </td>
                    <td>{formatDateTime(run.created_at)}</td>
                    <td>
                      {["COMPLETED", "REPORTING"].includes(run.status) ? (
                        <Link to={`/runs/${run.id}/reports`} className="text-link">
                          View report
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
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
