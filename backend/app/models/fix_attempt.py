from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.fix_attempt_enums import FixAttemptStatus


class FixAttempt(BaseModel):
    """Persisted record of a code-fix application attempt."""

    model_config = ConfigDict(populate_by_name=True)

    fix_attempt_id: str
    run_id: str
    patch_plan_id: str
    attempt_number: int = Field(ge=1)
    status: FixAttemptStatus
    planned_files: list[str]
    changed_files: list[str] = Field(default_factory=list)
    unexpected_files: list[str] = Field(default_factory=list)
    scope_violation: bool = False
    backup_path: str | None = None
    diff_artifact_path: str | None = None
    error_message: str | None = None
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "FixAttempt":
        document = document.copy()
        document["fix_attempt_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        document["patch_plan_id"] = str(document["patch_plan_id"])
        return cls.model_validate(document)
