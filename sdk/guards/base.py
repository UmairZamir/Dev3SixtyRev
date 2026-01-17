"""
Guard Base Module
=================

Base classes and types for the 3SixtyRev SDK guard system.

Guards enforce code quality standards and prevent common AI coding pitfalls:
- Bandaid patterns (TODOs, type ignores, bare excepts)
- Shell components (placeholder implementations)
- Security issues (hardcoded secrets, SQL injection)
- Hallucinations (invented APIs, non-existent packages)
- Context loss (forgotten requirements)
- Scope creep (unintended file modifications)

Guard Levels:
- INSTANT: Run on every edit (<100ms)
- TASK: Run after each task completion (<30s)
- PHASE: Run at phase gates (<5min)
- CONTINUOUS: Background monitoring
"""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set


class GuardLevel(str, Enum):
    """Guard execution levels."""

    INSTANT = "instant"  # Every edit, <100ms
    TASK = "task"  # After each task, <30s
    PHASE = "phase"  # End of phase, <5min
    CONTINUOUS = "continuous"  # Background monitoring


class GuardSeverity(str, Enum):
    """Severity levels for guard violations."""

    ERROR = "error"  # Blocks commit/completion
    WARNING = "warning"  # Warns but allows
    INFO = "info"  # Informational only


class GuardCategory(str, Enum):
    """Categories of guards based on research."""

    # Core guards (from proven SDK)
    BANDAID = "bandaid"  # Temporary fixes that hide problems
    SHELL = "shell"  # Placeholder implementations
    SECURITY = "security"  # Security vulnerabilities

    # New guards (from vibe coding research)
    HALLUCINATION = "hallucination"  # Invented APIs, non-existent packages
    CONTEXT = "context"  # Context loss, drift, poisoning
    SCOPE = "scope"  # Scope creep, unintended modifications
    QUALITY = "quality"  # Over-engineering, anti-patterns
    EVIDENCE = "evidence"  # Task completion verification
    SPEC = "spec"  # Specification compliance


@dataclass
class GuardViolation:
    """A single guard violation."""

    guard_name: str
    severity: GuardSeverity
    message: str
    category: GuardCategory = GuardCategory.QUALITY
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    column: Optional[int] = None
    pattern_matched: Optional[str] = None
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None
    evidence_required: bool = False

    def __str__(self) -> str:
        """Format violation for display."""
        location = ""
        if self.file_path:
            location = f"{self.file_path}"
            if self.line_number:
                location += f":{self.line_number}"
            location = f" at {location}"

        severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(
            self.severity.value, "❓"
        )

        result = f"{severity_icon} [{self.severity.value.upper()}] {self.guard_name}{location}: {self.message}"

        if self.suggestion:
            result += f"\n   💡 Suggestion: {self.suggestion}"

        if self.code_snippet:
            result += f"\n   📝 Code: {self.code_snippet[:100]}"

        return result

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "guard_name": self.guard_name,
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "column": self.column,
            "pattern_matched": self.pattern_matched,
            "suggestion": self.suggestion,
            "code_snippet": self.code_snippet,
            "evidence_required": self.evidence_required,
        }


