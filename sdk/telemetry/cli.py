"""
Telemetry CLI Commands
======================

CLI commands for telemetry management and reporting.
"""

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(name="telemetry", help="Telemetry and metrics commands")
console = Console()


@app.command()
def report(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
):
    """Generate quality telemetry report."""
    from sdk.telemetry import get_analytics
    
    analytics = get_analytics()
    report_text = analytics.generate_report(days)
    console.print(report_text)


@app.command()
def trend(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
):
    """Show quality trend analysis."""
    from sdk.telemetry import get_analytics
    
    analytics = get_analytics()
    trend = analytics.compute_quality_trend(days)
    
    console.print(Panel.fit(
        f"[bold]Quality Trend Analysis[/bold]\n"
        f"Period: {trend.period_start.strftime('%Y-%m-%d')} to {trend.period_end.strftime('%Y-%m-%d')}",
        title="Trend Analysis",
    ))
    
    table = Table(title="Violation Trends")
    table.add_column("Metric", style="cyan")
    table.add_column("Direction", justify="center")
    table.add_column("Change", justify="right")
    
    table.add_row(
        "Total Violations",
        f"{trend.total_violations.emoji} {trend.total_violations.direction}",
        f"{trend.total_violations.change_percent:+.1f}%",
    )
    table.add_row(
        "Errors",
        f"{trend.errors.emoji} {trend.errors.direction}",
        f"{trend.errors.change_percent:+.1f}%",
    )
    table.add_row(
        "Warnings",
        f"{trend.warnings.emoji} {trend.warnings.direction}",
        f"{trend.warnings.change_percent:+.1f}%",
    )
    table.add_row(
        "Resolution Time",
        f"{trend.resolution_time_trend.emoji} {trend.resolution_time_trend.direction}",
        f"{trend.resolution_time_trend.change_percent:+.1f}%",
    )
    
    console.print(table)
    
    console.print(f"\n[bold]Overall Health:[/bold] {trend.overall_health.upper()} ({trend.health_score:.0f}/100)")


@app.command()
def violations(
    status: str = typer.Option("open", "--status", "-s", help="Filter by status (open/resolved/all)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum violations to show"),
):
    """List tracked violations."""
    from sdk.telemetry import get_telemetry_store, ResolutionStatus
    
    store = get_telemetry_store()
    
    if status == "open":
        violations = store.get_open_violations()[:limit]
    elif status == "resolved":
        from datetime import datetime, timedelta
        all_v = store.get_violations_since(datetime.utcnow() - timedelta(days=90))
        violations = [v for v in all_v if v.status == ResolutionStatus.RESOLVED][:limit]
    else:
        from datetime import datetime, timedelta
        violations = store.get_violations_since(datetime.utcnow() - timedelta(days=90))[:limit]
    
    if not violations:
        console.print("[green]No violations found.[/green]")
        return
    
    table = Table(title=f"Violations ({status})")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Guard", style="cyan", width=15)
    table.add_column("Severity", width=8)
    table.add_column("File", width=30)
    table.add_column("Line", justify="right", width=5)
    table.add_column("Age", justify="right", width=8)
    
    for v in violations:
        severity_style = "red" if v.severity == "error" else "yellow" if v.severity == "warning" else "dim"
        age = f"{v.age_hours:.1f}h" if v.age_hours < 48 else f"{v.age_hours/24:.1f}d"
        
        table.add_row(
            v.id[:8],
            v.guard_name,
            f"[{severity_style}]{v.severity}[/{severity_style}]",
            v.file_path[-30:] if len(v.file_path) > 30 else v.file_path,
            str(v.line_number),
            age,
        )
    
    console.print(table)
    console.print(f"\n[dim]Showing {len(violations)} violations[/dim]")


@app.command()
def guards():
    """Show guard effectiveness metrics."""
    from sdk.telemetry import get_analytics
    
    analytics = get_analytics()
    guards = analytics.get_guard_effectiveness()
    
    if not guards:
        console.print("[yellow]No guard data available yet.[/yellow]")
        return
    
    table = Table(title="Guard Effectiveness (Last 90 Days)")
    table.add_column("Guard", style="cyan")
    table.add_column("Total", justify="right")
    table.add_column("Open", justify="right")
    table.add_column("Resolved", justify="right")
    table.add_column("Resolution Rate", justify="right")
    table.add_column("Avg Time", justify="right")
    
    for g in guards:
        rate_style = "green" if g.resolution_rate >= 0.8 else "yellow" if g.resolution_rate >= 0.5 else "red"
        
        table.add_row(
            g.guard_name,
            str(g.total_violations),
            str(g.open_violations),
            str(g.resolved_violations),
            f"[{rate_style}]{g.resolution_rate:.0%}[/{rate_style}]",
            f"{g.avg_resolution_hours:.1f}h",
        )
    
    console.print(table)


