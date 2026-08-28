export type HumanDecision = "approve" | "reject" | "request_changes";

export interface ApprovalDecisionRequest {
  decision: HumanDecision;
  feedback?: string;
}

export interface ApprovalDecisionResponse {
  approval: HumanApproval;
  run_status: string;
  replanning_required: boolean;
}

export interface PrepareApprovalsResponse {
  run_id: string;
  approvals: HumanApproval[];
  approval_count: number;
  pending_count: number;
  run_status: string;
}

export interface ApprovalDiffResponse {
  approval_id: string;
  run_id: string;
  diff_path: string;
  content: string;
}

export interface FixAttemptDiffResponse {
  fix_attempt_id: string;
  run_id: string;
  diff_path: string;
  content: string;
  changed_files: string[];
}

export interface HumanApproval {
  approval_id: string;
  run_id: string;
  patch_plan_id: string | null;
  trigger: string;
  status: string;
  reason: string;
  issue_title: string | null;
  root_cause: string | null;
  risk_level: string | null;
  affected_files: string[];
  diff_artifact_path: string | null;
  evidence_summary: string | null;
  expected_tests: string[];
  verification_summary: string | null;
  reviewer_feedback: string[];
  human_decision: string | null;
  human_feedback: string | null;
  created_at: string;
}
