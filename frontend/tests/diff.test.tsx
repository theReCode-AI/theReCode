import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DiffViewer } from "@/components/diff/DiffViewer";
import { parseUnifiedDiff } from "@/utils/diff";

describe("diff utilities", () => {
  it("classifies unified diff lines", () => {
    const lines = parseUnifiedDiff("--- a/file.py\n+++ b/file.py\n+added\n-removed\n context");
    expect(lines.map((line) => line.kind)).toEqual([
      "meta",
      "meta",
      "add",
      "remove",
      "context",
    ]);
  });

  it("renders diff viewer", () => {
    render(<DiffViewer content={"--- a/file.py\n+++ b/file.py\n+added"} />);
    expect(screen.getByTestId("diff-viewer")).toBeInTheDocument();
    expect(screen.getByText("+added")).toBeInTheDocument();
  });
});