@dataclass
class GuardResult:
    """Result from running a single guard."""

    guard_name: str
    passed: bool
    violations: List[GuardViolation] = field(default_factory=list)
    execution_time_ms: float = 0.0
    files_checked: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        """Check if any ERROR-level violations exist."""
        return any(v.severity == GuardSeverity.ERROR for v in self.violations)

    @property
    def error_count(self) -> int:
        """Count ERROR-level violations."""
        return sum(1 for v in self.violations if v.severity == GuardSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count WARNING-level violations."""
        return sum(1 for v in self.violations if v.severity == GuardSeverity.WARNING)

    def format(self) -> str:
        """Format result for display."""
        if self.passed:
            return f"✅ {self.guard_name}: Passed ({self.execution_time_ms:.1f}ms)"

        lines = [f"❌ {self.guard_name}: {self.error_count} error(s), {self.warning_count} warning(s)"]

        for v in self.violations[:10]:  # Show first 10
            lines.append(f"   {v}")

        if len(self.violations) > 10:
            lines.append(f"   ... and {len(self.violations) - 10} more")

        return "\n".join(lines)


class Guard(ABC):
    """Abstract base class for all guards."""

    def __init__(
        self,
        name: str,
        description: str,
        level: GuardLevel,
        category: GuardCategory,
        enabled: bool = True,
        severity: GuardSeverity = GuardSeverity.ERROR,
    ):
        self.name = name
        self.description = description
        self.level = level
        self.category = category
        self.enabled = enabled
        self.severity = severity
        self._patterns: List[re.Pattern] = []
        self._exceptions: Set[str] = set()
        self._file_extensions: Set[str] = set()

    def add_pattern(self, pattern: str, flags: int = re.MULTILINE | re.IGNORECASE) -> None:
        """Add a regex pattern to check."""
        self._patterns.append(re.compile(pattern, flags))

    def add_patterns(self, patterns: List[str]) -> None:
        """Add multiple patterns."""
        for pattern in patterns:
            self.add_pattern(pattern)

    def add_exception(self, path_pattern: str) -> None:
        """Add a path pattern to exclude from checking."""
        self._exceptions.add(path_pattern)

    def add_file_extensions(self, extensions: List[str]) -> None:
        """Limit guard to specific file extensions."""
        self._file_extensions.update(extensions)

    def should_check_file(self, file_path: str) -> bool:
        """Determine if a file should be checked."""
        # Check exceptions
        for exception in self._exceptions:
            if exception in file_path:
                return False

        # Check file extensions if specified
        if self._file_extensions:
            path = Path(file_path)
            if path.suffix.lower() not in self._file_extensions:
                return False

        return True

    @abstractmethod
    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """
        Check content for violations.

        Args:
            content: The file content to check
            file_path: Optional path to the file

        Returns:
            GuardResult with any violations found
        """
        pass

    def check_file(self, file_path: Path) -> GuardResult:
        """Check a file for violations."""
        if not file_path.exists():
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                metadata={"reason": "file_not_found"},
            )

        if not self.should_check_file(str(file_path)):
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                metadata={"reason": "file_excluded"},
            )

        try:
            content = file_path.read_text(encoding="utf-8")
            return self.check(content, str(file_path))
        except UnicodeDecodeError:
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                metadata={"reason": "binary_file"},
            )

    def check_files(self, file_paths: List[Path]) -> GuardResult:
        """Check multiple files and aggregate results."""
        start_time = time.time()
        all_violations: List[GuardViolation] = []
        files_checked = 0

        for file_path in file_paths:
            result = self.check_file(file_path)
            all_violations.extend(result.violations)
            if result.metadata.get("reason") not in ["file_excluded", "binary_file"]:
                files_checked += 1

        has_errors = any(v.severity == GuardSeverity.ERROR for v in all_violations)

        return GuardResult(
            guard_name=self.name,
            passed=not has_errors,
            violations=all_violations,
            execution_time_ms=(time.time() - start_time) * 1000,
            files_checked=files_checked,
        )


class PatternGuard(Guard):
    """Guard that checks for regex patterns in code."""

    def __init__(
        self,
        name: str,
        description: str,
        level: GuardLevel = GuardLevel.INSTANT,
        category: GuardCategory = GuardCategory.QUALITY,
        enabled: bool = True,
        severity: GuardSeverity = GuardSeverity.ERROR,
        patterns: Optional[List[str]] = None,
        suggestions: Optional[Dict[str, str]] = None,
    ):
        super().__init__(name, description, level, category, enabled, severity)
        self.suggestions = suggestions or {}
        if patterns:
            self.add_patterns(patterns)

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check content against all patterns."""
        start_time = time.time()

        # Check if file should be excluded
        if file_path and not self.should_check_file(file_path):
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                execution_time_ms=(time.time() - start_time) * 1000,
                metadata={"reason": "file_excluded"},
            )

        violations: List[GuardViolation] = []
        lines = content.split("\n")

        for pattern in self._patterns:
            for match in pattern.finditer(content):
                # Calculate line number
                line_start = content.count("\n", 0, match.start()) + 1
                code_snippet = lines[line_start - 1].strip() if line_start <= len(lines) else match.group(0)

                # Get suggestion if available
                suggestion = self.suggestions.get(pattern.pattern)

                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=self.severity,
                        category=self.category,
                        message=f"Banned pattern detected: {match.group(0)[:50]}",
                        file_path=file_path,
                        line_number=line_start,
                        pattern_matched=pattern.pattern,
                        suggestion=suggestion,
                        code_snippet=code_snippet,
                    )
                )

        # Only fail for ERROR-level violations
        has_errors = any(v.severity == GuardSeverity.ERROR for v in violations)

        return GuardResult(
            guard_name=self.name,
            passed=not has_errors,
            violations=violations,
            execution_time_ms=(time.time() - start_time) * 1000,
            files_checked=1,
        )


