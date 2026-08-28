import type { GitProvider } from "@/types/project";

export interface GitCredential {
  id: string;
  provider: GitProvider;
  token_label: string | null;
  created_at: string;
  updated_at: string;
}

export interface GitCredentialCreate {
  provider: GitProvider;
  access_token: string;
  token_label?: string;
}
