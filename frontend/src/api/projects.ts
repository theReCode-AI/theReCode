import { apiGet, apiPost } from "./client";
import type { Project, ProjectCreate, Repository, RepositoryCreate } from "@/types/project";

export async function listProjects(token: string): Promise<Project[]> {
  return apiGet<Project[]>("/projects", token);
}

export async function getProject(projectId: string, token: string): Promise<Project> {
  return apiGet<Project>(`/projects/${projectId}`, token);
}

export async function createProject(payload: ProjectCreate, token: string): Promise<Project> {
  return apiPost<Project>("/projects", payload, token);
}

export async function listRepositories(projectId: string, token: string): Promise<Repository[]> {
  return apiGet<Repository[]>(`/projects/${projectId}/repositories`, token);
}

export async function createRepository(
  projectId: string,
  payload: RepositoryCreate,
  token: string,
): Promise<Repository> {
  return apiPost<Repository>(`/projects/${projectId}/repositories`, payload, token);
}
