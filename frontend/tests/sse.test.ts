import { describe, expect, it } from "vitest";

import { parseSseChunk } from "@/api/sse";

describe("parseSseChunk", () => {
  it("parses snapshot and agent_event frames", () => {
    const chunk = [
      'event: snapshot',
      'data: {"run":{"id":"1"},"state":null,"events":[]}',
      "",
      'event: agent_event',
      'id: evt-1',
      'data: {"id":"evt-1","event_type":"CLONE_COMPLETED"}',
      "",
    ].join("\n");

    const messages = parseSseChunk(chunk);
    expect(messages).toHaveLength(2);
    expect(messages[0]?.event).toBe("snapshot");
    expect(messages[1]?.event).toBe("agent_event");
    expect(messages[1]?.id).toBe("evt-1");
  });
});
