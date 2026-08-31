import type { HumanApproval } from "@/types/approval";
import type { FixAttempt, PeerReviewResult, Run, VerificationResult } from "@/types/run";

const PUSH_READY_STATUSES = new Set([
  "FINAL_REVIEW",
  "REPORTING",
  "COMPLETED",
  "FAILED",
]);

const FORCE_PUSH_READY_STATUSES = new Set([
  "FIXING",
  "VERIFYING",
  "SELF_CORRECTING",
  "PEER_REVIEW",
  "FINAL_REVIEW",
  "REPORTING",
  "COMPLETED",
  "FAILED",
]);

export interface GitPushEligibility {
  canPush: boolean;
  canForcePush: boolean;
  blockedReason: string | null;
  forcePushHint: string | null;
  pushableFixAttempts: FixAttempt[];
}

export function getGitPushEligibility(input: {
  run: Run;
  fixAttempts: FixAttempt[];
  verifications: VerificationResult[];
  approvals: HumanApproval[];
  peerReviews: PeerReviewResult[];
  hasSuccessfulPush: boolean;
}): GitPushEligibility {
  const {
    run,
    fixAttempts,
    verifications,
    approvals,
    peerReviews,
    hasSuccessfulPush,
  } = input;

  const appliedFixAttempts = fixAttempts.filter((attempt) => attempt.status === "applied");
  const pushableFixAttempts = appliedFixAttempts.filter(
    (attempt) => attempt.changed_files.length > 0,
  );
  const pendingApprovals = approvals.filter((approval) => approval.status === "pending").length;
  const rejectedApprovals = approvals.filter((approval) => approval.status === "rejected").length;
  const skippedFixAttempts = fixAttempts.filter((attempt) => attempt.status === "skipped").length;
  const failedFixAttempts = fixAttempts.filter((attempt) => attempt.status === "failed").length;
  const peerReviewApproved =
    peerReviews.length === 0 ||
    peerReviews.every((review) => review.verdict === "approved");
  const appliedPlanIds = new Set(
    appliedFixAttempts.map((attempt) => attempt.patch_plan_id),
  );
  const passedPlanIds = new Set(
    verifications
      .filter((result) => result.status === "passed")
      .map((result) => result.patch_plan_id),
  );
  const verificationRequired = verifications.some((result) =>
    appliedPlanIds.has(result.patch_plan_id),
  );
  const verificationPassed =
    !verificationRequired ||
    [...appliedPlanIds].some((planId) => passedPlanIds.has(planId));
  const isRunComplete = run.status === "COMPLETED";
  const isStuckInFixing = run.status === "FIXING";
  const baseForceEligible =
    Boolean(run.repository_id) &&
    !hasSuccessfulPush &&
    FORCE_PUSH_READY_STATUSES.has(run.status) &&
    pendingApprovals === 0 &&
    rejectedApprovals === 0;

  if (!run.repository_id) {
    return {
      canPush: false,
      canForcePush: false,
      blockedReason: "Link a repository on the project page before pushing.",
      forcePushHint: null,
      pushableFixAttempts,
    };
  }
  if (hasSuccessfulPush) {
    return {
      canPush: false,
      canForcePush: false,
      blockedReason: "A pull request has already been created for this run.",
      forcePushHint: null,
      pushableFixAttempts,
    };
  }
  if (!PUSH_READY_STATUSES.has(run.status)) {
    return {
      canPush: false,
      canForcePush: baseForceEligible,
      blockedReason: isStuckInFixing
        ? "Run is stuck in FIXING (Retry code fixes finished but the pipeline did not continue to peer review)."
        : `Push is available after peer review (current: ${run.status}).`,
      forcePushHint: baseForceEligible
        ? isStuckInFixing
          ? "Use Continue pipeline to finish review, or Push to GitHub anyway."
          : "You can push the workspace to GitHub anyway."
        : null,
      pushableFixAttempts,
    };
  }
  if (pendingApprovals > 0) {
    return {
      canPush: false,
      canForcePush: false,
      blockedReason: "Resolve pending approvals before pushing.",
      forcePushHint: null,
      pushableFixAttempts,
    };
  }
  if (rejectedApprovals > 0) {
    return {
      canPush: false,
      canForcePush: false,
      blockedReason: "Rejected approvals block push.",
      forcePushHint: null,
      pushableFixAttempts,
    };
  }
  if (!peerReviewApproved) {
    return {
      canPush: false,
      canForcePush: baseForceEligible && (isRunComplete || isStuckInFixing),
      blockedReason: "Peer review must be approved before pushing.",
      forcePushHint: baseForceEligible && (isRunComplete || isStuckInFixing)
        ? "You can push the workspace to GitHub anyway without waiting for peer review approval."
        : null,
      pushableFixAttempts,
    };
  }
  if (!verificationPassed) {
    return {
      canPush: false,
      canForcePush: baseForceEligible && isRunComplete,
      blockedReason: "Applied fixes must pass verification before pushing.",
      forcePushHint: baseForceEligible && isRunComplete
        ? "You can push the workspace to GitHub anyway without passing verification."
        : null,
      pushableFixAttempts,
    };
  }
  if (pushableFixAttempts.length === 0) {
    const skipMessages = fixAttempts
      .filter((attempt) => attempt.status === "skipped" && attempt.error_message)
      .map((attempt) => attempt.error_message as string);
    if (fixAttempts.length === 0) {
      return {
        canPush: false,
        canForcePush: baseForceEligible && isRunComplete,
        blockedReason: isRunComplete
          ? "This run completed without any code fixes. There is nothing to push."
          : "No fix attempts yet. Run the pipeline and wait for code fixes to be applied.",
        forcePushHint: baseForceEligible && isRunComplete
          ? "Push the cloned workspace to GitHub anyway and open a pull request."
          : null,
        pushableFixAttempts,
      };
    }
    if (appliedFixAttempts.length > 0) {
      return {
        canPush: false,
        canForcePush: baseForceEligible && isRunComplete,
        blockedReason:
          "Fix attempts were recorded as applied but no files were changed. Check the Diff tab.",
        forcePushHint: baseForceEligible && isRunComplete
          ? "Push the workspace to GitHub anyway."
          : null,
        pushableFixAttempts,
      };
    }
    const parts = [
      skippedFixAttempts > 0 ? `${skippedFixAttempts} skipped` : null,
      failedFixAttempts > 0 ? `${failedFixAttempts} failed` : null,
    ].filter(Boolean);
    const summary = parts.length > 0 ? parts.join(", ") : "none applied";
    const skipHint =
      skippedFixAttempts > 0
        ? " Use Retry code fixes on Overview if you already approved the risk gate."
        : "";
    const detail = skipMessages.length > 0 ? ` Reason: ${skipMessages[0]}` : "";
    return {
      canPush: false,
      canForcePush: baseForceEligible && isRunComplete,
      blockedReason: isRunComplete
        ? `This run completed but no fixes were applied (${fixAttempts.length} attempts: ${summary}).${detail}${skipHint}`
        : "At least one applied fix with changed files is required before pushing.",
      forcePushHint: baseForceEligible && isRunComplete
        ? "Push the workspace to GitHub anyway. Any local workspace changes will be committed."
        : null,
      pushableFixAttempts,
    };
  }

  return {
    canPush: true,
    canForcePush: false,
    blockedReason: null,
    forcePushHint: null,
    pushableFixAttempts,
  };
}
