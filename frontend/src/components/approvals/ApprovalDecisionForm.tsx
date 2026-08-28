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
    <div className="approval-decision-form" data-testid="approval-decision-form">
      <label>
        Feedback
        <textarea
          value={feedback}
          onChange={(event) => setFeedback(event.target.value)}
          placeholder="Optional for approve/reject. Required for request changes."
          rows={4}
        />
      </label>
      {error ? <p className="form-error">{error}</p> : null}
      <div className="approval-actions">
        <button
          type="button"
          className="primary-button"
          disabled={disabled || isSubmitting}
          onClick={() => handleDecision("approve")}
        >
          Approve
        </button>
        <button
          type="button"
          className="ghost-button"
          disabled={disabled || isSubmitting}
          onClick={() => handleDecision("reject")}
        >
          Reject
        </button>
        <button
          type="button"
          className="ghost-button"
          disabled={disabled || isSubmitting}
          onClick={() => handleDecision("request_changes")}
        >
          Request changes
        </button>
      </div>
    </div>
  );
}
