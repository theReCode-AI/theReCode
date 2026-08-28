"""Generate markdown and PDF reports for autonomous runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.adk.reporting.markdown_builder import (
    GeneratedReportContent,
    MarkdownReportBuilder,
    ReportGenerationContext,
)
from app.adk.reporting.pdf_writer import write_text_pdf


@dataclass(frozen=True)
class ReportArtifactPaths:
    markdown_path: Path
    pdf_path: Path


class ReportGenerationEngine:
    """Build report artifacts from a populated generation context."""

    def __init__(self, markdown_builder: MarkdownReportBuilder | None = None) -> None:
        self._markdown_builder = markdown_builder or MarkdownReportBuilder()

    def generate(
        self,
        context: ReportGenerationContext,
        output_dir: Path,
    ) -> tuple[GeneratedReportContent, ReportArtifactPaths]:
        content = self._markdown_builder.build(context)
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "run_report.md"
        pdf_path = output_dir / "run_report.pdf"
        markdown_path.write_text(content.markdown, encoding="utf-8")
        write_text_pdf(pdf_path, "CodeThera Run Report", content.plain_text_lines)
        return content, ReportArtifactPaths(markdown_path=markdown_path, pdf_path=pdf_path)
