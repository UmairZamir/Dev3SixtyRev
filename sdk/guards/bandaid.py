"""
Bandaid Patterns Guard
======================

Detects and blocks common "bandaid" patterns that hide problems:
- # type: ignore
- # noqa
- except: pass
- @pytest.mark.skip
- pragma: no cover
- Hardcoded values to pass tests
- skip_validation flags
- TODO/FIXME/HACK comments

These patterns often indicate shortcuts that hide real issues.
From vibe coding research: "Almost right" code is the #1 frustration.
"""

from typing import Dict, List

from sdk.guards.base import (
    GuardCategory,
    GuardLevel,
    GuardSeverity,
    PatternGuard,
)


class BandaidPatternsGuard(PatternGuard):
    """
    Guard that detects bandaid patterns in code.

    These patterns often indicate shortcuts that hide real issues:
    - Type ignores hide type errors
    - noqa hides linting issues
    - except: pass hides exceptions
    - pytest.skip hides failing tests
    - Hardcoded returns bypass real logic
    """

    BANDAID_PATTERNS: Dict[str, str] = {
        # Type ignores
        r"#\s*type:\s*ignore(?:\[[\w\-,\s]+\])?": (
            "Fix the actual type error. Use Optional[T] for nullable, "
            "or fix the return type. Never silence type checkers."
        ),
        # Linting ignores
        r"#\s*noqa(?::\s*[\w,]+)?": (
            "Fix the linting issue. Common fixes: break long lines, "
            "fix imports, rename variables. Don't silence linters."
        ),
        # Bare except clauses
        r"except:\s*pass": (
            "Handle exceptions properly: except SpecificError as e: "
            "logger.exception('Error: %s', e)"
        ),
        r"except\s+Exception:\s*pass": (
            "Catch specific exceptions and handle them. "
            "At minimum, log the error."
        ),
        r"except\s+BaseException:\s*pass": (
            "NEVER catch BaseException silently - it catches SystemExit "
            "and KeyboardInterrupt. Use specific exception types."
        ),
        r"except.*:\s*\.\.\.\s*$": (
            "Empty except with ellipsis hides errors. Handle or re-raise."
        ),
        # Test skipping
        r"@pytest\.mark\.skip(?:\(|$)": (
            "Fix the test or delete it. If temporarily disabled, "
            "use @pytest.mark.xfail(reason='ticket-123') with tracking."
        ),
        r"@pytest\.mark\.skipif": (
            "Ensure skip condition is still needed. "
            "Document with clear reason string."
        ),
        r"#\s*def\s+test_": (
            "Commented-out test detected. Fix it or delete it. "
            "Don't leave dead test code."
        ),
        # Coverage exclusion
        r"#\s*pragma:\s*no\s*cover": (
            "Coverage exclusion should be rare. Add comment explaining "
            "why this code can't be tested."
        ),
        # TODO patterns that indicate bandaids
        r"#\s*TODO:?\s*(?:fix|hack|workaround|temp|temporary|later)\b": (
            "Fix it now or create a tracked issue. "
            "TODOs that say 'later' are often forgotten."
        ),
        r"#\s*FIXME\b": (
            "Known bugs should be fixed or tracked in issue system, "
            "not left as comments."
        ),
        r"#\s*HACK\b": (
            "Refactor the hack into a proper solution. "
            "Document why if truly necessary."
        ),
        r"#\s*XXX\b": (
            "XXX indicates something that needs attention. "
            "Fix it or create an issue."
        ),
        # Validation skipping
        r"skip_validation\s*=\s*True": (
            "Don't skip validation. Fix the validation to handle "
            "the edge case properly."
        ),
        r"validate\s*=\s*False": (
            "Validation should not be optional. Fix the validation "
            "logic to handle all cases."
        ),
        # Disabled features
        r"if\s+False\s*:": (
            "Dead code detected. Remove disabled code or use feature flags properly."
        ),
        r"if\s+True\s*:.*#.*(?:TODO|temp|remove)": (
            "Temporary bypass detected. Implement proper conditional logic."
        ),
        # Assertion skipping
        r"assert\s+True\s*(?:#|$)": (
            "Trivial assertion detected. Write meaningful assertions or remove."
        ),
        # Return None patterns that might hide issues
        r"return\s+None\s*#\s*(?:TODO|temp|fix)": (
            "Returning None as placeholder. Implement the actual logic."
        ),
    }

    def __init__(self, enabled: bool = True):
        patterns = list(self.BANDAID_PATTERNS.keys())
        suggestions = self.BANDAID_PATTERNS

        super().__init__(
            name="bandaid_patterns",
            description="Detects bandaid patterns that hide real issues",
            level=GuardLevel.INSTANT,
            category=GuardCategory.BANDAID,
            enabled=enabled,
            severity=GuardSeverity.ERROR,
            patterns=patterns,
            suggestions=suggestions,
        )

        # Add exceptions for files where some patterns are OK
        self.add_exception("conftest.py")  # Test configs may need marks
        self.add_exception("/tests/fixtures/")  # Test fixtures
        self.add_exception("__pycache__")  # Compiled files


