"""
Telemetry Metrics
=================

Aggregation and trend analysis for quality metrics.

Answers questions like:
- Are we getting better or worse over time?
- Which guards catch the most issues?
- What's our mean time to resolution?
- Which files have the most problems?

Enterprise Pattern: Pre-computed daily metrics with trend analysis.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
import statistics

from .events import EventType, Severity, TelemetryEvent
from .store import TelemetryStore, get_telemetry_store


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: datetime
    value: float
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MetricSeries:
    """A time series of metric values."""
    name: str
    points: List[MetricPoint]
    
    @property
    def values(self) -> List[float]:
        return [p.value for p in self.points]
    
    @property
    def latest(self) -> Optional[float]:
        return self.points[-1].value if self.points else None
    
    @property
    def average(self) -> Optional[float]:
        return statistics.mean(self.values) if self.values else None
    
    @property
    def trend(self) -> str:
        """Calculate trend direction."""
        if len(self.values) < 2:
            return "stable"
        
        # Compare last 25% to first 25%
        quarter = max(1, len(self.values) // 4)
        early = statistics.mean(self.values[:quarter])
        late = statistics.mean(self.values[-quarter:])
        
        change = (late - early) / early if early != 0 else 0
        
        if change > 0.1:
            return "increasing"
        elif change < -0.1:
            return "decreasing"
        return "stable"
    
    def change_percent(self, periods: int = 7) -> Optional[float]:
        """Calculate percent change over last N periods."""
        if len(self.values) < periods + 1:
            return None
        
        old_val = self.values[-(periods + 1)]
        new_val = self.values[-1]
        
        if old_val == 0:
            return None
        
        return ((new_val - old_val) / old_val) * 100


@dataclass
class QualityMetrics:
    """Collection of quality metrics."""
    
    # Violation metrics
    total_violations: int = 0
    violations_by_severity: Dict[str, int] = None
    violations_by_guard: Dict[str, int] = None
    violations_by_file: Dict[str, int] = None
    
    # Resolution metrics
    resolved_count: int = 0
    unresolved_count: int = 0
    mean_resolution_time_hours: Optional[float] = None
    
    # Trend metrics
    daily_violation_counts: List[Tuple[str, int]] = None
    
    # Top offenders
    top_offending_files: List[Tuple[str, int]] = None
    top_offending_guards: List[Tuple[str, int]] = None
    
    def __post_init__(self):
        if self.violations_by_severity is None:
            self.violations_by_severity = {}
        if self.violations_by_guard is None:
            self.violations_by_guard = {}
        if self.violations_by_file is None:
            self.violations_by_file = {}
        if self.daily_violation_counts is None:
            self.daily_violation_counts = []
        if self.top_offending_files is None:
            self.top_offending_files = []
        if self.top_offending_guards is None:
            self.top_offending_guards = []
    
    @property
    def resolution_rate(self) -> float:
        """Percentage of violations resolved."""
        total = self.resolved_count + self.unresolved_count
        return (self.resolved_count / total * 100) if total > 0 else 0
    
    def format_report(self) -> str:
        """Format metrics as a report."""
        lines = [
            "",
            "═" * 60,
            "           QUALITY METRICS REPORT",
            "═" * 60,
            "",
            f"Total Violations: {self.total_violations}",
            f"Resolved: {self.resolved_count} ({self.resolution_rate:.1f}%)",
            f"Unresolved: {self.unresolved_count}",
        ]
        
        if self.mean_resolution_time_hours:
            lines.append(f"Mean Resolution Time: {self.mean_resolution_time_hours:.1f} hours")
        
        lines.append("")
        lines.append("By Severity:")
        for sev, count in sorted(self.violations_by_severity.items(), key=lambda x: -x[1]):
            lines.append(f"  {sev}: {count}")
        
        if self.top_offending_files:
            lines.append("")
            lines.append("Top Offending Files:")
            for file, count in self.top_offending_files[:5]:
                lines.append(f"  {file}: {count}")
        
        if self.top_offending_guards:
            lines.append("")
            lines.append("Guards Catching Most Issues:")
            for guard, count in self.top_offending_guards[:5]:
                lines.append(f"  {guard}: {count}")
        
        lines.append("")
        lines.append("═" * 60)
        return "\n".join(lines)


class MetricsCalculator:
    """
    Calculates quality metrics from telemetry data.
    
    Usage:
        calc = MetricsCalculator()
        metrics = calc.calculate_quality_metrics(days=30)
        print(metrics.format_report())
        
        # Trend analysis
        trend = calc.get_violation_trend(days=90)
        print(f"Trend: {trend.trend}")
    """
    
    def __init__(self, store: Optional[TelemetryStore] = None):
        self.store = store or get_telemetry_store()
    
    def calculate_quality_metrics(
        self,
        days: int = 30,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> QualityMetrics:
        """Calculate comprehensive quality metrics."""
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(days=days)
        
        # Get all violation events
        events = self.store.query(
            event_types=[EventType.GUARD_VIOLATION],
            start_time=start_time,
            end_time=end_time,
            limit=10000,
        )
        
        metrics = QualityMetrics()
        metrics.total_violations = len(events)
        
        # Aggregate by severity
        by_severity: Dict[str, int] = defaultdict(int)
        by_guard: Dict[str, int] = defaultdict(int)
        by_file: Dict[str, int] = defaultdict(int)
        by_day: Dict[str, int] = defaultdict(int)
        
        resolution_times = []
        
        for event in events:
            by_severity[event.severity.value] += 1
            
            if event.guard_name:
                by_guard[event.guard_name] += 1
            
            if event.source_file:
                by_file[event.source_file] += 1
            
            day = event.timestamp.strftime("%Y-%m-%d")
            by_day[day] += 1
            
            if event.resolved:
                metrics.resolved_count += 1
                if event.resolution_time_seconds:
                    resolution_times.append(event.resolution_time_seconds / 3600)  # Convert to hours
            else:
                metrics.unresolved_count += 1
        
        metrics.violations_by_severity = dict(by_severity)
        metrics.violations_by_guard = dict(by_guard)
        metrics.violations_by_file = dict(by_file)
        
        # Daily counts
        metrics.daily_violation_counts = sorted(by_day.items())
        
        # Top offenders
        metrics.top_offending_files = sorted(by_file.items(), key=lambda x: -x[1])[:10]
        metrics.top_offending_guards = sorted(by_guard.items(), key=lambda x: -x[1])[:10]
        
        # Mean resolution time
        if resolution_times:
            metrics.mean_resolution_time_hours = statistics.mean(resolution_times)
        
        return metrics
    
    def get_violation_trend(self, days: int = 30) -> MetricSeries:
        """Get daily violation count trend."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        events = self.store.query(
            event_types=[EventType.GUARD_VIOLATION],
            start_time=start_time,
            end_time=end_time,
            limit=50000,
        )
        
        # Group by day
        by_day: Dict[str, int] = defaultdict(int)
        for event in events:
            day = event.timestamp.strftime("%Y-%m-%d")
            by_day[day] += 1
        
        # Fill in missing days with zeros
        points = []
        current = start_time.date()
        end = end_time.date()
        while current <= end:
            day_str = current.strftime("%Y-%m-%d")
            points.append(MetricPoint(
                timestamp=datetime.combine(current, datetime.min.time()),
                value=by_day.get(day_str, 0),
            ))
            current += timedelta(days=1)
        
        return MetricSeries(name="daily_violations", points=points)
    
    def get_resolution_rate_trend(self, days: int = 30) -> MetricSeries:
        """Get resolution rate trend over time."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        events = self.store.query(
            event_types=[EventType.GUARD_VIOLATION],
            start_time=start_time,
            end_time=end_time,
            limit=50000,
        )
        
        # Group by day
        by_day: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "resolved": 0})
        for event in events:
            day = event.timestamp.strftime("%Y-%m-%d")
            by_day[day]["total"] += 1
            if event.resolved:
                by_day[day]["resolved"] += 1
        
        # Calculate rate per day
        points = []
        current = start_time.date()
        end = end_time.date()
        while current <= end:
            day_str = current.strftime("%Y-%m-%d")
            data = by_day.get(day_str, {"total": 0, "resolved": 0})
            rate = (data["resolved"] / data["total"] * 100) if data["total"] > 0 else 100
            points.append(MetricPoint(
                timestamp=datetime.combine(current, datetime.min.time()),
                value=rate,
                metadata={"total": data["total"], "resolved": data["resolved"]},
            ))
            current += timedelta(days=1)
        
        return MetricSeries(name="resolution_rate", points=points)
    
    def get_guard_effectiveness(self, days: int = 30) -> Dict[str, Dict[str, Any]]:
        """Get effectiveness metrics per guard."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Get violations
        violations = self.store.query(
            event_types=[EventType.GUARD_VIOLATION],
            start_time=start_time,
            end_time=end_time,
            limit=50000,
        )
        
        # Get guard runs
        runs = self.store.query(
            event_types=[EventType.GUARD_RUN, EventType.GUARD_PASS],
            start_time=start_time,
            end_time=end_time,
            limit=50000,
        )
        
        # Aggregate
        by_guard: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "violations": 0,
            "runs": 0,
            "files_affected": set(),
            "resolution_times": [],
        })
        
        for event in violations:
            if event.guard_name:
                by_guard[event.guard_name]["violations"] += 1
                if event.source_file:
                    by_guard[event.guard_name]["files_affected"].add(event.source_file)
                if event.resolved and event.resolution_time_seconds:
                    by_guard[event.guard_name]["resolution_times"].append(
                        event.resolution_time_seconds / 3600
                    )
        
        for event in runs:
            if event.guard_name:
                by_guard[event.guard_name]["runs"] += 1
        
        # Calculate effectiveness
        result = {}
        for guard, data in by_guard.items():
            result[guard] = {
                "violations": data["violations"],
                "runs": data["runs"],
                "catch_rate": (data["violations"] / data["runs"] * 100) if data["runs"] > 0 else 0,
                "files_affected": len(data["files_affected"]),
                "mean_resolution_time_hours": (
                    statistics.mean(data["resolution_times"]) if data["resolution_times"] else None
                ),
            }
        
        return result
    
    def get_file_health(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get health score for files with most issues."""
        metrics = self.calculate_quality_metrics(days=30)
        
        results = []
        for file_path, count in metrics.top_offending_files[:limit]:
            # Get more details about this file
            events = self.store.query(
                event_types=[EventType.GUARD_VIOLATION],
                source_file=file_path,
                limit=100,
            )
            
            unresolved = sum(1 for e in events if not e.resolved)
            
            results.append({
                "file": file_path,
                "total_violations": count,
                "unresolved": unresolved,
                "health_score": max(0, 100 - (count * 5) - (unresolved * 10)),
            })
        
        return results
    
    def compare_periods(
        self,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Compare metrics between two equal periods."""
        end_time = datetime.utcnow()
        mid_time = end_time - timedelta(days=days)
        start_time = mid_time - timedelta(days=days)
        
        # Get metrics for each period
        current = self.calculate_quality_metrics(
            start_time=mid_time,
            end_time=end_time,
        )
        previous = self.calculate_quality_metrics(
            start_time=start_time,
            end_time=mid_time,
        )
        
        # Calculate changes
        def change(current_val, previous_val):
            if previous_val == 0:
                return None
            return ((current_val - previous_val) / previous_val) * 100
        
        return {
            "period_days": days,
            "current": {
                "violations": current.total_violations,
                "resolved": current.resolved_count,
                "resolution_rate": current.resolution_rate,
            },
            "previous": {
                "violations": previous.total_violations,
                "resolved": previous.resolved_count,
                "resolution_rate": previous.resolution_rate,
            },
            "changes": {
                "violations": change(current.total_violations, previous.total_violations),
                "resolved": change(current.resolved_count, previous.resolved_count),
                "resolution_rate": change(current.resolution_rate, previous.resolution_rate),
            },
            "improving": current.total_violations < previous.total_violations,
        }


def calculate_metrics(days: int = 30) -> QualityMetrics:
    """Convenience function to calculate quality metrics."""
    calc = MetricsCalculator()
    return calc.calculate_quality_metrics(days=days)


def get_quality_trend(days: int = 30) -> MetricSeries:
    """Convenience function to get quality trend."""
    calc = MetricsCalculator()
    return calc.get_violation_trend(days=days)
