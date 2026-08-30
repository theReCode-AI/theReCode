import { apiGet, apiPost } from "./client";
import type { HumanApproval } from "@/types/approval";
import type {
  AgentEvent,
  Finding,
  FixAttempt,
  GitOperation,
  PeerReviewResult,
  RiskDecision,
  Run,
  RunAgentState,
  RunCreate,
  RunGitFinalizationResponse,
  RunReport,
  VerificationResult,
} from "@/types/run";

export async function listRuns(projectId: string, token: string): Promise<Run[]> {
  return apiGet<Run[]>(`/runs?project_id=${encodeURIComponent(projectId)}`, token);
}

export async function getRun(runId: string, token: string): Promise<Run> {
  return apiGet<Run>(`/runs/${runId}`, token);
}

export async function createRun(payload: RunCreate, token: string): Promise<Run> {
  return apiPost<Run>("/runs", payload, token);
}

export async function getRunState(runId: string, token: string): Promise<RunAgentState> {
  return apiGet<RunAgentState>(`/runs/${runId}/state`, token);
}

export async function getRunEvents(runId: string, token: string): Promise<AgentEvent[]> {
  return apiGet<AgentEvent[]>(`/runs/${runId}/events`, token);
}

export async function getRunFindings(runId: string, token: string): Promise<Finding[]> {
  return apiGet<Finding[]>(`/runs/${runId}/findings`, token);
}

export async function getFixAttempts(runId: string, token: string): Promise<FixAttempt[]> {
  return apiGet<FixAttempt[]>(`/runs/${runId}/fix-attempts`, token);
}

export async function getVerificationResults(
  runId: string,
  token: string,
): Promise<VerificationResult[]> {
  return apiGet<VerificationResult[]>(`/runs/${runId}/verification-results`, token);
}

export async function getRiskDecisions(runId: string, token: string): Promise<RiskDecision[]> {
  return apiGet<RiskDecision[]>(`/runs/${runId}/risk-decisions`, token);
}

export async function getApprovals(runId: string, token: string): Promise<HumanApproval[]> {
  return apiGet<HumanApproval[]>(`/runs/${runId}/approvals`, token);
}

export async function getPeerReviews(runId: string, token: string): Promise<PeerReviewResult[]> {
  return apiGet<PeerReviewResult[]>(`/runs/${runId}/peer-reviews`, token);
}

export async function getGitOperations(runId: string, token: string): Promise<GitOperation[]> {
  return apiGet<GitOperation[]>(`/runs/${runId}/git/operations`, token);
}

export async function getRunReport(
  runId: string,
  token: string,
): Promise<RunReport | null> {
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? "/api/v1"}/runs/${runId}/reports`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = typeof payload.detail === "string" ? payload.detail : undefined;
    } catch {
      detail = undefined;
    }
    throw new Error(detail ?? `API request failed: ${response.status} ${response.statusText}`);
  }

  const payload = (await response.json()) as RunReport | null;
  return payload ?? null;
}

export interface RunReportMarkdown {
  report_id: string;
  run_id: string;
  markdown: string;
}

export async function getRunReportMarkdown(
  runId: string,
  token: string,
): Promise<RunReportMarkdown | null> {
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? "/api/v1"}/runs/${runId}/reports/markdown`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = typeof payload.detail === "string" ? payload.detail : undefined;
    } catch {
      detail = undefined;
    }
    throw new Error(detail ?? `API request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as RunReportMarkdown;
}

export interface RepositoryCloneResponse {
  success: boolean;
  destination: string;
  branch: string;
  commit_sha: string | null;
  message: string | null;
}

export interface RunOrchestrationResponse {
  run_id: string;
  event_count: number;
}

export async function cloneRun(
  runId: string,
  token: string,
  branch?: string,
): Promise<RepositoryCloneResponse> {
  return apiPost<RepositoryCloneResponse>(
    `/runs/${runId}/clone`,
    branch ? { branch } : {},
    token,
  );
}

export interface GenerateRunReportResponse {
  run_id: string;
  report: RunReport;
  run_status: string;
}

export async function generateRunReport(
  runId: string,
  token: string,
): Promise<RunReport> {
  const response = await apiPost<GenerateRunReportResponse>(
    `/runs/${runId}/reports/generate`,
    {},
    token,
  );
  return response.report;
}

export async function executeRun(
  runId: string,
  token: string,
  options?: { branch?: string; skip_clone?: boolean; resume_after_approval?: boolean },
): Promise<RunOrchestrationResponse> {
  return apiPost<RunOrchestrationResponse>(
    `/runs/${runId}/execute`,
    options ?? {},
    token,
  );
}

export async function finalizeRunGit(
  runId: string,
  token: string,
  baseBranch?: string,
): Promise<RunGitFinalizationResponse> {
  return apiPost<RunGitFinalizationResponse>(
    `/runs/${runId}/git/finalize`,
    baseBranch ? { base_branch: baseBranch } : {},
    token,
  );
}
