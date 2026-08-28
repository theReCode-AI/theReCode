import { useQuery } from "@tanstack/react-query";

import { getHealth } from "../api/client";

export function HealthStatus() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    retry: false,
  });

  if (isLoading) {
    return <p data-testid="health-status">Checking backend health...</p>;
  }

  if (isError || !data) {
    return <p data-testid="health-status">Backend unavailable</p>;
  }

  return (
    <p data-testid="health-status">
      Backend status: {data.status} ({data.service})
    </p>
  );
}
