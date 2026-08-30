import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Label, Select, TextInput } from "flowbite-react";
import { FormEvent, useMemo, useState } from "react";

import { createProject, listProjects } from "@/api/projects";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { PlusIcon, ProjectsStatIcon } from "@/components/common/SidebarNavIcons";
import { ProjectCard } from "@/components/projects/ProjectCard";
import { useAuthStore } from "@/stores/authStore";
import type { Project } from "@/types/project";

type ProjectSort = "created_desc" | "created_asc";

function sortProjects(projects: Project[], sort: ProjectSort): Project[] {
  const sorted = [...projects];
  sorted.sort((left, right) => {
    const leftTime = new Date(left.created_at).getTime();
    const rightTime = new Date(right.created_at).getTime();
    return sort === "created_asc" ? leftTime - rightTime : rightTime - leftTime;
  });
  return sorted;
}

export function ProjectsPage() {
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [sort, setSort] = useState<ProjectSort>("created_desc");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["projects"],
    queryFn: () => listProjects(token!),
    enabled: Boolean(token),
  });

  const sortedProjects = useMemo(
    () => (data ? sortProjects(data, sort) : []),
    [data, sort],
  );

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
      <PageHeader
        title="Projects"
        subtitle="Organize repositories and autonomous runs."
        actions={
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/40">
            <ProjectsStatIcon className="h-6 w-6 text-blue-600 dark:text-blue-400" />
          </span>
        }
      />

      <Card className="mb-4">
        <form onSubmit={handleSubmit}>
          <div className="mb-4 flex items-center gap-2">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900/40">
              <PlusIcon className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            </span>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Create project</h2>
          </div>
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
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/40">
              <ProjectsStatIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </span>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Your projects</h2>
          </div>
          {data && data.length > 0 ? (
            <div className="w-full sm:w-52">
              <Label htmlFor="projectSort" className="sr-only">
                Sort by create date
              </Label>
              <Select
                id="projectSort"
                value={sort}
                onChange={(event) => setSort(event.target.value as ProjectSort)}
              >
                <option value="created_desc">Newest created</option>
                <option value="created_asc">Oldest created</option>
              </Select>
            </div>
          ) : null}
        </div>
        {!data || data.length === 0 ? (
          <EmptyState message="No projects yet." />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {sortedProjects.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
        )}
      </Card>
    </section>
  );
}
