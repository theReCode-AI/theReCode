from app.models.verification_enums import VerificationCheckStatus
from app.models.verification_result import VerificationResult


class FailureAnalyzer:
    """Derive a deterministic root-cause summary from failed verification checks."""

    def analyze(self, verification_result: VerificationResult) -> str:
        failed_checks = [
            check
            for check in verification_result.checks
            if check.status in {VerificationCheckStatus.FAILED, VerificationCheckStatus.ERROR}
        ]
        if not failed_checks:
            if verification_result.failure_summary:
                return verification_result.failure_summary
            return "Verification failed without detailed check output"

        summaries: list[str] = []
        for check in failed_checks[:5]:
            detail = check.message or check.status.value
            summaries.append(f"{check.check_type.value}:{check.name} ({detail})")

        return "; ".join(summaries)
