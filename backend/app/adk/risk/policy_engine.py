"""Deterministic risk policy engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from bson import ObjectId

from app.models.patch_plan import PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, RiskLevel
from app.models.risk_decision import RiskDecision
from app.models.risk_enums import AutonomyDecision

RISK_ORDER = (
    RiskLevel.LOW,
    RiskLevel.MEDIUM,
    RiskLevel.HIGH,
    RiskLevel.CRITICAL,
    RiskLevel.BLOCKED,
)

AUTHENTICATION_MARKERS = ("auth", "login", "oauth", "jwt", "session")
AUTHORIZATION_MARKERS = ("permission", "authorize", "authorization", "rbac", "acl")
DATABASE_MARKERS = ("migration", "alembic", "database", "db/", "sql/")
SECRET_MARKERS = ("secret", "credential", "password", "token", "api_key", "config")
INFRASTRUCTURE_MARKERS = ("docker", "kubernetes", "terraform", "deploy", "production")
BLOCKED_MARKERS = (".env", "credentials", "kubeconfig", "id_rsa")


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    description: str
    minimum_risk: RiskLevel
    requires_approval: bool = False
    blocks_autonomy: bool = False


POLICY_RULES: dict[str, PolicyRule] = {
    "high_estimated_risk": PolicyRule(
        rule_id="high_estimated_risk",
        description="Patch plan estimated risk is high or above.",
        minimum_risk=RiskLevel.HIGH,
        requires_approval=True,
    ),
    "critical_estimated_risk": PolicyRule(
        rule_id="critical_estimated_risk",
        description="Patch plan estimated risk is critical.",
        minimum_risk=RiskLevel.CRITICAL,
        requires_approval=True,
    ),
    "blocked_estimated_risk": PolicyRule(
        rule_id="blocked_estimated_risk",
        description="Patch plan is blocked by policy.",
        minimum_risk=RiskLevel.BLOCKED,
        requires_approval=True,
        blocks_autonomy=True,
    ),
    "secret_handling": PolicyRule(
        rule_id="secret_handling",
        description="Plan modifies secret or credential handling.",
        minimum_risk=RiskLevel.CRITICAL,
        requires_approval=True,
    ),
    "security_remediation": PolicyRule(
        rule_id="security_remediation",
        description="Security remediation with broad impact requires review.",
        minimum_risk=RiskLevel.HIGH,
        requires_approval=True,
    ),
    "authentication_change": PolicyRule(
        rule_id="authentication_change",
        description="Authentication-related files are in scope.",
        minimum_risk=RiskLevel.HIGH,
        requires_approval=True,
    ),
    "authorization_change": PolicyRule(
        rule_id="authorization_change",
        description="Authorization-related files are in scope.",
        minimum_risk=RiskLevel.HIGH,
        requires_approval=True,
    ),
    "database_change": PolicyRule(
        rule_id="database_change",
        description="Database or migration files are in scope.",
        minimum_risk=RiskLevel.HIGH,
        requires_approval=True,
    ),
    "dependency_change": PolicyRule(
        rule_id="dependency_change",
        description="Dependency manifest changes can affect runtime behavior.",
        minimum_risk=RiskLevel.MEDIUM,
    ),
    "repository_wide_scope": PolicyRule(
        rule_id="repository_wide_scope",
        description="Repository-wide scope increases blast radius.",
        minimum_risk=RiskLevel.MEDIUM,
    ),
    "multi_file_scope": PolicyRule(
        rule_id="multi_file_scope",
        description="Multiple files are in scope.",
        minimum_risk=RiskLevel.MEDIUM,
    ),
    "infrastructure_sensitive": PolicyRule(
        rule_id="infrastructure_sensitive",
        description="Infrastructure or deployment files are in scope.",
        minimum_risk=RiskLevel.HIGH,
        requires_approval=True,
    ),
    "blocked_file_pattern": PolicyRule(
        rule_id="blocked_file_pattern",
        description="Plan touches blocked sensitive file patterns.",
        minimum_risk=RiskLevel.BLOCKED,
        requires_approval=True,
        blocks_autonomy=True,
    ),
    "manual_review_required": PolicyRule(
        rule_id="manual_review_required",
        description="Planner marked the issue for manual review.",
        minimum_risk=RiskLevel.MEDIUM,
        requires_approval=True,
    ),
}


class RiskPolicyEngine:
    """Apply deterministic policy rules to patch plans."""

    def assess(self, run_id: str, patch_plans: list[PatchPlan]) -> list[RiskDecision]:
        now = datetime.now(UTC)
        return [self._assess_plan(run_id, patch_plan, now) for patch_plan in patch_plans]

    def _assess_plan(
        self,
        run_id: str,
        patch_plan: PatchPlan,
        created_at: datetime,
    ) -> RiskDecision:
        assessed_risk = patch_plan.estimated_risk
        triggered_rules: list[str] = []

        assessed_risk, triggered_rules = self._apply_estimated_risk_rules(
            patch_plan.estimated_risk,
            triggered_rules,
        )
        assessed_risk, triggered_rules = self._apply_change_type_rules(
            patch_plan,
            assessed_risk,
            triggered_rules,
        )
        assessed_risk, triggered_rules = self._apply_scope_rules(
            patch_plan.expected_scope,
            assessed_risk,
            triggered_rules,
        )
        assessed_risk, triggered_rules = self._apply_file_rules(
            patch_plan.affected_files,
            assessed_risk,
            triggered_rules,
        )

        approval_required = self._requires_approval(assessed_risk, triggered_rules)
        autonomy_decision = self._resolve_autonomy(
            assessed_risk,
            approval_required,
            triggered_rules,
        )
        autonomous_fix_allowed = autonomy_decision == AutonomyDecision.AUTONOMOUS

        return RiskDecision(
            risk_decision_id=str(ObjectId()),
            run_id=run_id,
            patch_plan_id=patch_plan.patch_plan_id,
            estimated_risk=patch_plan.estimated_risk,
            assessed_risk=assessed_risk,
            autonomy_decision=autonomy_decision,
            approval_required=approval_required,
            autonomous_fix_allowed=autonomous_fix_allowed,
            policy_rules=triggered_rules,
            rationale=self._build_rationale(
                patch_plan,
                assessed_risk,
                autonomy_decision,
                triggered_rules,
            ),
            created_at=created_at,
        )

    @staticmethod
    def _apply_estimated_risk_rules(
        estimated_risk: RiskLevel,
        triggered_rules: list[str],
    ) -> tuple[RiskLevel, list[str]]:
        assessed_risk = estimated_risk
        rules = list(triggered_rules)

        if estimated_risk == RiskLevel.BLOCKED:
            rules.append("blocked_estimated_risk")
            return RiskLevel.BLOCKED, rules
        if estimated_risk == RiskLevel.CRITICAL:
            rules.append("critical_estimated_risk")
            return RiskLevel.CRITICAL, rules
        if estimated_risk == RiskLevel.HIGH:
            rules.append("high_estimated_risk")
            return RiskLevel.HIGH, rules

        return assessed_risk, rules

    @staticmethod
    def _apply_change_type_rules(
        patch_plan: PatchPlan,
        assessed_risk: RiskLevel,
        triggered_rules: list[str],
    ) -> tuple[RiskLevel, list[str]]:
        rules = list(triggered_rules)
        risk = assessed_risk
        change_types = {
            modification.change_type for modification in patch_plan.expected_modifications
        }

        if ChangeType.SECRET_REMOVAL.value in change_types:
            rules.append("secret_handling")
            risk = RiskPolicyEngine._max_risk(risk, RiskLevel.CRITICAL)

        if ChangeType.SECURITY_REMEDIATION.value in change_types:
            rules.append("security_remediation")
            risk = RiskPolicyEngine._max_risk(risk, RiskLevel.HIGH)

        if ChangeType.DEPENDENCY_UPDATE.value in change_types:
            rules.append("dependency_change")
            risk = RiskPolicyEngine._max_risk(risk, RiskLevel.MEDIUM)

        if ChangeType.MANUAL_REVIEW.value in change_types:
            rules.append("manual_review_required")
            risk = RiskPolicyEngine._max_risk(risk, RiskLevel.MEDIUM)

        return risk, rules

    @staticmethod
    def _apply_scope_rules(
        scope: FixScope,
        assessed_risk: RiskLevel,
        triggered_rules: list[str],
    ) -> tuple[RiskLevel, list[str]]:
        rules = list(triggered_rules)
        risk = assessed_risk

        if scope == FixScope.REPOSITORY:
            rules.append("repository_wide_scope")
            risk = RiskPolicyEngine._max_risk(risk, RiskLevel.MEDIUM)
        elif scope == FixScope.MULTI_FILE:
            rules.append("multi_file_scope")
            risk = RiskPolicyEngine._max_risk(risk, RiskLevel.MEDIUM)
        elif scope == FixScope.DEPENDENCY:
            rules.append("dependency_change")
            risk = RiskPolicyEngine._max_risk(risk, RiskLevel.MEDIUM)

        return risk, rules

    @staticmethod
    def _apply_file_rules(
        affected_files: list[str],
        assessed_risk: RiskLevel,
        triggered_rules: list[str],
    ) -> tuple[RiskLevel, list[str]]:
        rules = list(triggered_rules)
        risk = assessed_risk

        for file_path in affected_files:
            normalized = file_path.lower()
            if any(marker in normalized for marker in BLOCKED_MARKERS):
                rules.append("blocked_file_pattern")
                risk = RiskLevel.BLOCKED
            if any(marker in normalized for marker in AUTHENTICATION_MARKERS):
                rules.append("authentication_change")
                risk = RiskPolicyEngine._max_risk(risk, RiskLevel.HIGH)
            if any(marker in normalized for marker in AUTHORIZATION_MARKERS):
                rules.append("authorization_change")
                risk = RiskPolicyEngine._max_risk(risk, RiskLevel.HIGH)
            if any(marker in normalized for marker in DATABASE_MARKERS):
                rules.append("database_change")
                risk = RiskPolicyEngine._max_risk(risk, RiskLevel.HIGH)
            if any(marker in normalized for marker in SECRET_MARKERS):
                rules.append("secret_handling")
                risk = RiskPolicyEngine._max_risk(risk, RiskLevel.CRITICAL)
            if any(marker in normalized for marker in INFRASTRUCTURE_MARKERS):
                rules.append("infrastructure_sensitive")
                risk = RiskPolicyEngine._max_risk(risk, RiskLevel.HIGH)

        return risk, list(dict.fromkeys(rules))

    @staticmethod
    def _requires_approval(assessed_risk: RiskLevel, triggered_rules: list[str]) -> bool:
        if assessed_risk in {RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.BLOCKED}:
            return True

        return any(
            POLICY_RULES[rule_id].requires_approval
            for rule_id in triggered_rules
            if rule_id in POLICY_RULES
        )

    @staticmethod
    def _resolve_autonomy(
        assessed_risk: RiskLevel,
        approval_required: bool,
        triggered_rules: list[str],
    ) -> AutonomyDecision:
        if assessed_risk == RiskLevel.BLOCKED:
            return AutonomyDecision.BLOCKED
        if any(
            POLICY_RULES[rule_id].blocks_autonomy
            for rule_id in triggered_rules
            if rule_id in POLICY_RULES
        ):
            return AutonomyDecision.BLOCKED
        if approval_required:
            return AutonomyDecision.REQUIRES_APPROVAL
        return AutonomyDecision.AUTONOMOUS

    @staticmethod
    def _build_rationale(
        patch_plan: PatchPlan,
        assessed_risk: RiskLevel,
        autonomy_decision: AutonomyDecision,
        triggered_rules: list[str],
    ) -> str:
        if autonomy_decision == AutonomyDecision.AUTONOMOUS:
            return (
                f"Patch plan '{patch_plan.title}' is approved for autonomous execution "
                f"at assessed risk '{assessed_risk.value}'."
            )

        rule_descriptions = [
            POLICY_RULES[rule_id].description
            for rule_id in triggered_rules
            if rule_id in POLICY_RULES
        ]
        if rule_descriptions:
            joined_rules = "; ".join(rule_descriptions)
        else:
            joined_rules = "Policy thresholds exceeded."
        return (
            f"Patch plan '{patch_plan.title}' requires human review "
            f"(assessed risk '{assessed_risk.value}', autonomy '{autonomy_decision.value}'). "
            f"Triggered rules: {joined_rules}"
        )

    @staticmethod
    def _max_risk(current: RiskLevel, candidate: RiskLevel) -> RiskLevel:
        return RISK_ORDER[max(RISK_ORDER.index(current), RISK_ORDER.index(candidate))]
