"""
Telemetry Collector
===================

Integrates telemetry collection with guards.

Automatically:
- Records violations when guards run
- Tracks resolution when violations disappear
- Captures quality snapshots
- Emits events for CI integration
"""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .models import (
    ViolationRecord,
    MetricRecord,
    TelemetryEvent,
    QualitySnapshot,
    EventType,
    MetricType,
    ResolutionStatus,
)
from .store import TelemetryStore, get_telemetry_store


class TelemetryCollector:
    """
    Collects telemetry from guard runs and other SDK operations.
    
    Usage:
        collector = TelemetryCollector()
        
        # After running guards
        from sdk.guards import run_guards
        result = run_guards(content, "path/to/file.py")
        collector.record_guard_run(result, "path/to/file.py")
        
        # Take a snapshot
        collector.take_snapshot(files_checked=10)
        
        # Check for resolutions
        collector.check_resolutions()
    """
    
    def __init__(self, store: Optional[TelemetryStore] = None):
        self.store = store or get_telemetry_store()
        self._git_context: Optional[Dict[str, str]] = None
    
    @property
    def git_context(self) -> Dict[str, str]:
        """Get current git context (cached)."""
        if self._git_context is None:
            self._git_context = self._get_git_context()
        return self._git_context
    
    def _get_git_context(self) -> Dict[str, str]:
        """Get current git context from environment."""
        context = {
            "commit_hash": None,
            "branch": None,
            "author": None,
        }
        
        try:
            # Get current commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                context["commit_hash"] = result.stdout.strip()[:12]
            
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                context["branch"] = result.stdout.strip()
            
            # Get author of last commit
            result = subprocess.run(
                ["git", "log", "-1", "--format=%an"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                context["author"] = result.stdout.strip()
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return context
    
    def record_guard_run(
        self,
        result: "AggregatedResult",  # From sdk.guards
        file_path: Optional[str] = None,
        commit_hash: Optional[str] = None,
    ) -> int:
        """
        Record violations from a guard run.
        
        Returns number of new violations recorded.
        """
        from sdk.guards import GuardSeverity
        
        new_violations = 0
        git = self.git_context
        
        for violation in result.violations:
            # Generate unique ID
            violation_id = ViolationRecord.generate_id(
                guard_name=violation.guard or "unknown",
                file_path=file_path or "unknown",
                line=violation.line,
                message=violation.message,
            )
            
            # Check if already exists
            existing = self.store.get_violation(violation_id)
            if existing:
                continue  # Already tracked
            
            # Create new record
            record = ViolationRecord(
                id=violation_id,
                guard_name=violation.guard or "unknown",
                guard_category=violation.category.value if violation.category else "unknown",
                guard_level="instant",  # Default, could be passed in
                severity=violation.severity.value if violation.severity else "warning",
                file_path=file_path or "unknown",
                line_number=violation.line,
                column=violation.column,
                message=violation.message,
                code_snippet=violation.code,
                suggestion=violation.suggestion,
                author=git.get("author"),
                commit_hash=commit_hash or git.get("commit_hash"),
                branch=git.get("branch"),
            )
            
            self.store.store_violation(record)
            new_violations += 1
        
        # Record metrics
        self.store.store_metric(MetricRecord(
            name="guard_run.violations",
            metric_type=MetricType.GAUGE,
            value=len(result.violations),
            dimensions={
                "file": file_path or "unknown",
                "passed": str(result.passed),
            },
        ))
        
        self.store.store_metric(MetricRecord(
            name="guard_run.duration_ms",
            metric_type=MetricType.TIMER,
            value=result.execution_time_ms,
            unit="ms",
        ))
        
        # Record event
        self.store.store_event(TelemetryEvent(
            event_type=EventType.GUARD_RUN,
            data={
                "file": file_path,
                "passed": result.passed,
                "violations": len(result.violations),
                "errors": result.error_count,
                "warnings": result.warning_count,
                "guards_run": result.guards_run,
                "duration_ms": result.execution_time_ms,
            },
            commit_hash=commit_hash or git.get("commit_hash"),
            branch=git.get("branch"),
            author=git.get("author"),
        ))
        
        return new_violations
    
    def record_guard_run_from_violations(
        self,
        violations: List[Dict[str, Any]],
        file_path: str,
        passed: bool,
        execution_time_ms: float = 0.0,
    ) -> int:
        """
        Record violations from a list of dicts (for direct integration).
        
        Each violation dict should have:
        - guard_name: str
        - guard_category: str
        - severity: str
        - line: int
        - message: str
        - code: Optional[str]
        - suggestion: Optional[str]
        """
        new_violations = 0
        git = self.git_context
        
        for v in violations:
            violation_id = ViolationRecord.generate_id(
                guard_name=v.get("guard_name", "unknown"),
                file_path=file_path,
                line=v.get("line", 0),
                message=v.get("message", ""),
            )
            
            existing = self.store.get_violation(violation_id)
            if existing:
                continue
            
            record = ViolationRecord(
                id=violation_id,
                guard_name=v.get("guard_name", "unknown"),
                guard_category=v.get("guard_category", "unknown"),
                guard_level=v.get("guard_level", "instant"),
                severity=v.get("severity", "warning"),
                file_path=file_path,
                line_number=v.get("line", 0),
                column=v.get("column"),
                message=v.get("message", ""),
                code_snippet=v.get("code"),
                suggestion=v.get("suggestion"),
                author=git.get("author"),
                commit_hash=git.get("commit_hash"),
                branch=git.get("branch"),
            )
            
            self.store.store_violation(record)
            new_violations += 1
        
        # Record event
        self.store.store_event(TelemetryEvent(
            event_type=EventType.GUARD_RUN,
            data={
                "file": file_path,
                "passed": passed,
                "violations": len(violations),
                "new_violations": new_violations,
                "duration_ms": execution_time_ms,
            },
            commit_hash=git.get("commit_hash"),
            branch=git.get("branch"),
        ))
        
        return new_violations
    
    def check_resolutions(self, files: Optional[List[str]] = None) -> int:
        """
        Check for resolved violations (no longer present in files).
        
        Returns number of violations marked as resolved.
        """
        open_violations = self.store.get_open_violations()
        resolved_count = 0
        git = self.git_context
        
        # Group by file
        by_file: Dict[str, List[ViolationRecord]] = {}
        for v in open_violations:
            if files is None or v.file_path in files:
                if v.file_path not in by_file:
                    by_file[v.file_path] = []
                by_file[v.file_path].append(v)
        
        from sdk.guards import get_guard_registry
        registry = get_guard_registry()
        
        for file_path, violations in by_file.items():
            path = Path(file_path)
            if not path.exists():
                # File deleted - mark all as resolved
                for v in violations:
                    self.store.resolve_violation(
                        v.id,
                        resolved_by=git.get("author"),
                        resolution_commit=git.get("commit_hash"),
                    )
                    resolved_count += 1
                continue
            
            try:
                content = path.read_text()
            except (IOError, UnicodeDecodeError):
                continue
            
            # Run guards to get current violations
            result = registry.run_all(content, str(path))
            
            # Build set of current violation IDs
            current_ids: Set[str] = set()
            for v in result.violations:
                vid = ViolationRecord.generate_id(
                    guard_name=v.guard or "unknown",
                    file_path=str(path),
                    line=v.line,
                    message=v.message,
                )
                current_ids.add(vid)
            
            # Mark missing violations as resolved
            for v in violations:
                if v.id not in current_ids:
                    self.store.resolve_violation(
                        v.id,
                        resolved_by=git.get("author"),
                        resolution_commit=git.get("commit_hash"),
                    )
                    resolved_count += 1
                    
                    # Record event
                    self.store.store_event(TelemetryEvent(
                        event_type=EventType.VIOLATION_RESOLVED,
                        data={
                            "violation_id": v.id,
                            "guard_name": v.guard_name,
                            "file_path": v.file_path,
                            "resolution_time_hours": v.age_hours,
                        },
                        commit_hash=git.get("commit_hash"),
                        branch=git.get("branch"),
                        author=git.get("author"),
                    ))
        
        return resolved_count
    
    def take_snapshot(
        self,
        files_checked: int = 0,
        commit_hash: Optional[str] = None,
    ) -> QualitySnapshot:
        """
        Take a quality snapshot of current state.
        """
        open_violations = self.store.get_open_violations()
        git = self.git_context
        
        # Count by severity
        error_count = sum(1 for v in open_violations if v.severity == "error")
        warning_count = sum(1 for v in open_violations if v.severity == "warning")
        info_count = sum(1 for v in open_violations if v.severity == "info")
        
        # Count by category
        by_category: Dict[str, int] = {}
        for v in open_violations:
            by_category[v.guard_category] = by_category.get(v.guard_category, 0) + 1
        
        # Count by guard
        by_guard: Dict[str, int] = {}
        for v in open_violations:
            by_guard[v.guard_name] = by_guard.get(v.guard_name, 0) + 1
        
        # Files with violations
        files_with_violations = len(set(v.file_path for v in open_violations))
        
        snapshot = QualitySnapshot(
            commit_hash=commit_hash or git.get("commit_hash"),
            branch=git.get("branch"),
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            by_category=by_category,
            by_guard=by_guard,
            files_with_violations=files_with_violations,
            total_files_checked=files_checked,
        )
        
        self.store.store_snapshot(snapshot)
        
        # Record metrics
        self.store.store_metric(MetricRecord(
            name="quality.total_violations",
            metric_type=MetricType.GAUGE,
            value=snapshot.total_violations,
        ))
        self.store.store_metric(MetricRecord(
            name="quality.error_count",
            metric_type=MetricType.GAUGE,
            value=error_count,
        ))
        self.store.store_metric(MetricRecord(
            name="quality.clean_file_rate",
            metric_type=MetricType.GAUGE,
            value=snapshot.clean_file_rate * 100,
            unit="percent",
        ))
        
        return snapshot
    
    def record_phase_gate(
        self,
        phase_number: int,
        passed: bool,
        commit_hash: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a phase gate result."""
        git = self.git_context
        
        event_type = EventType.PHASE_GATE_PASSED if passed else EventType.PHASE_GATE_FAILED
        
        self.store.store_event(TelemetryEvent(
            event_type=event_type,
            data={
                "phase_number": phase_number,
                "passed": passed,
                **(details or {}),
            },
            commit_hash=commit_hash or git.get("commit_hash"),
            branch=git.get("branch"),
            author=git.get("author"),
        ))
    
    def record_task_completion(
        self,
        task_id: str,
        verified: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a task verification result."""
        git = self.git_context
        
        event_type = EventType.TASK_VERIFIED if verified else EventType.TASK_FAILED
        
        self.store.store_event(TelemetryEvent(
            event_type=event_type,
            data={
                "task_id": task_id,
                "verified": verified,
                **(details or {}),
            },
            commit_hash=git.get("commit_hash"),
            branch=git.get("branch"),
            author=git.get("author"),
        ))
    
    def record_build(
        self,
        build_id: str,
        status: str,
        duration_seconds: float,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a build event (for CI integration)."""
        git = self.git_context
        
        event_type = EventType.BUILD_COMPLETED
        
        self.store.store_event(TelemetryEvent(
            event_type=event_type,
            data={
                "build_id": build_id,
                "status": status,
                "duration_seconds": duration_seconds,
                **(details or {}),
            },
            commit_hash=git.get("commit_hash"),
            branch=git.get("branch"),
            author=git.get("author"),
        ))
        
        self.store.store_metric(MetricRecord(
            name="build.duration_seconds",
            metric_type=MetricType.TIMER,
            value=duration_seconds,
            unit="seconds",
            dimensions={"status": status},
        ))


# Singleton instance
_collector: Optional[TelemetryCollector] = None


def get_telemetry_collector(store: Optional[TelemetryStore] = None) -> TelemetryCollector:
    """Get the singleton telemetry collector."""
    global _collector
    if _collector is None:
        _collector = TelemetryCollector(store)
    return _collector
