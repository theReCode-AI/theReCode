from datetime import UTC, datetime

from bson import ObjectId

from app.adk.memory.extractor import MemoryExtractionContext, MemoryExtractor
from app.models.approval import HumanApproval
from app.models.approval_enums import ApprovalStatus, ApprovalTrigger, HumanDecision
from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.memory_enums import MemoryType
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.peer_review_enums import PeerReviewVerdict
from app.models.peer_review_result import PeerReviewResult
from app.models.project_intelligence import (
    ApplicationArchitecture,
    PackageManager,
    ProjectIntelligence,
)
from app.models.run import Run, RunStatus
from app.models.verification_enums import VerificationStatus
from app.models.verification_result import VerificationResult


def _run(project_id: str, run_id: str) -> Run:
    now = datetime.now(UTC)
    return Run(
        id=run_id,
        project_id=project_id,
        user_id=str(ObjectId()),
        status=RunStatus.FINAL_REVIEW,
        workspace_path="/tmp/workspace",
        created_at=now,
        updated_at=now,
        project_intelligence=ProjectIntelligence(
            language="python",
            package_manager=PackageManager.UV,
            frameworks=["fastapi"],
            architecture=ApplicationArchitecture.FASTAPI,
            entrypoints=["src/main.py"],
            source_directories=["src"],
            test_directories=["tests"],
        ),
    )


def test_extractor_creates_project_decision_and_success_memories() -> None:
    project_id = str(ObjectId())
    run_id = str(ObjectId())
    now = datetime.now(UTC)
    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    verification_result_id = str(ObjectId())
    approval_id = str(ObjectId())

    patch_plan = PatchPlan(
        patch_plan_id=patch_plan_id,
        run_id=run_id,
        issue_group_id=str(ObjectId()),
        title="Security issue",
        root_cause="Unsafe eval usage",
        affected_files=["src/auth.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/auth.py",
                description="Remove eval",
                change_type=ChangeType.SECURITY_REMEDIATION.value,
            ),
        ],
        expected_tests=["uv run pytest"],
        estimated_risk=RiskLevel.MEDIUM,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Replace eval with safe parser",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    context = MemoryExtractionContext(
        run=_run(project_id, run_id),
        patch_plans=[patch_plan],
        approvals=[
            HumanApproval(
                approval_id=approval_id,
                run_id=run_id,
                patch_plan_id=patch_plan_id,
                trigger=ApprovalTrigger.PEER_REVIEW,
                status=ApprovalStatus.APPROVED,
                reason="Peer review requested changes",
                human_decision=HumanDecision.APPROVE,
                human_feedback="Looks good after review",
                created_at=now,
            ),
        ],
        fix_attempts=[
            FixAttempt(
                fix_attempt_id=fix_attempt_id,
                run_id=run_id,
                patch_plan_id=patch_plan_id,
                attempt_number=1,
                status=FixAttemptStatus.APPLIED,
                planned_files=["src/auth.py"],
                changed_files=["src/auth.py"],
                created_at=now,
            ),
        ],
        verification_results=[
            VerificationResult(
                verification_result_id=verification_result_id,
                run_id=run_id,
                fix_attempt_id=fix_attempt_id,
                patch_plan_id=patch_plan_id,
                status=VerificationStatus.PASSED,
                created_at=now,
            ),
        ],
        regression_results=[],
        peer_reviews=[
            PeerReviewResult(
                peer_review_id=str(ObjectId()),
                run_id=run_id,
                patch_plan_id=patch_plan_id,
                fix_attempt_id=fix_attempt_id,
                verification_result_id=verification_result_id,
                regression_test_id=str(ObjectId()),
                verdict=PeerReviewVerdict.APPROVED,
                synthesis_summary="Approved",
                reviewer_opinions=[],
                created_at=now,
            ),
        ],
        self_correction_cycles=[],
    )

    entries = MemoryExtractor().extract(context)
    memory_types = {entry.memory_type for entry in entries}

    assert MemoryType.PROJECT in memory_types
    assert MemoryType.DECISION in memory_types
    assert MemoryType.SUCCESS_STRATEGY in memory_types
    assert MemoryType.FAILURE not in memory_types
    assert all(entry.project_id == project_id for entry in entries)
    assert all(entry.run_id == run_id for entry in entries)
