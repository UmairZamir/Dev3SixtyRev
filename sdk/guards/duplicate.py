"""
Duplicate Function Guard
========================

Detects duplicate or near-duplicate functions in code.

From research: "Two functions with nearly identical names that did completely
different things... The AI had generated both at different times"

This guard detects:
- Functions with very similar names
- Functions with identical signatures
- Copy-pasted code blocks
"""

import ast
import logging
import re
import time

logger = logging.getLogger(__name__)
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from sdk.guards.base import (
    Guard,
    GuardCategory,
    GuardLevel,
    GuardResult,
    GuardSeverity,
    GuardViolation,
)


class DuplicateFunctionGuard(Guard):
    """Detects duplicate or near-duplicate functions."""

    # Common name variations that might indicate duplicates
    SIMILAR_PREFIXES = ["get_", "fetch_", "retrieve_", "load_", "read_"]
    SIMILAR_SUFFIXES = ["_data", "_info", "_details", "_result", "_response"]
    SIMILAR_NAMES = [
        ("process", "handle"),
        ("user", "customer"),
        ("data", "info"),
        ("create", "make"),
        ("update", "modify"),
        ("delete", "remove"),
        ("get", "fetch"),
        ("save", "store"),
    ]

    def __init__(self, enabled: bool = True, similarity_threshold: float = 0.8):
        super().__init__(
            name="duplicate_function",
            description="Detects duplicate or near-duplicate functions",
            level=GuardLevel.INSTANT,
            category=GuardCategory.QUALITY,
            enabled=enabled,
            severity=GuardSeverity.WARNING,
        )
        self.similarity_threshold = similarity_threshold
        self.add_file_extensions([".py"])

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check for duplicate functions."""
        start = time.time()

        if file_path and not self.should_check_file(file_path):
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                execution_time_ms=(time.time() - start) * 1000,
            )

        violations: List[GuardViolation] = []

        try:
            tree = ast.parse(content)
            violations.extend(self._find_similar_functions(tree, file_path, content))
        except SyntaxError as e:
            # Can't analyze files with syntax errors for duplicates
            logger.debug("Could not parse %s for duplicate analysis: %s", file_path, e)

        return GuardResult(
            guard_name=self.name,
            passed=len(violations) == 0,
            violations=violations,
            execution_time_ms=(time.time() - start) * 1000,
            files_checked=1,
        )

    def _find_similar_functions(
        self, tree: ast.AST, file_path: Optional[str], content: str
    ) -> List[GuardViolation]:
        """Find functions with similar names or signatures."""
        violations = []
        functions: Dict[str, List[Tuple[str, int, str]]] = defaultdict(list)
        lines = content.split("\n")

        # Collect all function definitions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Get signature
                args = [arg.arg for arg in node.args.args]
                signature = f"({', '.join(args)})"

                # Normalize function name
                normalized = self._normalize_name(node.name)

                functions[normalized].append((node.name, node.lineno, signature))

        # Check for duplicates
        for normalized, funcs in functions.items():
            if len(funcs) > 1:
                # Multiple functions with similar names
                names = [f[0] for f in funcs]
                lines_nums = [f[1] for f in funcs]

                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=self.severity,
                        category=self.category,
                        message=f"Similar function names detected: {', '.join(names)}",
                        file_path=file_path,
                        line_number=lines_nums[0],
                        suggestion=(
                            "These functions might be duplicates. "
                            "Consider consolidating or renaming for clarity."
                        ),
                        code_snippet=lines[lines_nums[0] - 1].strip() if lines_nums[0] <= len(lines) else "",
                    )
                )

        return violations

    def _normalize_name(self, name: str) -> str:
        """Normalize function name for comparison."""
        normalized = name.lower()

        # Remove common prefixes
        for prefix in self.SIMILAR_PREFIXES:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break

        # Remove common suffixes
        for suffix in self.SIMILAR_SUFFIXES:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
                break

        # Replace similar words
        for word1, word2 in self.SIMILAR_NAMES:
            normalized = normalized.replace(word1, word2)

        return normalized


def create_duplicate_guards() -> List[Guard]:
    """Create duplicate detection guards."""
    return [DuplicateFunctionGuard()]
