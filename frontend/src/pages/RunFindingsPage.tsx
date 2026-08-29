import { Card, Table, TableBody, TableCell, TableHead, TableHeadCell, TableRow } from "flowbite-react";
import { useOutletContext } from "react-router-dom";

import { EmptyState } from "@/components/common/EmptyState";
import { SeverityBadge } from "@/components/runs/SeverityBadge";
import type { RunOutletContext } from "@/pages/RunDetailPage";
import { formatFindingLocation } from "@/utils/findingLocation";
import { formatDateTime } from "@/utils/runStages";

export function RunFindingsPage() {
  const { findings } = useOutletContext<RunOutletContext>();

  return (
    <Card>
      <h2 className="mb-4 text-lg font-semibold text-gray-900">Findings</h2>
      {findings.length === 0 ? (
        <EmptyState message="No findings available for this run." />
      ) : (
        <div className="overflow-x-auto">
          <Table hoverable>
            <TableHead>
              <TableRow>
                <TableHeadCell>Severity</TableHeadCell>
                <TableHeadCell>Agent</TableHeadCell>
                <TableHeadCell>Location</TableHeadCell>
                <TableHeadCell>Message</TableHeadCell>
                <TableHeadCell>Created</TableHeadCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {findings.map((finding) => (
                <TableRow key={finding.finding_id}>
                  <TableCell>
                    <SeverityBadge severity={finding.severity} />
                  </TableCell>
                  <TableCell>{finding.agent}</TableCell>
                  <TableCell>
                    {formatFindingLocation(finding.file, finding.line_start)}
                  </TableCell>
                  <TableCell>{finding.message}</TableCell>
                  <TableCell>{formatDateTime(finding.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </Card>
  );
}
