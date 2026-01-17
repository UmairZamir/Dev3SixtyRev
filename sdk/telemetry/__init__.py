"""
Telemetry Module
================

Persistent telemetry tracking for code quality metrics.

Features:
- Violation persistence with git context
- Time-series metrics
- Quality trend analysis
- CI integration support
- Export to JSON/external systems

Usage:
    from sdk.telemetry import get_telemetry_collector, get_analytics
    
    # Record guard run
    from sdk.guards import run_guards
    result = run_guards(content, "path/to/file.py")
    
    collector = get_telemetry_collector()
    collector.record_guard_run(result, "path/to/file.py")
    
    # Take snapshot
    collector.take_snapshot(files_checked=100)
    
    # Analyze trends
    analytics = get_analytics()
    trend = analytics.compute_quality_trend(days=30)
    print(f"Health: {trend.overall_health} ({trend.health_score:.0f}/100)")
    
    # Generate report
    print(analytics.generate_report())
"""

from .models import (
    MetricType,
    EventType,
    ResolutionStatus,
    ViolationRecord,
    MetricRecord,
    TelemetryEvent,
    QualitySnapshot,
)

from .store import (
    TelemetryStore,
    SQLiteTelemetryStore,
    get_telemetry_store,
    reset_telemetry_store,
)

from .analytics import (
    TrendDirection,
    QualityTrend,
    GuardEffectiveness,
    FileHealth,
    TelemetryAnalytics,
    get_analytics,
)

from .collector import (
    TelemetryCollector,
    get_telemetry_collector,
)

__all__ = [
    # Models
    "MetricType",
    "EventType",
    "ResolutionStatus",
    "ViolationRecord",
    "MetricRecord",
    "TelemetryEvent",
    "QualitySnapshot",
    # Store
    "TelemetryStore",
    "SQLiteTelemetryStore",
    "get_telemetry_store",
    "reset_telemetry_store",
    # Analytics
    "TrendDirection",
    "QualityTrend",
    "GuardEffectiveness",
    "FileHealth",
    "TelemetryAnalytics",
    "get_analytics",
    # Collector
    "TelemetryCollector",
    "get_telemetry_collector",
]
