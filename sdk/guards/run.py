"""
Guard Runner
============

CLI for running guards from pre-commit hooks or command line.

Usage:
    python -m sdk.guards.run [--guard NAME] [--level LEVEL] [files...]
    python -m sdk.guards.run --all src/
    python -m sdk.guards.run --guard bandaid file.py
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.table import Table

from sdk.guards.base import GuardLevel, GuardCategory
from sdk.guards.registry import GuardRegistry, AggregatedResult


console = Console()


def run_guards_on_files(
    file_paths: List[str],
    guard_name: Optional[str] = None,
    level: Optional[str] = None,
    category: Optional[str] = None,
    verbose: bool = False,
) -> AggregatedResult:
    """Run guards on specified files."""
    registry = GuardRegistry(auto_init=True)

    # Convert string paths to Path objects
    paths = []
    for fp in file_paths:
        p = Path(fp)
        if p.is_file():
            paths.append(p)
        elif p.is_dir():
            # Add all Python files in directory
            paths.extend(p.rglob("*.py"))

    if not paths:
        console.print("[yellow]No files to check[/yellow]")
        return AggregatedResult(passed=True)

    if verbose:
        console.print(f"[dim]Checking {len(paths)} file(s)...[/dim]")

    # Run specific guard
    if guard_name:
        guard = registry.get(guard_name)
        if not guard:
            console.print(f"[red]Guard '{guard_name}' not found[/red]")
            console.print("\nAvailable guards:")
            for g in registry.get_all():
                console.print(f"  - {g.name}")
            return AggregatedResult(passed=False)

        result = guard.check_files(paths)
        return AggregatedResult(
            passed=result.passed,
            violations=result.violations,
            execution_time_ms=result.execution_time_ms,
            guards_run=1,
            files_checked=result.files_checked,
        )

    # Run guards by level
    if level:
        try:
            guard_level = GuardLevel(level.lower())
        except ValueError:
            console.print(f"[red]Invalid level '{level}'[/red]")
            console.print(f"Valid levels: {', '.join(l.value for l in GuardLevel)}")
            return AggregatedResult(passed=False)

        guards = registry.get_by_level(guard_level)
        if not guards:
            console.print(f"[yellow]No guards at level '{level}'[/yellow]")
            return AggregatedResult(passed=True)

    # Run guards by category
    elif category:
        try:
            guard_cat = GuardCategory(category.lower())
        except ValueError:
            console.print(f"[red]Invalid category '{category}'[/red]")
            console.print(f"Valid categories: {', '.join(c.value for c in GuardCategory)}")
            return AggregatedResult(passed=False)

        guards = registry.get_by_category(guard_cat)
        if not guards:
            console.print(f"[yellow]No guards in category '{category}'[/yellow]")
            return AggregatedResult(passed=True)

    # Run all guards
    else:
        pass  # Will use registry.run_on_files

    return registry.run_on_files(paths)


def print_result(result: AggregatedResult, verbose: bool = False) -> None:
    """Print guard results."""
    if result.passed:
        console.print(result.format_short())
        if verbose and result.violations:
            console.print("\n[dim]Warnings/Info:[/dim]")
            for v in result.violations[:5]:
                console.print(f"  {v}")
    else:
        console.print(result.format())


def list_guards() -> None:
    """List all available guards."""
    registry = GuardRegistry(auto_init=True)

    table = Table(title="Available Guards")
    table.add_column("Name", style="cyan")
    table.add_column("Level", style="green")
    table.add_column("Category", style="yellow")
    table.add_column("Enabled", style="magenta")
    table.add_column("Description")

    for guard in sorted(registry.get_all(), key=lambda g: (g.level.value, g.name)):
        enabled = "✅" if guard.enabled else "❌"
        table.add_row(
            guard.name,
            guard.level.value,
            guard.category.value,
            enabled,
            guard.description[:50],
        )

    console.print(table)
    console.print(f"\nTotal: {len(registry.get_all())} guards")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run 3SixtyRev SDK guards on files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m sdk.guards.run file.py              Run all guards on file.py
  python -m sdk.guards.run --guard bandaid .    Run bandaid guard on current dir
  python -m sdk.guards.run --level instant .    Run all instant-level guards
  python -m sdk.guards.run --list               List all available guards
        """,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="Files or directories to check",
    )
    parser.add_argument(
        "--guard", "-g",
        help="Run specific guard by name",
    )
    parser.add_argument(
        "--level", "-l",
        choices=[l.value for l in GuardLevel],
        help="Run all guards at specified level",
    )
    parser.add_argument(
        "--category", "-c",
        choices=[c.value for c in GuardCategory],
        help="Run all guards in specified category",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available guards",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show verbose output",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run all guards (default behavior)",
    )

    args = parser.parse_args()

    # List guards
    if args.list:
        list_guards()
        return 0

    # Check files
    if not args.files:
        parser.print_help()
        return 1

    result = run_guards_on_files(
        args.files,
        guard_name=args.guard,
        level=args.level,
        category=args.category,
        verbose=args.verbose,
    )

    print_result(result, args.verbose)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
