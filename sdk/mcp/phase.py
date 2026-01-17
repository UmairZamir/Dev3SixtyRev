"""
Phase Management
================

Manages development phases with file creation restrictions.

Phases:
- PLANNING: Only docs, specs, .md files allowed (maps to RESEARCH + PLAN)
- TESTING: Only test files allowed (maps to TEST)
- IMPLEMENTATION: Source files allowed if tests exist (maps to IMPLEMENT)
- REVIEW: Read-only, no file creation (maps to REVIEW)

Each phase has restrictions on what files can be created/modified.
"""

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sdk.mcp.audit import log_decision

# Phase state file
PHASE_FILE_NAME = ".dev-phase.json"


class Phase(str, Enum):
    """Development phases."""

    PLANNING = "planning"
    TESTING = "testing"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"


@dataclass
class PhaseRestriction:
    """File restrictions for a phase."""

    allowed_patterns: List[str]  # Regex patterns for allowed files
    blocked_patterns: List[str]  # Regex patterns for blocked files
    description: str
    requires_tests: bool = False  # For IMPLEMENTATION phase


# Phase restrictions configuration
PHASE_RESTRICTIONS: Dict[Phase, PhaseRestriction] = {
    Phase.PLANNING: PhaseRestriction(
        allowed_patterns=[
            r"^docs/.*",
            r"^specs/.*",
            r".*\.md$",
            r".*\.txt$",
            r"^\.claude/.*",
            r"^CLAUDE\.md$",
            r"^README\.md$",
        ],
        blocked_patterns=[
            r"^src/.*\.py$",
            r"^sdk/.*\.py$",
            r"^tests/.*\.py$",
        ],
        description="Planning phase: only documentation and specs allowed",
    ),
    Phase.TESTING: PhaseRestriction(
        allowed_patterns=[
            r"^tests/.*\.py$",
            r"^test_.*\.py$",
            r".*_test\.py$",
            r"^conftest\.py$",
            r"^tests/conftest\.py$",
        ],
        blocked_patterns=[
            r"^src/.*\.py$",
            r"^sdk/(?!.*test).*\.py$",  # Block non-test sdk files
        ],
        description="Testing phase: only test files allowed",
    ),
    Phase.IMPLEMENTATION: PhaseRestriction(
        allowed_patterns=[
            r".*\.py$",
            r".*\.ts$",
            r".*\.tsx$",
            r".*\.js$",
            r".*\.jsx$",
            r".*\.go$",
        ],
        blocked_patterns=[],
        description="Implementation phase: source files allowed (tests must exist)",
        requires_tests=True,
    ),
    Phase.REVIEW: PhaseRestriction(
        allowed_patterns=[],  # No new files allowed
        blocked_patterns=[r".*"],  # Block everything
        description="Review phase: read-only, no file creation",
    ),
}


def _get_phase_file_path(project_root: Optional[Path] = None) -> Path:
    """Get the path to the phase state file."""
    if project_root is None:
        current = Path.cwd()
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current / PHASE_FILE_NAME
            current = current.parent
        return Path.cwd() / PHASE_FILE_NAME
    return Path(project_root) / PHASE_FILE_NAME


def _get_project_root(project_root: Optional[Path] = None) -> Path:
    """Get the project root directory."""
    if project_root is not None:
        return Path(project_root)
    current = Path.cwd()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path.cwd()


