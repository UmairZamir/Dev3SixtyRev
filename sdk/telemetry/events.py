"""
Telemetry Events
================

Event types for tracking guard violations, quality metrics, and system events.

Every event captures:
- Timestamp
- Event type
- Source (file, guard, user)
- Severity
- Metadata

Follows enterprise patterns from:
- AWS CloudWatch Events
- Datadog APM
- Stripe telemetry
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
import json
import os
import hashlib


class EventType(str, Enum):
    """Types of telemetry events."""
    # Guard events
    GUARD_RUN = "guard.run"
    GUARD_VIOLATION = "guard.violation"
    GUARD_PASS = "guard.pass"
    
    # Verification events
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_VERIFIED = "task.verified"
    TASK_FAILED = "task.failed"
    
    # Phase events
    PHASE_STARTED = "phase.started"
    PHASE_GATE_PASSED = "phase.gate_passed"
    PHASE_GATE_FAILED = "phase.gate_failed"
    
    # Quality events
    QUALITY_DEGRADED = "quality.degraded"
    QUALITY_IMPROVED = "quality.improved"
    QUALITY_ALERT = "quality.alert"
    
    # Registry events
    REGISTRY_LOADED = "registry.loaded"
    REGISTRY_VALIDATED = "registry.validated"
    EXTRACTION_TESTED = "extraction.tested"
    
    # System events
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    ERROR = "error"


class Severity(str, Enum):
    """Event severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class TelemetryEvent:
    """
    A single telemetry event.
    
    Immutable record of something that happened in the system.
    """
    event_type: EventType
    severity: Severity
    message: str
    
    # Auto-generated
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Context
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    guard_name: Optional[str] = None
    task_id: Optional[str] = None
    phase_number: Optional[int] = None
    
    # Git context (populated if available)
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    git_author: Optional[str] = None
    
    # Environment
    session_id: Optional[str] = None
    hostname: Optional[str] = field(default_factory=lambda: os.uname().nodename if hasattr(os, 'uname') else None)
    
    # Arbitrary metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Resolution tracking
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_time_seconds: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["severity"] = self.severity.value
        data["timestamp"] = self.timestamp.isoformat()
        if self.resolved_at:
            data["resolved_at"] = self.resolved_at.isoformat()
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryEvent":
        """Create from dictionary."""
        data = data.copy()
        data["event_type"] = EventType(data["event_type"])
        data["severity"] = Severity(data["severity"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if data.get("resolved_at"):
            data["resolved_at"] = datetime.fromisoformat(data["resolved_at"])
        return cls(**data)
    
    def fingerprint(self) -> str:
        """
        Generate a fingerprint for deduplication.
        
        Same violation in same file = same fingerprint.
        Used for tracking resolution and frequency.
        """
        components = [
            self.event_type.value,
            self.source_file or "",
            str(self.source_line or ""),
            self.guard_name or "",
            self.message[:100],  # First 100 chars of message
        ]
        content = "|".join(components)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def mark_resolved(self) -> None:
        """Mark this event as resolved."""
        self.resolved = True
        self.resolved_at = datetime.utcnow()
        if self.timestamp:
            delta = self.resolved_at - self.timestamp
            self.resolution_time_seconds = delta.total_seconds()


@dataclass
class ViolationEvent(TelemetryEvent):
    """
    Specialized event for guard violations.
    
    Captures all context needed to:
    - Track who introduced it
    - How long it took to fix
    - Frequency of occurrence
    """
    violation_code: Optional[str] = None
    suggestion: Optional[str] = None
    guard_category: Optional[str] = None
    guard_level: Optional[str] = None
    
    def __post_init__(self):
        if self.event_type is None:
            self.event_type = EventType.GUARD_VIOLATION
        if self.severity is None:
            self.severity = Severity.ERROR


def create_violation_event(
    guard_name: str,
    message: str,
    file_path: Optional[str] = None,
    line: Optional[int] = None,
    violation_code: Optional[str] = None,
    suggestion: Optional[str] = None,
    severity: Severity = Severity.ERROR,
    category: Optional[str] = None,
    level: Optional[str] = None,
    **kwargs
) -> ViolationEvent:
    """Factory function to create violation events."""
    return ViolationEvent(
        event_type=EventType.GUARD_VIOLATION,
        severity=severity,
        message=message,
        guard_name=guard_name,
        source_file=file_path,
        source_line=line,
        violation_code=violation_code,
        suggestion=suggestion,
        guard_category=category,
        guard_level=level,
        **kwargs
    )


def create_guard_run_event(
    guard_name: str,
    file_path: str,
    passed: bool,
    violation_count: int = 0,
    execution_time_ms: float = 0,
    **kwargs
) -> TelemetryEvent:
    """Factory function to create guard run events."""
    return TelemetryEvent(
        event_type=EventType.GUARD_PASS if passed else EventType.GUARD_RUN,
        severity=Severity.INFO if passed else Severity.WARNING,
        message=f"Guard '{guard_name}' {'passed' if passed else f'found {violation_count} issues'} on {file_path}",
        guard_name=guard_name,
        source_file=file_path,
        metadata={
            "passed": passed,
            "violation_count": violation_count,
            "execution_time_ms": execution_time_ms,
        },
        **kwargs
    )


def create_quality_alert(
    message: str,
    metric_name: str,
    current_value: float,
    threshold: float,
    direction: str = "above",  # "above" or "below"
    **kwargs
) -> TelemetryEvent:
    """Factory function to create quality alert events."""
    return TelemetryEvent(
        event_type=EventType.QUALITY_ALERT,
        severity=Severity.WARNING,
        message=message,
        metadata={
            "metric_name": metric_name,
            "current_value": current_value,
            "threshold": threshold,
            "direction": direction,
        },
        **kwargs
    )
