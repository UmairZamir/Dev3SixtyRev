"""
SDK Modes
=========

Development modes that control SDK behavior.

Modes:
- chat: Free conversation, minimal restrictions
- plan: Planning phase, read-only exploration
- build: Active implementation with guards
- review: Code review mode with strict checks
- test: Test writing and execution
- migrate: Migration tasks with extra caution
- debug: Debugging with relaxed restrictions
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

from rich.console import Console


console = Console()


class Mode(str, Enum):
    """Development modes."""
    CHAT = "chat"
    PLAN = "plan"
    BUILD = "build"
    REVIEW = "review"
    TEST = "test"
    MIGRATE = "migrate"
    DEBUG = "debug"


@dataclass
class ModeCapabilities:
    """Capabilities for each mode."""
    can_read_files: bool = True
    can_write_files: bool = False
    can_delete_files: bool = False
    can_run_commands: bool = False
    can_run_tests: bool = False
    can_commit: bool = False
    can_push: bool = False
    guards_enabled: bool = True
    evidence_required: bool = True
    phase_gates_enabled: bool = True
    allowed_file_patterns: Set[str] = field(default_factory=set)
    blocked_file_patterns: Set[str] = field(default_factory=set)


# Default capabilities per mode
MODE_CAPABILITIES: Dict[Mode, ModeCapabilities] = {
    Mode.CHAT: ModeCapabilities(
        can_read_files=True,
        can_write_files=False,
        can_delete_files=False,
        can_run_commands=False,
        can_run_tests=False,
        can_commit=False,
        guards_enabled=False,
        evidence_required=False,
        phase_gates_enabled=False,
    ),
    Mode.PLAN: ModeCapabilities(
        can_read_files=True,
        can_write_files=False,
        can_delete_files=False,
        can_run_commands=False,
        can_run_tests=False,
        can_commit=False,
        guards_enabled=False,
        evidence_required=False,
        phase_gates_enabled=True,
    ),
    Mode.BUILD: ModeCapabilities(
        can_read_files=True,
        can_write_files=True,
        can_delete_files=False,
        can_run_commands=True,
        can_run_tests=True,
        can_commit=True,
        can_push=False,
        guards_enabled=True,
        evidence_required=True,
        phase_gates_enabled=True,
    ),
    Mode.REVIEW: ModeCapabilities(
        can_read_files=True,
        can_write_files=True,
        can_delete_files=False,
        can_run_commands=True,
        can_run_tests=True,
        can_commit=True,
        guards_enabled=True,
        evidence_required=True,
        phase_gates_enabled=True,
    ),
    Mode.TEST: ModeCapabilities(
        can_read_files=True,
        can_write_files=True,  # Can write test files
        can_delete_files=False,
        can_run_commands=True,
        can_run_tests=True,
        can_commit=True,
        guards_enabled=True,
        evidence_required=True,
        phase_gates_enabled=True,
        allowed_file_patterns={"test_*.py", "*_test.py", "tests/"},
    ),
    Mode.MIGRATE: ModeCapabilities(
        can_read_files=True,
        can_write_files=True,
        can_delete_files=True,  # Migrations may delete
        can_run_commands=True,
        can_run_tests=True,
        can_commit=True,
        guards_enabled=True,
        evidence_required=True,
        phase_gates_enabled=True,
    ),
    Mode.DEBUG: ModeCapabilities(
        can_read_files=True,
        can_write_files=True,
        can_delete_files=False,
        can_run_commands=True,
        can_run_tests=True,
        can_commit=False,
        guards_enabled=False,  # Relaxed for debugging
        evidence_required=False,
        phase_gates_enabled=False,
    ),
}


class ModeManager:
    """
    Manages development modes.
    
    Usage:
        manager = ModeManager()
        manager.set_mode(Mode.BUILD)
        
        if manager.can_write():
            # Write file
            pass
    """

    def __init__(self, initial_mode: Mode = Mode.CHAT):
        self._mode = initial_mode
        self._mode_history: List[Mode] = []

    @property
    def mode(self) -> Mode:
        """Get current mode."""
        return self._mode

    @property
    def capabilities(self) -> ModeCapabilities:
        """Get capabilities for current mode."""
        return MODE_CAPABILITIES[self._mode]

    def set_mode(self, mode: Mode) -> None:
        """Set current mode."""
        if mode != self._mode:
            self._mode_history.append(self._mode)
            self._mode = mode
            console.print(f"[blue]🔄 Mode changed to: {mode.value}[/blue]")
            self._print_capabilities()

    def _print_capabilities(self) -> None:
        """Print current mode capabilities."""
        caps = self.capabilities
        console.print(f"   [dim]Capabilities: ", end="")
        if caps.can_write_files:
            console.print("write ", end="")
        if caps.can_run_commands:
            console.print("run ", end="")
        if caps.can_commit:
            console.print("commit ", end="")
        if caps.guards_enabled:
            console.print("guards ", end="")
        console.print("[/dim]")

    def previous_mode(self) -> Optional[Mode]:
        """Get previous mode."""
        return self._mode_history[-1] if self._mode_history else None

    def restore_previous(self) -> bool:
        """Restore previous mode."""
        if self._mode_history:
            self._mode = self._mode_history.pop()
            console.print(f"[blue]↩️  Restored mode: {self._mode.value}[/blue]")
            return True
        return False

    # Capability checks
    def can_read(self) -> bool:
        """Check if reading files is allowed."""
        return self.capabilities.can_read_files

    def can_write(self, file_path: Optional[str] = None) -> bool:
        """Check if writing files is allowed."""
        if not self.capabilities.can_write_files:
            return False

        if file_path and self.capabilities.allowed_file_patterns:
            # Check against allowed patterns
            from fnmatch import fnmatch
            return any(
                fnmatch(file_path, pattern)
                for pattern in self.capabilities.allowed_file_patterns
            )

        return True

    def can_delete(self) -> bool:
        """Check if deleting files is allowed."""
        return self.capabilities.can_delete_files

    def can_run_commands(self) -> bool:
        """Check if running commands is allowed."""
        return self.capabilities.can_run_commands

    def can_run_tests(self) -> bool:
        """Check if running tests is allowed."""
        return self.capabilities.can_run_tests

    def can_commit(self) -> bool:
        """Check if committing is allowed."""
        return self.capabilities.can_commit

    def can_push(self) -> bool:
        """Check if pushing is allowed."""
        return self.capabilities.can_push

    def guards_enabled(self) -> bool:
        """Check if guards are enabled."""
        return self.capabilities.guards_enabled

    def evidence_required(self) -> bool:
        """Check if evidence is required."""
        return self.capabilities.evidence_required

    def phase_gates_enabled(self) -> bool:
        """Check if phase gates are enabled."""
        return self.capabilities.phase_gates_enabled

    def check_action(self, action: str) -> bool:
        """Check if an action is allowed in current mode."""
        action_checks = {
            "read": self.can_read,
            "write": self.can_write,
            "delete": self.can_delete,
            "run": self.can_run_commands,
            "test": self.can_run_tests,
            "commit": self.can_commit,
            "push": self.can_push,
        }
        check = action_checks.get(action.lower())
        return check() if check else False

    def format_status(self) -> str:
        """Format current mode status."""
        caps = self.capabilities
        lines = [
            "",
            f"Mode: {self._mode.value.upper()}",
            "",
            "Capabilities:",
            f"  Read files:    {'✅' if caps.can_read_files else '❌'}",
            f"  Write files:   {'✅' if caps.can_write_files else '❌'}",
            f"  Delete files:  {'✅' if caps.can_delete_files else '❌'}",
            f"  Run commands:  {'✅' if caps.can_run_commands else '❌'}",
            f"  Run tests:     {'✅' if caps.can_run_tests else '❌'}",
            f"  Commit:        {'✅' if caps.can_commit else '❌'}",
            f"  Push:          {'✅' if caps.can_push else '❌'}",
            "",
            "Enforcement:",
            f"  Guards:        {'✅' if caps.guards_enabled else '❌'}",
            f"  Evidence:      {'✅' if caps.evidence_required else '❌'}",
            f"  Phase gates:   {'✅' if caps.phase_gates_enabled else '❌'}",
        ]
        return "\n".join(lines)


# Global mode manager
_manager: Optional[ModeManager] = None


def get_mode_manager() -> ModeManager:
    """Get or create global mode manager."""
    global _manager
    if _manager is None:
        _manager = ModeManager()
    return _manager


def get_mode() -> Mode:
    """Get current mode."""
    return get_mode_manager().mode


def set_mode(mode: Mode) -> None:
    """Set current mode."""
    get_mode_manager().set_mode(mode)
