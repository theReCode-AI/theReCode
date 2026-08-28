from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.models.patch_plan import PatchPlan


class InMemoryFixPlanRepository(FixPlanRepository):
    def __init__(self) -> None:
        self._patch_plans: dict[str, list[PatchPlan]] = {}

    def replace_for_run(self, run_id: str, patch_plans: list[PatchPlan]) -> list[PatchPlan]:
        self._patch_plans[run_id] = list(patch_plans)
        return list(patch_plans)

    def list_by_run(self, run_id: str) -> list[PatchPlan]:
        return list(self._patch_plans.get(run_id, []))

    def get_by_id_for_run(self, patch_plan_id: str, run_id: str) -> PatchPlan | None:
        for patch_plan in self._patch_plans.get(run_id, []):
            if patch_plan.patch_plan_id == patch_plan_id:
                return patch_plan
        return None
