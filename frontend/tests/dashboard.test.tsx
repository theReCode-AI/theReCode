import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentTimeline } from "@/components/runs/AgentTimeline";
import { PipelineGraph } from "@/components/runs/PipelineGraph";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import type { AgentEvent } from "@/types/run";
import { formatEventLabel } from "@/utils/runStages";
import {
  getGraphProgressPercent,
  resolvePipelineNodeStates,
} from "@/utils/pipelineGraph";

const sampleEvents: AgentEvent[] = [
  {
    id: "1",
    run_id: "run-1",
    event_type: "CLONE_COMPLETED",
    stage: "cloning",
    agent: null,
    tool: null,
    status: "ok",
    message: "Repository cloned",
    payload: {},
    created_at: "2026-08-28T12:00:00.000Z",
  },
];

describe("run dashboard components", () => {
  it("renders pipeline graph for active run", () => {
    const { container } = render(
      <PipelineGraph
        status="FIXING"
        currentStage="code_fixing"
        completedStages={["initialization", "cloning", "project_intelligence"]}
      />,
    );
    expect(screen.getByTestId("pipeline-graph")).toBeInTheDocument();
    expect(container.querySelector(".pipeline-graph-node.is-active")).toBeTruthy();
    expect(container.querySelectorAll(".pipeline-graph-node.is-complete").length).toBeGreaterThan(0);
  });

  it("marks completed stages in graph state", () => {
    const states = resolvePipelineNodeStates({
      status: "FIXING",
      currentStage: "code_fixing",
      completedStages: ["cloning", "diagnostics"],
    });
    expect(states.cloning).toBe("complete");
    expect(states.code_fixing).toBe("active");
    expect(states.finalization).toBe("pending");
  });

  it("uses live progress percent when available", () => {
    expect(
      getGraphProgressPercent({
        status: "FIXING",
        progress: 72,
      }),
    ).toBe(72);
  });

  it("renders status badge", () => {
    render(<RunStatusBadge status="COMPLETED" />);
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
  });

  it("formats timeline labels", () => {
    expect(formatEventLabel("GIT_PR_CREATED")).toBe("PR created");
  });

  it("renders agent timeline events", () => {
    render(<AgentTimeline events={sampleEvents} />);
    expect(screen.getByTestId("agent-timeline")).toBeInTheDocument();
    expect(screen.getAllByText("Repository cloned").length).toBeGreaterThan(0);
  });
});
