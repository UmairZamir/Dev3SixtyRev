"""
Telemetry Store
===============

Persistent storage for telemetry data using SQLite.

Features:
- Local SQLite database for development
- Export to JSON/CSV for CI integration
- Support for external backends (Datadog, CloudWatch, etc.)

Schema:
- violations: Individual violation records
- metrics: Time-series metrics
- events: Workflow events
- snapshots: Quality snapshots over time
"""

import sqlite3
import json
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple
import threading

from .models import (
    ViolationRecord,
    MetricRecord,
    TelemetryEvent,
    QualitySnapshot,
    ResolutionStatus,
    EventType,
    MetricType,
)


class TelemetryStore(ABC):
    """Abstract base class for telemetry storage."""
    
    @abstractmethod
    def store_violation(self, violation: ViolationRecord) -> None:
        """Store a violation record."""
        pass
    
    @abstractmethod
    def store_metric(self, metric: MetricRecord) -> None:
        """Store a metric data point."""
        pass
    
    @abstractmethod
    def store_event(self, event: TelemetryEvent) -> None:
        """Store a telemetry event."""
        pass
    
    @abstractmethod
    def store_snapshot(self, snapshot: QualitySnapshot) -> None:
        """Store a quality snapshot."""
        pass
    
    @abstractmethod
    def get_violation(self, violation_id: str) -> Optional[ViolationRecord]:
        """Get a violation by ID."""
        pass
    
    @abstractmethod
    def get_open_violations(self) -> List[ViolationRecord]:
        """Get all open violations."""
        pass
    
    @abstractmethod
    def resolve_violation(
        self, 
        violation_id: str, 
        resolved_by: Optional[str] = None,
        resolution_commit: Optional[str] = None,
        status: ResolutionStatus = ResolutionStatus.RESOLVED,
    ) -> bool:
        """Mark a violation as resolved."""
        pass
    
    @abstractmethod
    def get_snapshots(
        self, 
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[QualitySnapshot]:
        """Get quality snapshots in a time range."""
        pass


class SQLiteTelemetryStore(TelemetryStore):
    """
    SQLite-based telemetry store for local development.
    
    Thread-safe with connection pooling.
    """
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".3sr" / "telemetry.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._initialize_schema()
    
    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._local.connection.row_factory = sqlite3.Row
        
        try:
            yield self._local.connection
        except Exception:
            self._local.connection.rollback()
            raise
    
    def _initialize_schema(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Violations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS violations (
                    id TEXT PRIMARY KEY,
                    guard_name TEXT NOT NULL,
                    guard_category TEXT NOT NULL,
                    guard_level TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    column_number INTEGER,
                    message TEXT NOT NULL,
                    code_snippet TEXT,
                    suggestion TEXT,
                    author TEXT,
                    commit_hash TEXT,
                    branch TEXT,
                    created_at TIMESTAMP NOT NULL,
                    resolved_at TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'open',
                    resolved_by TEXT,
                    resolution_commit TEXT,
                    tags TEXT
                )
            ''')
            
            # Metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    value REAL NOT NULL,
                    dimensions TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    unit TEXT
                )
            ''')
            
            # Events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    data TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    commit_hash TEXT,
                    branch TEXT,
                    author TEXT
                )
            ''')
            
            # Snapshots table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    commit_hash TEXT,
                    branch TEXT,
                    error_count INTEGER NOT NULL,
                    warning_count INTEGER NOT NULL,
                    info_count INTEGER NOT NULL,
                    by_category TEXT,
                    by_guard TEXT,
                    files_with_violations INTEGER NOT NULL,
                    total_files_checked INTEGER NOT NULL
                )
            ''')
            
            # Indexes for common queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_violations_status 
                ON violations(status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_violations_created 
                ON violations(created_at)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_violations_guard 
                ON violations(guard_name)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_metrics_name_time 
                ON metrics(name, timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_events_type_time 
                ON events(event_type, timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_snapshots_time 
                ON snapshots(timestamp)
            ''')
            
            conn.commit()
    
    def store_violation(self, violation: ViolationRecord) -> None:
        """Store a violation record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO violations (
                    id, guard_name, guard_category, guard_level, severity,
                    file_path, line_number, column_number, message,
                    code_snippet, suggestion, author, commit_hash, branch,
                    created_at, resolved_at, status, resolved_by,
                    resolution_commit, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                violation.id,
                violation.guard_name,
                violation.guard_category,
                violation.guard_level,
                violation.severity,
                violation.file_path,
                violation.line_number,
                violation.column,
                violation.message,
                violation.code_snippet,
                violation.suggestion,
                violation.author,
                violation.commit_hash,
                violation.branch,
                violation.created_at,
                violation.resolved_at,
                violation.status.value,
                violation.resolved_by,
                violation.resolution_commit,
                json.dumps(violation.tags),
            ))
            conn.commit()
    
    def store_metric(self, metric: MetricRecord) -> None:
        """Store a metric data point."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO metrics (name, metric_type, value, dimensions, timestamp, unit)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                metric.name,
                metric.metric_type.value,
                metric.value,
                json.dumps(metric.dimensions),
                metric.timestamp,
                metric.unit,
            ))
            conn.commit()
    
    def store_event(self, event: TelemetryEvent) -> None:
        """Store a telemetry event."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO events (
                    event_id, event_type, source, data, timestamp,
                    commit_hash, branch, author
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.event_id,
                event.event_type.value,
                event.source,
                json.dumps(event.data),
                event.timestamp,
                event.commit_hash,
                event.branch,
                event.author,
            ))
            conn.commit()
    
    def store_snapshot(self, snapshot: QualitySnapshot) -> None:
        """Store a quality snapshot."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO snapshots (
                    timestamp, commit_hash, branch,
                    error_count, warning_count, info_count,
                    by_category, by_guard,
                    files_with_violations, total_files_checked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                snapshot.timestamp,
                snapshot.commit_hash,
                snapshot.branch,
                snapshot.error_count,
                snapshot.warning_count,
                snapshot.info_count,
                json.dumps(snapshot.by_category),
                json.dumps(snapshot.by_guard),
                snapshot.files_with_violations,
                snapshot.total_files_checked,
            ))
            conn.commit()
    
    def get_violation(self, violation_id: str) -> Optional[ViolationRecord]:
        """Get a violation by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM violations WHERE id = ?', (violation_id,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_violation(row)
            return None
    
    def get_open_violations(self) -> List[ViolationRecord]:
        """Get all open violations."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM violations WHERE status = ? ORDER BY created_at DESC',
                (ResolutionStatus.OPEN.value,)
            )
            return [self._row_to_violation(row) for row in cursor.fetchall()]
    
    def get_violations_by_file(self, file_path: str) -> List[ViolationRecord]:
        """Get all violations for a file."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM violations WHERE file_path = ? ORDER BY line_number',
                (file_path,)
            )
            return [self._row_to_violation(row) for row in cursor.fetchall()]
    
    def get_violations_by_guard(self, guard_name: str) -> List[ViolationRecord]:
        """Get all violations from a specific guard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM violations WHERE guard_name = ? ORDER BY created_at DESC',
                (guard_name,)
            )
            return [self._row_to_violation(row) for row in cursor.fetchall()]
    
    def get_violations_since(self, since: datetime) -> List[ViolationRecord]:
        """Get violations created since a timestamp."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM violations WHERE created_at >= ? ORDER BY created_at DESC',
                (since,)
            )
            return [self._row_to_violation(row) for row in cursor.fetchall()]
    
    def resolve_violation(
        self,
        violation_id: str,
        resolved_by: Optional[str] = None,
        resolution_commit: Optional[str] = None,
        status: ResolutionStatus = ResolutionStatus.RESOLVED,
    ) -> bool:
        """Mark a violation as resolved."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE violations 
                SET status = ?, resolved_at = ?, resolved_by = ?, resolution_commit = ?
                WHERE id = ?
            ''', (
                status.value,
                datetime.utcnow(),
                resolved_by,
                resolution_commit,
                violation_id,
            ))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_snapshots(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[QualitySnapshot]:
        """Get quality snapshots in a time range."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM snapshots WHERE 1=1'
            params: List[Any] = []
            
            if since:
                query += ' AND timestamp >= ?'
                params.append(since)
            if until:
                query += ' AND timestamp <= ?'
                params.append(until)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            return [self._row_to_snapshot(row) for row in cursor.fetchall()]
    
    def get_metrics(
        self,
        name: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        dimensions: Optional[Dict[str, str]] = None,
        limit: int = 1000,
    ) -> List[MetricRecord]:
        """Get metrics by name and optional filters."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM metrics WHERE name = ?'
            params: List[Any] = [name]
            
            if since:
                query += ' AND timestamp >= ?'
                params.append(since)
            if until:
                query += ' AND timestamp <= ?'
                params.append(until)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            metrics = [self._row_to_metric(row) for row in cursor.fetchall()]
            
            # Filter by dimensions in Python (SQLite JSON support is limited)
            if dimensions:
                metrics = [
                    m for m in metrics
                    if all(m.dimensions.get(k) == v for k, v in dimensions.items())
                ]
            
            return metrics
    
    def get_events(
        self,
        event_type: Optional[EventType] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[TelemetryEvent]:
        """Get events by type and time range."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM events WHERE 1=1'
            params: List[Any] = []
            
            if event_type:
                query += ' AND event_type = ?'
                params.append(event_type.value)
            if since:
                query += ' AND timestamp >= ?'
                params.append(since)
            if until:
                query += ' AND timestamp <= ?'
                params.append(until)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            return [self._row_to_event(row) for row in cursor.fetchall()]
    
    def _row_to_violation(self, row: sqlite3.Row) -> ViolationRecord:
        """Convert database row to ViolationRecord."""
        return ViolationRecord(
            id=row['id'],
            guard_name=row['guard_name'],
            guard_category=row['guard_category'],
            guard_level=row['guard_level'],
            severity=row['severity'],
            file_path=row['file_path'],
            line_number=row['line_number'],
            column=row['column_number'],
            message=row['message'],
            code_snippet=row['code_snippet'],
            suggestion=row['suggestion'],
            author=row['author'],
            commit_hash=row['commit_hash'],
            branch=row['branch'],
            created_at=row['created_at'] if isinstance(row['created_at'], datetime) 
                       else datetime.fromisoformat(row['created_at']),
            resolved_at=row['resolved_at'] if isinstance(row['resolved_at'], datetime)
                        else (datetime.fromisoformat(row['resolved_at']) if row['resolved_at'] else None),
            status=ResolutionStatus(row['status']),
            resolved_by=row['resolved_by'],
            resolution_commit=row['resolution_commit'],
            tags=json.loads(row['tags']) if row['tags'] else {},
        )
    
    def _row_to_metric(self, row: sqlite3.Row) -> MetricRecord:
        """Convert database row to MetricRecord."""
        return MetricRecord(
            name=row['name'],
            metric_type=MetricType(row['metric_type']),
            value=row['value'],
            dimensions=json.loads(row['dimensions']) if row['dimensions'] else {},
            timestamp=row['timestamp'] if isinstance(row['timestamp'], datetime)
                      else datetime.fromisoformat(row['timestamp']),
            unit=row['unit'],
        )
    
    def _row_to_event(self, row: sqlite3.Row) -> TelemetryEvent:
        """Convert database row to TelemetryEvent."""
        return TelemetryEvent(
            event_id=row['event_id'],
            event_type=EventType(row['event_type']),
            source=row['source'],
            data=json.loads(row['data']) if row['data'] else {},
            timestamp=row['timestamp'] if isinstance(row['timestamp'], datetime)
                      else datetime.fromisoformat(row['timestamp']),
            commit_hash=row['commit_hash'],
            branch=row['branch'],
            author=row['author'],
        )
    
    def _row_to_snapshot(self, row: sqlite3.Row) -> QualitySnapshot:
        """Convert database row to QualitySnapshot."""
        return QualitySnapshot(
            timestamp=row['timestamp'] if isinstance(row['timestamp'], datetime)
                      else datetime.fromisoformat(row['timestamp']),
            commit_hash=row['commit_hash'],
            branch=row['branch'],
            error_count=row['error_count'],
            warning_count=row['warning_count'],
            info_count=row['info_count'],
            by_category=json.loads(row['by_category']) if row['by_category'] else {},
            by_guard=json.loads(row['by_guard']) if row['by_guard'] else {},
            files_with_violations=row['files_with_violations'],
            total_files_checked=row['total_files_checked'],
        )
    
    # Export methods for CI integration
    
    def export_to_json(self, output_path: Path) -> Dict[str, int]:
        """Export all data to JSON file."""
        with self._get_connection() as conn:
            data = {
                "violations": [v.to_dict() for v in self.get_violations_since(
                    datetime.utcnow() - timedelta(days=365)
                )],
                "snapshots": [s.to_dict() for s in self.get_snapshots(limit=1000)],
                "events": [e.to_dict() for e in self.get_events(limit=1000)],
            }
        
        output_path.write_text(json.dumps(data, indent=2, default=str))
        
        return {
            "violations": len(data["violations"]),
            "snapshots": len(data["snapshots"]),
            "events": len(data["events"]),
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall telemetry statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Violation stats
            cursor.execute('SELECT COUNT(*) FROM violations WHERE status = ?', 
                          (ResolutionStatus.OPEN.value,))
            open_violations = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM violations')
            total_violations = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM violations WHERE status = ?',
                          (ResolutionStatus.RESOLVED.value,))
            resolved_violations = cursor.fetchone()[0]
            
            # Avg resolution time
            cursor.execute('''
                SELECT AVG(
                    (julianday(resolved_at) - julianday(created_at)) * 24
                ) FROM violations 
                WHERE resolved_at IS NOT NULL
            ''')
            avg_resolution_hours = cursor.fetchone()[0] or 0
            
            # Snapshot count
            cursor.execute('SELECT COUNT(*) FROM snapshots')
            snapshot_count = cursor.fetchone()[0]
            
            # Event count
            cursor.execute('SELECT COUNT(*) FROM events')
            event_count = cursor.fetchone()[0]
            
            return {
                "violations": {
                    "open": open_violations,
                    "resolved": resolved_violations,
                    "total": total_violations,
                    "avg_resolution_hours": round(avg_resolution_hours, 2),
                },
                "snapshots": snapshot_count,
                "events": event_count,
            }


# Singleton store instance
_store: Optional[SQLiteTelemetryStore] = None


def get_telemetry_store(db_path: Optional[Path] = None) -> SQLiteTelemetryStore:
    """Get the singleton telemetry store."""
    global _store
    if _store is None:
        _store = SQLiteTelemetryStore(db_path)
    return _store


def reset_telemetry_store(db_path: Optional[Path] = None) -> SQLiteTelemetryStore:
    """Reset and return a fresh telemetry store."""
    global _store
    _store = SQLiteTelemetryStore(db_path)
    return _store
