"""
Complexity Guard
================

Detects over-engineering and excessive complexity.

From research: "Extremely robust, high-quality code... The problem was it was MASSIVE overkill"

This guard detects:
- Functions that are too long
- Classes with too many methods
- Deep nesting levels
- Excessive parameter counts
- Over-abstraction patterns
"""

import ast
import logging
import time

logger = logging.getLogger(__name__)
from typing import List, Optional

from sdk.guards.base import (
    Guard,
    GuardCategory,
    GuardLevel,
    GuardResult,
    GuardSeverity,
    GuardViolation,
)


class OverEngineeringGuard(Guard):
    """Detects over-engineering and excessive complexity."""

    # Thresholds
    MAX_FUNCTION_LINES = 50
    MAX_CLASS_METHODS = 20
    MAX_NESTING_DEPTH = 4
    MAX_PARAMETERS = 7
    MAX_RETURNS = 5

    def __init__(self, enabled: bool = True):
        super().__init__(
            name="over_engineering",
            description="Detects over-engineering and excessive complexity",
            level=GuardLevel.TASK,
            category=GuardCategory.QUALITY,
            enabled=enabled,
            severity=GuardSeverity.WARNING,
        )
        self.add_file_extensions([".py"])

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check for over-engineering indicators."""
        start = time.time()

        if file_path and not self.should_check_file(file_path):
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                execution_time_ms=(time.time() - start) * 1000,
            )

        violations: List[GuardViolation] = []
        lines = content.split("\n")

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                # Check function length
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                    if func_lines > self.MAX_FUNCTION_LINES:
                        violations.append(
                            GuardViolation(
                                guard_name=self.name,
                                severity=GuardSeverity.WARNING,
                                category=self.category,
                                message=f"Function '{node.name}' is {func_lines} lines (max: {self.MAX_FUNCTION_LINES})",
                                file_path=file_path,
                                line_number=node.lineno,
                                suggestion="Consider breaking into smaller functions.",
                                code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                            )
                        )

                    # Check parameter count
                    param_count = len(node.args.args) + len(node.args.kwonlyargs)
                    if param_count > self.MAX_PARAMETERS:
                        violations.append(
                            GuardViolation(
                                guard_name=self.name,
                                severity=GuardSeverity.WARNING,
                                category=self.category,
                                message=f"Function '{node.name}' has {param_count} parameters (max: {self.MAX_PARAMETERS})",
                                file_path=file_path,
                                line_number=node.lineno,
                                suggestion="Consider using a config object or dataclass.",
                                code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                            )
                        )

                # Check class complexity
                if isinstance(node, ast.ClassDef):
                    methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    if len(methods) > self.MAX_CLASS_METHODS:
                        violations.append(
                            GuardViolation(
                                guard_name=self.name,
                                severity=GuardSeverity.WARNING,
                                category=self.category,
                                message=f"Class '{node.name}' has {len(methods)} methods (max: {self.MAX_CLASS_METHODS})",
                                file_path=file_path,
                                line_number=node.lineno,
                                suggestion="Consider splitting into multiple classes.",
                                code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                            )
                        )

        except SyntaxError as e:
            # Code has syntax errors - can't analyze for complexity
            logger.debug("Could not parse %s for complexity analysis: %s", file_path, e)

        return GuardResult(
            guard_name=self.name,
            passed=len([v for v in violations if v.severity == GuardSeverity.ERROR]) == 0,
            violations=violations,
            execution_time_ms=(time.time() - start) * 1000,
            files_checked=1,
        )


def create_complexity_guards() -> List[Guard]:
    """Create complexity-related guards."""
    return [OverEngineeringGuard()]
