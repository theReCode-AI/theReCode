import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { consumeRunProgressStream } from "@/api/sse";
import { useAuthStore } from "@/stores/authStore";
import { useRunLiveStore } from "@/stores/runLiveStore";
import type { AgentEvent } from "@/types/run";

const EVENT_INVALIDATION_MAP: Record<string, string[][]> = {
  FINDING_CREATED: [["run-findings"]],
  AGENT_COMPLETED: [["run-findings"]],
  PATCH_APPLIED: [["run-fix-attempts"]],
  VERIFICATION_STARTED: [["run-verifications"]],
  VERIFICATION_PASSED: [["run-verifications"]],
  VERIFICATION_FAILED: [["run-verifications"]],
  RISK_ASSESSED: [["run-risk-decisions"]],
  APPROVAL_REQUIRED: [["run-approvals"]],
  HUMAN_APPROVED: [["run-approvals"], ["run"]],
  HUMAN_REJECTED: [["run-approvals"], ["run"]],
  HUMAN_CHANGES_REQUESTED: [["run-approvals"], ["run"]],
  PEER_REVIEW_STARTED: [["run-peer-reviews"]],
  PEER_REVIEW_COMPLETED: [["run-peer-reviews"]],
  GIT_FINALIZATION_COMPLETED: [["run-git-ops"], ["run"]],
  GIT_PR_CREATED: [["run-git-ops"], ["run-report"]],
  REPORT_GENERATION_COMPLETED: [["run-report"], ["run-report-markdown"], ["run"]],
  RUN_COMPLETED: [["run"], ["run-report"], ["run-report-markdown"], ["dashboard-runs"]],
  RUN_FAILED: [["run"], ["dashboard-runs"]],
};

function invalidateForAgentEvent(
  queryClient: ReturnType<typeof useQueryClient>,
  runId: string,
  event: AgentEvent,
) {
  const prefixes = EVENT_INVALIDATION_MAP[event.event_type] ?? [];
  for (const prefix of prefixes) {
    queryClient.invalidateQueries({ queryKey: [...prefix, runId] });
  }
}

export function useRunProgressStream(runId: string | undefined) {
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const initializeRun = useRunLiveStore((state) => state.initializeRun);
  const setConnectionStatus = useRunLiveStore((state) => state.setConnectionStatus);
  const setError = useRunLiveStore((state) => state.setError);
  const applySnapshot = useRunLiveStore((state) => state.applySnapshot);
  const applyRunUpdate = useRunLiveStore((state) => state.applyRunUpdate);
  const applyStateUpdate = useRunLiveStore((state) => state.applyStateUpdate);
  const appendEvent = useRunLiveStore((state) => state.appendEvent);
  const resetRun = useRunLiveStore((state) => state.resetRun);

  useEffect(() => {
    if (!runId || !token) {
      return;
    }

    initializeRun(runId);
    setConnectionStatus(runId, "connecting");
    setError(runId, null);

    const abortController = new AbortController();
    let isActive = true;

    void consumeRunProgressStream(
      runId,
      token,
      {
        onSnapshot: (snapshot) => {
          if (!isActive) {
            return;
          }
          applySnapshot(runId, snapshot);
          queryClient.setQueryData(["run", runId], snapshot.run);
          if (snapshot.state) {
            queryClient.setQueryData(["run-state", runId], snapshot.state);
          }
          queryClient.setQueryData(["run-events", runId], snapshot.events);
        },
        onRunUpdate: (run) => {
          if (!isActive) {
            return;
          }
          applyRunUpdate(runId, run);
          queryClient.setQueryData(["run", runId], run);
        },
        onStateUpdate: (state) => {
          if (!isActive) {
            return;
          }
          applyStateUpdate(runId, state);
          queryClient.setQueryData(["run-state", runId], state);
        },
        onAgentEvent: (event) => {
          if (!isActive) {
            return;
          }
          appendEvent(runId, event);
          queryClient.setQueryData(["run-events", runId], (current: AgentEvent[] | undefined) => {
            const events = current ?? [];
            if (events.some((existing) => existing.id === event.id)) {
              return events;
            }
            return [...events, event];
          });
          invalidateForAgentEvent(queryClient, runId, event);
        },
        onComplete: () => {
          if (!isActive) {
            return;
          }
          setConnectionStatus(runId, "closed");
          queryClient.invalidateQueries({ queryKey: ["run", runId] });
          queryClient.invalidateQueries({ queryKey: ["run-report", runId] });
          queryClient.invalidateQueries({ queryKey: ["run-report-markdown", runId] });
        },
        onError: (error) => {
          if (!isActive) {
            return;
          }
          setError(runId, error.message);
        },
      },
      abortController.signal,
    ).catch((error: unknown) => {
      if (!isActive || abortController.signal.aborted) {
        return;
      }
      const message = error instanceof Error ? error.message : "Live stream disconnected.";
      setError(runId, message);
      setConnectionStatus(runId, "error");
    });

    return () => {
      isActive = false;
      abortController.abort();
      resetRun(runId);
    };
  }, [
    appendEvent,
    applyRunUpdate,
    applySnapshot,
    applyStateUpdate,
    initializeRun,
    queryClient,
    resetRun,
    runId,
    setConnectionStatus,
    setError,
    token,
  ]);
}
