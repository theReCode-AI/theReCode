import { apiDelete, apiGet, apiPut } from "@/api/client";
import type { GeminiCredential, GeminiCredentialCreate } from "@/types/settings";

export async function getGeminiCredential(
  token: string,
): Promise<GeminiCredential | null> {
  return apiGet<GeminiCredential | null>("/settings/gemini-key", token);
}

export async function saveGeminiCredential(
  payload: GeminiCredentialCreate,
  token: string,
): Promise<GeminiCredential> {
  return apiPut<GeminiCredential>("/settings/gemini-key", payload, token);
}

export async function deleteGeminiCredential(token: string): Promise<void> {
  return apiDelete("/settings/gemini-key", token);
}
