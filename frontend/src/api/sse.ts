import { getApiBaseUrl } from "./client";
import type { AgentEvent, Run, RunAgentState } from "@/types/run";

export interface RunProgressSnapshot {
  run: Run;
  state: RunAgentState | null;
  events: AgentEvent[];
}

export interface ParsedSseMessage {
  event: string;
  data: string;
  id?: string;
}

export interface RunStreamHandlers {
  onSnapshot: (snapshot: RunProgressSnapshot) => void;
  onRunUpdate: (run: Run) => void;
  onStateUpdate: (state: RunAgentState) => void;
  onAgentEvent: (event: AgentEvent) => void;
  onComplete: (payload: { run_id: string; status: string; reason: string }) => void;
  onHeartbeat?: () => void;
  onError?: (error: Error) => void;
}

export function parseSseChunk(chunk: string): ParsedSseMessage[] {
  const messages: ParsedSseMessage[] = [];
  const blocks = chunk.split("\n\n").filter((block) => block.trim().length > 0);

  for (const block of blocks) {
    let event = "message";
    let data = "";
    let id: string | undefined;

    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        data += line.slice(5).trim();
      } else if (line.startsWith("id:")) {
        id = line.slice(3).trim();
      }
    }

    if (data) {
      messages.push({ event, data, id });
    }
  }

  return messages;
}

function dispatchSseMessage(message: ParsedSseMessage, handlers: RunStreamHandlers): boolean {
  const payload = JSON.parse(message.data) as unknown;

  switch (message.event) {
    case "snapshot":
      handlers.onSnapshot(payload as RunProgressSnapshot);
      return true;
    case "run_update":
      handlers.onRunUpdate(payload as Run);
      return true;
    case "state_update":
      handlers.onStateUpdate(payload as RunAgentState);
      return true;
    case "agent_event":
      handlers.onAgentEvent(payload as AgentEvent);
      return true;
    case "heartbeat":
      handlers.onHeartbeat?.();
      return true;
    case "complete":
      handlers.onComplete(
        payload as { run_id: string; status: string; reason: string },
      );
      return false;
    default:
      return true;
  }
}

export async function consumeRunProgressStream(
  runId: string,
  token: string,
  handlers: RunStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/runs/${runId}/stream`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "text/event-stream",
    },
    signal,
  });

  if (!response.ok) {
    throw new Error(`SSE connection failed: ${response.status} ${response.statusText}`);
  }

  if (!response.body) {
    throw new Error("SSE response body is unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const messages = parseSseChunk(part);
      for (const message of messages) {
        const shouldContinue = dispatchSseMessage(message, handlers);
        if (!shouldContinue) {
          return;
        }
      }
    }
  }
}
