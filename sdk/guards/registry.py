"""
Guard Registry
===============

Central registry for all guards in the 3SixtyRev SDK.

The registry:
- Manages guard lifecycle (register, enable, disable)
- Provides guard lookup by name, level, or category
- Runs guards and aggregates results
- Initializes default guards on startup

Usage:
    registry = GuardRegistry(auto_init=True)
    result = registry.run_all(code, "path/to/file.py")
    print(result.format())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
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


@dataclass
class AggregatedResult:
    """Aggregated result from multiple guards."""

    passed: bool = True
    violations: List[GuardViolation] = field(default_factory=list)
    execution_time_ms: float = 0.0
    guards_run: int = 0
    files_checked: int = 0

    @property
    def error_count(self) -> int:
        """Count of ERROR-level violations."""
        return sum(1 for v in self.violations if v.severity == GuardSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of WARNING-level violations."""
        return sum(1 for v in self.violations if v.severity == GuardSeverity.WARNING)

    @property
    def info_count(self) -> int:
        """Count of INFO-level violations."""
        return sum(1 for v in self.violations if v.severity == GuardSeverity.INFO)

    def get_by_category(self, category: GuardCategory) -> List[GuardViolation]:
        """Get violations by category."""
        return [v for v in self.violations if v.category == category]

    def format(self) -> str:
        """Format the result for display."""
        lines = [
            "",
            "═══════════════════════════════════════════════════════════",
            "                    GUARD RESULTS",
            "═══════════════════════════════════════════════════════════",
            "",
        ]

        if self.passed:
            extra = ""
            if self.warning_count:
                extra = f" ({self.warning_count} warnings)"
            elif self.info_count:
                extra = f" ({self.info_count} suggestions)"
            lines.append(
                f"✅ All {self.guards_run} guards passed ({self.execution_time_ms:.1f}ms){extra}"
            )
        else:
            lines.append(f"❌ {self.error_count} error(s), {self.warning_count} warning(s)")
            lines.append("")

            # Group violations by category
            by_category: Dict[GuardCategory, List[GuardViolation]] = {}
            for v in self.violations:
                if v.category not in by_category:
                    by_category[v.category] = []
                by_category[v.category].append(v)

            for category, violations in by_category.items():
                lines.append(f"─── {category.value.upper()} ───")
                for v in violations[:5]:  # Show first 5 per category
                    lines.append(f"  {v}")
                if len(violations) > 5:
                    lines.append(f"  ... and {len(violations) - 5} more")
                lines.append("")

        lines.append("═══════════════════════════════════════════════════════════")
        lines.append(
            f"Summary: {self.guards_run} guards | {self.files_checked} files | "
            f"{self.execution_time_ms:.1f}ms"
        )
        lines.append("═══════════════════════════════════════════════════════════")

        return "\n".join(lines)

    def format_short(self) -> str:
        """Format a short summary."""
        if self.passed:
            return f"✅ {self.guards_run} guards passed ({self.execution_time_ms:.0f}ms)"
        return f"❌ {self.error_count} errors, {self.warning_count} warnings"


