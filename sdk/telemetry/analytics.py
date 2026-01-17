"""
Telemetry Analytics
===================

Trend analysis and quality metrics computation.

Answers questions like:
- Are we getting better or worse over time?
- What's our average time to fix violations?
- Which guards catch the most issues?
- Which files have the most problems?

Based on patterns from:
- Stripe's quality dashboards
- Google's code health metrics
- SonarQube quality gates
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
import statistics

from .models import (
    ViolationRecord,
    QualitySnapshot,
    ResolutionStatus,
    MetricRecord,
    MetricType,
)
from .store import TelemetryStore, get_telemetry_store


@dataclass
class TrendDirection:
    """Represents a trend direction with magnitude."""
    direction: str  # "improving", "degrading", "stable"
    change_percent: float
    confidence: float  # 0-1 based on data points
    
    @property
    def emoji(self) -> str:
        if self.direction == "improving":
            return "📈" if self.change_percent > 10 else "↗️"
        elif self.direction == "degrading":
            return "📉" if self.change_percent > 10 else "↘️"
        return "➡️"


@dataclass
class QualityTrend:
    """Quality trend over a time period."""
    period_start: datetime
    period_end: datetime
    
    # Violation trends
    total_violations: TrendDirection
    errors: TrendDirection
    warnings: TrendDirection
    
    # Resolution trends
    avg_resolution_time_hours: float
    resolution_time_trend: TrendDirection
    
    # Top issues
    top_guards: List[Tuple[str, int]]  # (guard_name, count)
    top_files: List[Tuple[str, int]]   # (file_path, count)
    top_categories: List[Tuple[str, int]]  # (category, count)
    
    # Summary
    overall_health: str  # "healthy", "warning", "critical"
    health_score: float  # 0-100


@dataclass  
class GuardEffectiveness:
    """Effectiveness metrics for a single guard."""
    guard_name: str
    total_violations: int
    resolved_violations: int
    open_violations: int
    avg_resolution_hours: float
    false_positive_rate: float
    
    @property
    def resolution_rate(self) -> float:
        if self.total_violations == 0:
            return 1.0
        return self.resolved_violations / self.total_violations


@dataclass
class FileHealth:
    """Health metrics for a single file."""
    file_path: str
    total_violations: int
    open_violations: int
    violation_density: float  # violations per 100 lines (estimated)
    top_violation_types: List[Tuple[str, int]]
    last_violation_at: Optional[datetime]
    
    @property
    def health_status(self) -> str:
        if self.open_violations == 0:
            return "healthy"
        elif self.open_violations <= 2:
            return "warning"
        return "critical"


class TelemetryAnalytics:
    """
    Analytics engine for telemetry data.
    
    Computes trends, identifies patterns, and generates insights.
    """
    
    def __init__(self, store: Optional[TelemetryStore] = None):
        self.store = store or get_telemetry_store()
    
    def compute_quality_trend(
        self,
        days: int = 30,
        compare_to_previous: bool = True,
    ) -> QualityTrend:
        """
        Compute quality trend over a time period.
        
        Args:
            days: Number of days to analyze
            compare_to_previous: Compare to previous period of same length
        """
        now = datetime.utcnow()
        period_start = now - timedelta(days=days)
        
        # Get current period snapshots
        current_snapshots = self.store.get_snapshots(
            since=period_start,
            until=now,
            limit=1000,
        )
        
        # Get previous period snapshots for comparison
        prev_start = period_start - timedelta(days=days)
        prev_snapshots = self.store.get_snapshots(
            since=prev_start,
            until=period_start,
            limit=1000,
        ) if compare_to_previous else []
        
        # Compute violation trends
        total_trend = self._compute_trend(
            [s.total_violations for s in current_snapshots],
            [s.total_violations for s in prev_snapshots],
        )
        error_trend = self._compute_trend(
            [s.error_count for s in current_snapshots],
            [s.error_count for s in prev_snapshots],
        )
        warning_trend = self._compute_trend(
            [s.warning_count for s in current_snapshots],
            [s.warning_count for s in prev_snapshots],
        )
        
        # Get violations for detailed analysis
        violations = self.store.get_violations_since(period_start)
        
        # Compute resolution time
        resolved = [v for v in violations if v.resolution_time_hours is not None]
        avg_resolution = (
            statistics.mean([v.resolution_time_hours for v in resolved])
            if resolved else 0.0
        )
        
        # Resolution time trend
        resolution_trend = self._compute_resolution_trend(violations, days)
        
        # Top issues
        guard_counts: Dict[str, int] = defaultdict(int)
        file_counts: Dict[str, int] = defaultdict(int)
        category_counts: Dict[str, int] = defaultdict(int)
        
        for v in violations:
            guard_counts[v.guard_name] += 1
            file_counts[v.file_path] += 1
            category_counts[v.guard_category] += 1
        
        top_guards = sorted(guard_counts.items(), key=lambda x: -x[1])[:5]
        top_files = sorted(file_counts.items(), key=lambda x: -x[1])[:5]
        top_categories = sorted(category_counts.items(), key=lambda x: -x[1])[:5]
        
        # Compute overall health
        health_score, health_status = self._compute_health_score(
            current_snapshots, violations
        )
        
        return QualityTrend(
            period_start=period_start,
            period_end=now,
            total_violations=total_trend,
            errors=error_trend,
            warnings=warning_trend,
            avg_resolution_time_hours=avg_resolution,
            resolution_time_trend=resolution_trend,
            top_guards=top_guards,
            top_files=top_files,
            top_categories=top_categories,
            overall_health=health_status,
            health_score=health_score,
        )
    
    def get_guard_effectiveness(self, guard_name: Optional[str] = None) -> List[GuardEffectiveness]:
        """Get effectiveness metrics for guards."""
        violations = self.store.get_violations_since(
            datetime.utcnow() - timedelta(days=90)
        )
        
        # Group by guard
        by_guard: Dict[str, List[ViolationRecord]] = defaultdict(list)
        for v in violations:
            if guard_name is None or v.guard_name == guard_name:
                by_guard[v.guard_name].append(v)
        
        results = []
        for name, guard_violations in by_guard.items():
            resolved = [v for v in guard_violations if v.status == ResolutionStatus.RESOLVED]
            open_v = [v for v in guard_violations if v.status == ResolutionStatus.OPEN]
            false_positives = [v for v in guard_violations if v.status == ResolutionStatus.FALSE_POSITIVE]
            
            avg_resolution = 0.0
            if resolved:
                times = [v.resolution_time_hours for v in resolved if v.resolution_time_hours]
                avg_resolution = statistics.mean(times) if times else 0.0
            
            fp_rate = len(false_positives) / len(guard_violations) if guard_violations else 0.0
            
            results.append(GuardEffectiveness(
                guard_name=name,
                total_violations=len(guard_violations),
                resolved_violations=len(resolved),
                open_violations=len(open_v),
                avg_resolution_hours=avg_resolution,
                false_positive_rate=fp_rate,
            ))
        
        return sorted(results, key=lambda x: -x.total_violations)
    
    def get_file_health(self, file_path: Optional[str] = None, top_n: int = 10) -> List[FileHealth]:
        """Get health metrics for files."""
        violations = self.store.get_violations_since(
            datetime.utcnow() - timedelta(days=90)
        )
        
        # Group by file
        by_file: Dict[str, List[ViolationRecord]] = defaultdict(list)
        for v in violations:
            if file_path is None or v.file_path == file_path:
                by_file[v.file_path].append(v)
        
        results = []
        for path, file_violations in by_file.items():
            open_v = [v for v in file_violations if v.status == ResolutionStatus.OPEN]
            
            # Group by guard for top violation types
            by_guard: Dict[str, int] = defaultdict(int)
            for v in file_violations:
                by_guard[v.guard_name] += 1
            top_types = sorted(by_guard.items(), key=lambda x: -x[1])[:3]
            
            # Estimate violation density (assuming ~50 lines per file if unknown)
            density = len(file_violations) / 50 * 100
            
            last_violation = max(
                (v.created_at for v in file_violations),
                default=None
            )
            
            results.append(FileHealth(
                file_path=path,
                total_violations=len(file_violations),
                open_violations=len(open_v),
                violation_density=density,
                top_violation_types=top_types,
                last_violation_at=last_violation,
            ))
        
        # Sort by open violations, then total
        results = sorted(results, key=lambda x: (-x.open_violations, -x.total_violations))
        return results[:top_n] if file_path is None else results
    
    def get_daily_metrics(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily violation counts for charting."""
        now = datetime.utcnow()
        violations = self.store.get_violations_since(now - timedelta(days=days))
        
        # Group by day
        by_day: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "total": 0, "errors": 0, "warnings": 0, "resolved": 0
        })
        
        for v in violations:
            day = v.created_at.strftime("%Y-%m-%d")
            by_day[day]["total"] += 1
            if v.severity == "error":
                by_day[day]["errors"] += 1
            elif v.severity == "warning":
                by_day[day]["warnings"] += 1
            if v.status == ResolutionStatus.RESOLVED:
                by_day[day]["resolved"] += 1
        
        # Fill in missing days
        result = []
        current = now - timedelta(days=days)
        while current <= now:
            day = current.strftime("%Y-%m-%d")
            data = by_day.get(day, {"total": 0, "errors": 0, "warnings": 0, "resolved": 0})
            result.append({
                "date": day,
                **data,
            })
            current += timedelta(days=1)
        
        return result
    
    def generate_report(self, days: int = 30) -> str:
        """Generate a human-readable quality report."""
        trend = self.compute_quality_trend(days)
        guards = self.get_guard_effectiveness()[:5]
        files = self.get_file_health(top_n=5)
        stats = self.store.get_statistics()
        
        lines = [
            "",
            "═" * 60,
            "           QUALITY TELEMETRY REPORT",
            "═" * 60,
            f"Period: {trend.period_start.strftime('%Y-%m-%d')} to {trend.period_end.strftime('%Y-%m-%d')}",
            "",
            f"Overall Health: {trend.overall_health.upper()} ({trend.health_score:.0f}/100)",
            "",
            "─── TRENDS ───",
            f"  Total Violations: {trend.total_violations.emoji} {trend.total_violations.direction} ({trend.total_violations.change_percent:+.1f}%)",
            f"  Errors: {trend.errors.emoji} {trend.errors.direction} ({trend.errors.change_percent:+.1f}%)",
            f"  Warnings: {trend.warnings.emoji} {trend.warnings.direction} ({trend.warnings.change_percent:+.1f}%)",
            "",
            f"  Avg Resolution Time: {trend.avg_resolution_time_hours:.1f} hours",
            f"  Resolution Trend: {trend.resolution_time_trend.emoji} {trend.resolution_time_trend.direction}",
            "",
            "─── CURRENT STATUS ───",
            f"  Open Violations: {stats['violations']['open']}",
            f"  Resolved (all time): {stats['violations']['resolved']}",
            f"  Avg Resolution: {stats['violations']['avg_resolution_hours']:.1f} hours",
            "",
            "─── TOP ISSUES BY GUARD ───",
        ]
        
        for guard_name, count in trend.top_guards:
            lines.append(f"  • {guard_name}: {count}")
        
        lines.extend([
            "",
            "─── FILES NEEDING ATTENTION ───",
        ])
        
        for file in files[:5]:
            status_icon = "🟢" if file.health_status == "healthy" else "🟡" if file.health_status == "warning" else "🔴"
            lines.append(f"  {status_icon} {file.file_path}: {file.open_violations} open")
        
        lines.extend([
            "",
            "─── GUARD EFFECTIVENESS ───",
        ])
        
        for guard in guards[:5]:
            lines.append(
                f"  • {guard.guard_name}: {guard.resolution_rate:.0%} resolved, "
                f"{guard.avg_resolution_hours:.1f}h avg"
            )
        
        lines.extend([
            "",
            "═" * 60,
        ])
        
        return "\n".join(lines)
    
    def _compute_trend(
        self, 
        current_values: List[float], 
        previous_values: List[float]
    ) -> TrendDirection:
        """Compute trend direction between two periods."""
        if not current_values:
            return TrendDirection("stable", 0.0, 0.0)
        
        current_avg = statistics.mean(current_values) if current_values else 0
        previous_avg = statistics.mean(previous_values) if previous_values else current_avg
        
        if previous_avg == 0:
            change_percent = 0.0 if current_avg == 0 else 100.0
        else:
            change_percent = ((current_avg - previous_avg) / previous_avg) * 100
        
        # For violations, decreasing is good
        if change_percent < -5:
            direction = "improving"
        elif change_percent > 5:
            direction = "degrading"
        else:
            direction = "stable"
        
        confidence = min(1.0, len(current_values) / 10)  # More data = higher confidence
        
        return TrendDirection(direction, abs(change_percent), confidence)
    
    def _compute_resolution_trend(
        self, 
        violations: List[ViolationRecord], 
        days: int
    ) -> TrendDirection:
        """Compute trend in resolution time."""
        resolved = [v for v in violations if v.resolution_time_hours is not None]
        
        if len(resolved) < 2:
            return TrendDirection("stable", 0.0, 0.0)
        
        # Split into halves
        sorted_v = sorted(resolved, key=lambda x: x.created_at)
        mid = len(sorted_v) // 2
        
        first_half = [v.resolution_time_hours for v in sorted_v[:mid]]
        second_half = [v.resolution_time_hours for v in sorted_v[mid:]]
        
        first_avg = statistics.mean(first_half) if first_half else 0
        second_avg = statistics.mean(second_half) if second_half else 0
        
        if first_avg == 0:
            change_percent = 0.0
        else:
            change_percent = ((second_avg - first_avg) / first_avg) * 100
        
        # For resolution time, decreasing is good
        if change_percent < -10:
            direction = "improving"
        elif change_percent > 10:
            direction = "degrading"
        else:
            direction = "stable"
        
        confidence = min(1.0, len(resolved) / 20)
        
        return TrendDirection(direction, abs(change_percent), confidence)
    
    def _compute_health_score(
        self,
        snapshots: List[QualitySnapshot],
        violations: List[ViolationRecord],
    ) -> Tuple[float, str]:
        """Compute overall health score (0-100) and status."""
        if not snapshots:
            return 100.0, "healthy"
        
        # Latest snapshot
        latest = snapshots[0] if snapshots else None
        
        # Factors:
        # 1. Open error count (weight: 40%)
        # 2. Violation rate (weight: 30%)
        # 3. Resolution rate (weight: 30%)
        
        open_violations = [v for v in violations if v.status == ResolutionStatus.OPEN]
        open_errors = len([v for v in open_violations if v.severity == "error"])
        
        # Error penalty: -10 points per error, max -40
        error_score = max(0, 40 - (open_errors * 10))
        
        # Violation rate: target < 0.1 violations per file
        if latest and latest.total_files_checked > 0:
            violation_rate = latest.total_violations / latest.total_files_checked
            rate_score = max(0, 30 - (violation_rate * 100))
        else:
            rate_score = 30
        
        # Resolution rate
        total = len(violations)
        resolved = len([v for v in violations if v.status == ResolutionStatus.RESOLVED])
        resolution_rate = resolved / total if total > 0 else 1.0
        resolution_score = resolution_rate * 30
        
        score = error_score + rate_score + resolution_score
        
        if score >= 80:
            status = "healthy"
        elif score >= 50:
            status = "warning"
        else:
            status = "critical"
        
        return score, status


def get_analytics(store: Optional[TelemetryStore] = None) -> TelemetryAnalytics:
    """Get analytics instance."""
    return TelemetryAnalytics(store)
