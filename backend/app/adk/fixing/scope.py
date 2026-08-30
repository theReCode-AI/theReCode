from dataclasses import dataclass


@dataclass(frozen=True)
class ScopeValidationResult:
    valid: bool
    planned_files: list[str]
    changed_files: list[str]
    unexpected_files: list[str]


class ScopeValidator:
    """Validate that only planned files were modified."""

    def validate(
        self,
        planned_files: list[str],
        changed_files: list[str],
    ) -> ScopeValidationResult:
        planned = {
            file_path
            for file_path in planned_files
            if file_path and file_path != "repository"
        }
        changed = set(changed_files)
        unexpected = sorted(changed - planned)

        return ScopeValidationResult(
            valid=len(unexpected) == 0,
            planned_files=sorted(planned),
            changed_files=sorted(changed),
            unexpected_files=unexpected,
        )
