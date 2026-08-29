import { Badge, Button, ButtonGroup } from "flowbite-react";
import { NavLink, useMatch } from "react-router-dom";

const RUN_TABS = [
  { to: "", label: "Overview", end: true },
  { to: "findings", label: "Findings", end: true },
  { to: "diff", label: "Diff", end: true },
  { to: "approvals", label: "Approvals", end: true },
  { to: "reports", label: "Reports", end: true },
] as const;

interface RunTabGroupProps {
  runId: string;
  pendingApprovalCount: number;
  approvalRequired: boolean;
}

interface RunTabButtonProps {
  runId: string;
  to: string;
  label: string;
  end?: boolean;
  pendingApprovalCount: number;
  approvalRequired: boolean;
}

function RunTabButton({
  runId,
  to,
  label,
  end,
  pendingApprovalCount,
  approvalRequired,
}: RunTabButtonProps) {
  const matchPath = to ? `/runs/${runId}/${to}` : `/runs/${runId}`;
  const isActive = Boolean(useMatch({ path: matchPath, end: end ?? false }));
  const showApprovalBadge =
    to === "approvals" && (pendingApprovalCount > 0 || approvalRequired);

  return (
    <Button
      as={NavLink}
      to={to}
      end={end}
      color={isActive ? "blue" : "gray"}
      outline={!isActive}
      className={`inline-flex items-center gap-2 ${
        isActive ? "border border-blue-600" : "border border-gray-300 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
      }`}
    >
      {label}
      {showApprovalBadge ? (
        <Badge color="failure" size="xs">
          {pendingApprovalCount > 0 ? pendingApprovalCount : "!"}
        </Badge>
      ) : null}
    </Button>
  );
}

export function RunTabGroup({
  runId,
  pendingApprovalCount,
  approvalRequired,
}: RunTabGroupProps) {
  return (
    <ButtonGroup
      outline
      className="mb-4 flex-wrap rounded-lg border border-gray-300 shadow-sm"
      data-testid="run-tab-group"
    >
      {RUN_TABS.map((tab) => (
        <RunTabButton
          key={tab.to}
          runId={runId}
          to={tab.to}
          label={tab.label}
          end={tab.end}
          pendingApprovalCount={pendingApprovalCount}
          approvalRequired={approvalRequired}
        />
      ))}
    </ButtonGroup>
  );
}
