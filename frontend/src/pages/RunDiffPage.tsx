import { useQuery } from "@tanstack/react-query";
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
      <section className="panel">
        <h2>Code changes</h2>
        <EmptyState message="No diff artifacts available yet." />
      </section>
    );
  }

  return (
    <section className="panel diff-page">
      <h2>Code changes</h2>
      <div className="diff-layout">
        <aside className="diff-sidebar">
          {attemptsWithDiff.map((attempt) => (
            <button
              key={attempt.fix_attempt_id}
              type="button"
              className={
                attempt.fix_attempt_id === selectedAttemptId
                  ? "diff-option active"
                  : "diff-option"
              }
              onClick={() => setSelectedAttemptId(attempt.fix_attempt_id)}
            >
              <strong>Attempt {attempt.attempt_number}</strong>
              <span>{attempt.status}</span>
              <small>{attempt.changed_files.join(", ") || "No files"}</small>
            </button>
          ))}
        </aside>
        <div className="diff-main">
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
    </section>
  );
}
