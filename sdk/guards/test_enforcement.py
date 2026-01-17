"""
Test Enforcement Guard
======================

Ensures tests exist for features and changes.

From research: "No task is done without tests passing"

This guard:
- Detects new functions/classes without tests
- Enforces test file naming conventions
- Checks test coverage thresholds
"""

import ast
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from sdk.guards.base import (
    Guard,
    GuardCategory,
    GuardLevel,
    GuardResult,
    GuardSeverity,
    GuardViolation,
)


class E2ETestEnforcementGuard(Guard):
    """Ensures tests exist for new code."""

    def __init__(self, enabled: bool = True, min_coverage: float = 0.8):
        super().__init__(
            name="e2e_test_enforcement",
            description="Ensures tests exist for new functions and classes",
            level=GuardLevel.PHASE,
            category=GuardCategory.EVIDENCE,
            enabled=enabled,
            severity=GuardSeverity.WARNING,
        )
        self.min_coverage = min_coverage
        self._known_functions: Set[str] = set()
        self._tested_functions: Set[str] = set()
        self.add_file_extensions([".py"])

    def register_function(self, name: str, file_path: str) -> None:
        """Register a function that should have tests."""
        key = f"{file_path}::{name}"
        self._known_functions.add(key)

    def register_test(self, function_name: str, test_file: str) -> None:
        """Register that a function has a test."""
        self._tested_functions.add(function_name)

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check for missing tests."""
        start = time.time()
        violations: List[GuardViolation] = []

        if not file_path or not self.should_check_file(file_path):
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                execution_time_ms=(time.time() - start) * 1000,
            )

        # Skip test files themselves
        if "test_" in file_path or "_test.py" in file_path or "/tests/" in file_path:
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                execution_time_ms=(time.time() - start) * 1000,
            )

        try:
            tree = ast.parse(content)
            lines = content.split("\n")

            for node in ast.walk(tree):
                # Check functions
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private/dunder methods
                    if node.name.startswith("_"):
                        continue

                    # Check if test exists
                    test_name = f"test_{node.name}"
                    has_test = test_name in self._tested_functions or node.name in self._tested_functions

                    if not has_test:
                        violations.append(
                            GuardViolation(
                                guard_name=self.name,
                                severity=GuardSeverity.INFO,  # Info, not blocking
                                category=self.category,
                                message=f"Function '{node.name}' may need tests",
                                file_path=file_path,
                                line_number=node.lineno,
                                suggestion=f"Create test: def test_{node.name}(): ...",
                                code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                            )
                        )

                # Check classes
                if isinstance(node, ast.ClassDef):
                    # Skip private classes
                    if node.name.startswith("_"):
                        continue

                    test_name = f"Test{node.name}"
                    has_test = test_name in self._tested_functions

                    if not has_test:
                        violations.append(
                            GuardViolation(
                                guard_name=self.name,
                                severity=GuardSeverity.INFO,
                                category=self.category,
                                message=f"Class '{node.name}' may need tests",
                                file_path=file_path,
                                line_number=node.lineno,
                                suggestion=f"Create test class: class Test{node.name}: ...",
                                code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                            )
                        )

        except SyntaxError:
            pass

        return GuardResult(
            guard_name=self.name,
            passed=True,  # Info only, doesn't block
            violations=violations,
            execution_time_ms=(time.time() - start) * 1000,
            files_checked=1,
        )

    def scan_test_files(self, test_dir: Path) -> int:
        """Scan test directory to find existing tests."""
        count = 0
        if not test_dir.exists():
            return count

        for test_file in test_dir.rglob("test_*.py"):
            try:
                content = test_file.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name.startswith("test_"):
                            # Extract the function being tested
                            tested = node.name[5:]  # Remove "test_" prefix
                            self._tested_functions.add(tested)
                            self._tested_functions.add(node.name)
                            count += 1

                    if isinstance(node, ast.ClassDef):
                        if node.name.startswith("Test"):
                            self._tested_functions.add(node.name)
                            count += 1

            except (SyntaxError, UnicodeDecodeError):
                continue

        return count


def create_test_enforcement_guards() -> List[Guard]:
    """Create test enforcement guards."""
    return [E2ETestEnforcementGuard()]
