from app.db.repositories.self_correction_cycle_repository import SelfCorrectionCycleRepository
from app.models.self_correction_cycle import SelfCorrectionCycle


class InMemorySelfCorrectionCycleRepository(SelfCorrectionCycleRepository):
    def __init__(self) -> None:
        self._cycles: dict[str, list[SelfCorrectionCycle]] = {}

    def add(self, cycle: SelfCorrectionCycle) -> SelfCorrectionCycle:
        self._cycles.setdefault(cycle.run_id, []).append(cycle)
        return cycle

    def list_by_run(self, run_id: str) -> list[SelfCorrectionCycle]:
        return list(self._cycles.get(run_id, []))

    def get_by_id_for_run(
        self,
        self_correction_cycle_id: str,
        run_id: str,
    ) -> SelfCorrectionCycle | None:
        for cycle in self._cycles.get(run_id, []):
            if cycle.self_correction_cycle_id == self_correction_cycle_id:
                return cycle
        return None
