import { apiDelete, apiGet, apiPost } from "./client";
import type { ChatMessage, ChatSendResponse } from "@/types/chat";

export async function listChatMessages(runId: string, token: string): Promise<ChatMessage[]> {
  return apiGet<ChatMessage[]>(`/runs/${runId}/chat/messages`, token);
}

export async function sendChatMessage(
  runId: string,
  content: string,
  token: string,
): Promise<ChatSendResponse> {
  return apiPost<ChatSendResponse>(`/runs/${runId}/chat/messages`, { content }, token);
}

export async function clearChatMessages(runId: string, token: string): Promise<void> {
  return apiDelete(`/runs/${runId}/chat/messages`, token);
}
