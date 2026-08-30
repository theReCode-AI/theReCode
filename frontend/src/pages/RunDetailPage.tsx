import { useQuery } from "@tanstack/react-query";
import { Alert, Badge, Card } from "flowbite-react";
import { Link, Outlet, useParams } from "react-router-dom";

import {
  getApprovals,
  getFixAttempts,
  getGitOperations,
  getPeerReviews,
  getRiskDecisions,
  getRun,
  getRunFindings,
  getRunReport,
  getVerificationResults,
} from "@/api/runs";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { PageHeader } from "@/components/common/PageHeader";
import { LiveConnectionBadge } from "@/components/runs/LiveConnectionBadge";
import { PipelineGraph } from "@/components/runs/PipelineGraph";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { RunTabGroup } from "@/components/runs/RunTabGroup";
import { useRunProgressStream } from "@/hooks/useRunProgressStream";
import { useAuthStore } from "@/stores/authStore";
import { useRunLiveSlice } from "@/stores/runLiveStore";
import type {
  AgentEvent,
  Finding,
  FixAttempt,
  GitOperation,
  PeerReviewResult,
  RiskDecision,
  Run,
  RunReport,
  VerificationResult,
} from "@/types/run";
import type { HumanApproval } from "@/types/approval";
import {
  countPendingApprovals,
  hasUnpreparedApprovalTriggers,
} from "@/utils/approvals";
import { formatDateTime } from "@/utils/runStages";
import { getActiveGraphNodeLabel, getGraphProgressPercent } from "@/utils/pipelineGraph";

export interface RunOutletContext {
  run: Run;
  findings: Finding[];
  fixAttempts: FixAttempt[];
  verifications: VerificationResult[];
  approvals: HumanApproval[];
  riskDecisions: RiskDecision[];
  peerReviews: PeerReviewResult[];
  gitOps: GitOperation[];
  report?: RunReport;
  events: AgentEvent[];
  connectionStatus: string;
  approvalRequired: boolean;
}

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const token = useAuthStore((state) => state.token);
  const liveSlice = useRunLiveSlice(runId);

  useRunProgressStream(runId);

  const runQuery = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId, token!),
    enabled: Boolean(token && runId),
  });

  const findingsQuery = useQuery({
    queryKey: ["run-findings", runId],
    queryFn: () => getRunFindings(runId, token!),
    enabled: Boolean(token && runId),
    retry: false,
  });

  const fixAttemptsQuery = useQuery({
    queryKey: ["run-fix-attempts", runId],
    queryFn: () => getFixAttempts(runId, token!),
    enabled: Boolean(token && runId),
    retry: false,
  });

  const verificationQuery = useQuery({
    queryKey: ["run-verifications", runId],
    queryFn: () => getVerificationResults(runId, token!),
    enabled: Boolean(token && runId),
    retry: false,
  });

  const approvalsQuery = useQuery({
    queryKey: ["run-approvals", runId],
    queryFn: () => getApprovals(runId, token!),
    enabled: Boolean(token && runId),
    retry: false,
  });

  const riskDecisionsQuery = useQuery({
    queryKey: ["run-risk-decisions", runId],
    queryFn: () => getRiskDecisions(runId, token!),
    enabled: Boolean(token && runId),
    retry: false,
  });

  const peerReviewsQuery = useQuery({
    queryKey: ["run-peer-reviews", runId],
    queryFn: () => getPeerReviews(runId, token!),
    enabled: Boolean(token && runId),
    retry: false,
  });

  const gitOpsQuery = useQuery({
    queryKey: ["run-git-ops", runId],
    queryFn: () => getGitOperations(runId, token!),
    enabled: Boolean(token && runId),
    retry: false,
  });

  const reportQuery = useQuery({
    queryKey: ["run-report", runId],
    queryFn: () => getRunReport(runId, token!),
    enabled: Boolean(token && runId),
    retry: false,
  });

  if (runQuery.isLoading && !liveSlice.run) {
    return <LoadingState message="Loading run..." />;
  }

  const run = liveSlice.run ?? runQuery.data;
  if (!run) {
    return <ErrorState message="Unable to load run." />;
  }

  const state = liveSlice.state;
  const events = liveSlice.events.length > 0 ? liveSlice.events : [];
  const approvals = approvalsQuery.data ?? [];
  const riskDecisions = riskDecisionsQuery.data ?? [];
  const approvalRequired = Boolean(
    state?.approval_required ||
      run.status === "AWAITING_APPROVAL" ||
      hasUnpreparedApprovalTriggers(approvals, riskDecisions),
  );
  const pendingApprovalCount = countPendingApprovals(approvals);
  const graphProgress = getGraphProgressPercent({
    status: run.status,
    currentStage: state?.current_stage,
    completedStages: state?.completed_stages,
    progress: state?.progress,
  });
  const activeGraphLabel = getActiveGraphNodeLabel(run.status, state);

  const outletContext: RunOutletContext = {
    run,
    findings: findingsQuery.data ?? [],
    fixAttempts: fixAttemptsQuery.data ?? [],
    verifications: verificationQuery.data ?? [],
    approvals,
    riskDecisions,
    peerReviews: peerReviewsQuery.data ?? [],
    gitOps: gitOpsQuery.data ?? [],
    report: reportQuery.data ?? undefined,
    events,
    connectionStatus: liveSlice.connectionStatus,
    approvalRequired,
  };

  return (
    <section className="run-detail-page">
      <PageHeader
        title={`Run ${run.id.slice(-8)}`}
        subtitle={`Project ${run.project_id} · Updated ${formatDateTime(run.updated_at)}`}
        actions={
          <div className="flex items-center gap-3">
            <LiveConnectionBadge status={liveSlice.connectionStatus} />
            <Link to={`/projects/${run.project_id}`} className="text-sm font-medium text-blue-600 hover:underline">
              Back to project
            </Link>
          </div>
        }
      />

      {liveSlice.error ? <Alert color="failure" className="mb-4">{liveSlice.error}</Alert> : null}

      <Card className="mb-4">
        <div className="mb-4 flex items-center justify-between">
          <RunStatusBadge status={run.status} />
          <Badge color="info">{graphProgress}% complete</Badge>
        </div>
        <PipelineGraph
          status={run.status}
          currentStage={state?.current_stage}
          completedStages={state?.completed_stages}
        />
        {state || approvalRequired || activeGraphLabel ? (
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
            {activeGraphLabel ? `Stage: ${activeGraphLabel}` : null}
            {state?.current_agent ? ` · Agent: ${state.current_agent}` : ""}
            {approvalRequired ? " · Approval required" : ""}
            {state && state.progress > 0 ? ` · Progress: ${state.progress}%` : ""}
          </p>
        ) : null}
      </Card>

      <RunTabGroup
        runId={run.id}
        pendingApprovalCount={pendingApprovalCount}
        approvalRequired={approvalRequired}
      />

      <Outlet context={outletContext} />
    </section>
  );
}
