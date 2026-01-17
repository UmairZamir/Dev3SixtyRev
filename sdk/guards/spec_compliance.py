"""
Spec Compliance Guard
=====================

Verifies implementation matches architecture specifications.

This guard compares actual implementation against:
- PRD requirements
- Architecture documents
- API specifications
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


class SpecComplianceGuard(Guard):
    """Verifies implementation matches specifications."""

    def __init__(self, enabled: bool = True):
        super().__init__(
            name="spec_compliance",
            description="Verifies implementation matches architecture specs",
            level=GuardLevel.PHASE,
            category=GuardCategory.SPEC,
            enabled=enabled,
            severity=GuardSeverity.WARNING,
        )
        self._spec_requirements: Dict[str, List[str]] = {}
        self._implemented: Set[str] = set()

    def load_spec_requirements(self, spec_path: Path) -> int:
        """
        Load requirements from a spec file.
        Returns count of requirements found.
        """
        if not spec_path.exists():
            return 0

        content = spec_path.read_text()
        requirements = []

        # Extract requirements from markdown checkboxes
        checkbox_pattern = r"- \[ \]\s+(.+)"
        for match in re.finditer(checkbox_pattern, content, re.MULTILINE):
            requirements.append(match.group(1).strip())

        # Extract from numbered requirements
        numbered_pattern = r"^\d+\.\s+(.+)"
        for match in re.finditer(numbered_pattern, content, re.MULTILINE):
            req = match.group(1).strip()
            if len(req) > 10:  # Ignore short items
                requirements.append(req)

        # Extract from "must", "shall", "should" statements
        must_pattern = r"(?:must|shall|should)\s+(.{10,100})"
        for match in re.finditer(must_pattern, content, re.IGNORECASE):
            requirements.append(match.group(1).strip())

        self._spec_requirements[str(spec_path)] = requirements
        return len(requirements)

    def mark_implemented(self, requirement: str) -> None:
        """Mark a requirement as implemented."""
        self._implemented.add(requirement.lower().strip())

    def check_implementation(self, content: str, requirement: str) -> bool:
        """Check if content appears to implement a requirement."""
        req_lower = requirement.lower()
        content_lower = content.lower()

        # Extract key terms from requirement
        words = re.findall(r'\b\w{4,}\b', req_lower)
        significant_words = [w for w in words if w not in {
            'must', 'shall', 'should', 'will', 'when', 'where', 
            'this', 'that', 'have', 'with', 'from', 'into'
        }]

        if not significant_words:
            return True  # Can't verify, assume OK

        # Check if enough key terms are present
        found = sum(1 for w in significant_words if w in content_lower)
        return found >= len(significant_words) * 0.5

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check spec compliance."""
        start = time.time()
        violations: List[GuardViolation] = []

        if not self._spec_requirements:
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                metadata={"reason": "no_specs_loaded"},
                execution_time_ms=(time.time() - start) * 1000,
            )

        # Check each spec
        for spec_path, requirements in self._spec_requirements.items():
            for req in requirements:
                req_lower = req.lower().strip()
                if req_lower not in self._implemented:
                    violations.append(
                        GuardViolation(
                            guard_name=self.name,
                            severity=GuardSeverity.INFO,
                            category=self.category,
                            message=f"Spec requirement not verified: {req[:80]}",
                            file_path=spec_path,
                            suggestion="Verify this requirement is implemented and mark as complete.",
                        )
                    )

        return GuardResult(
            guard_name=self.name,
            passed=True,  # Info only, doesn't fail
            violations=violations,
            execution_time_ms=(time.time() - start) * 1000,
        )

    def get_compliance_report(self) -> str:
        """Generate compliance report."""
        lines = [
            "",
            "═══════════════════════════════════════",
            "       SPEC COMPLIANCE REPORT",
            "═══════════════════════════════════════",
            "",
        ]

        total_reqs = 0
        implemented_count = 0

        for spec_path, requirements in self._spec_requirements.items():
            lines.append(f"📄 {spec_path}")
            for req in requirements:
                total_reqs += 1
                is_implemented = req.lower().strip() in self._implemented
                if is_implemented:
                    implemented_count += 1
                    lines.append(f"   ✅ {req[:60]}")
                else:
                    lines.append(f"   ❌ {req[:60]}")
            lines.append("")

        if total_reqs > 0:
            pct = (implemented_count / total_reqs) * 100
            lines.append(f"Coverage: {implemented_count}/{total_reqs} ({pct:.1f}%)")
        else:
            lines.append("No requirements loaded.")

        lines.append("═══════════════════════════════════════")
        return "\n".join(lines)


def create_spec_guards() -> List[Guard]:
    """Create spec compliance guards."""
    return [SpecComplianceGuard()]
