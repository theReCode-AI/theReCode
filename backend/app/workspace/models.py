from dataclasses import dataclass
from pathlib import Path

from app.workspace import constants


@dataclass(frozen=True)
class RunWorkspace:
    """Resolved filesystem layout for a single autonomous run."""

    run_id: str
    root: Path

    @property
    def repository(self) -> Path:
        return self.root / constants.REPOSITORY

    @property
    def baseline(self) -> Path:
        return self.root / constants.BASELINE

    @property
    def working(self) -> Path:
        return self.root / constants.WORKING

    @property
    def artifacts(self) -> Path:
        return self.root / constants.ARTIFACTS

    @property
    def patches(self) -> Path:
        return self.root / constants.PATCHES

    @property
    def logs(self) -> Path:
        return self.root / constants.LOGS

    @property
    def reports(self) -> Path:
        return self.root / constants.REPORTS

    def all_directories(self) -> tuple[Path, ...]:
        return tuple(self.root / name for name in constants.RUN_DIRECTORIES)

    def to_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "root": str(self.root),
            "repository": str(self.repository),
            "baseline": str(self.baseline),
            "working": str(self.working),
            "artifacts": str(self.artifacts),
            "patches": str(self.patches),
            "logs": str(self.logs),
            "reports": str(self.reports),
        }
