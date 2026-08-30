import {
  PIPELINE_GRAPH_EDGES,
  PIPELINE_GRAPH_HEIGHT,
  PIPELINE_GRAPH_NODES,
  PIPELINE_GRAPH_WIDTH,
  PIPELINE_NODE_HEIGHT,
  PIPELINE_NODE_WIDTH,
  resolvePipelineNodeStates,
  type PipelineGraphNode,
  type PipelineNodeState,
} from "@/utils/pipelineGraph";
import type { RunStatus } from "@/types/run";

interface PipelineGraphProps {
  status: RunStatus;
  currentStage?: string | null;
  completedStages?: string[];
}

function nodeCenter(node: PipelineGraphNode) {
  return {
    x: node.x + PIPELINE_NODE_WIDTH / 2,
    y: node.y + PIPELINE_NODE_HEIGHT / 2,
  };
}

function edgePath(from: PipelineGraphNode, to: PipelineGraphNode, loop?: boolean): string {
  const start = nodeCenter(from);
  const end = nodeCenter(to);

  if (loop) {
    const controlX = (start.x + end.x) / 2;
    const controlY = Math.max(start.y, end.y) + 56;
    return `M ${start.x} ${start.y} Q ${controlX} ${controlY} ${end.x} ${end.y}`;
  }

  if (from.y === to.y) {
    return `M ${start.x} ${start.y} L ${end.x} ${end.y}`;
  }

  const midY = (start.y + end.y) / 2;
  return `M ${start.x} ${start.y} L ${start.x} ${midY} L ${end.x} ${midY} L ${end.x} ${end.y}`;
}

function edgeState(
  fromId: string,
  toId: string,
  nodeStates: Record<string, PipelineNodeState>,
): PipelineNodeState {
  const fromState = nodeStates[fromId];
  const toState = nodeStates[toId];

  if (fromState === "complete" && (toState === "complete" || toState === "active")) {
    return "complete";
  }
  if (fromState === "complete" && toState === "failed") {
    return "failed";
  }
  if (fromState === "active" || toState === "active") {
    return "active";
  }
  return "pending";
}

export function PipelineGraph({
  status,
  currentStage,
  completedStages = [],
}: PipelineGraphProps) {
  const nodeStates = resolvePipelineNodeStates({
    status,
    currentStage,
    completedStages,
  });
  const nodeById = Object.fromEntries(PIPELINE_GRAPH_NODES.map((node) => [node.id, node]));

  return (
    <div className="pipeline-graph-wrap" data-testid="pipeline-graph">
      <svg
        className="pipeline-graph"
        viewBox={`0 0 ${PIPELINE_GRAPH_WIDTH} ${PIPELINE_GRAPH_HEIGHT}`}
        role="img"
        aria-label="Run pipeline graph"
      >
        <defs>
          <marker
            id="pipeline-arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
          </marker>
        </defs>

        {PIPELINE_GRAPH_EDGES.map((edge) => {
          const from = nodeById[edge.from];
          const to = nodeById[edge.to];
          if (!from || !to) {
            return null;
          }

          const state = edgeState(edge.from, edge.to, nodeStates);
          return (
            <path
              key={`${edge.from}-${edge.to}-${edge.loop ? "loop" : "flow"}`}
              d={edgePath(from, to, edge.loop)}
              className={`pipeline-edge is-${state}${edge.loop ? " is-loop" : ""}`}
              markerEnd={edge.loop ? undefined : "url(#pipeline-arrow)"}
              fill="none"
            />
          );
        })}

        {PIPELINE_GRAPH_NODES.map((node) => {
          const state = nodeStates[node.id];
          return (
            <g
              key={node.id}
              className={`pipeline-graph-node is-${state}`}
              transform={`translate(${node.x}, ${node.y})`}
            >
              <title>{node.label}</title>
              <rect
                width={PIPELINE_NODE_WIDTH}
                height={PIPELINE_NODE_HEIGHT}
                rx={10}
                ry={10}
              />
              <text x={PIPELINE_NODE_WIDTH / 2} y={PIPELINE_NODE_HEIGHT / 2 + 4}>
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
