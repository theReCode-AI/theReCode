import type { HumanApproval } from "@/types/approval";
import type { RiskDecision } from "@/types/run";

export function hasRiskApprovalTriggers(riskDecisions: RiskDecision[]): boolean {
  return riskDecisions.some((decision) => decision.approval_required);
}

export function hasUnpreparedApprovalTriggers(
  approvals: HumanApproval[],
  riskDecisions: RiskDecision[],
): boolean {
  if (approvals.length > 0) {
    return false;
  }
  return hasRiskApprovalTriggers(riskDecisions);
}

export function countPendingApprovals(approvals: HumanApproval[]): number {
  return approvals.filter((approval) => approval.status === "pending").length;
}

export function shouldShowPrepareApprovals(
  approvals: HumanApproval[],
  riskDecisions: RiskDecision[],
  approvalRequiredFromState?: boolean,
  runStatus?: string,
): boolean {
  if (countPendingApprovals(approvals) > 0) {
    return false;
  }
  if (hasUnpreparedApprovalTriggers(approvals, riskDecisions)) {
    return true;
  }
  return Boolean(approvalRequiredFromState && runStatus === "AWAITING_APPROVAL");
}
