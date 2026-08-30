import { describe, expect, it } from "vitest";

import { sanitizeReportMarkdown } from "@/utils/reportMarkdown";

describe("sanitizeReportMarkdown", () => {
  it("strips absolute paths from finding lines", () => {
    const markdown =
      "- [low] /home/codezerro/Desktop/harpic-agent-ai-cursor/workspace/runs/abc/repository/kimi_test.py:1 Import (ruff)";

    expect(sanitizeReportMarkdown(markdown)).toBe("- [low] kimi_test.py:1 Import (ruff)");
  });

  it("leaves already-short paths unchanged", () => {
    const markdown = "- [high] src/auth.py:42 Missing auth (semgrep)";

    expect(sanitizeReportMarkdown(markdown)).toBe(markdown);
  });
});
