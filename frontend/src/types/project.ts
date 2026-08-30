export type GitProvider = "github" | "gitlab";

export interface Project {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Repository {
  id: string;
  project_id: string;
  provider: GitProvider;
  full_name: string;
  default_branch: string;
  clone_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

export interface RepositoryCreate {
  provider: GitProvider;
  full_name: string;
  default_branch?: string;
  clone_url?: string;
}
