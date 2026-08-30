import { Alert, Button, Label, Textarea } from "flowbite-react";
import { useState } from "react";

import { ApiError } from "@/api/client";
import type { HumanDecision } from "@/types/approval";

interface ApprovalDecisionFormProps {
  disabled?: boolean;
  onSubmit: (decision: HumanDecision, feedback?: string) => Promise<void>;
}

export function ApprovalDecisionForm({ disabled = false, onSubmit }: ApprovalDecisionFormProps) {
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleDecision(decision: HumanDecision) {
    setError(null);
    setIsSubmitting(true);
    try {
      await onSubmit(decision, feedback.trim() ? feedback.trim() : undefined);
      setFeedback("");
    } catch (submitError) {
      const message =
        submitError instanceof ApiError
          ? submitError.detail ?? submitError.message
          : "Unable to submit approval decision.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div data-testid="approval-decision-form">
      <div className="mb-4">
        <Label htmlFor="approvalFeedback">Feedback</Label>
        <Textarea
          id="approvalFeedback"
          value={feedback}
          onChange={(event) => setFeedback(event.target.value)}
          placeholder="Optional for approve/reject. Required for request changes."
          rows={4}
        />
      </div>
      {error ? <Alert color="failure" className="mb-4">{error}</Alert> : null}
      <div className="flex flex-wrap gap-3">
        <Button
          type="button"
          disabled={disabled || isSubmitting}
          onClick={() => handleDecision("approve")}
        >
          Approve
        </Button>
        <Button
          type="button"
          color="light"
          disabled={disabled || isSubmitting}
          onClick={() => handleDecision("reject")}
        >
          Reject
        </Button>
        <Button
          type="button"
          color="light"
          disabled={disabled || isSubmitting}
          onClick={() => handleDecision("request_changes")}
        >
          Request changes
        </Button>
      </div>
    </div>
  );
}
