"""Tests for guard base classes."""

import pytest
from sdk.guards.base import (
    Guard,
    GuardCategory,
    GuardLevel,
    GuardResult,
    GuardSeverity,
    GuardViolation,
    PatternGuard,
    create_pattern_guard,
)


class TestGuardViolation:
    """Tests for GuardViolation."""

    def test_create_violation(self):
        """Test creating a violation."""
        violation = GuardViolation(
            guard_name="test_guard",
            severity=GuardSeverity.ERROR,
            message="Test message",
        )
        assert violation.guard_name == "test_guard"
        assert violation.severity == GuardSeverity.ERROR
        assert violation.message == "Test message"

    def test_violation_with_location(self):
        """Test violation with file location."""
        violation = GuardViolation(
            guard_name="test_guard",
            severity=GuardSeverity.WARNING,
            message="Test",
            file_path="test.py",
            line_number=10,
        )
        assert "test.py:10" in str(violation)

    def test_violation_to_dict(self):
        """Test converting violation to dictionary."""
        violation = GuardViolation(
            guard_name="test",
            severity=GuardSeverity.ERROR,
            message="Test",
            category=GuardCategory.SECURITY,
        )
        d = violation.to_dict()
        assert d["guard_name"] == "test"
        assert d["severity"] == "error"
        assert d["category"] == "security"


class TestGuardResult:
    """Tests for GuardResult."""

    def test_passed_result(self):
        """Test passed result."""
        result = GuardResult(
            guard_name="test",
            passed=True,
            violations=[],
        )
        assert result.passed
        assert result.error_count == 0

    def test_failed_result(self):
        """Test failed result with violations."""
        violations = [
            GuardViolation(
                guard_name="test",
                severity=GuardSeverity.ERROR,
                message="Error 1",
            ),
            GuardViolation(
                guard_name="test",
                severity=GuardSeverity.WARNING,
                message="Warning 1",
            ),
        ]
        result = GuardResult(
            guard_name="test",
            passed=False,
            violations=violations,
        )
        assert not result.passed
        assert result.error_count == 1
        assert result.warning_count == 1
        assert result.has_errors


class TestPatternGuard:
    """Tests for PatternGuard."""

    def test_create_pattern_guard(self):
        """Test creating a pattern guard."""
        guard = PatternGuard(
            name="test_pattern",
            description="Test guard",
            patterns=[r"TODO"],
        )
        assert guard.name == "test_pattern"
        assert len(guard._patterns) == 1

    def test_pattern_detection(self):
        """Test pattern detection."""
        guard = PatternGuard(
            name="todo_guard",
            description="Detect TODOs",
            patterns=[r"#\s*TODO"],
        )
        code = """
def foo():
    # TODO: implement this
    pass
"""
        result = guard.check(code, "test.py")
        assert not result.passed
        assert len(result.violations) == 1
        assert result.violations[0].line_number == 3

    def test_no_violations(self):
        """Test code with no violations."""
        guard = PatternGuard(
            name="todo_guard",
            description="Detect TODOs",
            patterns=[r"#\s*TODO"],
        )
        code = """
def foo():
    return 42
"""
        result = guard.check(code)
        assert result.passed
        assert len(result.violations) == 0

    def test_pattern_with_suggestion(self):
        """Test pattern with suggestion."""
        guard = PatternGuard(
            name="test",
            description="Test",
            patterns=[r"print\("],
            suggestions={r"print\(": "Use logging instead"},
        )
        result = guard.check("print('hello')")
        assert len(result.violations) == 1
        assert result.violations[0].suggestion == "Use logging instead"


class TestCreatePatternGuard:
    """Tests for create_pattern_guard factory."""

    def test_factory_creates_guard(self):
        """Test factory function creates guard correctly."""
        guard = create_pattern_guard(
            name="factory_test",
            description="Test guard from factory",
            patterns={
                r"eval\(": "Don't use eval",
                r"exec\(": "Don't use exec",
            },
            level=GuardLevel.INSTANT,
            category=GuardCategory.SECURITY,
        )
        assert guard.name == "factory_test"
        assert guard.level == GuardLevel.INSTANT
        assert guard.category == GuardCategory.SECURITY

    def test_factory_with_exceptions(self):
        """Test factory with path exceptions."""
        guard = create_pattern_guard(
            name="test",
            description="Test",
            patterns={r"print\(": "No print"},
            exceptions=["/tests/", "conftest.py"],
        )
        assert "/tests/" in guard._exceptions
        assert "conftest.py" in guard._exceptions
