import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card } from "flowbite-react";
import { useState } from "react";
import { useOutletContext } from "react-router-dom";

import { cloneRun, executeRun, finalizeRunGit } from "@/api/runs";
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
  const [pushMessage, setPushMessage] = useState<string | null>(null);
  const [pushError, setPushError] = useState<string | null>(null);

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

  const pushMutation = useMutation({
    mutationFn: () => {
      if (!token) {
        throw new Error("You must be signed in to push changes.");
      }
      return finalizeRunGit(run.id, token);
    },
    onSuccess: (result) => {
      setPushError(null);
      const prUrl = result.operation.pull_request_url;
      setPushMessage(
        prUrl
          ? `Changes pushed to branch ${result.operation.branch_name ?? `fix/${run.id}`}. Pull request created.`
          : `Git finalization completed with status ${result.operation.status}.`,
      );
      queryClient.invalidateQueries({ queryKey: ["run", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-git-ops", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-events", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-report", run.id] });
    },
    onError: (error: Error) => {
      setPushMessage(null);
      setPushError(error.message);
    },
  });

  const passedVerifications = verifications.filter(
    (result) => result.status === "passed",
  ).length;
  const pendingApprovals = approvals.filter((approval) => approval.status === "pending").length;
  const rejectedApprovals = approvals.filter((approval) => approval.status === "rejected").length;
  const appliedFixAttempts = fixAttempts.filter((attempt) => attempt.status === "applied").length;
  const peerReviewApproved =
    peerReviews.length === 0 ||
    peerReviews.every((review) => review.verdict === "approved");
  const latestGitOp = gitOps[0];
  const hasSuccessfulPush = gitOps.some((operation) => operation.status === "pr_created");
  const pushReadyStatuses = ["FINAL_REVIEW", "REPORTING", "COMPLETED", "FAILED"];
  const canClone = Boolean(run.repository_id) && run.status === "CREATED";
  const canExecute = Boolean(run.repository_id) && ["CREATED", "FAILED"].includes(run.status);
  const canPushGit =
    Boolean(run.repository_id) &&
    pushReadyStatuses.includes(run.status) &&
    pendingApprovals === 0 &&
    rejectedApprovals === 0 &&
    appliedFixAttempts > 0 &&
    peerReviewApproved &&
    !hasSuccessfulPush;
  const isPushing = run.status === "PUSHING" || pushMutation.isPending;
  const awaitingApproval = run.status === "AWAITING_APPROVAL";
  const pushBranchName = `fix/${run.id}`;

  return (
    <>
      <Card className="mb-4">
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Repository actions</h2>
        {!run.repository_id ? (
          <EmptyState message="Link a repository on the project page before cloning." />
        ) : (
          <>
            <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
              Clone pulls the GitHub/GitLab repo into the run workspace on this server. Save your
              personal access token under Settings first.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button
                color="light"
                disabled={!canClone || cloneMutation.isPending || executeMutation.isPending}
                onClick={() => cloneMutation.mutate()}
              >
                {cloneMutation.isPending ? "Cloning..." : "Clone repository"}
              </Button>
              <Button
                disabled={!canExecute || executeMutation.isPending || cloneMutation.isPending}
                onClick={() => executeMutation.mutate()}
              >
                {executeMutation.isPending ? "Starting..." : "Run full pipeline"}
              </Button>
            </div>
          </>
        )}
        {actionMessage ? <Alert color="info" className="mt-4">{actionMessage}</Alert> : null}
        {actionError ? <Alert color="failure" className="mt-4">{actionError}</Alert> : null}
      </Card>

      <Card className="mb-4">
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Git push</h2>
        {!run.repository_id ? (
          <EmptyState message="Link a repository on the project page before pushing changes." />
        ) : hasSuccessfulPush && latestGitOp ? (
          <div className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
            <p>
              Changes were pushed to branch{" "}
              <strong>{latestGitOp.branch_name ?? pushBranchName}</strong>
              {latestGitOp.commit_sha ? ` (${latestGitOp.commit_sha.slice(0, 8)})` : ""}.
            </p>
            {latestGitOp.pull_request_url ? (
              <p>
                <a
                  href={latestGitOp.pull_request_url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium text-blue-600 hover:underline"
                >
                  Open pull request
                </a>
              </p>
            ) : null}
          </div>
        ) : (
          <>
            <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
              After the pipeline reaches final review, push applied fixes to branch{" "}
              <strong>{pushBranchName}</strong> and open a pull request. Save your Git
              personal access token under Settings first.
            </p>
            <Button
              color="success"
              disabled={!canPushGit || isPushing}
              onClick={() => pushMutation.mutate()}
            >
              {isPushing ? "Pushing..." : "Push to GitHub"}
            </Button>
            {!canPushGit && run.status !== "PUSHING" ? (
              <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
                {!pushReadyStatuses.includes(run.status)
                  ? `Run must finish peer review before pushing (current: ${run.status}).`
                  : pendingApprovals > 0
                    ? "Resolve pending approvals before pushing."
                    : rejectedApprovals > 0
                      ? "Rejected approvals block git push."
                      : appliedFixAttempts === 0
                        ? "At least one applied fix attempt is required."
                        : !peerReviewApproved
                          ? "Peer review must be approved before pushing."
                          : hasSuccessfulPush
                            ? "A pull request has already been created for this run."
                            : "Git push is not available yet."}
              </p>
            ) : null}
            {pushMessage ? <Alert color="info" className="mt-4">{pushMessage}</Alert> : null}
            {pushError ? <Alert color="failure" className="mt-4">{pushError}</Alert> : null}
          </>
        )}
      </Card>

      <Card className="mb-4">
        <h2 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">Autonomous run overview</h2>
        <p className="mb-4 text-sm text-gray-700 dark:text-gray-300">
          This run is currently <strong>{run.status}</strong>. Updates stream live over SSE
          ({connectionStatus}).
        </p>
        {awaitingApproval ? (
          <Alert color="warning" className="mb-4">
            The pipeline is paused until you review and approve the required changes on the
            Approvals tab.
          </Alert>
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
          <div className="mt-4">
            <EmptyState message="No findings recorded yet. Diagnostic agents will populate this view." />
          </div>
        ) : null}
      </Card>

      <Card>
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Agent timeline</h2>
        <AgentTimeline events={events} />
      </Card>
    </>
  );
}
