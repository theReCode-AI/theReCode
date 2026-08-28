import { apiGet, apiPost } from "./client";
import type {
  ApprovalDecisionRequest,
  ApprovalDecisionResponse,
  ApprovalDiffResponse,
  FixAttemptDiffResponse,
  HumanApproval,
  PrepareApprovalsResponse,
} from "@/types/approval";

export async function prepareApprovals(
  runId: string,
  token: string,
): Promise<PrepareApprovalsResponse> {
  return apiPost<PrepareApprovalsResponse>(`/runs/${runId}/approvals/prepare`, undefined, token);
}

export async function submitApprovalDecision(
  runId: string,
  approvalId: string,
  payload: ApprovalDecisionRequest,
  token: string,
): Promise<ApprovalDecisionResponse> {
  return apiPost<ApprovalDecisionResponse>(
    `/runs/${runId}/approvals/${approvalId}/decide`,
    payload,
    token,
  );
}

export async function getApprovalDiff(
  runId: string,
  approvalId: string,
  token: string,
): Promise<ApprovalDiffResponse> {
  return apiGet<ApprovalDiffResponse>(`/runs/${runId}/approvals/${approvalId}/diff`, token);
}

export async function getFixAttemptDiff(
  runId: string,
  fixAttemptId: string,
  token: string,
): Promise<FixAttemptDiffResponse> {
  return apiGet<FixAttemptDiffResponse>(
    `/runs/${runId}/fix-attempts/${fixAttemptId}/diff`,
    token,
  );
}

export type { HumanApproval };
