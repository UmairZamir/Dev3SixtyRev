"""
Scope Guard
===========

Detects scope creep - unintended file modifications.

From research: "User asks to fix login, Claude modifies src/auth/login.ts (correct) 
AND src/admin/login.ts (unintended)"

This guard helps track expected vs actual changes.
"""

import time
from pathlib import Path
from typing import List, Optional, Set

from sdk.guards.base import (
    Guard,
    GuardCategory,
    GuardLevel,
    GuardResult,
    GuardSeverity,
    GuardViolation,
)


class ScopeCreepGuard(Guard):
    """Detects modifications outside expected scope."""

    def __init__(self, enabled: bool = True):
        super().__init__(
            name="scope_creep",
            description="Detects modifications outside expected scope",
            level=GuardLevel.TASK,
            category=GuardCategory.SCOPE,
            enabled=enabled,
            severity=GuardSeverity.WARNING,
        )
        self._expected_files: Set[str] = set()
        self._task_description: Optional[str] = None

    def set_expected_scope(self, files: List[str], task_description: str = "") -> None:
        """Set the expected files to be modified for current task."""
        self._expected_files = set(files)
        self._task_description = task_description

    def clear_scope(self) -> None:
        """Clear the expected scope."""
        self._expected_files.clear()
        self._task_description = None

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check if file modification is within expected scope."""
        start = time.time()

        violations: List[GuardViolation] = []

        # If no scope set, allow all (but warn)
        if not self._expected_files:
            if file_path:
                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=GuardSeverity.INFO,
                        category=self.category,
                        message="No expected scope defined for this task",
                        file_path=file_path,
                        suggestion="Use set_expected_scope() before starting a task.",
                    )
                )
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=violations,
                execution_time_ms=(time.time() - start) * 1000,
            )

        # Check if file is in expected scope
        if file_path:
            normalized_path = str(Path(file_path).resolve())
            in_scope = any(
                expected in normalized_path or normalized_path.endswith(expected)
                for expected in self._expected_files
            )

            if not in_scope:
                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=GuardSeverity.WARNING,
                        category=self.category,
                        message=f"File outside expected scope: {file_path}",
                        file_path=file_path,
                        suggestion=(
                            f"Expected files: {', '.join(self._expected_files)}. "
                            "Verify this change is intentional."
                        ),
                    )
                )

        return GuardResult(
            guard_name=self.name,
            passed=len([v for v in violations if v.severity == GuardSeverity.ERROR]) == 0,
            violations=violations,
            execution_time_ms=(time.time() - start) * 1000,
            files_checked=1,
        )

    def check_modified_files(self, modified_files: List[str]) -> GuardResult:
        """Check a list of modified files against expected scope."""
        start = time.time()
        violations: List[GuardViolation] = []

        if not self._expected_files:
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                execution_time_ms=(time.time() - start) * 1000,
            )

        unexpected = []
        for file_path in modified_files:
            normalized = str(Path(file_path).resolve())
            in_scope = any(
                expected in normalized or normalized.endswith(expected)
                for expected in self._expected_files
            )
            if not in_scope:
                unexpected.append(file_path)

        if unexpected:
            violations.append(
                GuardViolation(
                    guard_name=self.name,
                    severity=GuardSeverity.WARNING,
                    category=self.category,
                    message=f"Files modified outside expected scope: {', '.join(unexpected)}",
                    suggestion=(
                        f"Task: {self._task_description or 'No description'}. "
                        f"Expected: {', '.join(self._expected_files)}"
                    ),
                )
            )

        return GuardResult(
            guard_name=self.name,
            passed=len(violations) == 0,
            violations=violations,
            execution_time_ms=(time.time() - start) * 1000,
            files_checked=len(modified_files),
        )


def create_scope_guards() -> List[Guard]:
    """Create scope-related guards."""
    return [ScopeCreepGuard()]
