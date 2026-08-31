import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.adk.fixing.llm_rewriter import GeminiCodeRewriter, _parse_rewrites
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel


def test_parse_rewrites_accepts_fenced_json() -> None:
    payload = {
        "files": [
            {"path": "src/a.py", "content": "print(1)\n"},
            {"path": "src/b.py", "content": "print(2)\n"},
        ],
    }
    text = f"```json\n{json.dumps(payload)}\n```"
    rewrites = _parse_rewrites(text, allowed_paths={"src/a.py", "src/b.py"})
    assert [item.path for item in rewrites] == ["src/a.py", "src/b.py"]


def test_gemini_rewriter_writes_changed_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "src" / "auth.py"
    target.parent.mkdir(parents=True)
    target.write_text("TOKEN = 'secret'\n", encoding="utf-8")

    now = datetime.now(UTC)
    plan = PatchPlan(
        patch_plan_id=str(ObjectId()),
        run_id=str(ObjectId()),
        issue_group_id=str(ObjectId()),
        title="Remove secret",
        root_cause="Hardcoded token",
        affected_files=["src/auth.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/auth.py",
                description="Load token from env",
                change_type=ChangeType.SECURITY_REMEDIATION.value,
            ),
        ],
        expected_tests=[],
        estimated_risk=RiskLevel.HIGH,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Use environment variables",
        rollback_strategy="Revert",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )

    class FakeResponse:
        text = json.dumps(
            {
                "files": [
                    {
                        "path": "src/auth.py",
                        "content": "import os\nTOKEN = os.environ['TOKEN']\n",
                    },
                ],
            },
        )

    class FakeModels:
        def generate_content(self, **_kwargs):
            return FakeResponse()

    class FakeClient:
        def __init__(self, **_kwargs):
            self.models = FakeModels()

    monkeypatch.setattr("app.adk.fixing.llm_rewriter.genai.Client", FakeClient)
    monkeypatch.setattr(
        "app.adk.fixing.llm_rewriter.bootstrap_google_genai",
        lambda _s, api_key=None: None,
    )
    monkeypatch.setattr(
        "app.adk.fixing.llm_rewriter.ensure_google_adk_configured",
        lambda _s, api_key=None: None,
    )

    from app.core.config import Settings

    rewriter = GeminiCodeRewriter(Settings(environment="test", google_api_key="test-key"))
    changed = rewriter.rewrite_files(plan, tmp_path)

    assert changed == ["src/auth.py"]
    assert "os.environ" in target.read_text(encoding="utf-8")
