import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useOutletContext } from "react-router-dom";

import { cloneRun, executeRun } from "@/api/runs";
import { EmptyState } from "@/components/common/EmptyState";
import { AgentTimeline } from "@/components/runs/AgentTimeline";
import { RunSummaryGrid } from "@/components/runs/RunSummaryGrid";
import type { RunOutletContext } from "@/pages/RunDetailPage";
import { useAuthStore } from "@/stores/authStore";

export function RunOverviewPage() {
  const {
    run,
    findings,
    fixAttempts,
    verifications,
    approvals,
    peerReviews,
    gitOps,
    report,
    events,
    connectionStatus,
  } = useOutletContext<RunOutletContext>();
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const cloneMutation = useMutation({
    mutationFn: () => cloneRun(run.id, token!),
    onSuccess: (result) => {
      setActionError(null);
      setActionMessage(
        result.success
          ? `Repository cloned to ${result.destination} (${result.branch}).`
          : result.message ?? "Clone completed.",
      );
      queryClient.invalidateQueries({ queryKey: ["run", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-events", run.id] });
    },
    onError: (error: Error) => {
      setActionMessage(null);
      setActionError(error.message);
    },
  });

  const executeMutation = useMutation({
    mutationFn: () => executeRun(run.id, token!),
    onSuccess: () => {
      setActionError(null);
      setActionMessage("Autonomous pipeline started. Live updates will appear below.");
      queryClient.invalidateQueries({ queryKey: ["run", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-events", run.id] });
    },
    onError: (error: Error) => {
      setActionMessage(null);
      setActionError(error.message);
    },
  });

  const passedVerifications = verifications.filter(
    (result) => result.status === "passed",
  ).length;
  const pendingApprovals = approvals.filter((approval) => approval.status === "pending").length;
  const canClone = Boolean(run.repository_id) && run.status === "CREATED";
  const canExecute = Boolean(run.repository_id) && ["CREATED", "FAILED"].includes(run.status);
  const awaitingApproval = run.status === "AWAITING_APPROVAL";

  return (
    <>
      <section className="panel">
        <div className="panel-header">
          <h2>Repository actions</h2>
        </div>
        {!run.repository_id ? (
          <EmptyState message="Link a repository on the project page before cloning." />
        ) : (
          <>
            <p className="run-meta">
              Clone pulls the GitHub/GitLab repo into the run workspace on this server. Save your
              personal access token under Settings first.
            </p>
            <div className="page-actions">
              <button
                type="button"
                className="secondary-button"
                disabled={!canClone || cloneMutation.isPending || executeMutation.isPending}
                onClick={() => cloneMutation.mutate()}
              >
                {cloneMutation.isPending ? "Cloning..." : "Clone repository"}
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={!canExecute || executeMutation.isPending || cloneMutation.isPending}
                onClick={() => executeMutation.mutate()}
              >
                {executeMutation.isPending ? "Starting..." : "Run full pipeline"}
              </button>
            </div>
          </>
        )}
        {actionMessage ? <p className="state-message">{actionMessage}</p> : null}
        {actionError ? <p className="form-error">{actionError}</p> : null}
      </section>

      <section className="panel">
        <h2>Autonomous run overview</h2>
        <p>
          This run is currently <strong>{run.status}</strong>. Updates stream live over SSE
          ({connectionStatus}).
        </p>
        {awaitingApproval ? (
          <p className="state-message">
            The pipeline is paused until you review and approve the required changes on the
            Approvals tab.
          </p>
        ) : null}
        <RunSummaryGrid
          items={[
            { label: "Findings", value: findings.length },
            { label: "Fix attempts", value: fixAttempts.length },
            {
              label: "Verification",
              value: `${passedVerifications}/${verifications.length || 0}`,
              hint: "passed",
            },
            { label: "Approvals", value: pendingApprovals, hint: "pending" },
            { label: "Peer reviews", value: peerReviews.length },
            { label: "Git ops", value: gitOps.length },
            {
              label: "Report",
              value: report ? "Ready" : "Pending",
              hint: report ? `${report.final_health_score}/100` : undefined,
              link: report ? `/runs/${run.id}/reports` : undefined,
            },
          ]}
        />
        {findings.length === 0 ? (
          <EmptyState message="No findings recorded yet. Diagnostic agents will populate this view." />
        ) : null}
      </section>

      <section className="panel">
        <h2>Agent timeline</h2>
        <AgentTimeline events={events} />
      </section>
    </>
  );
}
