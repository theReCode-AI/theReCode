import json
from datetime import UTC, datetime
from pathlib import Path

from app.scanners.runner import CallableCommandRunner, ProcessResult


def build_mock_command_runner() -> CallableCommandRunner:
    def handler(command: list[str], cwd: str, timeout_seconds: int) -> ProcessResult:
        del timeout_seconds
        now = datetime.now(UTC)
        executable = command[0]

        if command[-1] == "--version":
            return ProcessResult(
                command=command,
                cwd=cwd,
                exit_code=0,
                stdout=f"{executable} 1.0.0",
                stderr="",
                started_at=now,
                ended_at=now,
            )

        if executable == "ruff":
            stdout = "[]"
            exit_code = 0
        elif executable == "semgrep":
            stdout = json.dumps({"results": []})
            exit_code = 0
        elif executable == "bandit":
            stdout = json.dumps({"results": [], "metrics": {}})
            exit_code = 0
        elif executable == "osv-scanner":
            stdout = json.dumps({"results": []})
            exit_code = 0
        elif executable == "gitleaks":
            report_flag_index = command.index("--report-path")
            report_path = Path(command[report_flag_index + 1])
            report_path.write_text("[]", encoding="utf-8")
            stdout = ""
            exit_code = 0
        elif executable == "pytest":
            junit_flag = next(arg for arg in command if arg.startswith("--junitxml="))
            junit_path = Path(junit_flag.split("=", 1)[1])
            junit_path.write_text(
                '<testsuite tests="1" failures="0" errors="0" skipped="0"></testsuite>',
                encoding="utf-8",
            )
            stdout = "1 passed"
            exit_code = 0
        elif executable == "bash":
            json_flag = command[-1]
            if "coverage json" in json_flag:
                output_path = json_flag.rsplit(" ", 1)[-1]
                Path(output_path).write_text(
                    json.dumps({"totals": {"percent_covered": 90.0}, "files": {}}),
                    encoding="utf-8",
                )
            stdout = ""
            exit_code = 0
        else:
            stdout = ""
            exit_code = 0

        return ProcessResult(
            command=command,
            cwd=cwd,
            exit_code=exit_code,
            stdout=stdout,
            stderr="",
            started_at=now,
            ended_at=now,
        )

    return CallableCommandRunner(handler)


def build_fix_command_runner(extra_file: str | None = None) -> CallableCommandRunner:
    def handler(command: list[str], cwd: str, timeout_seconds: int) -> ProcessResult:
        del timeout_seconds
        now = datetime.now(UTC)
        if command[0] == "ruff":
            file_path = Path(cwd) / command[-1]
            if file_path.is_file():
                content = file_path.read_text(encoding="utf-8")
                file_path.write_text(content.replace("unused_var", "fixed_var"), encoding="utf-8")
            if extra_file is not None:
                extra_path = Path(cwd) / extra_file
                extra_path.parent.mkdir(parents=True, exist_ok=True)
                extra_path.write_text("unexpected change\n", encoding="utf-8")
        return ProcessResult(
            command=command,
            cwd=cwd,
            exit_code=0,
            stdout="",
            stderr="",
            started_at=now,
            ended_at=now,
        )

    return CallableCommandRunner(handler)