class HardcodedValueGuard(PatternGuard):
    """Guard that detects suspicious hardcoded values."""

    HARDCODED_PATTERNS: Dict[str, str] = {
        # Suspicious hardcoded IDs
        r"(?:user_id|tenant_id|customer_id)\s*=\s*['\"]?\d+['\"]?": (
            "Hardcoded ID detected. Get from auth context or parameter."
        ),
        r"(?:api_key|apikey|api_token)\s*=\s*['\"][^'\"]+['\"]": (
            "Hardcoded API key detected. Use environment variables."
        ),
        # Hardcoded URLs in code (not config)
        r"https?://(?:localhost|127\.0\.0\.1):\d+(?:/[^\s'\"]*)?": (
            "Hardcoded localhost URL. Use environment variable or config."
        ),
        r"https?://[a-zA-Z0-9.-]+\.(?:com|io|dev|app)/[^\s'\"]*": (
            "Hardcoded external URL. Consider using config for flexibility."
        ),
        # Hardcoded file paths
        r"['\"]\/Users\/[^'\"]+['\"]": (
            "Hardcoded absolute path. Use relative paths or Path library."
        ),
        r"['\"]\/home\/[^'\"]+['\"]": (
            "Hardcoded home directory path. Use Path.home() or config."
        ),
        r"['\"]C:\\\\[^'\"]+['\"]": (
            "Hardcoded Windows path. Use os.path or pathlib for cross-platform."
        ),
        # Hardcoded credentials patterns
        r"(?:password|passwd|pwd)\s*=\s*['\"][^'\"]+['\"]": (
            "Hardcoded password detected! Use environment variables or secrets manager."
        ),
        r"(?:secret|token)\s*=\s*['\"][^'\"]{8,}['\"]": (
            "Hardcoded secret detected! Use environment variables or secrets manager."
        ),
    }

    def __init__(self, enabled: bool = True):
        patterns = list(self.HARDCODED_PATTERNS.keys())
        suggestions = self.HARDCODED_PATTERNS

        super().__init__(
            name="hardcoded_values",
            description="Detects suspicious hardcoded values",
            level=GuardLevel.INSTANT,
            category=GuardCategory.BANDAID,
            enabled=enabled,
            severity=GuardSeverity.WARNING,  # Warning, not error
            patterns=patterns,
            suggestions=suggestions,
        )

        # Don't check test files for some of these
        self.add_exception("/tests/")
        self.add_exception("test_")
        self.add_exception("_test.py")
        self.add_exception("conftest.py")


class PrintStatementGuard(PatternGuard):
    """Guard that detects print statements in production code."""

    PRINT_PATTERNS: Dict[str, str] = {
        r"(?<!['\"])print\s*\(": (
            "Use logger.debug() or logger.info() instead of print()"
        ),
        r"console\.log\s*\(": (
            "Use proper logging or remove debug statements"
        ),
        r"console\.debug\s*\(": (
            "Use proper logging framework instead of console.debug"
        ),
        r"console\.info\s*\(": (
            "Use proper logging framework instead of console.info"
        ),
        r"System\.out\.print": (
            "Use proper logging framework instead of System.out"
        ),
        r"fmt\.Print(?:ln|f)?\s*\(": (
            "Use proper logging package instead of fmt.Print"
        ),
    }

    def __init__(self, enabled: bool = True):
        patterns = list(self.PRINT_PATTERNS.keys())
        suggestions = self.PRINT_PATTERNS

        super().__init__(
            name="print_statements",
            description="Detects print statements that should use logging",
            level=GuardLevel.INSTANT,
            category=GuardCategory.BANDAID,
            enabled=enabled,
            severity=GuardSeverity.WARNING,
            patterns=patterns,
            suggestions=suggestions,
        )

        # Don't check test files or scripts
        self.add_exception("/tests/")
        self.add_exception("/scripts/")
        self.add_exception("__main__")
        self.add_exception("cli.py")
        self.add_exception("_cli")


def create_bandaid_guards() -> List[PatternGuard]:
    """Create all bandaid-related guards."""
    return [
        BandaidPatternsGuard(),
        HardcodedValueGuard(),
        PrintStatementGuard(),
    ]
