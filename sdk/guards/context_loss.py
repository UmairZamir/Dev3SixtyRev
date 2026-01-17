"""
Context Loss Guard
==================

Detects when implementation drifts from requirements.

From research:
- "The agent will not learn as it goes... Every time you reset context, 
   you're working with another brand new hire"
- "Context poisoning: When a hallucination early in chat gets referenced repeatedly"

This guard detects:
- Orphaned TODOs without implementation
- Missing requirements from task specs
- Unfinished implementations
- Drift between spec and implementation
"""

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


class ContextLossGuard(Guard):
    """Detects signs of context loss during development."""

    # Patterns indicating incomplete implementation
    INCOMPLETE_PATTERNS: Dict[str, str] = {
        r"#\s*TODO:?\s+(?!ticket|issue|jira)": (
            "Untracked TODO detected. Create an issue or implement now."
        ),
        r"#\s*INCOMPLETE:?": (
            "INCOMPLETE marker found. Finish the implementation."
        ),
        r"#\s*WIP:?": (
            "Work-in-progress marker found. Complete before committing."
        ),
        r"#\s*CONTINUE:?\s+HERE": (
            "CONTINUE HERE marker indicates interrupted work. Complete it."
        ),
        r"#\s*LEFT\s+OFF": (
            "LEFT OFF marker indicates interrupted work. Complete it."
        ),
        r"#\s*NEXT:?\s+(?:do|implement|add|fix|handle)": (
            "NEXT marker indicates planned but unfinished work."
        ),
        r"raise\s+NotImplementedError\(['\"](?!abstract)": (
            "NotImplementedError with message - implementation needed."
        ),
        r"pass\s*#\s*(?:TODO|implement|add|fix)": (
            "Placeholder pass with TODO - implement the function."
        ),
        r"\.\.\.\s*#\s*(?:TODO|implement|add|fix)": (
            "Placeholder ellipsis with TODO - implement the code."
        ),
        r"#\s*PLACEHOLDER": (
            "PLACEHOLDER marker found - replace with real implementation."
        ),
        r"#\s*STUB": (
            "STUB marker found - implement the actual logic."
        ),
        r"return\s+\{\}\s*#\s*(?:TODO|empty|stub)": (
            "Returning empty dict as placeholder."
        ),
        r"return\s+\[\]\s*#\s*(?:TODO|empty|stub)": (
            "Returning empty list as placeholder."
        ),
        r"return\s+None\s*#\s*(?:TODO|implement|stub)": (
            "Returning None as placeholder."
        ),
        r"#\s*FIXME:?\s+\w": (
            "FIXME marker indicates known bug that needs fixing."
        ),
        r"#\s*BUG:?": (
            "BUG marker indicates known issue."
        ),
        r"#\s*BROKEN:?": (
            "BROKEN marker indicates non-functional code."
        ),
    }

    # Patterns indicating context drift
    DRIFT_PATTERNS: Dict[str, str] = {
        r"#\s*This\s+(?:was|used\s+to|should)\s+(?:be|do)": (
            "Comment suggests previous behavior changed - verify correctness."
        ),
        r"#\s*(?:Old|Previous|Original)\s+(?:code|implementation|version)": (
            "Reference to old code - ensure new version is complete."
        ),
        r"#\s*Commented\s+out\s+(?:for\s+now|temporarily)": (
            "Temporarily disabled code - restore or remove."
        ),
        r"#\s*(?:Not\s+sure|Uncertain|May\s+need)": (
            "Uncertain comment indicates unclear requirements."
        ),
        r"#\s*(?:Might|Could|Should)\s+(?:need|add|implement)\s+later": (
            "Deferred work indicated - track in issue system."
        ),
    }

    def __init__(self, enabled: bool = True):
        super().__init__(
            name="context_loss",
            description="Detects signs of context loss and incomplete implementations",
            level=GuardLevel.TASK,
            category=GuardCategory.CONTEXT,
            enabled=enabled,
            severity=GuardSeverity.WARNING,
        )

        self._incomplete_patterns = {
            re.compile(pattern, re.MULTILINE | re.IGNORECASE): msg
            for pattern, msg in self.INCOMPLETE_PATTERNS.items()
        }
        self._drift_patterns = {
            re.compile(pattern, re.MULTILINE | re.IGNORECASE): msg
            for pattern, msg in self.DRIFT_PATTERNS.items()
        }

        self.add_file_extensions([".py", ".js", ".ts", ".jsx", ".tsx"])
        self.add_exception("/tests/")
        self.add_exception("test_")

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check for context loss indicators."""
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

        # Check incomplete patterns
        for pattern, suggestion in self._incomplete_patterns.items():
            for match in pattern.finditer(content):
                line_num = content.count("\n", 0, match.start()) + 1
                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=GuardSeverity.WARNING,
                        category=self.category,
                        message=f"Incomplete implementation: {match.group(0).strip()[:50]}",
                        file_path=file_path,
                        line_number=line_num,
                        suggestion=suggestion,
                        code_snippet=lines[line_num - 1].strip() if line_num <= len(lines) else "",
                    )
                )

        # Check drift patterns
        for pattern, suggestion in self._drift_patterns.items():
            for match in pattern.finditer(content):
                line_num = content.count("\n", 0, match.start()) + 1
                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=GuardSeverity.INFO,  # Lower severity for drift
                        category=self.category,
                        message=f"Possible context drift: {match.group(0).strip()[:50]}",
                        file_path=file_path,
                        line_number=line_num,
                        suggestion=suggestion,
                        code_snippet=lines[line_num - 1].strip() if line_num <= len(lines) else "",
                    )
                )

        # Only fail for WARNING or higher
        has_warnings = any(
            v.severity in (GuardSeverity.ERROR, GuardSeverity.WARNING) 
            for v in violations
        )

        return GuardResult(
            guard_name=self.name,
            passed=not has_warnings,
            violations=violations,
            execution_time_ms=(time.time() - start) * 1000,
            files_checked=1,
        )


def create_context_guards() -> List[Guard]:
    """Create context-related guards."""
    return [ContextLossGuard()]
