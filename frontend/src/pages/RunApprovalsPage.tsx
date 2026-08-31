import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Button, Card } from "flowbite-react";
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
  const [replanningMessage, setReplanningMessage] = useState<string | null>(null);
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
    run.status,
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
    if (!token || !showPrepareButton || autoPrepareAttempted.current || prepareMutation.isError) {
      return;
    }
    autoPrepareAttempted.current = true;
    prepareMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- auto-prepare once when triggers appear
  }, [token, showPrepareButton]);

  const prepareErrorMessage =
    prepareMutation.error instanceof Error
      ? prepareMutation.error.message
      : "Unable to prepare approval cards. Try again or refresh the run.";

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
      queryClient.invalidateQueries({ queryKey: ["run-state", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-events", run.id] });
      queryClient.setQueryData(["run", run.id], (current: typeof run | undefined) =>
        current ? { ...current, status: response.run_status } : current,
      );
      if (response.replanning_required) {
        setReplanningMessage(
          "Your feedback was recorded. The pipeline is replanning automatically. Open Overview to watch progress, or click Continue pipeline if it does not resume.",
        );
      }
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
    <Card>
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Human approvals</h2>
        {showPrepareButton ? (
          <Button
            disabled={prepareMutation.isPending}
            onClick={() => {
              autoPrepareAttempted.current = true;
              prepareMutation.mutate();
            }}
          >
            {prepareMutation.isPending ? "Preparing..." : "Prepare approval cards"}
          </Button>
        ) : null}
      </div>

      {prepareMutation.isError ? (
        <ErrorState message={prepareErrorMessage} />
      ) : null}

      {replanningMessage ? (
        <p className="mb-4 text-sm text-blue-700 dark:text-blue-300">{replanningMessage}</p>
      ) : null}

      {pendingCount > 0 ? (
        <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
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
        <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
          <aside className="flex flex-col gap-2">
            {approvals.map((approval) => (
              <button
                key={approval.approval_id}
                type="button"
                className={`rounded-xl border bg-slate-900 p-3 text-left transition ${
                  approval.approval_id === selectedApprovalId
                    ? "border-slate-600 bg-blue-50"
                    : "border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-slate-600 hover:border-gray-300"
                }`}
                onClick={() => setSelectedApprovalId(approval.approval_id)}
              >
                <strong className="block text-gray-900 dark:text-white">{approval.trigger}</strong>
                <Badge color="gray" className="mt-1">{approval.status}</Badge>
                <small className="mt-1 block text-xs text-gray-500 dark:text-gray-400">
                  {formatDateTime(approval.created_at)}
                </small>
              </button>
            ))}
          </aside>

          {selectedApproval ? (
            <article className="space-y-4">
              <header className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {selectedApproval.issue_title ?? selectedApproval.trigger}
                  </h3>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{selectedApproval.reason}</p>
                </div>
                <Badge color="gray">{selectedApproval.status}</Badge>
              </header>

              {selectedApproval.root_cause ? (
                <p className="text-sm text-gray-700 dark:text-gray-300">
                  <strong>Root cause:</strong> {selectedApproval.root_cause}
                </p>
              ) : null}
              {selectedApproval.risk_level ? (
                <p className="text-sm text-gray-700 dark:text-gray-300">
                  <strong>Risk:</strong> {selectedApproval.risk_level}
                </p>
              ) : null}
              {selectedApproval.evidence_summary ? (
                <p className="text-sm text-gray-700 dark:text-gray-300">
                  <strong>Evidence:</strong> {selectedApproval.evidence_summary}
                </p>
              ) : null}
              {selectedApproval.verification_summary ? (
                <p className="text-sm text-gray-700 dark:text-gray-300">
                  <strong>Verification:</strong> {selectedApproval.verification_summary}
                </p>
              ) : null}
              {selectedApproval.expected_tests.length > 0 ? (
                <p className="text-sm text-gray-700 dark:text-gray-300">
                  <strong>Expected tests:</strong> {selectedApproval.expected_tests.join(", ")}
                </p>
              ) : null}
              {selectedApproval.reviewer_feedback.length > 0 ? (
                <ul className="list-disc space-y-1 pl-5 text-sm text-gray-700 dark:text-gray-300">
                  {selectedApproval.reviewer_feedback.map((feedback) => (
                    <li key={feedback}>{feedback}</li>
                  ))}
                </ul>
              ) : null}

              {selectedApproval.diff_artifact_path ? (
                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <h4 className="font-semibold text-gray-900 dark:text-white">Patch diff</h4>
                    <Link to="../diff" className="text-sm font-medium text-blue-600 hover:underline">
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
                <p className="text-sm text-gray-500 dark:text-gray-400">
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
    </Card>
  );
}
