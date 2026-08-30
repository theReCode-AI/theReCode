import { Card } from "flowbite-react";

import { HealthStatus } from "../components/HealthStatus";

export function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900 p-8">
      <Card className="max-w-lg text-center">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">theReCode</h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Autonomous AI software-engineering platform for Python repositories.
        </p>
        <div className="mt-4">
          <HealthStatus />
        </div>
      </Card>
    </main>
  );
}