@app.command()
def files(
    top: int = typer.Option(10, "--top", "-t", help="Number of files to show"),
):
    """Show file health metrics."""
    from sdk.telemetry import get_analytics
    
    analytics = get_analytics()
    files = analytics.get_file_health(top_n=top)
    
    if not files:
        console.print("[green]No files with violations.[/green]")
        return
    
    table = Table(title=f"Files Needing Attention (Top {top})")
    table.add_column("Status", width=3)
    table.add_column("File", style="cyan")
    table.add_column("Open", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Top Issue", width=15)
    
    for f in files:
        status_icon = "🟢" if f.health_status == "healthy" else "🟡" if f.health_status == "warning" else "🔴"
        top_issue = f.top_violation_types[0][0] if f.top_violation_types else "-"
        
        table.add_row(
            status_icon,
            f.file_path[-40:] if len(f.file_path) > 40 else f.file_path,
            str(f.open_violations),
            str(f.total_violations),
            top_issue,
        )
    
    console.print(table)


@app.command()
def stats():
    """Show telemetry statistics."""
    from sdk.telemetry import get_telemetry_store
    
    store = get_telemetry_store()
    stats = store.get_statistics()
    
    console.print(Panel.fit(
        f"[bold]Telemetry Statistics[/bold]",
        title="Stats",
    ))
    
    table = Table()
    table.add_column("Category", style="cyan")
    table.add_column("Metric", style="white")
    table.add_column("Value", justify="right", style="green")
    
    table.add_row("Violations", "Open", str(stats["violations"]["open"]))
    table.add_row("Violations", "Resolved", str(stats["violations"]["resolved"]))
    table.add_row("Violations", "Total", str(stats["violations"]["total"]))
    table.add_row("Violations", "Avg Resolution", f"{stats['violations']['avg_resolution_hours']:.1f}h")
    table.add_row("Data", "Snapshots", str(stats["snapshots"]))
    table.add_row("Data", "Events", str(stats["events"]))
    
    console.print(table)


@app.command()
def export(
    output: Path = typer.Argument(..., help="Output file path"),
    format: str = typer.Option("json", "--format", "-f", help="Export format (json)"),
):
    """Export telemetry data."""
    from sdk.telemetry import get_telemetry_store
    
    store = get_telemetry_store()
    
    if format == "json":
        counts = store.export_to_json(output)
        console.print(f"[green]✓[/green] Exported to {output}")
        console.print(f"  - Violations: {counts['violations']}")
        console.print(f"  - Snapshots: {counts['snapshots']}")
        console.print(f"  - Events: {counts['events']}")
    else:
        console.print(f"[red]Unsupported format: {format}[/red]")
        raise typer.Exit(1)


@app.command()
def snapshot():
    """Take a quality snapshot."""
    from sdk.telemetry import get_telemetry_collector
    
    collector = get_telemetry_collector()
    snapshot = collector.take_snapshot()
    
    console.print(f"[green]✓[/green] Snapshot taken")
    console.print(f"  - Errors: {snapshot.error_count}")
    console.print(f"  - Warnings: {snapshot.warning_count}")
    console.print(f"  - Total: {snapshot.total_violations}")
    console.print(f"  - Clean file rate: {snapshot.clean_file_rate:.1%}")


@app.command()
def daily(
    days: int = typer.Option(14, "--days", "-d", help="Number of days"),
):
    """Show daily violation counts."""
    from sdk.telemetry import get_analytics
    
    analytics = get_analytics()
    metrics = analytics.get_daily_metrics(days)
    
    table = Table(title=f"Daily Violations (Last {days} Days)")
    table.add_column("Date", style="cyan")
    table.add_column("Total", justify="right")
    table.add_column("Errors", justify="right", style="red")
    table.add_column("Warnings", justify="right", style="yellow")
    table.add_column("Resolved", justify="right", style="green")
    
    for day in metrics[-14:]:  # Show last 14 days
        table.add_row(
            day["date"],
            str(day["total"]),
            str(day["errors"]),
            str(day["warnings"]),
            str(day["resolved"]),
        )
    
    console.print(table)


if __name__ == "__main__":
    app()
