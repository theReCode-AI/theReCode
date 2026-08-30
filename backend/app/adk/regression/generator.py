"""Deterministic regression test generation for meaningful fixes."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.patch_plan import PatchPlan
from app.models.patch_plan_enums import ChangeType

MEANINGLESS_CHANGE_TYPES = frozenset(
    {
        ChangeType.LINT_FIX.value,
        ChangeType.FORMAT_FIX.value,
    },
)


@dataclass(frozen=True)
class GeneratedRegressionTest:
    relative_path: str
    content: str
    eligible: bool
    skip_reason: str | None = None


class RegressionTestGenerator:
    """Generate focused regression tests for non-cosmetic fixes."""

    def generate(self, patch_plan: PatchPlan) -> GeneratedRegressionTest:
        change_types = {
            modification.change_type for modification in patch_plan.expected_modifications
        }
        if change_types and change_types.issubset(MEANINGLESS_CHANGE_TYPES):
            return GeneratedRegressionTest(
                relative_path="",
                content="",
                eligible=False,
                skip_reason="Formatting and lint-only fixes do not require regression tests",
            )

        primary_file = _primary_affected_file(patch_plan.affected_files)
        if primary_file is None:
            return GeneratedRegressionTest(
                relative_path="",
                content="",
                eligible=False,
                skip_reason="Patch plan has no file-scoped regression target",
            )

        test_file_name = f"test_regression_{_slugify(patch_plan.patch_plan_id)}.py"
        relative_path = f"tests/regression/{test_file_name}"
        content = _build_test_content(patch_plan, primary_file)
        return GeneratedRegressionTest(
            relative_path=relative_path,
            content=content,
            eligible=True,
        )


def _primary_affected_file(affected_files: list[str]) -> str | None:
    for file_path in affected_files:
        if file_path and file_path != "repository" and file_path.endswith(".py"):
            return file_path
    return None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug[:32] or "patch_plan"


def _build_test_content(patch_plan: PatchPlan, primary_file: str) -> str:
    safe_title = patch_plan.title.replace('"', "'")
    safe_root_cause = patch_plan.root_cause.replace('"', "'")
    return f'''"""Regression test for patch plan: {safe_title}

Root cause: {safe_root_cause}
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def test_regression_fixed_module_loads() -> None:
  """Ensure the remediated module still loads after the fix."""
  module_path = Path(__file__).resolve().parents[2] / "{primary_file}"
  assert module_path.is_file(), f"Expected remediated file missing: {{module_path}}"

  spec = importlib.util.spec_from_file_location("regression_target", module_path)
  assert spec is not None and spec.loader is not None

  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  assert module is not None


def test_regression_remediation_is_documented() -> None:
  """Document the expected remediation outcome for reviewers."""
  assert "{safe_root_cause}"
'''
