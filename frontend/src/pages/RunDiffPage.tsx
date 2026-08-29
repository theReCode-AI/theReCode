import { useQuery } from "@tanstack/react-query";
import { Card } from "flowbite-react";
import { useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";

import { getFixAttemptDiff } from "@/api/approvals";
import { DiffViewer } from "@/components/diff/DiffViewer";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import type { RunOutletContext } from "@/pages/RunDetailPage";
import { useAuthStore } from "@/stores/authStore";

export function RunDiffPage() {
  const { run, fixAttempts } = useOutletContext<RunOutletContext>();
  const token = useAuthStore((state) => state.token);
  const attemptsWithDiff = fixAttempts.filter((attempt) => attempt.diff_artifact_path);
  const [selectedAttemptId, setSelectedAttemptId] = useState(
    attemptsWithDiff[0]?.fix_attempt_id ?? "",
  );

  const selectedAttempt = useMemo(
    () => attemptsWithDiff.find((attempt) => attempt.fix_attempt_id === selectedAttemptId),
    [attemptsWithDiff, selectedAttemptId],
  );

  const diffQuery = useQuery({
    queryKey: ["fix-attempt-diff", run.id, selectedAttemptId],
    queryFn: () => getFixAttemptDiff(run.id, selectedAttemptId, token!),
    enabled: Boolean(token && selectedAttemptId),
  });

  if (attemptsWithDiff.length === 0) {
    return (
      <Card>
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Code changes</h2>
        <EmptyState message="No diff artifacts available yet." />
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="mb-4 text-lg font-semibold text-gray-900">Code changes</h2>
      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        <aside className="flex flex-col gap-2">
          {attemptsWithDiff.map((attempt) => (
            <button
              key={attempt.fix_attempt_id}
              type="button"
              className={`rounded-xl border p-3 text-left transition ${
                attempt.fix_attempt_id === selectedAttemptId
                  ? "border-blue-600 bg-blue-50"
                  : "border-gray-200 bg-gray-50 hover:border-gray-300"
              }`}
              onClick={() => setSelectedAttemptId(attempt.fix_attempt_id)}
            >
              <strong className="block text-gray-900">Attempt {attempt.attempt_number}</strong>
              <span className="text-sm text-gray-600">{attempt.status}</span>
              <small className="mt-1 block text-xs text-gray-500">
                {attempt.changed_files.join(", ") || "No files"}
              </small>
            </button>
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
          ) : null}
        </div>
      </div>
    </Card>
  );
}
