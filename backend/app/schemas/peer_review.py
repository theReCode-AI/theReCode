from datetime import datetime

from pydantic import BaseModel, Field

from app.models.peer_review_result import PeerReviewResult


class PeerReviewResultResponse(PeerReviewResult):
    """API response for a persisted peer review result."""


class RunPeerReviewResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    peer_reviews: list[PeerReviewResultResponse]
    result_count: int = Field(ge=0)
    approved_count: int = Field(ge=0)
    changes_requested_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    run_status: str
