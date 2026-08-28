import { describe, expect, it } from "vitest";

import {
  PIPELINE_GRAPH_ORDER,
  getActiveGraphNodeLabel,
  resolvePipelineNodeStates,
} from "@/utils/pipelineGraph";

describe("pipelineGraph", () => {
  it("completes all nodes when run is completed", () => {
    const states = resolvePipelineNodeStates({ status: "COMPLETED" });
    for (const stageId of PIPELINE_GRAPH_ORDER) {
      expect(states[stageId]).toBe("complete");
    }
  });

  it("maps run status to active graph node label", () => {
    expect(getActiveGraphNodeLabel("SELF_CORRECTING", null)).toBe("Self-correct");
    expect(getActiveGraphNodeLabel("AWAITING_APPROVAL", null)).toBe("Approval");
  });

  it("marks failed runs on the active stage", () => {
    const states = resolvePipelineNodeStates({
      status: "FAILED",
      currentStage: "verification",
      completedStages: ["initialization", "cloning", "code_fixing"],
    });
    expect(states.verification).toBe("failed");
    expect(states.cloning).toBe("complete");
  });
});
