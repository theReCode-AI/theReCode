import { useOutletContext } from "react-router-dom";

import { EmptyState } from "@/components/common/EmptyState";
import type { RunOutletContext } from "@/pages/RunDetailPage";
import { formatDateTime } from "@/utils/runStages";

export function RunFindingsPage() {
  const { findings } = useOutletContext<RunOutletContext>();

  return (
    <section className="panel">
      <h2>Findings</h2>
      {findings.length === 0 ? (
        <EmptyState message="No findings available for this run." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Agent</th>
                <th>Location</th>
                <th>Message</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((finding) => (
                <tr key={finding.finding_id}>
                  <td>
                    <span className={`severity-badge severity-${finding.severity}`}>
                      {finding.severity}
                    </span>
                  </td>
                  <td>{finding.agent}</td>
                  <td>
                    {finding.file
                      ? `${finding.file}${finding.line_start ? `:${finding.line_start}` : ""}`
                      : "—"}
                  </td>
                  <td>{finding.message}</td>
                  <td>{formatDateTime(finding.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
