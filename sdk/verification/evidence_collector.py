"""
Evidence Collector
==================

Collects and manages evidence for task completion verification.

Evidence types:
- Command output (test results, build logs)
- File content (generated code, configs)
- Test results (pytest output, coverage)
- Screenshots (UI verification)
- API responses (curl, httpie output)
"""

import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel


console = Console()


class EvidenceType(str, Enum):
    """Types of evidence."""
    COMMAND_OUTPUT = "command_output"
    FILE_CONTENT = "file_content"
    TEST_RESULT = "test_result"
    TYPE_CHECK = "type_check"
    LINT_RESULT = "lint_result"
    API_RESPONSE = "api_response"
    SCREENSHOT = "screenshot"
    LOG_ENTRY = "log_entry"
    MANUAL_VERIFICATION = "manual_verification"


class EvidenceStatus(str, Enum):
    """Status of evidence."""
    PENDING = "pending"
    COLLECTED = "collected"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class Evidence:
    """A piece of evidence for task completion."""
    id: str
    evidence_type: EvidenceType
    description: str
    status: EvidenceStatus = EvidenceStatus.PENDING
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    collected_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    command: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: float = 0.0

    def is_passing(self) -> bool:
        """Check if evidence indicates success."""
        if self.status == EvidenceStatus.FAILED:
            return False
        if self.exit_code is not None and self.exit_code != 0:
            return False
        return self.status in (EvidenceStatus.COLLECTED, EvidenceStatus.VERIFIED)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.evidence_type.value,
            "description": self.description,
            "status": self.status.value,
            "content": self.content[:1000] if self.content else "",
            "metadata": self.metadata,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "command": self.command,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
        }


@dataclass
class Task:
    """A task requiring evidence."""
    id: str
    description: str
    required_evidence: List[EvidenceType]
    evidence: List[Evidence] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def is_complete(self) -> bool:
        """Check if all required evidence is collected and passing."""
        collected_types = {
            e.evidence_type for e in self.evidence 
            if e.is_passing()
        }
        return all(req in collected_types for req in self.required_evidence)

    def missing_evidence(self) -> List[EvidenceType]:
        """Get list of missing evidence types."""
        collected_types = {
            e.evidence_type for e in self.evidence 
            if e.is_passing()
        }
        return [req for req in self.required_evidence if req not in collected_types]


