import { Card } from "flowbite-react";

import { HealthStatus } from "../components/HealthStatus";

export function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50 p-8">
      <Card className="max-w-lg text-center">
        <h1 className="text-3xl font-bold text-gray-900">CodeThera</h1>
        <p className="mt-2 text-gray-600">
          Autonomous AI software-engineering platform for Python repositories.
        </p>
        <div className="mt-4">
          <HealthStatus />
        </div>
      </Card>
    </main>
  );
}
