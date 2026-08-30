import { apiDelete, apiGet, apiPost } from "@/api/client";
import type { GitCredential, GitCredentialCreate } from "@/types/git";
import type { GitProvider } from "@/types/project";

export async function listGitCredentials(token: string): Promise<GitCredential[]> {
  return apiGet<GitCredential[]>("/git/credentials", token);
}

export async function saveGitCredential(
  payload: GitCredentialCreate,
  token: string,
): Promise<GitCredential> {
  return apiPost<GitCredential>("/git/credentials", payload, token);
}

export async function deleteGitCredential(
  provider: GitProvider,
  token: string,
): Promise<void> {
  return apiDelete(`/git/credentials/${provider}`, token);
}
