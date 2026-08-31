import { useQuery } from "@tanstack/react-query";
import { Alert, Card } from "flowbite-react";
import { useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";

import { getFixAttemptDiff } from "@/api/approvals";
import { DiffViewer } from "@/components/diff/DiffViewer";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import type { RunOutletContext } from "@/pages/RunDetailPage";
import { useAuthStore } from "@/stores/authStore";
import type { FixAttempt } from "@/types/run";

export function RunDiffPage() {
  const { run, fixAttempts } = useOutletContext<RunOutletContext>();
  const token = useAuthStore((state) => state.token);
  const attemptsWithDiff = fixAttempts.filter((attempt) => attempt.diff_artifact_path);
  const skippedAttempts = fixAttempts.filter((attempt) => attempt.status === "skipped");
  const [selectedAttemptId, setSelectedAttemptId] = useState(
    attemptsWithDiff[0]?.fix_attempt_id ?? fixAttempts[0]?.fix_attempt_id ?? "",
  );

  const selectedAttempt = useMemo(
    () => fixAttempts.find((attempt) => attempt.fix_attempt_id === selectedAttemptId),
    [fixAttempts, selectedAttemptId],
  );

  const diffQuery = useQuery({
    queryKey: ["fix-attempt-diff", run.id, selectedAttemptId],
    queryFn: () => getFixAttemptDiff(run.id, selectedAttemptId, token!),
    enabled: Boolean(token && selectedAttemptId && selectedAttempt?.diff_artifact_path),
  });

  if (fixAttempts.length === 0) {
    return (
      <Card>
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Code changes</h2>
        <EmptyState message="No fix attempts recorded yet." />
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Code changes</h2>
      {skippedAttempts.length > 0 ? (
        <Alert color="warning" className="mb-4">
          {skippedAttempts.length} fix attempt(s) were skipped and produced no diff. Common reasons:
          human approval was required but fixes were not re-applied, or the planned change type is not
          fully automatable. Use <strong>Retry code fixes</strong> on Overview after approving risk-gate
          items.
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {skippedAttempts.map((attempt) => (
              <li key={attempt.fix_attempt_id}>
                Attempt {attempt.attempt_number}: {attempt.error_message ?? "Skipped without details"}
              </li>
            ))}
          </ul>
        </Alert>
      ) : null}
      {attemptsWithDiff.length === 0 ? (
        <EmptyState message="No diff artifacts available yet." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
          <aside className="flex flex-col gap-2">
            {fixAttempts.map((attempt) => (
              <AttemptButton
                key={attempt.fix_attempt_id}
                attempt={attempt}
                selected={attempt.fix_attempt_id === selectedAttemptId}
                onSelect={() => setSelectedAttemptId(attempt.fix_attempt_id)}
              />
            ))}
          </aside>
          <div>
            {diffQuery.isLoading ? <LoadingState message="Loading diff..." /> : null}
            {diffQuery.isError ? <ErrorState message="Unable to load diff artifact." /> : null}
            {diffQuery.data ? (
              <DiffViewer
                title={selectedAttempt ? `Attempt ${selectedAttempt.attempt_number}` : undefined}
                content={diffQuery.data.content}
              />
            ) : selectedAttempt && !selectedAttempt.diff_artifact_path ? (
              <EmptyState message="This attempt has no diff because no files were changed." />
            ) : null}
          </div>
        </div>
      )}
    </Card>
  );
}

function AttemptButton({
  attempt,
  selected,
  onSelect,
}: {
  attempt: FixAttempt;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={`rounded-xl border p-3 text-left transition ${
        selected
          ? "border-blue-600 bg-blue-50"
          : "border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 hover:border-gray-300"
      }`}
      onClick={onSelect}
    >
      <strong className="block text-gray-900 dark:text-white">Attempt {attempt.attempt_number}</strong>
      <span className="text-sm text-gray-600 dark:text-gray-400">{attempt.status}</span>
      <small className="mt-1 block text-xs text-gray-500 dark:text-gray-400">
        {attempt.changed_files.join(", ") || attempt.error_message || "No files"}
      </small>
    </button>
  );
}
