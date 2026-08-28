import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import {
  getApprovalDiff,
  prepareApprovals,
  submitApprovalDecision,
} from "@/api/approvals";
import { ApprovalDecisionForm } from "@/components/approvals/ApprovalDecisionForm";
import { DiffViewer } from "@/components/diff/DiffViewer";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import type { RunOutletContext } from "@/pages/RunDetailPage";
import { useAuthStore } from "@/stores/authStore";
import type { HumanDecision } from "@/types/approval";
import {
  countPendingApprovals,
  shouldShowPrepareApprovals,
} from "@/utils/approvals";
import { formatDateTime } from "@/utils/runStages";

export function RunApprovalsPage() {
  const { run, approvals, riskDecisions, approvalRequired } =
    useOutletContext<RunOutletContext>();
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const autoPrepareAttempted = useRef(false);
  const [selectedApprovalId, setSelectedApprovalId] = useState(
    approvals[0]?.approval_id ?? "",
  );

  const selectedApproval = approvals.find(
    (approval) => approval.approval_id === selectedApprovalId,
  );
  const pendingCount = countPendingApprovals(approvals);
  const showPrepareButton = shouldShowPrepareApprovals(
    approvals,
    riskDecisions,
    approvalRequired,
  );

  const diffQuery = useQuery({
    queryKey: ["approval-diff", run.id, selectedApprovalId],
    queryFn: () => getApprovalDiff(run.id, selectedApprovalId, token!),
    enabled: Boolean(
      token && selectedApprovalId && selectedApproval?.diff_artifact_path,
    ),
    retry: false,
  });

  const prepareMutation = useMutation({
    mutationFn: () => prepareApprovals(run.id, token!),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["run-approvals", run.id] });
      queryClient.setQueryData(["run", run.id], (current: typeof run | undefined) =>
        current ? { ...current, status: response.run_status } : current,
      );
      if (response.approvals[0]) {
        setSelectedApprovalId(response.approvals[0].approval_id);
      }
    },
  });

  useEffect(() => {
    if (!approvals[0]?.approval_id || selectedApprovalId) {
      return;
    }
    setSelectedApprovalId(approvals[0].approval_id);
  }, [approvals, selectedApprovalId]);

  useEffect(() => {
    if (!token || !showPrepareButton || autoPrepareAttempted.current) {
      return;
    }
    autoPrepareAttempted.current = true;
    prepareMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- auto-prepare once when triggers appear
  }, [token, showPrepareButton]);

  const decisionMutation = useMutation({
    mutationFn: ({
      approvalId,
      decision,
      feedback,
    }: {
      approvalId: string;
      decision: HumanDecision;
      feedback?: string;
    }) => submitApprovalDecision(run.id, approvalId, { decision, feedback }, token!),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["run-approvals", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run", run.id] });
      queryClient.setQueryData(["run", run.id], (current: typeof run | undefined) =>
        current ? { ...current, status: response.run_status } : current,
      );
    },
  });

  async function handleDecision(decision: HumanDecision, feedback?: string) {
    if (!selectedApproval) {
      return;
    }
    await decisionMutation.mutateAsync({
      approvalId: selectedApproval.approval_id,
      decision,
      feedback,
    });
  }

  return (
    <section className="panel approvals-page">
      <div className="panel-header">
        <h2>Human approvals</h2>
        {showPrepareButton ? (
          <button
            type="button"
            className="primary-button"
            disabled={prepareMutation.isPending}
            onClick={() => prepareMutation.mutate()}
          >
            {prepareMutation.isPending ? "Preparing..." : "Prepare approval cards"}
          </button>
        ) : null}
      </div>

      {prepareMutation.isError ? (
        <ErrorState message="Unable to prepare approval cards. Try again or refresh the run." />
      ) : null}

      {pendingCount > 0 ? (
        <p className="page-subtitle">
          {pendingCount} approval{pendingCount === 1 ? "" : "s"} waiting for your decision. The
          pipeline will stay paused until you approve.
        </p>
      ) : null}

      {approvals.length === 0 ? (
        <EmptyState
          message={
            showPrepareButton || prepareMutation.isPending
              ? "Preparing approval cards from risk assessment..."
              : "No approval requests for this run."
          }
        />
      ) : (
        <div className="approvals-layout">
          <aside className="approvals-sidebar">
            {approvals.map((approval) => (
              <button
                key={approval.approval_id}
                type="button"
                className={
                  approval.approval_id === selectedApprovalId
                    ? "approval-option active"
                    : "approval-option"
                }
                onClick={() => setSelectedApprovalId(approval.approval_id)}
              >
                <strong>{approval.trigger}</strong>
                <span className="status-badge">{approval.status}</span>
                <small>{formatDateTime(approval.created_at)}</small>
              </button>
            ))}
          </aside>

          {selectedApproval ? (
            <article className="approval-detail">
              <header className="approval-card-header">
                <div>
                  <h3>{selectedApproval.issue_title ?? selectedApproval.trigger}</h3>
                  <p>{selectedApproval.reason}</p>
                </div>
                <span className="status-badge">{selectedApproval.status}</span>
              </header>

              {selectedApproval.root_cause ? (
                <p>
                  <strong>Root cause:</strong> {selectedApproval.root_cause}
                </p>
              ) : null}
              {selectedApproval.risk_level ? (
                <p>
                  <strong>Risk:</strong> {selectedApproval.risk_level}
                </p>
              ) : null}
              {selectedApproval.evidence_summary ? (
                <p>
                  <strong>Evidence:</strong> {selectedApproval.evidence_summary}
                </p>
              ) : null}
              {selectedApproval.verification_summary ? (
                <p>
                  <strong>Verification:</strong> {selectedApproval.verification_summary}
                </p>
              ) : null}
              {selectedApproval.expected_tests.length > 0 ? (
                <p>
                  <strong>Expected tests:</strong> {selectedApproval.expected_tests.join(", ")}
                </p>
              ) : null}
              {selectedApproval.reviewer_feedback.length > 0 ? (
                <ul className="simple-list">
                  {selectedApproval.reviewer_feedback.map((feedback) => (
                    <li key={feedback}>{feedback}</li>
                  ))}
                </ul>
              ) : null}

              {selectedApproval.diff_artifact_path ? (
                <div className="approval-diff-section">
                  <div className="panel-header">
                    <h4>Patch diff</h4>
                    <Link to="../diff" className="text-link">
                      Open full diff viewer
                    </Link>
                  </div>
                  {diffQuery.isLoading ? <LoadingState message="Loading diff..." /> : null}
                  {diffQuery.isError ? (
                    <ErrorState message="Diff artifact is not available for this approval." />
                  ) : null}
                  {diffQuery.data ? <DiffViewer content={diffQuery.data.content} /> : null}
                </div>
              ) : null}

              {selectedApproval.status === "pending" ? (
                <ApprovalDecisionForm
                  disabled={decisionMutation.isPending}
                  onSubmit={handleDecision}
                />
              ) : (
                <p className="page-subtitle">
                  Decision: {selectedApproval.human_decision}
                  {selectedApproval.human_feedback
                    ? ` — ${selectedApproval.human_feedback}`
                    : ""}
                </p>
              )}
            </article>
          ) : null}
        </div>
      )}
    </section>
  );
}
