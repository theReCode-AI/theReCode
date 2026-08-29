import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card } from "flowbite-react";
import { useOutletContext, useParams } from "react-router-dom";

import { generateRunReport, getRunReport, getRunReportMarkdown } from "@/api/runs";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { ReportMarkdownView } from "@/components/reports/ReportMarkdownView";
import type { RunOutletContext } from "@/pages/RunDetailPage";
import { useAuthStore } from "@/stores/authStore";
import { formatDateTime } from "@/utils/runStages";

export function RunReportsPage() {
  const { runId = "" } = useParams();
  const token = useAuthStore((state) => state.token);
  const { run, gitOps } = useOutletContext<RunOutletContext>();
  const queryClient = useQueryClient();
  const latestGitOp = gitOps[0];

  const reportQuery = useQuery({
    queryKey: ["run-report", runId],
    queryFn: () => getRunReport(runId, token!),
    enabled: Boolean(token && runId),
    retry: false,
  });

  const report = reportQuery.data ?? undefined;

  const markdownQuery = useQuery({
    queryKey: ["run-report-markdown", runId],
    queryFn: () => getRunReportMarkdown(runId, token!),
    enabled: Boolean(token && runId && report),
    retry: false,
  });

  const generateMutation = useMutation({
    mutationFn: () => generateRunReport(runId, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["run-report", runId] });
      queryClient.invalidateQueries({ queryKey: ["run-report-markdown", runId] });
      queryClient.invalidateQueries({ queryKey: ["run", runId] });
    },
  });

  const awaitingApproval = run.status === "AWAITING_APPROVAL";
  const canGenerateReport =
    !report &&
    !awaitingApproval &&
    ["REPORTING", "COMPLETED", "FAILED", "PUSHING", "FINAL_REVIEW"].includes(run.status);

  if (reportQuery.isLoading) {
    return <LoadingState message="Loading report..." />;
  }

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Run report</h2>
        {canGenerateReport ? (
          <Button disabled={generateMutation.isPending} onClick={() => generateMutation.mutate()}>
            {generateMutation.isPending ? "Generating..." : "Generate report"}
          </Button>
        ) : null}
      </div>

      {reportQuery.isError ? (
        <ErrorState message="Unable to load report metadata." />
      ) : null}
      {generateMutation.isError ? (
        <ErrorState message="Unable to generate report for this run." />
      ) : null}

      {!report ? (
        <EmptyState
          message={
            awaitingApproval
              ? "The pipeline is paused for human approval. The final report is generated after the run completes."
              : "Report has not been generated yet. Complete the run pipeline or use Generate report when the run has finished."
          }
        />
      ) : (
        <>
          <div className="mb-4 space-y-1 text-sm text-gray-700 dark:text-gray-300">
            <p>
              Final health score: <strong>{report.final_health_score}/100</strong>
            </p>
            <p>Status: {report.status}</p>
            <p>Generated: {formatDateTime(report.created_at)}</p>
            {report.pull_request_url ? (
              <p>
                <a
                  href={report.pull_request_url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium text-blue-600 hover:underline"
                >
                  Open pull request
                </a>
              </p>
            ) : null}
          </div>

          {markdownQuery.isLoading ? <LoadingState message="Loading report..." /> : null}
          {markdownQuery.isError ? (
            <ErrorState message="Unable to load report content." />
          ) : null}
          {markdownQuery.data?.markdown ? (
            <ReportMarkdownView markdown={markdownQuery.data.markdown} />
          ) : null}
        </>
      )}

      <h3 className="mb-3 mt-6 text-base font-semibold text-gray-900 dark:text-white">Git finalization</h3>
      {!latestGitOp ? (
        <EmptyState message="No git operations recorded yet." />
      ) : (
        <ul className="list-disc space-y-2 pl-5 text-sm text-gray-700 dark:text-gray-300">
          <li>
            Status: {latestGitOp.status}
            {latestGitOp.branch_name ? ` · Branch: ${latestGitOp.branch_name}` : ""}
            {latestGitOp.commit_sha ? ` · Commit: ${latestGitOp.commit_sha.slice(0, 8)}` : ""}
          </li>
          {latestGitOp.pull_request_url ? (
            <li>
              <a
                href={latestGitOp.pull_request_url}
                target="_blank"
                rel="noreferrer"
                className="font-medium text-blue-600 hover:underline"
              >
                View PR/MR
              </a>
            </li>
          ) : null}
        </ul>
      )}

      {report ? (
        <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
          Raw artifacts are stored on the server at{" "}
          <span className="mono-text">{report.markdown_path}</span>
        </p>
      ) : (
        <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
          After a completed run, the full report will appear here.
        </p>
      )}
    </Card>
  );
}
