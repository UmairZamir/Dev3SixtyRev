"""
Evidence Guard
==============

Enforces evidence-based task completion.

From research: "No task is done without proof"
- Tests pass (show output)
- Code compiles/type-checks
- Behavior verified

This guard blocks completion without evidence.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from sdk.guards.base import (
    Guard,
    GuardCategory,
    GuardLevel,
    GuardResult,
    GuardSeverity,
    GuardViolation,
)


class EvidenceType(str, Enum):
    """Types of evidence."""
    TEST_OUTPUT = "test_output"
    TYPE_CHECK = "type_check"
    LINT_CHECK = "lint_check"
    MANUAL_VERIFICATION = "manual_verification"
    SCREENSHOT = "screenshot"
    API_RESPONSE = "api_response"
    LOG_OUTPUT = "log_output"


@dataclass
class Evidence:
    """A piece of evidence for task completion."""
    evidence_type: EvidenceType
    description: str
    content: str = ""
    passed: bool = False
    collected_at: datetime = field(default_factory=datetime.now)
    command: Optional[str] = None
    file_path: Optional[str] = None


@dataclass
class TaskEvidence:
    """Evidence collection for a task."""
    task_id: str
    task_description: str
    required_evidence: List[EvidenceType]
    collected_evidence: List[Evidence] = field(default_factory=list)
    verified: bool = False
    verified_at: Optional[datetime] = None

    def is_complete(self) -> bool:
        """Check if all required evidence is collected and passing."""
        if not self.collected_evidence:
            return False
        
        collected_types = {e.evidence_type for e in self.collected_evidence if e.passed}
        return all(req in collected_types for req in self.required_evidence)

    def missing_evidence(self) -> List[EvidenceType]:
        """Get list of missing evidence types."""
        collected_types = {e.evidence_type for e in self.collected_evidence if e.passed}
        return [req for req in self.required_evidence if req not in collected_types]


class EvidenceRequiredGuard(Guard):
    """Enforces evidence-based task completion."""

    def __init__(self, enabled: bool = True):
        super().__init__(
            name="evidence_required",
            description="Enforces evidence collection before task completion",
            level=GuardLevel.PHASE,
            category=GuardCategory.EVIDENCE,
            enabled=enabled,
            severity=GuardSeverity.ERROR,
        )
        self._tasks: Dict[str, TaskEvidence] = {}
        self._current_task: Optional[str] = None

    def start_task(
        self,
        task_id: str,
        description: str,
        required_evidence: Optional[List[EvidenceType]] = None,
    ) -> TaskEvidence:
        """Start tracking evidence for a new task."""
        if required_evidence is None:
            required_evidence = [EvidenceType.TEST_OUTPUT]

        task = TaskEvidence(
            task_id=task_id,
            task_description=description,
            required_evidence=required_evidence,
        )
        self._tasks[task_id] = task
        self._current_task = task_id
        return task

    def add_evidence(
        self,
        evidence_type: EvidenceType,
        description: str,
        content: str = "",
        passed: bool = True,
        task_id: Optional[str] = None,
    ) -> None:
        """Add evidence for current or specified task."""
        task_id = task_id or self._current_task
        if not task_id or task_id not in self._tasks:
            return

        evidence = Evidence(
            evidence_type=evidence_type,
            description=description,
            content=content,
            passed=passed,
        )
        self._tasks[task_id].collected_evidence.append(evidence)

    def verify_task(self, task_id: Optional[str] = None) -> bool:
        """Mark task as verified if all evidence is present."""
        task_id = task_id or self._current_task
        if not task_id or task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        if task.is_complete():
            task.verified = True
            task.verified_at = datetime.now()
            return True
        return False

    def get_task(self, task_id: str) -> Optional[TaskEvidence]:
        """Get task evidence by ID."""
        return self._tasks.get(task_id)

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check if all tasks have required evidence."""
        start = time.time()
        violations: List[GuardViolation] = []

        for task_id, task in self._tasks.items():
            if not task.verified:
                missing = task.missing_evidence()
                if missing:
                    violations.append(
                        GuardViolation(
                            guard_name=self.name,
                            severity=GuardSeverity.ERROR,
                            category=self.category,
                            message=f"Task '{task.task_description}' missing evidence",
                            suggestion=f"Required evidence: {', '.join(e.value for e in missing)}",
                            evidence_required=True,
                        )
                    )

        return GuardResult(
            guard_name=self.name,
            passed=len(violations) == 0,
            violations=violations,
            execution_time_ms=(time.time() - start) * 1000,
        )

    def clear_tasks(self) -> None:
        """Clear all task evidence."""
        self._tasks.clear()
        self._current_task = None

    def format_evidence_report(self) -> str:
        """Generate evidence report."""
        lines = [
            "",
            "═══════════════════════════════════════",
            "          EVIDENCE REPORT",
            "═══════════════════════════════════════",
            "",
        ]

        for task_id, task in self._tasks.items():
            status = "✅" if task.verified else "❌"
            lines.append(f"{status} Task: {task.task_description}")

            for evidence in task.collected_evidence:
                ev_status = "✓" if evidence.passed else "✗"
                lines.append(f"   [{ev_status}] {evidence.evidence_type.value}: {evidence.description}")

            if not task.verified:
                missing = task.missing_evidence()
                if missing:
                    lines.append(f"   ⚠️  Missing: {', '.join(e.value for e in missing)}")

            lines.append("")

        verified = sum(1 for t in self._tasks.values() if t.verified)
        total = len(self._tasks)
        lines.append(f"Summary: {verified}/{total} tasks verified")
        lines.append("═══════════════════════════════════════")

        return "\n".join(lines)


def create_evidence_guards() -> List[Guard]:
    """Create evidence-related guards."""
    return [EvidenceRequiredGuard()]
