"""
Telemetry Models
================

Data models for persistent telemetry tracking.

Based on enterprise patterns from:
- Google Monarch metrics
- Stripe's telemetry system
- AWS CloudWatch dimensions

Every violation is tracked with:
- Timestamp
- Violation type/category
- File affected
- Author (from git)
- Resolution time (when fixed)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json


class MetricType(str, Enum):
    """Types of metrics tracked."""
    COUNTER = "counter"      # Cumulative count
    GAUGE = "gauge"          # Point-in-time value
    HISTOGRAM = "histogram"  # Distribution
    TIMER = "timer"          # Duration


class EventType(str, Enum):
    """Types of telemetry events."""
    VIOLATION_CREATED = "violation_created"
    VIOLATION_RESOLVED = "violation_resolved"
    GUARD_RUN = "guard_run"
    PHASE_GATE_PASSED = "phase_gate_passed"
    PHASE_GATE_FAILED = "phase_gate_failed"
    TASK_VERIFIED = "task_verified"
    TASK_FAILED = "task_failed"
    BUILD_STARTED = "build_started"
    BUILD_COMPLETED = "build_completed"
    DEPLOY_STARTED = "deploy_started"
    DEPLOY_COMPLETED = "deploy_completed"


class ResolutionStatus(str, Enum):
    """Status of a violation."""
    OPEN = "open"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    FALSE_POSITIVE = "false_positive"


@dataclass
class ViolationRecord:
    """
    Persistent record of a guard violation.
    
    Tracked for historical analysis and trend detection.
    """
    # Identity
    id: str  # Unique hash of violation
    
    # Source
    guard_name: str
    guard_category: str
    guard_level: str
    severity: str
    
    # Location
    file_path: str
    line_number: int
    
    # Details - message is required, so it must come before optional fields
    message: str
    
    # Optional fields (all have defaults)
    column: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    
    # Git context
    author: Optional[str] = None
    commit_hash: Optional[str] = None
    branch: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    
    # Status
    status: ResolutionStatus = ResolutionStatus.OPEN
    resolved_by: Optional[str] = None
    resolution_commit: Optional[str] = None
    
    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    
    @staticmethod
    def generate_id(guard_name: str, file_path: str, line: int, message: str) -> str:
        """Generate unique ID for a violation."""
        content = f"{guard_name}:{file_path}:{line}:{message}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    @property
    def resolution_time_hours(self) -> Optional[float]:
        """Get time to resolution in hours."""
        if self.resolved_at and self.created_at:
            delta = self.resolved_at - self.created_at
            return delta.total_seconds() / 3600
        return None
    
    @property
    def age_hours(self) -> float:
        """Get age of violation in hours."""
        delta = datetime.utcnow() - self.created_at
        return delta.total_seconds() / 3600
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "guard_name": self.guard_name,
            "guard_category": self.guard_category,
            "guard_level": self.guard_level,
            "severity": self.severity,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "column": self.column,
            "message": self.message,
            "code_snippet": self.code_snippet,
            "suggestion": self.suggestion,
            "author": self.author,
            "commit_hash": self.commit_hash,
            "branch": self.branch,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "status": self.status.value,
            "resolved_by": self.resolved_by,
            "resolution_commit": self.resolution_commit,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ViolationRecord":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            guard_name=data["guard_name"],
            guard_category=data["guard_category"],
            guard_level=data["guard_level"],
            severity=data["severity"],
            file_path=data["file_path"],
            line_number=data["line_number"],
            message=data["message"],
            column=data.get("column"),
            code_snippet=data.get("code_snippet"),
            suggestion=data.get("suggestion"),
            author=data.get("author"),
            commit_hash=data.get("commit_hash"),
            branch=data.get("branch"),
            created_at=datetime.fromisoformat(data["created_at"]),
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            status=ResolutionStatus(data.get("status", "open")),
            resolved_by=data.get("resolved_by"),
            resolution_commit=data.get("resolution_commit"),
            tags=data.get("tags", {}),
        )


@dataclass
class MetricRecord:
    """
    A single metric data point.
    
    Dimensions allow slicing (e.g., by guard_name, file_type).
    """
    # Identity
    name: str
    metric_type: MetricType
    
    # Value
    value: float
    
    # Dimensions for slicing
    dimensions: Dict[str, str] = field(default_factory=dict)
    
    # Timestamp
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "name": self.name,
            "metric_type": self.metric_type.value,
            "value": self.value,
            "dimensions": self.dimensions,
            "timestamp": self.timestamp.isoformat(),
            "unit": self.unit,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricRecord":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            metric_type=MetricType(data["metric_type"]),
            value=data["value"],
            dimensions=data.get("dimensions", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            unit=data.get("unit"),
        )


@dataclass
class TelemetryEvent:
    """
    A telemetry event for tracking workflow progress.
    """
    # Identity
    event_type: EventType
    event_id: str = field(default_factory=lambda: hashlib.sha256(
        f"{datetime.utcnow().isoformat()}".encode()
    ).hexdigest()[:16])
    
    # Context
    source: str = "sdk"  # What generated this event
    
    # Payload
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamp
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Git context
    commit_hash: Optional[str] = None
    branch: Optional[str] = None
    author: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "commit_hash": self.commit_hash,
            "branch": self.branch,
            "author": self.author,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryEvent":
        """Create from dictionary."""
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            source=data.get("source", "sdk"),
            data=data.get("data", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            commit_hash=data.get("commit_hash"),
            branch=data.get("branch"),
            author=data.get("author"),
        )


@dataclass
class QualitySnapshot:
    """
    Point-in-time snapshot of code quality.
    
    Captures the state for trend analysis.
    """
    # Timestamp
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Commit context
    commit_hash: Optional[str] = None
    branch: Optional[str] = None
    
    # Violation counts by severity
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    
    # Violation counts by category
    by_category: Dict[str, int] = field(default_factory=dict)
    
    # Violation counts by guard
    by_guard: Dict[str, int] = field(default_factory=dict)
    
    # Files affected
    files_with_violations: int = 0
    total_files_checked: int = 0
    
    # Computed metrics
    @property
    def total_violations(self) -> int:
        return self.error_count + self.warning_count + self.info_count
    
    @property
    def violation_rate(self) -> float:
        """Violations per file checked."""
        if self.total_files_checked == 0:
            return 0.0
        return self.total_violations / self.total_files_checked
    
    @property
    def clean_file_rate(self) -> float:
        """Percentage of files without violations."""
        if self.total_files_checked == 0:
            return 1.0
        clean = self.total_files_checked - self.files_with_violations
        return clean / self.total_files_checked
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "commit_hash": self.commit_hash,
            "branch": self.branch,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "by_category": self.by_category,
            "by_guard": self.by_guard,
            "files_with_violations": self.files_with_violations,
            "total_files_checked": self.total_files_checked,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualitySnapshot":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            commit_hash=data.get("commit_hash"),
            branch=data.get("branch"),
            error_count=data.get("error_count", 0),
            warning_count=data.get("warning_count", 0),
            info_count=data.get("info_count", 0),
            by_category=data.get("by_category", {}),
            by_guard=data.get("by_guard", {}),
            files_with_violations=data.get("files_with_violations", 0),
            total_files_checked=data.get("total_files_checked", 0),
        )
