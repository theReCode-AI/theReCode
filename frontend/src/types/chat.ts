export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  run_id: string;
  project_id: string;
  role: ChatRole;
  content: string;
  created_at: string;
}

export interface ChatSendResponse {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
}
