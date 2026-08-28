from app.db.repositories.fix_attempt_repository import FixAttemptRepository
from app.models.fix_attempt import FixAttempt


class InMemoryFixAttemptRepository(FixAttemptRepository):
    def __init__(self) -> None:
        self._fix_attempts: dict[str, list[FixAttempt]] = {}

    def add(self, fix_attempt: FixAttempt) -> FixAttempt:
        self._fix_attempts.setdefault(fix_attempt.run_id, []).append(fix_attempt)
        return fix_attempt

    def list_by_run(self, run_id: str) -> list[FixAttempt]:
        return list(self._fix_attempts.get(run_id, []))

    def count_by_patch_plan(self, run_id: str, patch_plan_id: str) -> int:
        return sum(
            1
            for attempt in self._fix_attempts.get(run_id, [])
            if attempt.patch_plan_id == patch_plan_id
        )

    def get_by_id_for_run(self, fix_attempt_id: str, run_id: str) -> FixAttempt | None:
        for attempt in self._fix_attempts.get(run_id, []):
            if attempt.fix_attempt_id == fix_attempt_id:
                return attempt
        return None
