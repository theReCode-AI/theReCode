import { describe, expect, it } from "vitest";

import { deleteGitCredential, listGitCredentials, saveGitCredential } from "@/api/git";

describe("git api", () => {
  it("exports credential endpoints", () => {
    expect(typeof listGitCredentials).toBe("function");
    expect(typeof saveGitCredential).toBe("function");
    expect(typeof deleteGitCredential).toBe("function");
  });
});