def get_phase(project_root: Optional[Path] = None) -> Phase:
    """
    Get current development phase.

    Returns:
        Current Phase (defaults to PLANNING if not set)
    """
    phase_file = _get_phase_file_path(project_root)

    if not phase_file.exists():
        return Phase.PLANNING

    try:
        with open(phase_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            phase_str = data.get("phase", "planning")
            return Phase(phase_str)
    except (json.JSONDecodeError, ValueError, KeyError):
        return Phase.PLANNING


def set_phase(
    phase: Phase,
    reason: str,
    project_root: Optional[Path] = None,
) -> Dict:
    """
    Set development phase.

    Args:
        phase: The phase to switch to
        reason: Reason for the phase change
        project_root: Optional project root path

    Returns:
        Phase change result dictionary
    """
    phase_file = _get_phase_file_path(project_root)
    old_phase = get_phase(project_root)

    # Ensure parent directory exists
    phase_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "phase": phase.value,
        "reason": reason,
    }

    with open(phase_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Log the phase change
    log_decision(
        event_type="phase_change",
        data={
            "old_phase": old_phase.value,
            "new_phase": phase.value,
            "reason": reason,
        },
        status="info",
        project_root=project_root,
    )

    return {
        "old_phase": old_phase.value,
        "new_phase": phase.value,
        "reason": reason,
        "restrictions": PHASE_RESTRICTIONS[phase].description,
    }


def check_file_allowed(
    filepath: str,
    phase: Optional[Phase] = None,
    project_root: Optional[Path] = None,
) -> Tuple[bool, str]:
    """
    Check if a file operation is allowed in the current phase.

    Args:
        filepath: Path to the file being created/modified
        phase: Phase to check against (uses current if not provided)
        project_root: Optional project root path

    Returns:
        Tuple of (allowed: bool, reason: str)
    """
    if phase is None:
        phase = get_phase(project_root)

    restrictions = PHASE_RESTRICTIONS[phase]

    # Normalize filepath
    filepath = filepath.replace("\\", "/")
    if filepath.startswith("./"):
        filepath = filepath[2:]

    # Check blocked patterns first
    for pattern in restrictions.blocked_patterns:
        if re.match(pattern, filepath):
            reason = f"File '{filepath}' blocked in {phase.value} phase: {restrictions.description}"
            log_decision(
                event_type="file_check",
                data={"phase": phase.value, "pattern": pattern},
                filepath=filepath,
                status="blocked",
                project_root=project_root,
            )
            return False, reason

    # Check allowed patterns
    for pattern in restrictions.allowed_patterns:
        if re.match(pattern, filepath):
            # Additional check for IMPLEMENTATION phase: tests must exist
            if restrictions.requires_tests and not filepath.startswith("tests/"):
                test_path = get_expected_test_path(filepath)
                root = _get_project_root(project_root)
                if test_path and not (root / test_path).exists():
                    reason = f"Test file required first: {test_path}"
                    log_decision(
                        event_type="file_check",
                        data={"phase": phase.value, "missing_test": test_path},
                        filepath=filepath,
                        status="blocked",
                        project_root=project_root,
                    )
                    return False, reason

            log_decision(
                event_type="file_check",
                data={"phase": phase.value, "pattern": pattern},
                filepath=filepath,
                status="allowed",
                project_root=project_root,
            )
            return True, f"Allowed by pattern: {pattern}"

    # If no patterns match and we're not in REVIEW, it might be allowed
    if phase != Phase.REVIEW and not restrictions.blocked_patterns:
        log_decision(
            event_type="file_check",
            data={"phase": phase.value, "note": "no matching pattern, allowed by default"},
            filepath=filepath,
            status="allowed",
            project_root=project_root,
        )
        return True, "No restrictions apply"

    reason = f"File '{filepath}' not in allowed patterns for {phase.value} phase"
    log_decision(
        event_type="file_check",
        data={"phase": phase.value},
        filepath=filepath,
        status="blocked",
        project_root=project_root,
    )
    return False, reason


def get_expected_test_path(filepath: str) -> Optional[str]:
    """
    Get the expected test file path for a source file.

    Args:
        filepath: Path to the source file

    Returns:
        Expected test file path, or None if not applicable
    """
    # Skip if already a test file
    if "test" in filepath.lower():
        return None

    # Skip non-Python files for now
    if not filepath.endswith(".py"):
        return None

    # Convert source path to test path
    # src/module/file.py -> tests/unit/test_file.py
    # sdk/guards/security.py -> tests/unit/test_security.py

    path = Path(filepath)
    filename = path.stem  # Without extension

    # Check for various source directories
    parts = list(path.parts)

    if "src" in parts:
        idx = parts.index("src")
        parts = parts[idx + 1 :]
    elif "sdk" in parts:
        idx = parts.index("sdk")
        parts = parts[idx + 1 :]
    else:
        parts = parts[:-1]  # Remove filename

    # Build test path
    if parts:
        # tests/unit/test_{module}_{file}.py
        module_parts = "_".join(parts[:-1]) if len(parts) > 1 else ""
        if module_parts:
            return f"tests/unit/test_{module_parts}_{filename}.py"
        return f"tests/unit/test_{filename}.py"
    else:
        return f"tests/unit/test_{filename}.py"


def get_phase_info(project_root: Optional[Path] = None) -> Dict:
    """
    Get detailed information about the current phase.

    Returns:
        Dictionary with phase details and restrictions
    """
    phase = get_phase(project_root)
    restrictions = PHASE_RESTRICTIONS[phase]

    return {
        "phase": phase.value,
        "description": restrictions.description,
        "allowed_patterns": restrictions.allowed_patterns,
        "blocked_patterns": restrictions.blocked_patterns,
        "requires_tests": restrictions.requires_tests,
    }
