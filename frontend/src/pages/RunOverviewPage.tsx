import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card } from "flowbite-react";
import { useState } from "react";
import { useOutletContext } from "react-router-dom";

import { cloneRun, applyRunFixes, executeRun, finalizeRunGit } from "@/api/runs";
import { EmptyState } from "@/components/common/EmptyState";
import { AgentTimeline } from "@/components/runs/AgentTimeline";
import { RunSummaryGrid } from "@/components/runs/RunSummaryGrid";
import type { RunOutletContext } from "@/pages/RunDetailPage";
import { useAuthStore } from "@/stores/authStore";
import { getGitPushEligibility } from "@/utils/gitPush";

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

  const pushMutation = useMutation({
    mutationFn: async (options?: { force?: boolean }) => {
      if (!token) {
        throw new Error("You must be signed in to push changes.");
      }
      const result = await finalizeRunGit(run.id, token, { force: options?.force });
      if (result.operation.status !== "pr_created") {
        throw new Error(
          result.operation.failure_summary ??
            `Git push failed with status ${result.operation.status}.`,
        );
      }
      return result;
    },
    onSuccess: (result) => {
      setActionError(null);
      const prUrl = result.operation.pull_request_url;
      setActionMessage(
        prUrl
          ? `Pushed to GitHub on branch ${result.operation.branch_name ?? `fix/${run.id}`}. Pull request created.`
          : "Git push completed successfully.",
      );
      queryClient.invalidateQueries({ queryKey: ["run", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-git-ops", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-events", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-report", run.id] });
    },
    onError: (error: Error) => {
      setActionMessage(null);
      setActionError(error.message);
      queryClient.invalidateQueries({ queryKey: ["run", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-git-ops", run.id] });
    },
  });

  const executeMutation = useMutation({
    mutationFn: (options?: {
      replanAfterFeedback?: boolean;
      resumeAfterApproval?: boolean;
      skipClone?: boolean;
    }) =>
      executeRun(run.id, token!, {
        skip_clone: options?.skipClone,
        replan_after_feedback: options?.replanAfterFeedback,
        resume_after_approval: options?.resumeAfterApproval,
      }),
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
  const latestGitOp = gitOps[0];
  const hasSuccessfulPush = gitOps.some((operation) => operation.status === "pr_created");
  const pushEligibility = getGitPushEligibility({
    run,
    fixAttempts,
    verifications,
    approvals,
    peerReviews,
    hasSuccessfulPush,
  });
  const { canPush: canPushGit, canForcePush, blockedReason: pushBlockedReason, forcePushHint, pushableFixAttempts } =
    pushEligibility;

  const skippedFixAttempts = fixAttempts.filter((attempt) => attempt.status === "skipped");
  const canRetryFixes =
    Boolean(run.repository_id) &&
    fixAttempts.length > 0 &&
    pushableFixAttempts.length === 0 &&
    skippedFixAttempts.length > 0 &&
    ["COMPLETED", "FINAL_REVIEW", "REPORTING", "FAILED", "FIXING"].includes(run.status);

  const retryFixesMutation = useMutation({
    mutationFn: () => {
      if (!token) {
        throw new Error("You must be signed in to retry code fixes.");
      }
      return applyRunFixes(run.id, token, { force: true });
    },
    onSuccess: (result) => {
      setActionError(null);
      setActionMessage(
        result.applied_count > 0
          ? `Applied ${result.applied_count} fix attempt(s). Check the Diff tab for changes.`
          : `Code fix finished with ${result.skipped_count} skipped and ${result.failed_count} failed attempt(s).`,
      );
      queryClient.invalidateQueries({ queryKey: ["run", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-fix-attempts", run.id] });
      queryClient.invalidateQueries({ queryKey: ["run-events", run.id] });
    },
    onError: (error: Error) => {
      setActionMessage(null);
      setActionError(error.message);
    },
  });

  const isRunComplete = run.status === "COMPLETED";
  const needsPipelineContinue = run.status === "PLANNING" || run.status === "FIXING";
  const canClone = Boolean(run.repository_id) && run.status === "CREATED";
  const canExecute =
    Boolean(run.repository_id) &&
    (["CREATED", "FAILED"].includes(run.status) || needsPipelineContinue);
  const isPushing = run.status === "PUSHING" || pushMutation.isPending;
  const awaitingApproval = run.status === "AWAITING_APPROVAL";
  const pushBranchName = `fix/${run.id}`;
  const pendingApprovals = approvals.filter((approval) => approval.status === "pending").length;

  return (
    <>
      <Card className="mb-4">
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Repository actions</h2>
        {!run.repository_id ? (
          <EmptyState message="Link a repository on the project page before cloning." />
        ) : (
          <>
            <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
              Clone pulls the GitHub/GitLab repo into the run workspace. When the run completes,
              click <strong>Push to GitHub</strong> to create branch{" "}
              <strong>{pushBranchName}</strong>, push your improved code, and open a pull request.
              Save your personal access token under Settings first.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button
                color="light"
                disabled={!canClone || cloneMutation.isPending || executeMutation.isPending || isPushing}
                onClick={() => cloneMutation.mutate()}
              >
                {cloneMutation.isPending ? "Cloning..." : "Clone repository"}
              </Button>
              <Button
                disabled={!canExecute || executeMutation.isPending || cloneMutation.isPending || isPushing || retryFixesMutation.isPending}
                onClick={() =>
                  executeMutation.mutate(
                    run.status === "PLANNING"
                      ? { replanAfterFeedback: true }
                      : run.status === "FIXING"
                        ? { resumeAfterApproval: true }
                        : undefined,
                  )
                }
              >
                {executeMutation.isPending
                  ? "Starting..."
                  : needsPipelineContinue
                    ? "Continue pipeline"
                    : "Run full pipeline"}
              </Button>
              {canRetryFixes ? (
                <Button
                  color="warning"
                  disabled={retryFixesMutation.isPending || isPushing}
                  onClick={() => retryFixesMutation.mutate()}
                >
                  {retryFixesMutation.isPending ? "Applying fixes..." : "Apply fixes now"}
                </Button>
              ) : null}
              <Button
                color="success"
                disabled={!canPushGit || isPushing || cloneMutation.isPending || executeMutation.isPending || retryFixesMutation.isPending}
                title={pushBlockedReason ?? undefined}
                onClick={() => pushMutation.mutate({})}
              >
                {isPushing ? "Pushing to GitHub..." : "Push to GitHub"}
              </Button>
              {canForcePush ? (
                <Button
                  color="warning"
                  disabled={isPushing || cloneMutation.isPending || executeMutation.isPending || retryFixesMutation.isPending}
                  title={forcePushHint ?? "Push workspace changes without applied fixes"}
                  onClick={() => pushMutation.mutate({ force: true })}
                >
                  {isPushing ? "Pushing to GitHub..." : "Push to GitHub anyway"}
                </Button>
              ) : null}
            </div>
            {isRunComplete && canPushGit ? (
              <p className="mt-3 text-sm text-green-700 dark:text-green-400">
                Run completed. Ready to push fixes to GitHub on branch{" "}
                <strong>{pushBranchName}</strong>.
              </p>
            ) : null}
            {hasSuccessfulPush && latestGitOp ? (
              <div className="mt-4 space-y-1 text-sm text-gray-700 dark:text-gray-300">
                <p>
                  Pushed to <strong>{latestGitOp.branch_name ?? pushBranchName}</strong>
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
            ) : pushBlockedReason ? (
              <div className="mt-3 space-y-1 text-sm text-gray-500 dark:text-gray-400">
                <p>{pushBlockedReason}</p>
                {canForcePush && forcePushHint ? (
                  <p className="text-amber-700 dark:text-amber-400">{forcePushHint}</p>
                ) : null}
              </div>
            ) : null}
          </>
        )}
        {actionMessage ? <Alert color="info" className="mt-4">{actionMessage}</Alert> : null}
        {actionError ? <Alert color="failure" className="mt-4">{actionError}</Alert> : null}
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
            Approvals tab. After you approve, the run continues automatically into code fixing.
          </Alert>
        ) : null}
        <RunSummaryGrid
          items={[
            { label: "Findings", value: findings.length },
            { label: "Fix attempts", value: fixAttempts.length, hint: `${pushableFixAttempts.length} pushable` },
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
