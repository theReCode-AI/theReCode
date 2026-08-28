import { create } from "zustand";

import type { AgentEvent, Run, RunAgentState } from "@/types/run";

export type RunStreamConnectionStatus =
  | "idle"
  | "connecting"
  | "open"
  | "closed"
  | "error";

export interface RunLiveSlice {
  connectionStatus: RunStreamConnectionStatus;
  run: Run | null;
  state: RunAgentState | null;
  events: AgentEvent[];
  error: string | null;
}

interface RunLiveStoreState {
  runs: Record<string, RunLiveSlice>;
  initializeRun: (runId: string) => void;
  setConnectionStatus: (runId: string, status: RunStreamConnectionStatus) => void;
  setError: (runId: string, error: string | null) => void;
  applySnapshot: (
    runId: string,
    snapshot: { run: Run; state: RunAgentState | null; events: AgentEvent[] },
  ) => void;
  applyRunUpdate: (runId: string, run: Run) => void;
  applyStateUpdate: (runId: string, state: RunAgentState) => void;
  appendEvent: (runId: string, event: AgentEvent) => void;
  resetRun: (runId: string) => void;
}

const emptySlice = (): RunLiveSlice => ({
  connectionStatus: "idle",
  run: null,
  state: null,
  events: [],
  error: null,
});

export const useRunLiveStore = create<RunLiveStoreState>((set) => ({
  runs: {},
  initializeRun: (runId) =>
    set((current) => ({
      runs: {
        ...current.runs,
        [runId]: current.runs[runId] ?? emptySlice(),
      },
    })),
  setConnectionStatus: (runId, status) =>
    set((current) => ({
      runs: {
        ...current.runs,
        [runId]: {
          ...(current.runs[runId] ?? emptySlice()),
          connectionStatus: status,
        },
      },
    })),
  setError: (runId, error) =>
    set((current) => ({
      runs: {
        ...current.runs,
        [runId]: {
          ...(current.runs[runId] ?? emptySlice()),
          error,
          connectionStatus: error ? "error" : current.runs[runId]?.connectionStatus ?? "idle",
        },
      },
    })),
  applySnapshot: (runId, snapshot) =>
    set((current) => ({
      runs: {
        ...current.runs,
        [runId]: {
          ...(current.runs[runId] ?? emptySlice()),
          run: snapshot.run,
          state: snapshot.state,
          events: snapshot.events,
          connectionStatus: "open",
          error: null,
        },
      },
    })),
  applyRunUpdate: (runId, run) =>
    set((current) => ({
      runs: {
        ...current.runs,
        [runId]: {
          ...(current.runs[runId] ?? emptySlice()),
          run,
        },
      },
    })),
  applyStateUpdate: (runId, state) =>
    set((current) => ({
      runs: {
        ...current.runs,
        [runId]: {
          ...(current.runs[runId] ?? emptySlice()),
          state,
        },
      },
    })),
  appendEvent: (runId, event) =>
    set((current) => {
      const slice = current.runs[runId] ?? emptySlice();
      const exists = slice.events.some((existing) => existing.id === event.id);
      return {
        runs: {
          ...current.runs,
          [runId]: {
            ...slice,
            events: exists ? slice.events : [...slice.events, event],
          },
        },
      };
    }),
  resetRun: (runId) =>
    set((current) => {
      const nextRuns = { ...current.runs };
      delete nextRuns[runId];
      return { runs: nextRuns };
    }),
}));

export function useRunLiveSlice(runId: string): RunLiveSlice {
  return useRunLiveStore((state) => state.runs[runId] ?? emptySlice());
}
