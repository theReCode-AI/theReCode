from app.models.scan import ScannerTool
from app.scanners.base import (
    BanditScanner,
    BaseScanner,
    CoverageScanner,
    GitleaksScanner,
    OsvScanner,
    PytestScanner,
    RuffScanner,
    SemgrepScanner,
)

DEFAULT_SCANNERS: tuple[BaseScanner, ...] = (
    RuffScanner(),
    SemgrepScanner(),
    BanditScanner(),
    OsvScanner(),
    GitleaksScanner(),
    PytestScanner(),
    CoverageScanner(),
)

SCANNER_BY_TOOL: dict[ScannerTool, BaseScanner] = {
    scanner.tool: scanner for scanner in DEFAULT_SCANNERS
}


def get_scanners(selected_tools: list[ScannerTool] | None = None) -> list[BaseScanner]:
    if selected_tools is None:
        return list(DEFAULT_SCANNERS)
    return [SCANNER_BY_TOOL[tool] for tool in selected_tools]
