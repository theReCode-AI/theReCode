import { Badge } from "flowbite-react";

const SEVERITY_COLOR: Record<string, "failure" | "warning" | "gray" | "info"> = {
  critical: "failure",
  high: "failure",
  medium: "warning",
  low: "gray",
  info: "info",
};

interface SeverityBadgeProps {
  severity: string;
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const color = SEVERITY_COLOR[severity] ?? "gray";
  return (
    <Badge color={color} className="uppercase">
      {severity}
    </Badge>
  );
}
