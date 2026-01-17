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

from enum import Enum

# Implementation in Phase 3


class Phase(str, Enum):
    """Development phases."""
    PLANNING = "planning"
    TESTING = "testing"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"


def get_phase():
    """Get current development phase."""
    raise NotImplementedError("Implementation in Phase 3")


def set_phase(phase: Phase, reason: str):
    """Set development phase."""
    raise NotImplementedError("Implementation in Phase 3")
