export type RunStatus =
  | "CREATED"
  | "CLONING"
  | "ANALYZING"
  | "DIAGNOSING"
  | "PLANNING"
  | "AWAITING_APPROVAL"
  | "FIXING"
  | "VERIFYING"
  | "SELF_CORRECTING"
  | "PEER_REVIEW"
  | "FINAL_REVIEW"
  | "PUSHING"
  | "REPORTING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export interface Run {
  id: string;
  project_id: string;
  user_id: string;
  repository_id: string | null;
  status: RunStatus;
  workspace_path: string;
  created_at: string;
  updated_at: string;
}

export interface RunCreate {
  project_id: string;
  repository_id?: string;
}

export type OrchestrationStatus = "pending" | "running" | "completed" | "failed";

export interface RunAgentState {
  id: string;
  run_id: string;
  status: OrchestrationStatus;
  current_stage: string | null;
  current_agent: string | null;
  iteration: number;
  progress: number;
  approval_required: boolean;
  completed_stages: string[];
  completed_agents: string[];
  error_message: string | null;
  updated_at: string;
  created_at: string;
}

export interface AgentEvent {
  id: string;
  run_id: string;
  event_type: string;
  stage: string;
  agent: string | null;
  tool: string | null;
  status: string;
  message: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export type FindingSeverity = "critical" | "high" | "medium" | "low" | "info";

export interface Finding {
  finding_id: string;
  run_id: string;
  agent: string;
  tool: string;
  category: string;
  severity: FindingSeverity;
  confidence: number;
  file: string | null;
  line_start: number | null;
  line_end: number | null;
  message: string;
  rule_id: string | null;
  evidence: string | null;
  fixability: string;
  status: string;
  created_at: string;
}

export interface FixAttempt {
  fix_attempt_id: string;
  run_id: string;
  patch_plan_id: string;
  attempt_number: number;
  status: string;
  planned_files: string[];
  changed_files: string[];
  unexpected_files: string[];
  scope_violation: boolean;
  diff_artifact_path: string | null;
  error_message: string | null;
  created_at: string;
}

export interface VerificationResult {
  verification_result_id: string;
  run_id: string;
  fix_attempt_id: string;
  patch_plan_id: string;
  status: string;
  checks: Array<{ name: string; status: string; message: string | null }>;
  passed_checks: number;
  failed_checks: number;
  created_at: string;
}

export interface RiskDecision {
  risk_decision_id: string;
  run_id: string;
  patch_plan_id: string;
  estimated_risk: string;
  assessed_risk: string;
  autonomy_decision: string;
  approval_required: boolean;
  autonomous_fix_allowed: boolean;
  rationale: string;
  created_at: string;
}

export interface PeerReviewResult {
  peer_review_id: string;
  run_id: string;
  patch_plan_id: string;
  verdict: string;
  synthesis_summary: string;
  created_at: string;
}

export interface GitOperation {
  git_operation_id: string;
  run_id: string;
  project_id: string;
  repository_id: string;
  provider: string;
  status: string;
  branch_name: string | null;
  commit_sha: string | null;
  pull_request_url: string | null;
  failure_summary: string | null;
  created_at: string;
}

export interface RunReport {
  report_id: string;
  run_id: string;
  project_id: string;
  status: string;
  markdown_path: string;
  pdf_path: string;
  final_health_score: number;
  pull_request_url: string | null;
  branch_name: string | null;
  commit_sha: string | null;
  duration_ms: number;
  tool_versions: Record<string, string>;
  artifact_path: string | null;
  created_at: string;
}
