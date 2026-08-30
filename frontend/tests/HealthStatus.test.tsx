import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HealthStatus } from "../src/components/HealthStatus";
import * as client from "../src/api/client";

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("HealthStatus", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows healthy status when backend responds", async () => {
    vi.spyOn(client, "getHealth").mockResolvedValue({
      status: "ok",
      service: "therecode-backend",
    });

    renderWithQuery(<HealthStatus />);

    await waitFor(() => {
      expect(screen.getByTestId("health-status")).toHaveTextContent(
        "Backend status: ok (therecode-backend)",
      );
    });
  });

  it("shows unavailable when backend fails", async () => {
    vi.spyOn(client, "getHealth").mockRejectedValue(new Error("Network error"));

    renderWithQuery(<HealthStatus />);

    await waitFor(() => {
      expect(screen.getByTestId("health-status")).toHaveTextContent("Backend unavailable");
    });
  });
});