class GuardRegistry:
    """Central registry for all guards."""

    def __init__(self, auto_init: bool = True):
        self._guards: Dict[str, Guard] = {}
        self._guards_by_level: Dict[GuardLevel, List[Guard]] = {level: [] for level in GuardLevel}
        self._guards_by_category: Dict[GuardCategory, List[Guard]] = {
            cat: [] for cat in GuardCategory
        }
        self._initialized = False

        if auto_init:
            self.initialize_default_guards()

    def register(self, guard: Guard) -> None:
        """Register a guard."""
        self._guards[guard.name] = guard
        self._guards_by_level[guard.level].append(guard)
        self._guards_by_category[guard.category].append(guard)

    def unregister(self, name: str) -> bool:
        """Unregister a guard by name."""
        guard = self._guards.pop(name, None)
        if guard:
            self._guards_by_level[guard.level].remove(guard)
            self._guards_by_category[guard.category].remove(guard)
            return True
        return False

    def get(self, name: str) -> Optional[Guard]:
        """Get a guard by name."""
        return self._guards.get(name)

    def get_by_level(self, level: GuardLevel) -> List[Guard]:
        """Get all enabled guards at a level."""
        return [g for g in self._guards_by_level[level] if g.enabled]

    def get_by_category(self, category: GuardCategory) -> List[Guard]:
        """Get all enabled guards in a category."""
        return [g for g in self._guards_by_category[category] if g.enabled]

    def get_all(self) -> List[Guard]:
        """Get all registered guards."""
        return list(self._guards.values())

    def get_enabled(self) -> List[Guard]:
        """Get all enabled guards."""
        return [g for g in self._guards.values() if g.enabled]

    def enable(self, name: str) -> bool:
        """Enable a guard by name."""
        guard = self._guards.get(name)
        if guard:
            guard.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a guard by name."""
        guard = self._guards.get(name)
        if guard:
            guard.enabled = False
            return True
        return False

    def enable_category(self, category: GuardCategory) -> int:
        """Enable all guards in a category. Returns count enabled."""
        count = 0
        for guard in self._guards_by_category[category]:
            guard.enabled = True
            count += 1
        return count

    def disable_category(self, category: GuardCategory) -> int:
        """Disable all guards in a category. Returns count disabled."""
        count = 0
        for guard in self._guards_by_category[category]:
            guard.enabled = False
            count += 1
        return count

    def run_guard(
        self, name: str, content: str, file_path: Optional[str] = None
    ) -> Optional[GuardResult]:
        """Run a specific guard by name."""
        guard = self._guards.get(name)
        if guard and guard.enabled:
            return guard.check(content, file_path)
        return None

    def run_level(
        self, level: GuardLevel, content: str, file_path: Optional[str] = None
    ) -> AggregatedResult:
        """Run all enabled guards at a specific level."""
        return self._run_guards(self.get_by_level(level), content, file_path)

    def run_category(
        self, category: GuardCategory, content: str, file_path: Optional[str] = None
    ) -> AggregatedResult:
        """Run all enabled guards in a category."""
        return self._run_guards(self.get_by_category(category), content, file_path)

    def run_instant_guards(
        self, content: str, file_path: Optional[str] = None
    ) -> AggregatedResult:
        """Run all INSTANT level guards."""
        return self.run_level(GuardLevel.INSTANT, content, file_path)

    def run_task_guards(self, content: str, file_path: Optional[str] = None) -> AggregatedResult:
        """Run all TASK level guards."""
        return self.run_level(GuardLevel.TASK, content, file_path)

    def run_phase_guards(self, content: str, file_path: Optional[str] = None) -> AggregatedResult:
        """Run all PHASE level guards."""
        return self.run_level(GuardLevel.PHASE, content, file_path)

    def run_all(self, content: str, file_path: Optional[str] = None) -> AggregatedResult:
        """Run all enabled guards."""
        return self._run_guards(self.get_enabled(), content, file_path)

    def run_on_file(self, file_path: Path) -> AggregatedResult:
        """Run all enabled guards on a file."""
        if not file_path.exists():
            return AggregatedResult(passed=True, guards_run=0)

        try:
            content = file_path.read_text(encoding="utf-8")
            return self.run_all(content, str(file_path))
        except UnicodeDecodeError:
            return AggregatedResult(passed=True, guards_run=0)

    def run_on_files(self, file_paths: List[Path]) -> AggregatedResult:
        """Run all enabled guards on multiple files."""
        start = time.time()
        all_violations: List[GuardViolation] = []
        guards_run: Set[str] = set()
        files_checked = 0

        for file_path in file_paths:
            result = self.run_on_file(file_path)
            all_violations.extend(result.violations)
            guards_run.update(g.name for g in self.get_enabled())
            if result.files_checked:
                files_checked += 1

        has_errors = any(v.severity == GuardSeverity.ERROR for v in all_violations)

        return AggregatedResult(
            passed=not has_errors,
            violations=all_violations,
            execution_time_ms=(time.time() - start) * 1000,
            guards_run=len(guards_run),
            files_checked=files_checked,
        )

    def _run_guards(
        self, guards: List[Guard], content: str, file_path: Optional[str]
    ) -> AggregatedResult:
        """Run a list of guards and aggregate results."""
        start = time.time()
        all_violations: List[GuardViolation] = []
        guards_run = 0

        for guard in guards:
            result = guard.check(content, file_path)
            all_violations.extend(result.violations)
            guards_run += 1

        has_errors = any(v.severity == GuardSeverity.ERROR for v in all_violations)

        return AggregatedResult(
            passed=not has_errors,
            violations=all_violations,
            execution_time_ms=(time.time() - start) * 1000,
            guards_run=guards_run,
            files_checked=1 if file_path else 0,
        )

    def list_guards(self) -> List[Dict]:
        """List all guards with their status."""
        return [
            {
                "name": g.name,
                "description": g.description,
                "level": g.level.value,
                "category": g.category.value,
                "enabled": g.enabled,
                "severity": g.severity.value,
            }
            for g in self._guards.values()
        ]

    def format_guards_table(self) -> str:
        """Format guards as a table for display."""
        lines = [
            "",
            "┌────────────────────────────┬──────────┬──────────────┬─────────┐",
            "│ Guard                      │ Level    │ Category     │ Enabled │",
            "├────────────────────────────┼──────────┼──────────────┼─────────┤",
        ]

        for guard in sorted(self._guards.values(), key=lambda g: (g.level.value, g.name)):
            enabled = "✅" if guard.enabled else "❌"
            name = guard.name[:26].ljust(26)
            level = guard.level.value[:8].ljust(8)
            category = guard.category.value[:12].ljust(12)
            lines.append(f"│ {name} │ {level} │ {category} │   {enabled}    │")

        lines.append("└────────────────────────────┴──────────┴──────────────┴─────────┘")
        lines.append(f"\nTotal: {len(self._guards)} guards ({len(self.get_enabled())} enabled)")

        return "\n".join(lines)

    def initialize_default_guards(self) -> None:
        """Initialize with default guards based on research."""
        if self._initialized:
            return

        # =====================================================
        # TIER 1: INSTANT guards (every edit, <100ms)
        # =====================================================

        # Bandaid patterns - proven from old SDK
        from sdk.guards.bandaid import (
            BandaidPatternsGuard,
            HardcodedValueGuard,
            PrintStatementGuard,
        )

        self.register(BandaidPatternsGuard())
        self.register(HardcodedValueGuard())
        self.register(PrintStatementGuard())

        # Shell components - proven from old SDK
        from sdk.guards.shell_component import ShellComponentGuard, PythonShellGuard

        self.register(ShellComponentGuard())
        self.register(PythonShellGuard())

        # Security - proven from old SDK
        from sdk.guards.security import SecurityGuard

        self.register(SecurityGuard())

        # Hallucination detection - NEW based on research
        from sdk.guards.hallucination import HallucinationGuard

        self.register(HallucinationGuard())

        # Duplicate function detection - NEW based on research
        from sdk.guards.duplicate import DuplicateFunctionGuard

        self.register(DuplicateFunctionGuard())

        # =====================================================
        # TIER 2: TASK guards (after each task, <30s)
        # =====================================================

        # Context loss detection - NEW based on research
        from sdk.guards.context_loss import ContextLossGuard

        self.register(ContextLossGuard())

        # NOTE: OverEngineeringGuard removed - extensive engineering is appropriate
        # for building a robust, dynamic conversational AI platform

        # Scope creep detection - NEW based on research
        from sdk.guards.scope import ScopeCreepGuard

        self.register(ScopeCreepGuard())

        # =====================================================
        # TIER 3: PHASE guards (end of phase, <5min)
        # =====================================================

        # Evidence required - NEW based on research
        from sdk.guards.evidence import EvidenceRequiredGuard

        self.register(EvidenceRequiredGuard())

        # Spec compliance - NEW based on research
        from sdk.guards.spec_compliance import SpecComplianceGuard

        self.register(SpecComplianceGuard())

        # E2E test enforcement - NEW based on research
        from sdk.guards.test_enforcement import E2ETestEnforcementGuard

        self.register(E2ETestEnforcementGuard())

        # E2E guard - No shell components
        from sdk.guards.e2e import E2EGuard

        self.register(E2EGuard())

        self._initialized = True


# Global registry instance
_registry: Optional[GuardRegistry] = None


def get_guard_registry(auto_init: bool = True) -> GuardRegistry:
    """Get or create the global guard registry."""
    global _registry
    if _registry is None:
        _registry = GuardRegistry(auto_init=auto_init)
    return _registry


def register_guard(guard: Guard) -> None:
    """Register a guard with the global registry."""
    get_guard_registry().register(guard)


def run_guards(content: str, file_path: Optional[str] = None) -> AggregatedResult:
    """Run all guards using the global registry."""
    return get_guard_registry().run_all(content, file_path)


# Export for backward compatibility
__all__ = [
    "GuardRegistry",
    "AggregatedResult",
    "get_guard_registry",
    "register_guard",
    "run_guards",
]