class EvidenceCollector:
    """
    Collects and manages evidence for task completion.
    
    Usage:
        collector = EvidenceCollector()
        task = collector.create_task("implement-login", "Implement user login")
        
        # Run tests and collect evidence
        evidence = collector.run_command("pytest tests/test_login.py -v")
        collector.add_evidence(task.id, evidence)
        
        # Check completion
        if task.is_complete():
            print("Task verified!")
    """

    def __init__(self, evidence_dir: Optional[Path] = None):
        self.evidence_dir = evidence_dir or Path(".3sr/evidence")
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: Dict[str, Task] = {}
        self._current_task: Optional[str] = None

    def create_task(
        self,
        task_id: str,
        description: str,
        required_evidence: Optional[List[EvidenceType]] = None,
    ) -> Task:
        """Create a new task requiring evidence."""
        if required_evidence is None:
            required_evidence = [EvidenceType.TEST_RESULT]

        task = Task(
            id=task_id,
            description=description,
            required_evidence=required_evidence,
        )
        self._tasks[task_id] = task
        self._current_task = task_id
        
        console.print(f"[green]📋 Task created:[/green] {description}")
        console.print(f"   Required evidence: {', '.join(e.value for e in required_evidence)}")
        
        return task

    def get_task(self, task_id: Optional[str] = None) -> Optional[Task]:
        """Get task by ID or current task."""
        task_id = task_id or self._current_task
        return self._tasks.get(task_id) if task_id else None

    def run_command(
        self,
        command: str,
        evidence_type: EvidenceType = EvidenceType.COMMAND_OUTPUT,
        description: Optional[str] = None,
        timeout: int = 300,
    ) -> Evidence:
        """Run a command and capture output as evidence."""
        evidence_id = f"ev_{int(time.time() * 1000)}"
        description = description or f"Command: {command[:50]}"

        console.print(f"[dim]Running: {command}[/dim]")
        start = time.time()

        try:
            # Note: shell=True is intentional here - we need to run user-provided
            # commands that may contain shell features (pipes, redirects, etc.)
            # This is safe because this tool runs in a controlled development context
            result = subprocess.run(
                command,
                shell=True,  # noqa: S602 - intentional for dev tooling
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            duration = (time.time() - start) * 1000
            content = result.stdout + result.stderr
            
            evidence = Evidence(
                id=evidence_id,
                evidence_type=evidence_type,
                description=description,
                status=EvidenceStatus.COLLECTED if result.returncode == 0 else EvidenceStatus.FAILED,
                content=content,
                command=command,
                exit_code=result.returncode,
                duration_ms=duration,
                collected_at=datetime.now(),
            )

            if result.returncode == 0:
                console.print(f"[green]✓[/green] {description} ({duration:.0f}ms)")
            else:
                console.print(f"[red]✗[/red] {description} (exit code: {result.returncode})")

            return evidence

        except subprocess.TimeoutExpired:
            return Evidence(
                id=evidence_id,
                evidence_type=evidence_type,
                description=description,
                status=EvidenceStatus.FAILED,
                content=f"Command timed out after {timeout}s",
                command=command,
                collected_at=datetime.now(),
            )

        except Exception as e:
            return Evidence(
                id=evidence_id,
                evidence_type=evidence_type,
                description=description,
                status=EvidenceStatus.FAILED,
                content=str(e),
                command=command,
                collected_at=datetime.now(),
            )

    def run_tests(
        self,
        test_path: str = "tests/",
        pytest_args: str = "-v --tb=short",
    ) -> Evidence:
        """Run pytest and collect evidence."""
        command = f"pytest {test_path} {pytest_args}"
        return self.run_command(
            command,
            evidence_type=EvidenceType.TEST_RESULT,
            description=f"Test: {test_path}",
        )

    def run_type_check(self, path: str = ".") -> Evidence:
        """Run mypy type checking."""
        command = f"mypy {path}"
        return self.run_command(
            command,
            evidence_type=EvidenceType.TYPE_CHECK,
            description=f"Type check: {path}",
        )

    def run_lint(self, path: str = ".") -> Evidence:
        """Run ruff linting."""
        command = f"ruff check {path}"
        return self.run_command(
            command,
            evidence_type=EvidenceType.LINT_RESULT,
            description=f"Lint: {path}",
        )

    def capture_file(
        self,
        file_path: Path,
        description: Optional[str] = None,
    ) -> Evidence:
        """Capture file content as evidence."""
        evidence_id = f"ev_{int(time.time() * 1000)}"
        description = description or f"File: {file_path}"

        try:
            content = file_path.read_text()
            return Evidence(
                id=evidence_id,
                evidence_type=EvidenceType.FILE_CONTENT,
                description=description,
                status=EvidenceStatus.COLLECTED,
                content=content,
                metadata={"file_path": str(file_path)},
                collected_at=datetime.now(),
            )
        except Exception as e:
            return Evidence(
                id=evidence_id,
                evidence_type=EvidenceType.FILE_CONTENT,
                description=description,
                status=EvidenceStatus.FAILED,
                content=str(e),
                collected_at=datetime.now(),
            )

    def add_manual_evidence(
        self,
        description: str,
        content: str,
        passed: bool = True,
    ) -> Evidence:
        """Add manual verification evidence."""
        evidence_id = f"ev_{int(time.time() * 1000)}"
        return Evidence(
            id=evidence_id,
            evidence_type=EvidenceType.MANUAL_VERIFICATION,
            description=description,
            status=EvidenceStatus.VERIFIED if passed else EvidenceStatus.FAILED,
            content=content,
            collected_at=datetime.now(),
            verified_at=datetime.now() if passed else None,
        )

    def add_evidence(
        self,
        evidence: Evidence,
        task_id: Optional[str] = None,
    ) -> bool:
        """Add evidence to a task."""
        task = self.get_task(task_id)
        if not task:
            console.print("[yellow]Warning: No task found, evidence not attached[/yellow]")
            return False

        task.evidence.append(evidence)
        self._save_evidence(evidence)
        return True

    def _save_evidence(self, evidence: Evidence) -> None:
        """Save evidence to file."""
        evidence_file = self.evidence_dir / f"{evidence.id}.json"
        evidence_file.write_text(json.dumps(evidence.to_dict(), indent=2))

    def verify_task(self, task_id: Optional[str] = None) -> bool:
        """Verify task completion."""
        task = self.get_task(task_id)
        if not task:
            return False

        if task.is_complete():
            task.completed_at = datetime.now()
            console.print(f"\n[green]✅ Task verified: {task.description}[/green]")
            return True
        else:
            missing = task.missing_evidence()
            console.print(f"\n[red]❌ Task incomplete: {task.description}[/red]")
            console.print(f"   Missing evidence: {', '.join(e.value for e in missing)}")
            return False

    def format_report(self, task_id: Optional[str] = None) -> str:
        """Generate evidence report."""
        task = self.get_task(task_id)
        if not task:
            return "No task found"

        lines = [
            "",
            "═" * 50,
            f"  EVIDENCE REPORT: {task.description}",
            "═" * 50,
            "",
            f"Task ID: {task.id}",
            f"Created: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Status: {'Complete ✅' if task.is_complete() else 'Incomplete ❌'}",
            "",
            "Evidence:",
        ]

        for ev in task.evidence:
            status_icon = "✅" if ev.is_passing() else "❌"
            lines.append(f"  {status_icon} [{ev.evidence_type.value}] {ev.description}")
            if ev.exit_code is not None:
                lines.append(f"     Exit code: {ev.exit_code}")
            if ev.duration_ms:
                lines.append(f"     Duration: {ev.duration_ms:.0f}ms")

        missing = task.missing_evidence()
        if missing:
            lines.append("")
            lines.append("Missing:")
            for m in missing:
                lines.append(f"  ⚠️  {m.value}")

        lines.append("")
        lines.append("═" * 50)

        return "\n".join(lines)


# Global collector instance
_collector: Optional[EvidenceCollector] = None


def get_collector() -> EvidenceCollector:
    """Get or create global evidence collector."""
    global _collector
    if _collector is None:
        _collector = EvidenceCollector()
    return _collector
