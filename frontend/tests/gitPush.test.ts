import { describe, expect, it } from "vitest";

import { getGitPushEligibility } from "@/utils/gitPush";
import type { Run } from "@/types/run";

const baseRun: Run = {
  id: "run-1",
  project_id: "project-1",
  user_id: "user-1",
  repository_id: "repo-1",
  status: "COMPLETED",
  workspace_path: "/tmp/run-1",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("getGitPushEligibility", () => {
  it("allows push when applied fixes have changed files and reviews pass", () => {
    const result = getGitPushEligibility({
      run: baseRun,
      fixAttempts: [
        {
          fix_attempt_id: "fix-1",
          run_id: "run-1",
          patch_plan_id: "plan-1",
          attempt_number: 1,
          status: "applied",
          planned_files: ["src/app.py"],
          changed_files: ["src/app.py"],
          unexpected_files: [],
          scope_violation: false,
          diff_artifact_path: null,
          error_message: null,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      verifications: [
        {
          verification_result_id: "verify-1",
          run_id: "run-1",
          fix_attempt_id: "fix-1",
          patch_plan_id: "plan-1",
          status: "passed",
          checks: [],
          passed_checks: 1,
          failed_checks: 0,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      approvals: [],
      peerReviews: [
        {
          peer_review_id: "review-1",
          run_id: "run-1",
          patch_plan_id: "plan-1",
          verdict: "approved",
          synthesis_summary: "Approved",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      hasSuccessfulPush: false,
    });

    expect(result.canPush).toBe(true);
    expect(result.blockedReason).toBeNull();
    expect(result.canForcePush).toBe(false);
  });

  it("blocks push when verification failed for applied fixes", () => {
    const result = getGitPushEligibility({
      run: baseRun,
      fixAttempts: [
        {
          fix_attempt_id: "fix-1",
          run_id: "run-1",
          patch_plan_id: "plan-1",
          attempt_number: 1,
          status: "applied",
          planned_files: ["src/app.py"],
          changed_files: ["src/app.py"],
          unexpected_files: [],
          scope_violation: false,
          diff_artifact_path: null,
          error_message: null,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      verifications: [
        {
          verification_result_id: "verify-1",
          run_id: "run-1",
          fix_attempt_id: "fix-1",
          patch_plan_id: "plan-1",
          status: "failed",
          checks: [],
          passed_checks: 0,
          failed_checks: 1,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      approvals: [],
      peerReviews: [],
      hasSuccessfulPush: false,
    });

    expect(result.canPush).toBe(false);
    expect(result.blockedReason).toContain("verification");
    expect(result.canForcePush).toBe(true);
  });

  it("offers force push when run is stuck in FIXING", () => {
    const result = getGitPushEligibility({
      run: { ...baseRun, status: "FIXING" },
      fixAttempts: [
        {
          fix_attempt_id: "fix-1",
          run_id: "run-1",
          patch_plan_id: "plan-1",
          attempt_number: 1,
          status: "skipped",
          planned_files: ["src/app.py"],
          changed_files: [],
          unexpected_files: [],
          scope_violation: false,
          diff_artifact_path: null,
          error_message: "requires manual remediation",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      verifications: [],
      approvals: [],
      peerReviews: [],
      hasSuccessfulPush: false,
    });

    expect(result.canPush).toBe(false);
    expect(result.canForcePush).toBe(true);
    expect(result.blockedReason).toContain("stuck in FIXING");
  });
});
