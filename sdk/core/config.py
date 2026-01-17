"""
SDK Configuration
=================

Configuration management for the 3SixtyRev SDK.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml


@dataclass
class GuardConfig:
    """Configuration for guards."""
    enabled_guards: Set[str] = field(default_factory=set)
    disabled_guards: Set[str] = field(default_factory=set)
    severity_overrides: Dict[str, str] = field(default_factory=dict)
    custom_patterns: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class EvidenceConfig:
    """Configuration for evidence collection."""
    evidence_dir: Path = field(default_factory=lambda: Path(".3sr/evidence"))
    required_evidence_types: List[str] = field(
        default_factory=lambda: ["test_result"]
    )
    auto_collect_tests: bool = True
    auto_collect_lint: bool = True
    auto_collect_typecheck: bool = True


@dataclass
class PhaseConfig:
    """Configuration for phase gates."""
    enforce_gates: bool = True
    skip_research: bool = False
    skip_plan: bool = False
    custom_requirements: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class SDKConfig:
    """Main SDK configuration."""
    project_name: str = "3SixtyRev"
    project_root: Path = field(default_factory=lambda: Path.cwd())
    guards: GuardConfig = field(default_factory=GuardConfig)
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)
    phases: PhaseConfig = field(default_factory=PhaseConfig)
    verbose: bool = False
    debug: bool = False

    # File patterns
    python_extensions: Set[str] = field(
        default_factory=lambda: {".py", ".pyi"}
    )
    frontend_extensions: Set[str] = field(
        default_factory=lambda: {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}
    )
    excluded_dirs: Set[str] = field(
        default_factory=lambda: {
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "dist",
            "build",
            ".3sr",
        }
    )

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "SDKConfig":
        """Load configuration from file."""
        if config_path is None:
            # Look for config in standard locations
            candidates = [
                Path.cwd() / ".3sr.yaml",
                Path.cwd() / ".3sr.yml",
                Path.cwd() / "pyproject.toml",
            ]
            for candidate in candidates:
                if candidate.exists():
                    config_path = candidate
                    break

        if config_path is None or not config_path.exists():
            return cls()

        if config_path.suffix in (".yaml", ".yml"):
            return cls._load_yaml(config_path)
        elif config_path.name == "pyproject.toml":
            return cls._load_pyproject(config_path)

        return cls()

    @classmethod
    def _load_yaml(cls, path: Path) -> "SDKConfig":
        """Load from YAML file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}

            return cls(
                project_name=data.get("project_name", "3SixtyRev"),
                project_root=Path(data.get("project_root", ".")),
                verbose=data.get("verbose", False),
                debug=data.get("debug", False),
                guards=GuardConfig(
                    enabled_guards=set(data.get("guards", {}).get("enabled", [])),
                    disabled_guards=set(data.get("guards", {}).get("disabled", [])),
                    severity_overrides=data.get("guards", {}).get("severity", {}),
                ),
                evidence=EvidenceConfig(
                    evidence_dir=Path(data.get("evidence", {}).get("dir", ".3sr/evidence")),
                    required_evidence_types=data.get("evidence", {}).get("required", ["test_result"]),
                ),
                phases=PhaseConfig(
                    enforce_gates=data.get("phases", {}).get("enforce", True),
                ),
            )
        except Exception:
            return cls()

    @classmethod
    def _load_pyproject(cls, path: Path) -> "SDKConfig":
        """Load from pyproject.toml [tool.3sr] section."""
        try:
            import toml
            data = toml.load(path)
            sdk_config = data.get("tool", {}).get("3sr", {})
            if not sdk_config:
                return cls()

            return cls(
                project_name=sdk_config.get("project_name", "3SixtyRev"),
                verbose=sdk_config.get("verbose", False),
                guards=GuardConfig(
                    enabled_guards=set(sdk_config.get("guards", {}).get("enabled", [])),
                    disabled_guards=set(sdk_config.get("guards", {}).get("disabled", [])),
                ),
            )
        except Exception:
            return cls()

    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        path = path or (self.project_root / ".3sr.yaml")
        
        data = {
            "project_name": self.project_name,
            "verbose": self.verbose,
            "debug": self.debug,
            "guards": {
                "enabled": list(self.guards.enabled_guards),
                "disabled": list(self.guards.disabled_guards),
                "severity": self.guards.severity_overrides,
            },
            "evidence": {
                "dir": str(self.evidence.evidence_dir),
                "required": self.evidence.required_evidence_types,
            },
            "phases": {
                "enforce": self.phases.enforce_gates,
            },
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)


# Global config instance
_config: Optional[SDKConfig] = None


def get_config() -> SDKConfig:
    """Get or load global configuration."""
    global _config
    if _config is None:
        _config = SDKConfig.load()
    return _config


def set_config(config: SDKConfig) -> None:
    """Set global configuration."""
    global _config
    _config = config
