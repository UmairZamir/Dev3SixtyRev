"""
SDK Core Package
================

Core functionality for the 3SixtyRev SDK.
"""

from sdk.core.config import (
    SDKConfig,
    GuardConfig,
    EvidenceConfig,
    PhaseConfig,
    get_config,
    set_config,
)

from sdk.core.modes import (
    Mode,
    ModeCapabilities,
    ModeManager,
    get_mode_manager,
    get_mode,
    set_mode,
)

__all__ = [
    # Config
    "SDKConfig",
    "GuardConfig",
    "EvidenceConfig",
    "PhaseConfig",
    "get_config",
    "set_config",
    # Modes
    "Mode",
    "ModeCapabilities",
    "ModeManager",
    "get_mode_manager",
    "get_mode",
    "set_mode",
]
