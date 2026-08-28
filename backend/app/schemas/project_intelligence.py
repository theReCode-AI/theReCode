from datetime import datetime

from pydantic import BaseModel

from app.models.project_intelligence import ProjectIntelligence


class ProjectIntelligenceResponse(ProjectIntelligence):
    """API response for project intelligence analysis."""


class ProjectIntelligenceArtifactResponse(BaseModel):
    run_id: str
    artifact_path: str
    analyzed_at: datetime
    intelligence: ProjectIntelligence
