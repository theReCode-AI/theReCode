import { describe, expect, it } from "vitest";

import { renderSimpleMarkdown } from "@/utils/markdown";

describe("renderSimpleMarkdown", () => {
  it("renders headings and lists", () => {
    const html = renderSimpleMarkdown("# Title\n\n## Section\n\n- item one\n- item two");
    expect(html).toContain("<h1>Title</h1>");
    expect(html).toContain("<h2>Section</h2>");
    expect(html).toContain("<li>item one</li>");
    expect(html).toContain("<li>item two</li>");
  });

  it("escapes unsafe html", () => {
    const html = renderSimpleMarkdown("<script>alert(1)</script>");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });
});
