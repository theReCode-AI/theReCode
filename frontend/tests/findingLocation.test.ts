import { describe, expect, it } from "vitest";

import { formatFindingLocation } from "@/utils/findingLocation";

describe("formatFindingLocation", () => {
  it("shows filename and line from absolute path", () => {
    expect(
      formatFindingLocation(
        "/home/codezerro/Desktop/harpic-agent-ai-cursor/workspace/runs/6a91c9a4b865219bc2d3a708/repository/kimi_test.py",
        1,
      ),
    ).toBe("kimi_test.py:1");
  });

  it("shows filename only when line is missing", () => {
    expect(formatFindingLocation("src/app/main.py", null)).toBe("main.py");
  });

  it("returns dash when file is missing", () => {
    expect(formatFindingLocation(null, 10)).toBe("—");
  });
});
