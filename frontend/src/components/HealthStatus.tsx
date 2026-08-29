import { useQuery } from "@tanstack/react-query";
import { Badge } from "flowbite-react";

import { getHealth } from "../api/client";

export function HealthStatus() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    retry: false,
  });

  if (isLoading) {
    return <p data-testid="health-status" className="text-sm text-gray-400">Checking backend health...</p>;
  }

  if (isError || !data) {
    return <p data-testid="health-status" className="text-sm text-gray-400">Backend unavailable</p>;
  }

  return (
    <p data-testid="health-status" className="text-sm text-gray-400">
      Backend status:{" "}
      <Badge color="success" className="inline">
        {data.status} ({data.service})
      </Badge>
    </p>
  );
}
