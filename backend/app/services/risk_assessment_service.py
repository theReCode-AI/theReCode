import json
from datetime import UTC, datetime
from pathlib import Path

from app.adk.agents.risk_agent import RiskAgent
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.workflows.stages import OrchestrationStage
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.db.repositories.risk_decision_repository import (
    RiskDecisionNotFoundError,
    RiskDecisionRepository,
)
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.models.agent_event import AgentEventType
from app.models.risk_decision import RiskDecision
from app.models.risk_enums import AutonomyDecision
from app.models.run import RunStatus
from app.schemas.risk_decision import RiskAssessmentResponse, RiskDecisionResponse
from app.services.fix_planner_service import FIX_PLANS_ARTIFACT_NAME
from app.services.run_service import RunService

logger = get_logger(__name__)

RISK_DECISIONS_ARTIFACT_NAME = "risk_decisions.json"


class PatchPlansRequiredError(Exception):
    def __init__(self, message: str = "Patch plans must be created before risk assessment") -> None:
        self.message = message
        super().__init__(message)


class RiskAssessmentService:
    """Assess patch-plan risk and gate autonomous fixes vs human approval."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        fix_plan_repository: FixPlanRepository,
        risk_decision_repository: RiskDecisionRepository,
        event_repository: AgentEventRepository,
        risk_agent: RiskAgent | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._fix_plan_repository = fix_plan_repository
        self._risk_decision_repository = risk_decision_repository
        self._event_repository = event_repository
        self._risk_agent = risk_agent or RiskAgent()

    def assess_run(self, user_id: str, run_id: str) -> RiskAssessmentResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        patch_plans = self._fix_plan_repository.list_by_run(run_id)
        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        plans_artifact = workspace.baseline / FIX_PLANS_ARTIFACT_NAME
        if not patch_plans and not plans_artifact.is_file():
            raise PatchPlansRequiredError()

        started_at = datetime.now(UTC)
        risk_decisions = self._risk_agent.run(run_id, patch_plans)
        persisted_decisions = self._risk_decision_repository.replace_for_run(run_id, risk_decisions)
        self._write_risk_decisions_artifact(workspace.baseline, persisted_decisions)

        next_status = self._resolve_run_status(persisted_decisions)
        self._run_repository.update_status(run_id, user_id, next_status)
        self._emit_risk_events(run_id, persisted_decisions)

        completed_at = datetime.now(UTC)
        response = RiskAssessmentResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            risk_decisions=[
                RiskDecisionResponse.model_validate(decision.model_dump())
                for decision in persisted_decisions
            ],
            decision_count=len(persisted_decisions),
            approval_required_count=sum(
                1 for decision in persisted_decisions if decision.approval_required
            ),
            autonomous_count=sum(
                1
                for decision in persisted_decisions
                if decision.autonomy_decision == AutonomyDecision.AUTONOMOUS
            ),
            blocked_count=sum(
                1
                for decision in persisted_decisions
                if decision.autonomy_decision == AutonomyDecision.BLOCKED
            ),
            run_status=next_status.value,
        )

        logger.info(
            "Risk assessment completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "decision_count": len(persisted_decisions),
                "approval_required_count": response.approval_required_count,
                "run_status": next_status.value,
                "stage": "risk_assessment",
            },
        )
        return response

    def list_risk_decisions(self, user_id: str, run_id: str) -> list[RiskDecisionResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        risk_decisions = self._risk_decision_repository.list_by_run(run_id)
        return [
            RiskDecisionResponse.model_validate(decision.model_dump())
            for decision in risk_decisions
        ]

    def get_risk_decision(
        self,
        user_id: str,
        run_id: str,
        risk_decision_id: str,
    ) -> RiskDecisionResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        risk_decision = self._risk_decision_repository.get_by_id_for_run(risk_decision_id, run_id)
        if risk_decision is None:
            raise RiskDecisionNotFoundError(risk_decision_id)

        return RiskDecisionResponse.model_validate(risk_decision.model_dump())

    @staticmethod
    def _resolve_run_status(risk_decisions: list[RiskDecision]) -> RunStatus:
        if any(
            decision.autonomy_decision == AutonomyDecision.BLOCKED
            for decision in risk_decisions
        ):
            return RunStatus.AWAITING_APPROVAL
        if any(decision.approval_required for decision in risk_decisions):
            return RunStatus.AWAITING_APPROVAL
        return RunStatus.PLANNING

    def _emit_risk_events(self, run_id: str, risk_decisions: list[RiskDecision]) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        for risk_decision in risk_decisions:
            emitter.yield_event(
                WorkflowEvent(
                    event_type=AgentEventType.RISK_ASSESSED,
                    stage=OrchestrationStage.RISK_ASSESSMENT,
                    agent="risk_agent",
                    payload={
                        "risk_decision_id": risk_decision.risk_decision_id,
                        "patch_plan_id": risk_decision.patch_plan_id,
                        "assessed_risk": risk_decision.assessed_risk.value,
                        "autonomy_decision": risk_decision.autonomy_decision.value,
                        "approval_required": risk_decision.approval_required,
                    },
                ),
            )
            if risk_decision.approval_required:
                emitter.yield_event(
                    WorkflowEvent(
                        event_type=AgentEventType.APPROVAL_REQUIRED,
                        stage=OrchestrationStage.RISK_ASSESSMENT,
                        agent="risk_agent",
                        payload={
                            "risk_decision_id": risk_decision.risk_decision_id,
                            "patch_plan_id": risk_decision.patch_plan_id,
                            "assessed_risk": risk_decision.assessed_risk.value,
                        },
                    ),
                )

    @staticmethod
    def _write_risk_decisions_artifact(
        baseline_dir: Path,
        risk_decisions: list[RiskDecision],
    ) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / RISK_DECISIONS_ARTIFACT_NAME
        payload = [decision.model_dump(mode="json") for decision in risk_decisions]
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path
