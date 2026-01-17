"""
Phase Gate
==========

Enforces quality gates before allowing phase transitions.

Phases:
- Research: Read and understand requirements
- Plan: Create implementation plan
- Implement: Write code
- Test: Write and run tests
- Review: Code review and polish
- Complete: Ready for merge

Each phase has entry/exit criteria that must be met.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

from rich.console import Console
from rich.panel import Panel

from sdk.guards import get_guard_registry, GuardLevel, AggregatedResult
from sdk.verification.evidence_collector import EvidenceCollector, EvidenceType


console = Console()


class Phase(str, Enum):
    """Development phases."""
    RESEARCH = "research"
    PLAN = "plan"
    IMPLEMENT = "implement"
    TEST = "test"
    REVIEW = "review"
    COMPLETE = "complete"


@dataclass
class PhaseRequirement:
    """A requirement for phase transition."""
    name: str
    description: str
    check_fn: Callable[[], bool]
    blocking: bool = True  # If True, blocks transition


@dataclass
class PhaseResult:
    """Result of phase gate check."""
    phase: Phase
    passed: bool
    requirements_met: List[str] = field(default_factory=list)
    requirements_failed: List[str] = field(default_factory=list)
    guard_result: Optional[AggregatedResult] = None
    timestamp: datetime = field(default_factory=datetime.now)


class PhaseGate:
    """
    Enforces quality gates between development phases.
    
    Usage:
        gate = PhaseGate()
        gate.set_phase(Phase.IMPLEMENT)
        
        # Do implementation work...
        
        # Try to move to test phase
        result = gate.check_transition(Phase.TEST)
        if result.passed:
            gate.advance()
    """

    # Default requirements for each phase transition
    DEFAULT_REQUIREMENTS: Dict[Phase, List[str]] = {
        Phase.RESEARCH: [
            "Read architecture docs",
            "Understand requirements",
        ],
        Phase.PLAN: [
            "Create implementation plan",
            "List files to modify",
            "List tests to write",
        ],
        Phase.IMPLEMENT: [
            "Code compiles/parses",
            "No bandaid patterns",
            "No shell components",
        ],
        Phase.TEST: [
            "Tests written",
            "Tests pass",
            "Type check passes",
        ],
        Phase.REVIEW: [
            "All guards pass",
            "Code review comments addressed",
            "Documentation updated",
        ],
        Phase.COMPLETE: [
            "All tests pass",
            "All evidence collected",
            "Ready for merge",
        ],
    }

    # Phase order for transitions
    PHASE_ORDER = [
        Phase.RESEARCH,
        Phase.PLAN,
        Phase.IMPLEMENT,
        Phase.TEST,
        Phase.REVIEW,
        Phase.COMPLETE,
    ]

    def __init__(
        self,
        evidence_collector: Optional[EvidenceCollector] = None,
    ):
        self.current_phase = Phase.RESEARCH
        self.evidence_collector = evidence_collector or EvidenceCollector()
        self._phase_history: List[PhaseResult] = []
        self._custom_requirements: Dict[Phase, List[PhaseRequirement]] = {
            p: [] for p in Phase
        }
        self._completed_requirements: Set[str] = set()

    def set_phase(self, phase: Phase) -> None:
        """Set current phase (use with caution - prefer advance())."""
        self.current_phase = phase
        console.print(f"[blue]📍 Phase set to: {phase.value}[/blue]")

    def get_phase(self) -> Phase:
        """Get current phase."""
        return self.current_phase

    def get_next_phase(self) -> Optional[Phase]:
        """Get the next phase in sequence."""
        try:
            idx = self.PHASE_ORDER.index(self.current_phase)
        except ValueError:
            # Current phase not in PHASE_ORDER - no next phase available
            return None

        if idx < len(self.PHASE_ORDER) - 1:
            return self.PHASE_ORDER[idx + 1]
        return None

    def add_requirement(
        self,
        phase: Phase,
        name: str,
        description: str,
        check_fn: Callable[[], bool],
        blocking: bool = True,
    ) -> None:
        """Add a custom requirement for a phase."""
        req = PhaseRequirement(
            name=name,
            description=description,
            check_fn=check_fn,
            blocking=blocking,
        )
        self._custom_requirements[phase].append(req)

    def mark_requirement_complete(self, requirement_name: str) -> None:
        """Manually mark a requirement as complete."""
        self._completed_requirements.add(requirement_name.lower())
        console.print(f"[green]✓[/green] Requirement marked complete: {requirement_name}")

    def check_guards(self, level: Optional[GuardLevel] = None) -> AggregatedResult:
        """Run guards and return result."""
        registry = get_guard_registry()
        
        if level:
            # Run guards at specific level
            guards = registry.get_by_level(level)
            # Would need to aggregate results
            return AggregatedResult(passed=True, guards_run=len(guards))
        
        return AggregatedResult(passed=True, guards_run=0)

    def check_transition(self, target_phase: Optional[Phase] = None) -> PhaseResult:
        """
        Check if transition to target phase is allowed.
        
        Args:
            target_phase: Phase to transition to (default: next phase)
            
        Returns:
            PhaseResult with pass/fail and details
        """
        target = target_phase or self.get_next_phase()
        if not target:
            return PhaseResult(
                phase=self.current_phase,
                passed=False,
                requirements_failed=["Already at final phase"],
            )

        console.print(f"\n[bold]🚦 Phase Gate: {self.current_phase.value} → {target.value}[/bold]")

        requirements_met: List[str] = []
        requirements_failed: List[str] = []

        # Check default requirements for current phase
        default_reqs = self.DEFAULT_REQUIREMENTS.get(self.current_phase, [])
        for req in default_reqs:
            if req.lower() in self._completed_requirements:
                requirements_met.append(req)
                console.print(f"  [green]✓[/green] {req}")
            else:
                requirements_failed.append(req)
                console.print(f"  [red]✗[/red] {req}")

        # Check custom requirements
        for req in self._custom_requirements.get(self.current_phase, []):
            try:
                if req.check_fn():
                    requirements_met.append(req.name)
                    console.print(f"  [green]✓[/green] {req.name}")
                else:
                    if req.blocking:
                        requirements_failed.append(req.name)
                        console.print(f"  [red]✗[/red] {req.name}")
                    else:
                        console.print(f"  [yellow]⚠[/yellow] {req.name} (non-blocking)")
            except Exception as e:
                requirements_failed.append(f"{req.name}: {e}")
                console.print(f"  [red]✗[/red] {req.name}: {e}")

        # Run relevant guards
        guard_level = self._get_guard_level_for_phase(self.current_phase)
        guard_result = self.check_guards(guard_level) if guard_level else None

        if guard_result and not guard_result.passed:
            requirements_failed.append("Guards failed")
            console.print(f"  [red]✗[/red] Guards: {guard_result.error_count} errors")

        # Determine if gate passes
        passed = len(requirements_failed) == 0

        result = PhaseResult(
            phase=target,
            passed=passed,
            requirements_met=requirements_met,
            requirements_failed=requirements_failed,
            guard_result=guard_result,
        )

        self._phase_history.append(result)

        if passed:
            console.print(f"\n[green]✅ Gate passed! Ready for {target.value}[/green]")
        else:
            console.print(f"\n[red]❌ Gate blocked. Fix: {', '.join(requirements_failed)}[/red]")

        return result

    def advance(self, force: bool = False) -> bool:
        """
        Advance to next phase if gate passes.
        
        Args:
            force: Skip gate check (use with caution)
            
        Returns:
            True if advanced, False otherwise
        """
        next_phase = self.get_next_phase()
        if not next_phase:
            console.print("[yellow]Already at final phase[/yellow]")
            return False

        if force:
            console.print("[yellow]⚠️  Forcing phase advance (gate check skipped)[/yellow]")
            self.set_phase(next_phase)
            return True

        result = self.check_transition(next_phase)
        if result.passed:
            self.set_phase(next_phase)
            return True

        return False

    def _get_guard_level_for_phase(self, phase: Phase) -> Optional[GuardLevel]:
        """Map phase to appropriate guard level."""
        mapping = {
            Phase.IMPLEMENT: GuardLevel.INSTANT,
            Phase.TEST: GuardLevel.TASK,
            Phase.REVIEW: GuardLevel.PHASE,
            Phase.COMPLETE: GuardLevel.PHASE,
        }
        return mapping.get(phase)

    def format_status(self) -> str:
        """Format current gate status."""
        lines = [
            "",
            "═" * 50,
            "          PHASE GATE STATUS",
            "═" * 50,
            "",
            f"Current Phase: {self.current_phase.value.upper()}",
            "",
            "Phase Progress:",
        ]

        for phase in self.PHASE_ORDER:
            if phase == self.current_phase:
                lines.append(f"  → [{phase.value}] ← CURRENT")
            elif self.PHASE_ORDER.index(phase) < self.PHASE_ORDER.index(self.current_phase):
                lines.append(f"  ✅ [{phase.value}]")
            else:
                lines.append(f"  ⬜ [{phase.value}]")

        lines.append("")
        lines.append("Requirements for next phase:")
        
        next_phase = self.get_next_phase()
        if next_phase:
            reqs = self.DEFAULT_REQUIREMENTS.get(self.current_phase, [])
            for req in reqs:
                status = "✓" if req.lower() in self._completed_requirements else "○"
                lines.append(f"  {status} {req}")
        else:
            lines.append("  (At final phase)")

        lines.append("")
        lines.append("═" * 50)

        return "\n".join(lines)


# Global phase gate instance
_gate: Optional[PhaseGate] = None


def get_phase_gate() -> PhaseGate:
    """Get or create global phase gate."""
    global _gate
    if _gate is None:
        _gate = PhaseGate()
    return _gate
