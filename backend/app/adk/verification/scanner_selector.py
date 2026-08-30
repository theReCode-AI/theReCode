from app.models.patch_plan import PatchPlan
from app.models.patch_plan_enums import ChangeType
from app.models.scan import ScannerTool

CHANGE_TYPE_SCANNERS: dict[str, tuple[ScannerTool, ...]] = {
    ChangeType.LINT_FIX.value: (ScannerTool.RUFF,),
    ChangeType.FORMAT_FIX.value: (ScannerTool.RUFF,),
    ChangeType.SECURITY_REMEDIATION.value: (ScannerTool.SEMGREP, ScannerTool.BANDIT),
    ChangeType.SECRET_REMOVAL.value: (ScannerTool.GITLEAKS,),
    ChangeType.DEPENDENCY_UPDATE.value: (ScannerTool.OSV_SCANNER,),
    ChangeType.TEST_FIX.value: (ScannerTool.PYTEST,),
    ChangeType.TEST_ADDITION.value: (ScannerTool.PYTEST,),
    ChangeType.COVERAGE_IMPROVEMENT.value: (ScannerTool.PYTEST, ScannerTool.COVERAGE),
    ChangeType.MANUAL_REVIEW.value: (ScannerTool.PYTEST,),
}

DEFAULT_SCANNERS = (ScannerTool.PYTEST,)


def select_scanners_for_plan(patch_plan: PatchPlan) -> list[ScannerTool]:
    selected: list[ScannerTool] = []
    seen: set[ScannerTool] = set()

    for modification in patch_plan.expected_modifications:
        for tool in CHANGE_TYPE_SCANNERS.get(modification.change_type, DEFAULT_SCANNERS):
            if tool not in seen:
                seen.add(tool)
                selected.append(tool)

    if not selected:
        return list(DEFAULT_SCANNERS)

    return selected
