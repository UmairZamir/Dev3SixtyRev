"""
Shell Component Guard
=====================

Detects shell/placeholder components in code.

From research: "vibe coding was brilliant for exploration but catastrophic for production"
Shell components are placeholder implementations that look functional but don't work.

This guard detects:
- Empty handlers (onClick={() => {}})
- Hardcoded mock data in state
- TODO console.logs
- Unimplemented methods (pass, ...)
- NotImplementedError placeholders
- Fetch without error handling
"""

import re
import time
from typing import Dict, List, Optional

from sdk.guards.base import (
    Guard,
    GuardCategory,
    GuardLevel,
    GuardResult,
    GuardSeverity,
    GuardViolation,
    PatternGuard,
)


class ShellComponentGuard(Guard):
    """Detects shell/placeholder components in frontend code."""

    SHELL_PATTERNS: Dict[str, Dict[str, str]] = {
        # Empty handlers
        r"onClick\s*=\s*\{\s*\(\s*\)\s*=>\s*\{\s*\}\s*\}": {
            "message": "Empty onClick handler - placeholder that does nothing",
            "suggestion": "Implement the click handler or remove it",
        },
        r"onSubmit\s*=\s*\{\s*\(\s*\)\s*=>\s*\{\s*\}\s*\}": {
            "message": "Empty onSubmit handler - form won't work",
            "suggestion": "Implement form submission logic",
        },
        r"onChange\s*=\s*\{\s*\(\s*\)\s*=>\s*\{\s*\}\s*\}": {
            "message": "Empty onChange handler - input won't update",
            "suggestion": "Implement state update logic",
        },
        r"on[A-Z]\w+\s*=\s*\{\s*\(\s*\)\s*=>\s*\{\s*\}\s*\}": {
            "message": "Empty event handler detected",
            "suggestion": "Implement the handler or remove the prop",
        },
        # Hardcoded mock data in state
        r"useState\s*\(\s*\[\s*\{[^}]*id\s*:\s*['\"]?\d+": {
            "message": "Hardcoded mock data in useState",
            "suggestion": "Fetch data from API using useQuery, useSWR, or useEffect",
        },
        r"useState\s*\(\s*\[\s*['\"][^'\"]+['\"]": {
            "message": "Hardcoded array in useState - likely placeholder",
            "suggestion": "Initialize with empty array and fetch real data",
        },
        # TODO placeholders
        r"console\.log\s*\(\s*['\"]TODO": {
            "message": "TODO console.log placeholder",
            "suggestion": "Implement the actual functionality",
        },
        r"console\.log\s*\(\s*['\"]implement": {
            "message": "Implement placeholder in console.log",
            "suggestion": "Complete the implementation",
        },
        # Fetch without error handling
        r"fetch\s*\([^)]+\)\s*\.then\s*\([^)]+\)(?!\s*\.catch)": {
            "message": "Fetch without error handling",
            "suggestion": "Add .catch() or use try/catch with async/await",
        },
        # Promise without catch
        r"\.then\s*\([^)]+\)\s*(?!\.then|\.catch|\.finally)[\s;]": {
            "message": "Promise chain without error handling",
            "suggestion": "Add .catch() to handle errors",
        },
        # Placeholder returns in React
        r"return\s+null\s*;\s*//\s*(?:TODO|placeholder|implement)": {
            "message": "Component returns null with TODO comment",
            "suggestion": "Implement the component's UI",
        },
        r"return\s+<>\s*</>\s*;": {
            "message": "Component returns empty fragment - likely placeholder",
            "suggestion": "Implement the component's content",
        },
    }

    def __init__(self, enabled: bool = True):
        super().__init__(
            name="shell_component",
            description="Detects shell/placeholder components in frontend code",
            level=GuardLevel.INSTANT,
            category=GuardCategory.SHELL,
            enabled=enabled,
            severity=GuardSeverity.ERROR,
        )

        self._compiled_patterns = {
            re.compile(pattern, re.MULTILINE | re.IGNORECASE): info
            for pattern, info in self.SHELL_PATTERNS.items()
        }

        # Only check frontend files
        self.add_file_extensions([".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"])

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check for shell components in frontend code."""
        start = time.time()

        # Skip if not a frontend file
        if file_path:
            if not self.should_check_file(file_path):
                return GuardResult(
                    guard_name=self.name,
                    passed=True,
                    violations=[],
                    execution_time_ms=(time.time() - start) * 1000,
                )

        violations: List[GuardViolation] = []
        lines = content.split("\n")

        for pattern, info in self._compiled_patterns.items():
            for match in pattern.finditer(content):
                line_num = content.count("\n", 0, match.start()) + 1
                code = lines[line_num - 1].strip() if line_num <= len(lines) else ""

                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=self.severity,
                        category=self.category,
                        message=info["message"],
                        file_path=file_path,
                        line_number=line_num,
                        suggestion=info["suggestion"],
                        code_snippet=code,
                    )
                )

        return GuardResult(
            guard_name=self.name,
            passed=len(violations) == 0,
            violations=violations,
            execution_time_ms=(time.time() - start) * 1000,
            files_checked=1,
        )


class PythonShellGuard(Guard):
    """Detects shell/placeholder implementations in Python code."""

    PYTHON_SHELL_PATTERNS: Dict[str, Dict[str, str]] = {
        # NotImplementedError
        r"raise\s+NotImplementedError(?:\(\s*\))?": {
            "message": "NotImplementedError - unimplemented method",
            "suggestion": "Implement the method or remove it from the interface",
        },
        r"raise\s+NotImplementedError\s*\(\s*['\"]": {
            "message": "NotImplementedError with message - still unimplemented",
            "suggestion": "Implement the actual functionality",
        },
        # Pass as sole body
        r"def\s+\w+\s*\([^)]*\)\s*(?:->.*)?:\s*\n\s+pass\s*$": {
            "message": "Function with only 'pass' - placeholder implementation",
            "suggestion": "Implement the function or add a docstring explaining why empty",
        },
        # Pass with TODO/placeholder comment
        r"pass\s*#\s*(?:TODO|placeholder|implement|stub|fixme)": {
            "message": "Pass statement with TODO comment - placeholder implementation",
            "suggestion": "Implement the actual functionality",
        },
        r"def\s+\w+\s*\([^)]*\)\s*(?:->.*)?:\s*\n\s+\.\.\.\s*$": {
            "message": "Function with only '...' - placeholder implementation",
            "suggestion": "Implement the function body",
        },
        # Placeholder returns
        r"return\s+None\s*#\s*(?:TODO|placeholder|implement|stub)": {
            "message": "Return None with placeholder comment",
            "suggestion": "Implement the actual return value logic",
        },
        r"return\s+\[\]\s*#\s*(?:TODO|placeholder|implement|stub)": {
            "message": "Return empty list placeholder",
            "suggestion": "Implement the actual data fetching",
        },
        r"return\s+\{\}\s*#\s*(?:TODO|placeholder|implement|stub)": {
            "message": "Return empty dict placeholder",
            "suggestion": "Implement the actual data structure",
        },
        # Hardcoded mock data
        r"return\s+\[\s*\{[^}]*['\"]id['\"]:\s*\d+": {
            "message": "Returning hardcoded mock data",
            "suggestion": "Fetch data from database or API",
        },
        # Async placeholders
        r"async\s+def\s+\w+\s*\([^)]*\)\s*(?:->.*)?:\s*\n\s+pass": {
            "message": "Async function with only 'pass'",
            "suggestion": "Implement the async logic or remove async keyword",
        },
        # Class method placeholders
        r"def\s+__\w+__\s*\([^)]*\)\s*:\s*\n\s+pass": {
            "message": "Dunder method with only 'pass'",
            "suggestion": "Implement the magic method or remove it",
        },
        # Exception handling that does nothing
        r"except\s+\w+(?:\s+as\s+\w+)?:\s*\n\s+pass": {
            "message": "Exception caught but ignored",
            "suggestion": "Handle the exception: log it, re-raise, or handle gracefully",
        },
    }

    def __init__(self, enabled: bool = True):
        super().__init__(
            name="python_shell",
            description="Detects shell/placeholder implementations in Python code",
            level=GuardLevel.INSTANT,
            category=GuardCategory.SHELL,
            enabled=enabled,
            severity=GuardSeverity.ERROR,
        )

        self._compiled_patterns = {
            re.compile(pattern, re.MULTILINE): info
            for pattern, info in self.PYTHON_SHELL_PATTERNS.items()
        }

        # Only check Python files
        self.add_file_extensions([".py"])

        # Exclude test files and abstract base classes
        self.add_exception("/tests/")
        self.add_exception("test_")
        self.add_exception("_test.py")
        self.add_exception("conftest.py")
        self.add_exception("abc.py")
        self.add_exception("interfaces.py")
        self.add_exception("protocols.py")
        self.add_exception("abstract")

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check for shell implementations in Python code."""
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

        # Check if file defines abstract classes (skip those)
        is_abstract = "ABC" in content or "abstractmethod" in content or "@abstract" in content

        for pattern, info in self._compiled_patterns.items():
            # Skip NotImplementedError check for abstract classes
            if is_abstract and "NotImplementedError" in info["message"]:
                continue

            for match in pattern.finditer(content):
                line_num = content.count("\n", 0, match.start()) + 1
                code = lines[line_num - 1].strip() if line_num <= len(lines) else ""

                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=self.severity,
                        category=self.category,
                        message=info["message"],
                        file_path=file_path,
                        line_number=line_num,
                        suggestion=info["suggestion"],
                        code_snippet=code,
                    )
                )

        return GuardResult(
            guard_name=self.name,
            passed=len(violations) == 0,
            violations=violations,
            execution_time_ms=(time.time() - start) * 1000,
            files_checked=1,
        )


def create_shell_guards() -> List[Guard]:
    """Create all shell component guards."""
    return [
        ShellComponentGuard(),
        PythonShellGuard(),
    ]
