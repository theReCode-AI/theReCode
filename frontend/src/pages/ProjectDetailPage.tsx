import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Label, Select, Table, TableBody, TableCell, TableHead, TableHeadCell, TableRow, TextInput } from "flowbite-react";
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
    <section className="w-full max-w-none">
      <PageHeader
        title={projectQuery.data.name}
        subtitle={projectQuery.data.description ?? "Project workspace"}
        actions={
          <Link to="/projects" className="text-sm font-medium text-blue-600 hover:underline">
            Back to projects
          </Link>
        }
      />

      <Card className="mb-4 w-full">
        <form onSubmit={handleRepositorySubmit}>
          <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Link repository</h2>
          <div className="mb-4 grid gap-4 sm:grid-cols-3">
            <div>
              <Label htmlFor="provider">Provider</Label>
              <Select
                id="provider"
                value={provider}
                onChange={(event) => setProvider(event.target.value as GitProvider)}
              >
                <option value="github">GitHub</option>
                <option value="gitlab">GitLab</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="fullName">Repository</Label>
              <TextInput
                id="fullName"
                placeholder="owner/repo or https://github.com/owner/repo"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="defaultBranch">Default branch</Label>
              <TextInput
                id="defaultBranch"
                value={defaultBranch}
                onChange={(event) => setDefaultBranch(event.target.value)}
                required
              />
            </div>
          </div>
          <Button type="submit" disabled={createRepositoryMutation.isPending}>
            {createRepositoryMutation.isPending ? "Linking..." : "Link repository"}
          </Button>
        </form>
      </Card>

      <Card className="mb-4 w-full">
        <h2 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">Start run</h2>
        <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
          Select a linked repository, then create a run. Open the run and use{" "}
          <strong>Clone repository</strong> on the Overview tab to pull the code. Save your Git token
          under Settings first.
        </p>
        <div className="mb-4 w-full sm:max-w-xl">
          <Label htmlFor="repository">Repository</Label>
          <Select
            id="repository"
            value={selectedRepositoryId}
            onChange={(event) => setSelectedRepositoryId(event.target.value)}
          >
            <option value="">No repository selected</option>
            {repositories.map((repository) => (
              <option key={repository.id} value={repository.id}>
                {repository.full_name} ({repository.default_branch})
              </option>
            ))}
          </Select>
        </div>
        <Button
          type="button"
          disabled={createRunMutation.isPending || !selectedRepositoryId}
          onClick={() => createRunMutation.mutate()}
        >
          {createRunMutation.isPending ? "Creating run..." : "Create run"}
        </Button>
      </Card>

      <Card className="mb-4 w-full">
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Linked repositories</h2>
        {repositories.length === 0 ? (
          <EmptyState message="No repositories linked yet." />
        ) : (
          <ul className="list-disc space-y-2 pl-5 text-sm text-gray-700 dark:text-gray-300">
            {repositories.map((repository) => (
              <li key={repository.id}>
                <strong>{repository.full_name}</strong> · {repository.provider} ·{" "}
                {repository.default_branch}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="w-full">
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Runs</h2>
        {runs.length === 0 ? (
          <EmptyState message="No runs for this project yet." />
        ) : (
          <div className="overflow-x-auto">
            <Table hoverable>
              <TableHead>
                <TableRow>
                  <TableHeadCell>Run</TableHeadCell>
                  <TableHeadCell>Status</TableHeadCell>
                  <TableHeadCell>Created</TableHeadCell>
                  <TableHeadCell>Report</TableHeadCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {runs.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>
                      <Link to={`/runs/${run.id}`} className="font-medium text-blue-600 hover:underline">
                        {run.id.slice(-8)}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <RunStatusBadge status={run.status} />
                    </TableCell>
                    <TableCell>{formatDateTime(run.created_at)}</TableCell>
                    <TableCell>
                      {["COMPLETED", "REPORTING"].includes(run.status) ? (
                        <Link to={`/runs/${run.id}/reports`} className="text-sm font-medium text-blue-600 hover:underline">
                          View report
                        </Link>
                      ) : (
                        "—"
                      )}
                    </TableCell>
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
