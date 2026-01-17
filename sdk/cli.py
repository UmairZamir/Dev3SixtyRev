"""
3SixtyRev SDK CLI
=================

Command-line interface for the SDK.

Usage:
    3sr guard [files...]           Run guards on files
    3sr verify                     Verify current task
    3sr gate                       Check phase gate
    3sr mode [MODE]                Set development mode
    3sr status                     Show SDK status
    3sr init                       Initialize SDK in project
    3sr registry <command>         Registry management
"""

import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Import subcommand CLIs
from sdk.registry.cli import app as registry_app
from sdk.telemetry.cli import app as telemetry_app

app = typer.Typer(
    name="3sr",
    help="3SixtyRev SDK - Enterprise AI Development Enforcement",
    add_completion=False,
)
console = Console()

# Add subcommands
app.add_typer(registry_app, name="registry", help="Registry management commands")
app.add_typer(telemetry_app, name="telemetry", help="Telemetry and metrics commands")


@app.command()
def guard(
    files: List[str] = typer.Argument(None, help="Files or directories to check"),
    guard_name: Optional[str] = typer.Option(None, "--guard", "-g", help="Run specific guard"),
    level: Optional[str] = typer.Option(None, "--level", "-l", help="Run guards at level"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    list_guards: bool = typer.Option(False, "--list", help="List available guards"),
):
    """Run guards on files."""
    from sdk.guards.run import run_guards_on_files, print_result, list_guards as show_guards

    if list_guards:
        show_guards()
        raise typer.Exit(0)

    if not files:
        files = ["."]

    result = run_guards_on_files(files, guard_name=guard_name, level=level, verbose=verbose)
    print_result(result, verbose)

    raise typer.Exit(0 if result.passed else 1)


@app.command()
def verify(
    task_id: Optional[str] = typer.Argument(None, help="Task ID to verify"),
):
    """Verify task completion with evidence."""
    from sdk.verification import get_collector

    collector = get_collector()
    task = collector.get_task(task_id)

    if not task:
        console.print("[yellow]No task found. Create one with 'collector.create_task()'[/yellow]")
        raise typer.Exit(1)

    if collector.verify_task(task_id):
        console.print(collector.format_report(task_id))
        raise typer.Exit(0)
    else:
        console.print(collector.format_report(task_id))
        raise typer.Exit(1)


@app.command()
def gate(
    target: Optional[str] = typer.Argument(None, help="Target phase"),
    force: bool = typer.Option(False, "--force", "-f", help="Force phase advance"),
):
    """Check or advance phase gate."""
    from sdk.verification import get_phase_gate, Phase

    gate = get_phase_gate()

    if target:
        try:
            target_phase = Phase(target.lower())
        except ValueError:
            console.print(f"[red]Invalid phase: {target}[/red]")
            console.print(f"Valid phases: {', '.join(p.value for p in Phase)}")
            raise typer.Exit(1)

        result = gate.check_transition(target_phase)
        if not result.passed and not force:
            raise typer.Exit(1)

        if force or result.passed:
            gate.advance(force=force)

    else:
        console.print(gate.format_status())


@app.command()
def mode(
    new_mode: Optional[str] = typer.Argument(None, help="Mode to set"),
):
    """Set or show development mode."""
    from sdk.core import get_mode_manager, Mode

    manager = get_mode_manager()

    if new_mode:
        try:
            m = Mode(new_mode.lower())
            manager.set_mode(m)
        except ValueError:
            console.print(f"[red]Invalid mode: {new_mode}[/red]")
            console.print(f"Valid modes: {', '.join(m.value for m in Mode)}")
            raise typer.Exit(1)
    else:
        console.print(manager.format_status())


@app.command()
def status():
    """Show SDK status."""
    from sdk import __version__
    from sdk.guards import get_guard_registry
    from sdk.verification import get_phase_gate
    from sdk.core import get_mode_manager, get_config
    from sdk.registry import get_registry

    config = get_config()
    registry = get_guard_registry()
    field_registry = get_registry()
    gate = get_phase_gate()
    mode_manager = get_mode_manager()

    console.print(Panel.fit(
        f"[bold]3SixtyRev SDK v{__version__}[/bold]\n"
        f"Project: {config.project_name}",
        title="Status",
    ))

    # Guards
    table = Table(title="Guards")
    table.add_column("Level", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Enabled", justify="right")

    from sdk.guards.base import GuardLevel
    for level in GuardLevel:
        guards = registry.get_by_level(level)
        enabled = len([g for g in guards if g.enabled])
        table.add_row(level.value, str(len(guards)), str(enabled))

    console.print(table)

    # Registry stats
    reg_stats = field_registry.get_statistics()
    reg_table = Table(title="Registry")
    reg_table.add_column("Category", style="cyan")
    reg_table.add_column("Count", justify="right")
    
    reg_table.add_row("Enums", str(reg_stats.get("enums", 0)))
    reg_table.add_row("Products", str(reg_stats.get("products", 0)))
    reg_table.add_row("Fields", str(reg_stats.get("product_fields", 0)))
    reg_table.add_row("Extraction Patterns", str(reg_stats.get("extraction_patterns", 0)))
    
    console.print(reg_table)

    # Mode and Phase
    console.print(f"\n[bold]Mode:[/bold] {mode_manager.mode.value}")
    console.print(f"[bold]Phase:[/bold] {gate.current_phase.value}")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
):
    """Initialize SDK in current project."""
    config_path = Path.cwd() / ".3sr.yaml"

    if config_path.exists() and not force:
        console.print(f"[yellow]Config already exists: {config_path}[/yellow]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)

    from sdk.core import SDKConfig

    config = SDKConfig(
        project_root=Path.cwd(),
    )
    config.save(config_path)

    console.print(f"[green]✓[/green] Created {config_path}")

    # Create evidence directory
    evidence_dir = Path.cwd() / ".3sr" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]✓[/green] Created {evidence_dir}")

    # Add to gitignore
    gitignore = Path.cwd() / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".3sr/" not in content:
            with open(gitignore, "a") as f:
                f.write("\n# 3SixtyRev SDK\n.3sr/\n")
            console.print(f"[green]✓[/green] Updated .gitignore")

    console.print("\n[bold]SDK initialized![/bold]")
    console.print("Run 'pre-commit install' to enable git hooks")


@app.command()
def run_tests(
    path: str = typer.Argument("tests/", help="Test path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Run tests and collect evidence."""
    from sdk.verification import get_collector, EvidenceType

    collector = get_collector()

    # Create a test task if none exists
    task = collector.get_task()
    if not task:
        task = collector.create_task(
            "run-tests",
            "Run pytest and collect evidence",
            required_evidence=[EvidenceType.TEST_RESULT],
        )

    # Run tests
    args = "-v --tb=short" if verbose else "-v --tb=short -q"
    evidence = collector.run_tests(path, args)
    collector.add_evidence(evidence)

    # Show report
    console.print(collector.format_report())

    raise typer.Exit(0 if evidence.is_passing() else 1)


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
