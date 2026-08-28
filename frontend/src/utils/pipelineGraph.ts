import type { RunAgentState, RunStatus } from "@/types/run";

export type PipelineNodeState = "pending" | "active" | "complete" | "failed";

export interface PipelineGraphNode {
  id: string;
  label: string;
  x: number;
  y: number;
}

export interface PipelineGraphEdge {
  from: string;
  to: string;
  loop?: boolean;
}

export const PIPELINE_GRAPH_NODES: PipelineGraphNode[] = [
  { id: "initialization", label: "Init", x: 0, y: 24 },
  { id: "cloning", label: "Clone", x: 128, y: 24 },
  { id: "project_intelligence", label: "Analyze", x: 256, y: 24 },
  { id: "diagnostics", label: "Diagnose", x: 384, y: 24 },
  { id: "issue_correlation", label: "Correlate", x: 512, y: 24 },
  { id: "fix_planning", label: "Plan", x: 640, y: 24 },
  { id: "risk_assessment", label: "Risk", x: 768, y: 24 },
  { id: "code_fixing", label: "Fix", x: 768, y: 132 },
  { id: "verification", label: "Verify", x: 640, y: 132 },
  { id: "regression_testing", label: "Regression", x: 512, y: 132 },
  { id: "peer_review", label: "Peer review", x: 384, y: 132 },
  { id: "human_approval", label: "Approval", x: 256, y: 132 },
  { id: "memory", label: "Memory", x: 128, y: 132 },
  { id: "git_finalization", label: "Git", x: 0, y: 132 },
  { id: "reporting", label: "Report", x: 0, y: 240 },
  { id: "finalization", label: "Done", x: 128, y: 240 },
  { id: "self_correction", label: "Self-correct", x: 512, y: 240 },
];

export const PIPELINE_GRAPH_EDGES: PipelineGraphEdge[] = [
  { from: "initialization", to: "cloning" },
  { from: "cloning", to: "project_intelligence" },
  { from: "project_intelligence", to: "diagnostics" },
  { from: "diagnostics", to: "issue_correlation" },
  { from: "issue_correlation", to: "fix_planning" },
  { from: "fix_planning", to: "risk_assessment" },
  { from: "risk_assessment", to: "code_fixing" },
  { from: "code_fixing", to: "verification" },
  { from: "verification", to: "regression_testing" },
  { from: "regression_testing", to: "peer_review" },
  { from: "peer_review", to: "human_approval" },
  { from: "human_approval", to: "memory" },
  { from: "memory", to: "git_finalization" },
  { from: "git_finalization", to: "reporting" },
  { from: "reporting", to: "finalization" },
  { from: "verification", to: "self_correction" },
  { from: "self_correction", to: "verification", loop: true },
];

export const PIPELINE_GRAPH_ORDER = [
  "initialization",
  "cloning",
  "project_intelligence",
  "diagnostics",
  "issue_correlation",
  "fix_planning",
  "risk_assessment",
  "code_fixing",
  "verification",
  "self_correction",
  "regression_testing",
  "peer_review",
  "human_approval",
  "memory",
  "git_finalization",
  "reporting",
  "finalization",
] as const;

const RUN_STATUS_TO_STAGE: Partial<Record<RunStatus, (typeof PIPELINE_GRAPH_ORDER)[number]>> = {
  CREATED: "initialization",
  CLONING: "cloning",
  ANALYZING: "project_intelligence",
  DIAGNOSING: "diagnostics",
  PLANNING: "fix_planning",
  AWAITING_APPROVAL: "human_approval",
  FIXING: "code_fixing",
  VERIFYING: "verification",
  SELF_CORRECTING: "self_correction",
  PEER_REVIEW: "peer_review",
  FINAL_REVIEW: "finalization",
  PUSHING: "git_finalization",
  REPORTING: "reporting",
  COMPLETED: "finalization",
};

export const PIPELINE_GRAPH_WIDTH = 896;
export const PIPELINE_GRAPH_HEIGHT = 296;
export const PIPELINE_NODE_WIDTH = 108;
export const PIPELINE_NODE_HEIGHT = 36;

function normalizeStage(stage: string | null | undefined): string | null {
  if (!stage) {
    return null;
  }
  return stage.trim().toLowerCase();
}

function resolveActiveStage(
  status: RunStatus,
  currentStage: string | null | undefined,
): string | null {
  const normalizedCurrent = normalizeStage(currentStage);
  if (normalizedCurrent && PIPELINE_GRAPH_ORDER.includes(normalizedCurrent as never)) {
    return normalizedCurrent;
  }
  return RUN_STATUS_TO_STAGE[status] ?? null;
}

export function resolvePipelineNodeStates(params: {
  status: RunStatus;
  currentStage?: string | null;
  completedStages?: string[];
}): Record<string, PipelineNodeState> {
  const { status, currentStage, completedStages = [] } = params;
  const states = Object.fromEntries(
    PIPELINE_GRAPH_NODES.map((node) => [node.id, "pending" as PipelineNodeState]),
  );
  const completed = new Set(
    completedStages
      .map((stage) => normalizeStage(stage))
      .filter((stage): stage is string => Boolean(stage)),
  );
  const activeStage = resolveActiveStage(status, currentStage);
  const isFailed = status === "FAILED" || status === "CANCELLED";
  const isComplete = status === "COMPLETED";

  if (isComplete) {
    for (const node of PIPELINE_GRAPH_NODES) {
      states[node.id] = "complete";
    }
    return states;
  }

  if (completed.size > 0) {
    for (const stageId of completed) {
      if (stageId in states) {
        states[stageId] = "complete";
      }
    }
  } else if (activeStage) {
    const activeIndex = PIPELINE_GRAPH_ORDER.indexOf(activeStage as never);
    if (activeIndex >= 0) {
      for (let index = 0; index < activeIndex; index += 1) {
        states[PIPELINE_GRAPH_ORDER[index]] = "complete";
      }
    }
  }

  if (activeStage && activeStage in states) {
    states[activeStage] = isFailed ? "failed" : "active";
  }

  return states;
}

export function getGraphProgressPercent(params: {
  status: RunStatus;
  currentStage?: string | null;
  completedStages?: string[];
  progress?: number;
}): number {
  if (typeof params.progress === "number" && params.progress > 0) {
    return Math.min(100, Math.round(params.progress));
  }

  const nodeStates = resolvePipelineNodeStates(params);
  const completedCount = PIPELINE_GRAPH_NODES.filter(
    (node) => nodeStates[node.id] === "complete",
  ).length;

  if (params.status === "COMPLETED") {
    return 100;
  }

  return Math.round((completedCount / PIPELINE_GRAPH_NODES.length) * 100);
}

export function getActiveGraphNodeLabel(
  status: RunStatus,
  agentState?: RunAgentState | null,
): string | null {
  const activeStage = resolveActiveStage(status, agentState?.current_stage);
  if (!activeStage) {
    return null;
  }
  return PIPELINE_GRAPH_NODES.find((node) => node.id === activeStage)?.label ?? activeStage;
}
