import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Label, TextInput } from "flowbite-react";
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

      <Card className="mb-4">
        <form onSubmit={handleSubmit}>
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Create project</h2>
          <div className="mb-4 grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="projectName">Name</Label>
              <TextInput
                id="projectName"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="projectDescription">Description</Label>
              <TextInput
                id="projectDescription"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </div>
          </div>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Creating..." : "Create project"}
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Your projects</h2>
        {!data || data.length === 0 ? (
          <EmptyState message="No projects yet." />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.map((project) => (
              <Link
                key={project.id}
                to={`/projects/${project.id}`}
                className="block rounded-xl border border-gray-200 bg-gray-50 p-4 transition hover:border-blue-300 hover:bg-blue-50"
              >
                <h3 className="font-semibold text-gray-900">{project.name}</h3>
                <p className="mt-1 text-sm text-gray-600">{project.description ?? "No description"}</p>
                <small className="mt-2 block text-xs text-gray-500">
                  Updated {formatDateTime(project.updated_at)}
                </small>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </section>
  );
}