class CompositeGuard(Guard):
    """Guard that combines multiple guards."""

    def __init__(
        self,
        name: str,
        description: str,
        guards: List[Guard],
        level: GuardLevel = GuardLevel.TASK,
        category: GuardCategory = GuardCategory.QUALITY,
    ):
        super().__init__(name, description, level, category)
        self.guards = guards

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Run all sub-guards and combine results."""
        start_time = time.time()
        all_violations: List[GuardViolation] = []

        for guard in self.guards:
            if guard.enabled:
                result = guard.check(content, file_path)
                all_violations.extend(result.violations)

        has_errors = any(v.severity == GuardSeverity.ERROR for v in all_violations)

        return GuardResult(
            guard_name=self.name,
            passed=not has_errors,
            violations=all_violations,
            execution_time_ms=(time.time() - start_time) * 1000,
            files_checked=1,
            metadata={"guards_run": len(self.guards)},
        )


class CallableGuard(Guard):
    """Guard that uses a custom callable for checking."""

    def __init__(
        self,
        name: str,
        description: str,
        check_fn: Callable[[str, Optional[str]], List[GuardViolation]],
        level: GuardLevel = GuardLevel.TASK,
        category: GuardCategory = GuardCategory.QUALITY,
        enabled: bool = True,
        severity: GuardSeverity = GuardSeverity.ERROR,
    ):
        super().__init__(name, description, level, category, enabled, severity)
        self._check_fn = check_fn

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Run the custom check function."""
        start_time = time.time()

        if file_path and not self.should_check_file(file_path):
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        violations = self._check_fn(content, file_path)
        has_errors = any(v.severity == GuardSeverity.ERROR for v in violations)

        return GuardResult(
            guard_name=self.name,
            passed=not has_errors,
            violations=violations,
            execution_time_ms=(time.time() - start_time) * 1000,
            files_checked=1,
        )


# Type aliases for convenience
GuardCheckFn = Callable[[str, Optional[str]], List[GuardViolation]]


def create_pattern_guard(
    name: str,
    description: str,
    patterns: Dict[str, str],
    level: GuardLevel = GuardLevel.INSTANT,
    category: GuardCategory = GuardCategory.QUALITY,
    severity: GuardSeverity = GuardSeverity.ERROR,
    exceptions: Optional[List[str]] = None,
) -> PatternGuard:
    """
    Factory function to create a pattern guard.

    Args:
        name: Guard name
        description: Guard description
        patterns: Dict mapping regex patterns to suggestion messages
        level: Guard level
        category: Guard category
        severity: Default severity
        exceptions: List of path patterns to exclude

    Returns:
        Configured PatternGuard instance
    """
    guard = PatternGuard(
        name=name,
        description=description,
        level=level,
        category=category,
        severity=severity,
        patterns=list(patterns.keys()),
        suggestions=patterns,
    )

    if exceptions:
        for exc in exceptions:
            guard.add_exception(exc)

    return guard
