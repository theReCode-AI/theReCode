import { HealthStatus } from "../components/HealthStatus";

export function HomePage() {
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>CodeThera</h1>
      <p>Autonomous AI software-engineering platform for Python repositories.</p>
      <HealthStatus />
    </main>
  );
}
