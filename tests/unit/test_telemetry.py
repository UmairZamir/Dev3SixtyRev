"""
Tests for Telemetry Module
==========================

Tests the telemetry system:
- Models
- Store (SQLite)
- Analytics
- Collector
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from sdk.telemetry import (
    ViolationRecord,
    MetricRecord,
    TelemetryEvent,
    QualitySnapshot,
    SQLiteTelemetryStore,
    TelemetryAnalytics,
    TelemetryCollector,
    ResolutionStatus,
    EventType,
    MetricType,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_telemetry.db"
        yield db_path


@pytest.fixture
def store(temp_db):
    """Create a test store."""
    return SQLiteTelemetryStore(temp_db)


@pytest.fixture
def sample_violation():
    """Create a sample violation."""
    return ViolationRecord(
        id="test123",
        guard_name="shell_component",
        guard_category="quality",
        guard_level="instant",
        severity="error",
        file_path="src/component.tsx",
        line_number=42,
        message="console.log('TODO') detected",
        code_snippet="console.log('TODO: implement')",
        author="developer",
        commit_hash="abc123",
        branch="main",
    )


class TestViolationRecord:
    """Tests for ViolationRecord model."""
    
    def test_generate_id(self):
        """Should generate unique IDs for different violations."""
        id1 = ViolationRecord.generate_id("guard1", "file.py", 10, "message1")
        id2 = ViolationRecord.generate_id("guard1", "file.py", 10, "message2")
        id3 = ViolationRecord.generate_id("guard1", "file.py", 10, "message1")
        
        assert id1 != id2
        assert id1 == id3  # Same inputs = same ID
    
    def test_age_hours(self, sample_violation):
        """Should calculate age correctly."""
        sample_violation.created_at = datetime.utcnow() - timedelta(hours=5)
        assert 4.9 < sample_violation.age_hours < 5.1
    
    def test_resolution_time_hours(self, sample_violation):
        """Should calculate resolution time correctly."""
        sample_violation.created_at = datetime.utcnow() - timedelta(hours=10)
        sample_violation.resolved_at = datetime.utcnow() - timedelta(hours=2)
        assert 7.9 < sample_violation.resolution_time_hours < 8.1
    
    def test_to_dict_and_back(self, sample_violation):
        """Should serialize and deserialize correctly."""
        data = sample_violation.to_dict()
        restored = ViolationRecord.from_dict(data)
        
        assert restored.id == sample_violation.id
        assert restored.guard_name == sample_violation.guard_name
        assert restored.file_path == sample_violation.file_path


class TestSQLiteTelemetryStore:
    """Tests for SQLite store."""
    
    def test_store_violation(self, store, sample_violation):
        """Should store and retrieve violations."""
        store.store_violation(sample_violation)
        
        retrieved = store.get_violation(sample_violation.id)
        assert retrieved is not None
        assert retrieved.id == sample_violation.id
        assert retrieved.guard_name == sample_violation.guard_name
    
    def test_get_open_violations(self, store, sample_violation):
        """Should get only open violations."""
        store.store_violation(sample_violation)
        
        open_v = store.get_open_violations()
        assert len(open_v) == 1
        
        # Resolve and check again
        store.resolve_violation(sample_violation.id)
        open_v = store.get_open_violations()
        assert len(open_v) == 0
    
    def test_resolve_violation(self, store, sample_violation):
        """Should resolve violations correctly."""
        store.store_violation(sample_violation)
        
        success = store.resolve_violation(
            sample_violation.id,
            resolved_by="fixer",
            resolution_commit="def456",
        )
        
        assert success
        
        retrieved = store.get_violation(sample_violation.id)
        assert retrieved.status == ResolutionStatus.RESOLVED
        assert retrieved.resolved_by == "fixer"
        assert retrieved.resolved_at is not None
    
    def test_store_metric(self, store):
        """Should store and retrieve metrics."""
        metric = MetricRecord(
            name="test.metric",
            metric_type=MetricType.GAUGE,
            value=42.5,
            dimensions={"env": "test"},
        )
        
        store.store_metric(metric)
        
        metrics = store.get_metrics("test.metric")
        assert len(metrics) == 1
        assert metrics[0].value == 42.5
    
    def test_store_event(self, store):
        """Should store and retrieve events."""
        event = TelemetryEvent(
            event_type=EventType.GUARD_RUN,
            data={"passed": True, "violations": 0},
        )
        
        store.store_event(event)
        
        events = store.get_events(EventType.GUARD_RUN)
        assert len(events) == 1
        assert events[0].data["passed"] is True
    
    def test_store_snapshot(self, store):
        """Should store and retrieve snapshots."""
        snapshot = QualitySnapshot(
            error_count=5,
            warning_count=10,
            info_count=2,
            files_with_violations=3,
            total_files_checked=50,
        )
        
        store.store_snapshot(snapshot)
        
        snapshots = store.get_snapshots(limit=10)
        assert len(snapshots) == 1
        assert snapshots[0].error_count == 5
        assert snapshots[0].total_violations == 17
    
    def test_get_statistics(self, store, sample_violation):
        """Should compute statistics correctly."""
        store.store_violation(sample_violation)
        
        stats = store.get_statistics()
        
        assert stats["violations"]["open"] == 1
        assert stats["violations"]["total"] == 1


class TestTelemetryAnalytics:
    """Tests for analytics engine."""
    
    def test_compute_quality_trend(self, store):
        """Should compute quality trends."""
        analytics = TelemetryAnalytics(store)
        
        # Add some snapshots
        for i in range(5):
            snapshot = QualitySnapshot(
                timestamp=datetime.utcnow() - timedelta(days=i),
                error_count=10 - i,  # Improving trend
                warning_count=5,
                info_count=2,
                files_with_violations=3,
                total_files_checked=50,
            )
            store.store_snapshot(snapshot)
        
        trend = analytics.compute_quality_trend(days=7)
        
        assert trend is not None
        assert trend.overall_health in ("healthy", "warning", "critical")
        assert 0 <= trend.health_score <= 100
    
    def test_get_guard_effectiveness(self, store, sample_violation):
        """Should compute guard effectiveness."""
        analytics = TelemetryAnalytics(store)
        
        # Add violations
        store.store_violation(sample_violation)
        
        # Add another and resolve it
        v2 = ViolationRecord(
            id="test456",
            guard_name="shell_component",
            guard_category="quality",
            guard_level="instant",
            severity="warning",
            file_path="src/other.tsx",
            line_number=10,
            message="Another issue",
        )
        store.store_violation(v2)
        store.resolve_violation(v2.id)
        
        effectiveness = analytics.get_guard_effectiveness()
        
        assert len(effectiveness) > 0
        guard = effectiveness[0]
        assert guard.guard_name == "shell_component"
        assert guard.total_violations == 2
        assert guard.resolved_violations == 1
    
    def test_get_file_health(self, store, sample_violation):
        """Should compute file health."""
        analytics = TelemetryAnalytics(store)
        
        store.store_violation(sample_violation)
        
        files = analytics.get_file_health()
        
        assert len(files) > 0
        assert files[0].file_path == "src/component.tsx"
        assert files[0].open_violations == 1
    
    def test_generate_report(self, store, sample_violation):
        """Should generate readable report."""
        analytics = TelemetryAnalytics(store)
        
        store.store_violation(sample_violation)
        store.store_snapshot(QualitySnapshot(
            error_count=1,
            warning_count=0,
            info_count=0,
            files_with_violations=1,
            total_files_checked=10,
        ))
        
        report = analytics.generate_report()
        
        assert "QUALITY TELEMETRY REPORT" in report
        assert "Overall Health" in report


class TestTelemetryCollector:
    """Tests for telemetry collector."""
    
    def test_record_guard_run_from_violations(self, store):
        """Should record violations from guard run."""
        collector = TelemetryCollector(store)
        
        violations = [
            {
                "guard_name": "test_guard",
                "guard_category": "quality",
                "severity": "error",
                "line": 10,
                "message": "Test violation",
            },
        ]
        
        new_count = collector.record_guard_run_from_violations(
            violations,
            file_path="test.py",
            passed=False,
        )
        
        assert new_count == 1
        
        # Recording same violation again shouldn't create duplicate
        new_count = collector.record_guard_run_from_violations(
            violations,
            file_path="test.py",
            passed=False,
        )
        
        assert new_count == 0
    
    def test_take_snapshot(self, store, sample_violation):
        """Should take quality snapshot."""
        collector = TelemetryCollector(store)
        
        store.store_violation(sample_violation)
        
        snapshot = collector.take_snapshot(files_checked=10)
        
        assert snapshot.error_count == 1
        assert snapshot.total_files_checked == 10
    
    def test_record_phase_gate(self, store):
        """Should record phase gate events."""
        collector = TelemetryCollector(store)
        
        collector.record_phase_gate(
            phase_number=1,
            passed=True,
            details={"tasks": 5},
        )
        
        events = store.get_events(EventType.PHASE_GATE_PASSED)
        
        assert len(events) == 1
        assert events[0].data["phase_number"] == 1
    
    def test_record_task_completion(self, store):
        """Should record task verification events."""
        collector = TelemetryCollector(store)
        
        collector.record_task_completion(
            task_id="task_1_1",
            verified=True,
            details={"evidence_count": 3},
        )
        
        events = store.get_events(EventType.TASK_VERIFIED)
        
        assert len(events) == 1
        assert events[0].data["task_id"] == "task_1_1"


class TestQualitySnapshot:
    """Tests for QualitySnapshot model."""
    
    def test_computed_properties(self):
        """Should compute derived metrics correctly."""
        snapshot = QualitySnapshot(
            error_count=5,
            warning_count=10,
            info_count=2,
            files_with_violations=3,
            total_files_checked=10,
        )
        
        assert snapshot.total_violations == 17
        assert snapshot.violation_rate == 1.7  # 17 / 10
        assert snapshot.clean_file_rate == 0.7  # 7 / 10
    
    def test_to_dict_and_back(self):
        """Should serialize and deserialize correctly."""
        snapshot = QualitySnapshot(
            error_count=5,
            warning_count=10,
            info_count=2,
            by_category={"quality": 10, "security": 7},
            by_guard={"shell_component": 15, "security": 2},
            files_with_violations=3,
            total_files_checked=10,
        )
        
        data = snapshot.to_dict()
        restored = QualitySnapshot.from_dict(data)
        
        assert restored.error_count == snapshot.error_count
        assert restored.by_category == snapshot.by_category
        assert restored.by_guard == snapshot.by_guard
