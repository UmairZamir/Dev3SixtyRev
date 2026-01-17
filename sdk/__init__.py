"""
3SixtyRev SDK
=============

Enterprise-grade AI development enforcement SDK.

This SDK provides:
- Guards: Automated code quality checks
- Verification: Evidence-based task completion
- Phase Gates: Quality gates between development phases
- Modes: Development mode management
- Registry: Field and product registry management

Quick Start:
    from sdk import get_guard_registry, run_guards
    
    # Run guards on code
    result = run_guards(code_content, "path/to/file.py")
    print(result.format())
    
    # Or use the registry directly
    registry = get_guard_registry()
    result = registry.run_on_file(Path("src/app.py"))
    
    # Work with field registry
    from sdk.registry import get_registry
    
    field_registry = get_registry()
    field = field_registry.get_field("auto_insurance", "driver_age")
    value, confidence = field.extract_value("I'm 35 years old")
"""

__version__ = "1.0.0"
__author__ = "Omar Zamir"

# Guards
from sdk.guards import (
    Guard,
    GuardCategory,
    GuardLevel,
    GuardResult,
    GuardSeverity,
    GuardViolation,
    GuardRegistry,
    AggregatedResult,
    get_guard_registry,
    register_guard,
    run_guards,
)

# Verification
from sdk.verification import (
    Evidence,
    EvidenceCollector,
    EvidenceType,
    EvidenceStatus,
    Task,
    get_collector,
    Phase,
    PhaseGate,
    PhaseResult,
    get_phase_gate,
)

# Core
from sdk.core import (
    SDKConfig,
    get_config,
    set_config,
    Mode,
    ModeManager,
    get_mode_manager,
    get_mode,
    set_mode,
)

# Registry - imported as submodule, not directly into namespace
# Use: from sdk.registry import get_registry, validate_registry, etc.

__all__ = [
    # Version
    "__version__",
    "__author__",
    # Guards
    "Guard",
    "GuardCategory",
    "GuardLevel",
    "GuardResult",
    "GuardSeverity",
    "GuardViolation",
    "GuardRegistry",
    "AggregatedResult",
    "get_guard_registry",
    "register_guard",
    "run_guards",
    # Verification
    "Evidence",
    "EvidenceCollector",
    "EvidenceType",
    "EvidenceStatus",
    "Task",
    "get_collector",
    "Phase",
    "PhaseGate",
    "PhaseResult",
    "get_phase_gate",
    # Core
    "SDKConfig",
    "get_config",
    "set_config",
    "Mode",
    "ModeManager",
    "get_mode_manager",
    "get_mode",
    "set_mode",
]
