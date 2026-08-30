import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Spinner, Textarea } from "flowbite-react";
import { FormEvent, useEffect, useRef, useState } from "react";

import { clearChatMessages, listChatMessages, sendChatMessage } from "@/api/chat";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { useAuthStore } from "@/stores/authStore";
import type { ChatMessage } from "@/types/chat";

interface RunChatPanelProps {
  runId: string;
  projectLabel?: string;
}

export function RunChatPanel({ runId, projectLabel }: RunChatPanelProps) {
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const messagesQuery = useQuery({
    queryKey: ["chat-messages", runId],
    queryFn: () => listChatMessages(runId, token!),
    enabled: Boolean(token && runId),
  });

  const sendMutation = useMutation({
    mutationFn: (content: string) => sendChatMessage(runId, content, token!),
    onSuccess: (response) => {
      queryClient.setQueryData<ChatMessage[]>(["chat-messages", runId], (current) => [
        ...(current ?? []),
        response.user_message,
        response.assistant_message,
      ]);
      setDraft("");
    },
  });

  const clearMutation = useMutation({
    mutationFn: () => clearChatMessages(runId, token!),
    onSuccess: () => {
      queryClient.setQueryData<ChatMessage[]>(["chat-messages", runId], []);
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messagesQuery.data, sendMutation.isPending]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || sendMutation.isPending) {
      return;
    }
    sendMutation.mutate(content);
  }

  if (messagesQuery.isLoading) {
    return <LoadingState message="Loading conversation..." />;
  }

  if (messagesQuery.isError) {
    return <ErrorState message="Unable to load chat messages for this run." />;
  }

  const messages = messagesQuery.data ?? [];

  return (
    <div className="flex h-[min(70vh,720px)] flex-col rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-center justify-between gap-3 border-b border-gray-200 px-4 py-3 dark:border-gray-700">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-gray-900 dark:text-white">
            Run chat{projectLabel ? ` · ${projectLabel}` : ""}
          </p>
          <p className="truncate font-mono text-xs text-gray-500 dark:text-gray-400">{runId}</p>
        </div>
        <Button
          color="light"
          size="xs"
          disabled={clearMutation.isPending || messages.length === 0}
          onClick={() => clearMutation.mutate()}
        >
          Clear
        </Button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <EmptyState message="Ask about findings, status, reports, or what happened in this run." />
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap ${
                  message.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-900 dark:bg-gray-900 dark:text-gray-100"
                }`}
              >
                {message.content}
              </div>
            </div>
          ))
        )}
        {sendMutation.isPending ? (
          <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <Spinner size="sm" />
            Gemini is thinking…
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>

      {sendMutation.isError ? (
        <Alert color="failure" className="mx-4 mb-2">
          {(sendMutation.error as Error).message || "Failed to send message."}
        </Alert>
      ) : null}

      <form onSubmit={handleSubmit} className="border-t border-gray-200 p-4 dark:border-gray-700">
        <Textarea
          rows={3}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask a question about this run…"
          disabled={sendMutation.isPending}
        />
        <div className="mt-3 flex justify-end">
          <Button type="submit" disabled={sendMutation.isPending || !draft.trim()}>
            {sendMutation.isPending ? "Sending…" : "Send"}
          </Button>
        </div>
      </form>
    </div>
  );
}
