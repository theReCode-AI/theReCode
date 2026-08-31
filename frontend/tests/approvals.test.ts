import { describe, expect, it } from "vitest";

import type { HumanApproval } from "@/types/approval";
import type { RiskDecision } from "@/types/run";
import {
  countPendingApprovals,
  hasRiskApprovalTriggers,
  shouldShowPrepareApprovals,
} from "@/utils/approvals";

const riskDecision: RiskDecision = {
  risk_decision_id: "risk-1",
  run_id: "run-1",
  patch_plan_id: "plan-1",
  estimated_risk: "high",
  assessed_risk: "high",
  autonomy_decision: "human_review",
  approval_required: true,
  autonomous_fix_allowed: false,
  rationale: "High risk change",
  created_at: "2026-01-01T00:00:00Z",
};

const pendingApproval: HumanApproval = {
  approval_id: "approval-1",
  run_id: "run-1",
  patch_plan_id: "plan-1",
  trigger: "risk_gate",
  status: "pending",
  reason: "Needs review",
  issue_title: "Auth issue",
  root_cause: "Unsafe auth",
  risk_level: "high",
  affected_files: ["src/auth.py"],
  diff_artifact_path: null,
  evidence_summary: null,
  expected_tests: [],
  verification_summary: null,
  reviewer_feedback: [],
  human_decision: null,
  human_feedback: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("approvals utils", () => {
  it("detects risk approval triggers", () => {
    expect(hasRiskApprovalTriggers([riskDecision])).toBe(true);
    expect(
      hasRiskApprovalTriggers([{ ...riskDecision, approval_required: false }]),
    ).toBe(false);
  });

  it("counts pending approvals", () => {
    expect(countPendingApprovals([pendingApproval])).toBe(1);
    expect(
      countPendingApprovals([{ ...pendingApproval, status: "approved" }]),
    ).toBe(0);
  });

  it("shows prepare when risk requires approval but cards are missing", () => {
    expect(shouldShowPrepareApprovals([], [riskDecision], false)).toBe(true);
    expect(shouldShowPrepareApprovals([pendingApproval], [riskDecision], false)).toBe(
      false,
    );
    expect(shouldShowPrepareApprovals([], [], true, "AWAITING_APPROVAL")).toBe(true);
    expect(shouldShowPrepareApprovals([], [], true, "COMPLETED")).toBe(false);
  });
});
