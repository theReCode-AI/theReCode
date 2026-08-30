
from pydantic import BaseModel, Field

from app.models.scan import BaselineDiagnosticsSummary, ScannerTool


class BaselineDiagnosticsResponse(BaselineDiagnosticsSummary):
    """API response for baseline diagnostics."""


class RunScannerRequest(BaseModel):
    tools: list[ScannerTool] | None = Field(
        default=None,
        description="Optional subset of scanners to run. Defaults to all scanners.",
    )
