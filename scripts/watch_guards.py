#!/usr/bin/env python3
"""
Real-Time Guard Watcher
=======================

Monitors file changes and runs guards automatically.
This is how enterprise teams get instant feedback during development.

Usage:
    python scripts/watch_guards.py
    python scripts/watch_guards.py --dir src/
    python scripts/watch_guards.py --sound  # Play sound on errors

Requirements:
    pip install watchdog rich
"""

import argparse
import sys
import time
from pathlib import Path
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
except ImportError:
    print("Install watchdog: pip install watchdog")
    sys.exit(1)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sdk.guards import run_guards
from sdk.guards.base import GuardSeverity


console = Console()


class GuardWatcher(FileSystemEventHandler):
    """Watches files and runs guards on changes."""
    
    def __init__(self, play_sound: bool = False):
        self.play_sound = play_sound
        self.last_run = {}
        self.debounce_seconds = 1  # Prevent rapid re-runs
        self.stats = {
            'files_checked': 0,
            'errors_found': 0,
            'warnings_found': 0,
            'last_check': None,
        }
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        if not isinstance(event, FileModifiedEvent):
            return
        
        file_path = Path(event.src_path)
        
        # Only check Python files
        if file_path.suffix != '.py':
            return
        
        # Skip venv and cache
        if '.venv' in str(file_path) or '__pycache__' in str(file_path):
            return
        
        # Debounce
        now = time.time()
        if file_path in self.last_run:
            if now - self.last_run[file_path] < self.debounce_seconds:
                return
        self.last_run[file_path] = now
        
        self.check_file(file_path)
    
    def check_file(self, file_path: Path):
        """Run guards on a single file."""
        try:
            content = file_path.read_text()
        except Exception as e:
            console.print(f"[red]Error reading {file_path}: {e}[/red]")
            return
        
        result = run_guards(content, str(file_path))
        
        self.stats['files_checked'] += 1
        self.stats['last_check'] = datetime.now().strftime('%H:%M:%S')
        
        errors = [v for v in result.violations if v.severity == GuardSeverity.ERROR]
        warnings = [v for v in result.violations if v.severity == GuardSeverity.WARNING]
        
        self.stats['errors_found'] = len(errors)
        self.stats['warnings_found'] = len(warnings)
        
        # Clear and print result
        console.clear()
        self.print_header()
        
        if result.passed and not warnings:
            console.print(Panel(
                f"[green]✅ {file_path.name}[/green]\n"
                f"All {result.guards_run} guards passed",
                title="File Saved",
                border_style="green"
            ))
        else:
            self.print_violations(file_path, errors, warnings)
            
            if errors and self.play_sound:
                # macOS sound
                import os
                os.system('afplay /System/Library/Sounds/Basso.aiff &')
    
    def print_header(self):
        """Print watcher header with stats."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="cyan")
        table.add_column(style="white")
        
        table.add_row("🛡️ Guard Watcher", "Active")
        table.add_row("Files Checked", str(self.stats['files_checked']))
        table.add_row("Last Check", self.stats['last_check'] or '-')
        
        console.print(Panel(table, title="3SixtyRev SDK", border_style="blue"))
        console.print()
    
    def print_violations(self, file_path: Path, errors: list, warnings: list):
        """Print violations in a nice format."""
        if errors:
            console.print(Panel(
                f"[red]❌ {len(errors)} ERROR(s) - Must fix before commit[/red]",
                title=str(file_path),
                border_style="red"
            ))
            
            for v in errors[:5]:
                console.print(f"  [red]Line {v.line_number}:[/red] {v.message}")
                if v.suggestion:
                    console.print(f"    [dim]💡 {v.suggestion}[/dim]")
            
            if len(errors) > 5:
                console.print(f"  [dim]... and {len(errors) - 5} more[/dim]")
        
        if warnings:
            console.print()
            console.print(Panel(
                f"[yellow]⚠️ {len(warnings)} WARNING(s)[/yellow]",
                border_style="yellow"
            ))
            
            for v in warnings[:3]:
                console.print(f"  [yellow]Line {v.line_number}:[/yellow] {v.message}")
            
            if len(warnings) > 3:
                console.print(f"  [dim]... and {len(warnings) - 3} more[/dim]")


def main():
    parser = argparse.ArgumentParser(description="Watch files and run guards")
    parser.add_argument(
        '--dir', '-d',
        default='.',
        help='Directory to watch (default: current)'
    )
    parser.add_argument(
        '--sound', '-s',
        action='store_true',
        help='Play sound on errors (macOS)'
    )
    
    args = parser.parse_args()
    
    watch_path = Path(args.dir).resolve()
    
    console.print(Panel(
        f"[cyan]Watching:[/cyan] {watch_path}\n"
        f"[cyan]Extensions:[/cyan] .py\n"
        f"[cyan]Sound:[/cyan] {'Enabled' if args.sound else 'Disabled'}\n\n"
        f"[dim]Save a Python file to see guard results...[/dim]\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        title="🛡️ 3SixtyRev Guard Watcher",
        border_style="blue"
    ))
    
    event_handler = GuardWatcher(play_sound=args.sound)
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        console.print("\n[yellow]Watcher stopped[/yellow]")
    
    observer.join()


if __name__ == '__main__':
    main()
