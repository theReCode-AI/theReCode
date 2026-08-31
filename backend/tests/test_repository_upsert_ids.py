from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from bson import ObjectId

from app.db.repositories.agent_state_repository import AgentStateRepository
from app.db.repositories.report_repository import ReportRepository
from app.models.agent_state import OrchestrationStatus, RunAgentState
from app.models.report_enums import ReportStatus
from app.models.run_report import RunReport


@pytest.fixture
def run_id() -> str:
    return str(ObjectId())


def test_agent_state_upsert_preserves_existing_id(run_id: str) -> None:
    existing_id = ObjectId()
    collection = MagicMock()
    collection.find_one.return_value = {
        "_id": existing_id,
        "run_id": ObjectId(run_id),
        "status": OrchestrationStatus.RUNNING.value,
        "progress": 50,
        "updated_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }

    repository = AgentStateRepository(MagicMock())
    repository._database = {AgentStateRepository.collection_name: collection}

    state = RunAgentState(
        _id=str(ObjectId()),
        run_id=run_id,
        status=OrchestrationStatus.PENDING,
        progress=0,
        updated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    persisted = repository.upsert(state)

    assert persisted.id == str(existing_id)
    replacement = collection.replace_one.call_args.args[1]
    assert replacement["_id"] == existing_id


def test_report_upsert_preserves_existing_id(run_id: str) -> None:
    existing_id = ObjectId()
    project_id = str(ObjectId())
    collection = MagicMock()
    collection.find_one.return_value = {
        "_id": existing_id,
        "run_id": ObjectId(run_id),
        "project_id": ObjectId(project_id),
        "status": ReportStatus.GENERATED.value,
        "markdown_path": "reports/run_report.md",
        "pdf_path": "reports/run_report.pdf",
        "final_health_score": 80.0,
        "created_at": datetime.now(UTC),
    }

    repository = ReportRepository(MagicMock())
    repository._database = {ReportRepository.collection_name: collection}

    report = RunReport(
        report_id=str(ObjectId()),
        run_id=run_id,
        project_id=project_id,
        status=ReportStatus.GENERATED,
        markdown_path="reports/run_report.md",
        pdf_path="reports/run_report.pdf",
        final_health_score=88.0,
        created_at=datetime.now(UTC),
    )
    persisted = repository.upsert_for_run(report)

    assert persisted.report_id == str(existing_id)
    replacement = collection.replace_one.call_args.args[1]
    assert replacement["_id"] == existing_id
