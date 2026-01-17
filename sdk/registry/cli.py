"""
Registry CLI Commands
=====================

CLI commands for registry management:
- Validate registry
- Test extraction patterns
- Generate TypeScript types
- Show statistics
"""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="registry", help="Registry management commands")
console = Console()


@app.command()
def validate(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show all issues"),
):
    """Validate the registry for consistency and completeness."""
    from sdk.registry import validate_registry
    
    console.print("\n[bold]Validating registry...[/bold]\n")
    
    result = validate_registry()
    console.print(result.format_report())
    
    raise typer.Exit(0 if result.passed else 1)


@app.command()
def test_extraction(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show all results"),
):
    """Test extraction patterns against standard test cases."""
    from sdk.registry import run_standard_tests
    
    console.print("\n[bold]Running extraction tests...[/bold]\n")
    
    result = run_standard_tests()
    console.print(result.format_report())
    
    raise typer.Exit(0 if result.passed == result.total else 1)


@app.command()
def generate_types(
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Generate TypeScript types from the registry."""
    from sdk.registry import generate_typescript_types
    
    console.print("\n[bold]Generating TypeScript types...[/bold]\n")
    
    if output:
        ts_code = generate_typescript_types(output_path=output)
        console.print(f"[green]✓[/green] Types written to {output}")
    else:
        ts_code = generate_typescript_types()
        console.print(ts_code)


@app.command()
def stats():
    """Show registry statistics."""
    from sdk.registry import get_registry
    
    registry = get_registry()
    statistics = registry.get_statistics()
    
    table = Table(title="Registry Statistics")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="green")
    
    for key, value in sorted(statistics.items()):
        display_key = key.replace("_", " ").title()
        table.add_row(display_key, str(value))
    
    console.print(table)


@app.command()
def list_enums():
    """List all enums in the registry."""
    from sdk.registry import get_registry
    
    registry = get_registry()
    
    table = Table(title="Registry Enums")
    table.add_column("Enum ID", style="cyan")
    table.add_column("Values", justify="right", style="green")
    table.add_column("UI Component", style="yellow")
    
    for enum_id, enum_def in sorted(registry.enums.items()):
        table.add_row(
            enum_id,
            str(len(enum_def.values)),
            enum_def.ui_component or "-",
        )
    
    console.print(table)


@app.command()
def list_products():
    """List all products in the registry."""
    from sdk.registry import get_registry
    
    registry = get_registry()
    
    table = Table(title="Registry Products")
    table.add_column("Product ID", style="cyan")
    table.add_column("Display Name", style="white")
    table.add_column("Required Fields", justify="right", style="green")
    table.add_column("Optional Fields", justify="right", style="yellow")
    
    for product_id, product in sorted(registry.products.items()):
        table.add_row(
            product_id,
            product.display_name,
            str(len(product.required_fields)),
            str(len(product.optional_fields)),
        )
    
    console.print(table)


@app.command()
def show_field(
    product_id: str = typer.Argument(..., help="Product ID"),
    field_id: str = typer.Argument(..., help="Field ID"),
):
    """Show details for a specific field."""
    from sdk.registry import get_registry
    
    registry = get_registry()
    field = registry.get_field(product_id, field_id)
    
    if not field:
        console.print(f"[red]Field '{field_id}' not found in product '{product_id}'[/red]")
        raise typer.Exit(1)
    
    console.print(f"\n[bold]{field.display_name}[/bold] ({field.field_id})\n")
    console.print(f"Type: {field.field_type.value}")
    console.print(f"Priority: {field.priority}")
    console.print(f"Required: {field.required}")
    
    if field.valid_range:
        console.print(f"Valid Range: {field.valid_range}")
    
    if field.extraction_patterns:
        console.print(f"\nExtraction Patterns ({len(field.extraction_patterns)}):")
        for i, pattern in enumerate(field.extraction_patterns):
            console.print(f"  {i+1}. {pattern.pattern} (conf: {pattern.confidence})")
    
    if field.options:
        console.print(f"\nOptions ({len(field.options)}):")
        for opt in field.options:
            console.print(f"  • {opt.id}: {opt.display}")
    
    if field.question_variations:
        console.print(f"\nQuestion Variations:")
        for q in field.question_variations:
            console.print(f"  • {q}")


@app.command()
def check_usage(
    backend_dir: Optional[Path] = typer.Option(
        None, "--backend", "-b", help="Backend directory to scan"
    ),
    frontend_dir: Optional[Path] = typer.Option(
        None, "--frontend", "-f", help="Frontend directory to scan"
    ),
):
    """Check field usage consistency between frontend and backend."""
    from sdk.registry import FieldUsageTracker, get_registry
    
    registry = get_registry()
    tracker = FieldUsageTracker(registry)
    
    if backend_dir:
        console.print(f"Scanning backend: {backend_dir}")
        tracker.scan_python_files(backend_dir)
    
    if frontend_dir:
        console.print(f"Scanning frontend: {frontend_dir}")
        tracker.scan_typescript_files(frontend_dir)
    
    report = tracker.get_consistency_report()
    
    console.print(f"\n[bold]Field Usage Report[/bold]\n")
    console.print(f"Total Fields: {report['total_fields']}")
    console.print(f"Used in Backend: {report['backend_usage']}")
    console.print(f"Used in Frontend: {report['frontend_usage']}")
    
    if report['backend_only']:
        console.print(f"\n[yellow]Backend Only ({len(report['backend_only'])}):[/yellow]")
        for field_id in sorted(report['backend_only'])[:10]:
            console.print(f"  • {field_id}")
        if len(report['backend_only']) > 10:
            console.print(f"  ... and {len(report['backend_only']) - 10} more")
    
    if report['frontend_only']:
        console.print(f"\n[yellow]Frontend Only ({len(report['frontend_only'])}):[/yellow]")
        for field_id in sorted(report['frontend_only'])[:10]:
            console.print(f"  • {field_id}")
        if len(report['frontend_only']) > 10:
            console.print(f"  ... and {len(report['frontend_only']) - 10} more")
    
    if report['unused']:
        console.print(f"\n[dim]Unused ({len(report['unused'])}):[/dim]")
        for field_id in sorted(report['unused'])[:10]:
            console.print(f"  • {field_id}")
        if len(report['unused']) > 10:
            console.print(f"  ... and {len(report['unused']) - 10} more")


if __name__ == "__main__":
    app()
