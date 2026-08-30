import { useOutletContext } from "react-router-dom";

import { RunChatPanel } from "@/components/chat/RunChatPanel";
import type { RunOutletContext } from "@/pages/RunDetailPage";

export function RunChatPage() {
  const { run } = useOutletContext<RunOutletContext>();

  return (
    <section className="w-full">
      <RunChatPanel runId={run.id} />
    </section>
  );
}
