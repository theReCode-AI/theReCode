import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { createProject, listProjects } from "@/api/projects";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { useAuthStore } from "@/stores/authStore";
import { formatDateTime } from "@/utils/runStages";

export function ProjectsPage() {
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["projects"],
    queryFn: () => listProjects(token!),
    enabled: Boolean(token),
  });

  const createMutation = useMutation({
    mutationFn: (payload: { name: string; description?: string }) =>
      createProject(payload, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setName("");
      setDescription("");
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createMutation.mutate({
      name,
      description: description.trim() ? description : undefined,
    });
  }

  if (isLoading) {
    return <LoadingState />;
  }

  if (isError) {
    return <ErrorState message="Unable to load projects." />;
  }

  return (
    <section>
      <PageHeader title="Projects" subtitle="Organize repositories and autonomous runs." />

      <form className="panel form-panel" onSubmit={handleSubmit}>
        <h2>Create project</h2>
        <div className="form-grid">
          <label>
            Name
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label>
            Description
            <input
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
        </div>
        <button type="submit" className="primary-button" disabled={createMutation.isPending}>
          {createMutation.isPending ? "Creating..." : "Create project"}
        </button>
      </form>

      <section className="panel">
        <h2>Your projects</h2>
        {!data || data.length === 0 ? (
          <EmptyState message="No projects yet." />
        ) : (
          <div className="card-grid">
            {data.map((project) => (
              <Link key={project.id} to={`/projects/${project.id}`} className="project-card">
                <h3>{project.name}</h3>
                <p>{project.description ?? "No description"}</p>
                <small>Updated {formatDateTime(project.updated_at)}</small>
              </Link>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
