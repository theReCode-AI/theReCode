import type { RunStatus } from "@/types/run";

export interface PipelineStage {
  key: string;
  label: string;
  statuses: RunStatus[];
}

export const PIPELINE_STAGES: PipelineStage[] = [
  { key: "clone", label: "Clone", statuses: ["CLONING"] },
  { key: "analyze", label: "Analyze", statuses: ["ANALYZING"] },
  { key: "diagnose", label: "Diagnose", statuses: ["DIAGNOSING"] },
  { key: "plan", label: "Plan", statuses: ["PLANNING", "AWAITING_APPROVAL"] },
  { key: "fix", label: "Fix", statuses: ["FIXING"] },
  { key: "verify", label: "Verify", statuses: ["VERIFYING", "SELF_CORRECTING"] },
  { key: "review", label: "Review", statuses: ["PEER_REVIEW", "FINAL_REVIEW"] },
  { key: "git", label: "Git", statuses: ["PUSHING"] },
  { key: "report", label: "Report", statuses: ["REPORTING"] },
  { key: "done", label: "Done", statuses: ["COMPLETED"] },
];

const STATUS_ORDER: RunStatus[] = [
  "CREATED",
  "CLONING",
  "ANALYZING",
  "DIAGNOSING",
  "PLANNING",
  "AWAITING_APPROVAL",
  "FIXING",
  "VERIFYING",
  "SELF_CORRECTING",
  "PEER_REVIEW",
  "FINAL_REVIEW",
  "PUSHING",
  "REPORTING",
  "COMPLETED",
];

export function getStageIndex(status: RunStatus): number {
  if (status === "FAILED" || status === "CANCELLED") {
    return STATUS_ORDER.indexOf("COMPLETED");
  }

  const stageIndex = PIPELINE_STAGES.findIndex((stage) => stage.statuses.includes(status));
  return stageIndex >= 0 ? stageIndex : 0;
}

export function getProgressPercent(status: RunStatus): number {
  if (status === "COMPLETED") {
    return 100;
  }

  if (status === "FAILED" || status === "CANCELLED") {
    return 0;
  }

  const index = STATUS_ORDER.indexOf(status);
  if (index < 0) {
    return 0;
  }

  return Math.round((index / (STATUS_ORDER.length - 1)) * 100);
}

const EVENT_LABELS: Record<string, string> = {
  RUN_CREATED: "Run created",
  CLONE_STARTED: "Repository clone started",
  CLONE_COMPLETED: "Repository cloned",
  CLONE_FAILED: "Repository clone failed",
  PROJECT_ANALYSIS_STARTED: "Project analysis started",
  PROJECT_ANALYSIS_COMPLETED: "Project intelligence generated",
  AGENT_STARTED: "Diagnostic agent started",
  AGENT_COMPLETED: "Diagnostic agent completed",
  FINDING_CREATED: "Finding recorded",
  ISSUE_GROUP_CREATED: "Root cause identified",
  FIX_PLAN_CREATED: "Fix planned",
  RISK_ASSESSED: "Risk assessed",
  APPROVAL_REQUIRED: "Human approval required",
  PATCH_APPLIED: "Patch applied",
  VERIFICATION_STARTED: "Verification started",
  VERIFICATION_FAILED: "Verification failed",
  VERIFICATION_PASSED: "Verification passed",
  SELF_CORRECTION_STARTED: "Self-correction started",
  SELF_CORRECTION_COMPLETED: "Self-correction completed",
  PEER_REVIEW_STARTED: "Peer review started",
  PEER_REVIEW_COMPLETED: "Peer review completed",
  HUMAN_APPROVED: "Human approved",
  HUMAN_REJECTED: "Human rejected",
  HUMAN_CHANGES_REQUESTED: "Changes requested",
  GIT_BRANCH_CREATED: "Branch created",
  GIT_COMMIT_CREATED: "Commit created",
  GIT_PUSH_COMPLETED: "Push completed",
  GIT_PR_CREATED: "PR created",
  REPORT_GENERATION_COMPLETED: "Report generated",
  RUN_COMPLETED: "Run completed",
  RUN_FAILED: "Run failed",
};

export function formatEventLabel(eventType: string): string {
  return EVENT_LABELS[eventType] ?? eventType.replace(/_/g, " ").toLowerCase();
}

export function formatStatus(status: string): string {
  return status.replace(/_/g, " ");
}

export function formatDateTime(value: string): string {
  return new Date(value).toLocaleString();
}
