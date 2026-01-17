"""
Audit Logging
=============

Logs all MCP tool decisions for accountability and debugging.
Writes to .dev-guardian-audit.jsonl in project root.

Event Types:
- phase_change: Phase transitions
- file_check: Pre-file-creation checks
- guard_run: Guard execution results
- override: Manual overrides with justification
- error: Errors and failures
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Default audit file location
AUDIT_FILE_NAME = ".dev-guardian-audit.jsonl"


def _get_audit_file_path(project_root: Optional[Path] = None) -> Path:
    """Get the path to the audit file."""
    if project_root is None:
        # Try to find project root by looking for pyproject.toml
        current = Path.cwd()
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current / AUDIT_FILE_NAME
            current = current.parent
        # Fallback to current directory
        return Path.cwd() / AUDIT_FILE_NAME
    return Path(project_root) / AUDIT_FILE_NAME


def _get_timestamp() -> str:
    """Get ISO format timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


def log_decision(
    event_type: str,
    data: Dict[str, Any],
    filepath: Optional[str] = None,
    status: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Log a decision to the audit file.

    Args:
        event_type: Type of event (phase_change, file_check, guard_run, override, error)
        data: Event-specific data dictionary
        filepath: Optional file path related to the event
        status: Optional status (allowed, blocked, passed, failed, etc.)
        project_root: Optional project root path (auto-detected if not provided)

    Returns:
        The logged entry dictionary
    """
    entry = {
        "timestamp": _get_timestamp(),
        "event_type": event_type,
        "data": data,
    }

    if filepath is not None:
        entry["filepath"] = filepath

    if status is not None:
        entry["status"] = status

    # Write to JSONL file
    audit_file = _get_audit_file_path(project_root)

    # Ensure parent directory exists
    audit_file.parent.mkdir(parents=True, exist_ok=True)

    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def get_audit_log(
    last_n: int = 20,
    event_type: Optional[str] = None,
    filepath_contains: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve recent audit log entries.

    Args:
        last_n: Number of entries to return (default 20)
        event_type: Filter by event type
        filepath_contains: Filter by filepath substring
        project_root: Optional project root path

    Returns:
        List of matching audit entries (most recent first)
    """
    audit_file = _get_audit_file_path(project_root)

    if not audit_file.exists():
        return []

    entries = []

    with open(audit_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)

                # Apply filters
                if event_type is not None and entry.get("event_type") != event_type:
                    continue

                if filepath_contains is not None:
                    entry_filepath = entry.get("filepath", "")
                    if filepath_contains not in entry_filepath:
                        continue

                entries.append(entry)
            except json.JSONDecodeError:
                # Skip malformed entries
                continue

    # Return most recent entries first
    return entries[-last_n:][::-1]


def clear_audit_log(project_root: Optional[Path] = None) -> bool:
    """
    Clear the audit log file.

    Args:
        project_root: Optional project root path

    Returns:
        True if file was cleared, False if it didn't exist
    """
    audit_file = _get_audit_file_path(project_root)

    if audit_file.exists():
        audit_file.unlink()
        return True
    return False


def format_audit_entry(entry: Dict[str, Any], verbose: bool = False) -> str:
    """
    Format an audit entry for display.

    Args:
        entry: Audit entry dictionary
        verbose: Include full data if True

    Returns:
        Formatted string representation
    """
    timestamp = entry.get("timestamp", "unknown")
    event_type = entry.get("event_type", "unknown")
    status = entry.get("status", "")
    filepath = entry.get("filepath", "")
    data = entry.get("data", {})

    # Parse timestamp for shorter display
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        time_str = dt.strftime("%H:%M:%S")
    except (ValueError, AttributeError):
        time_str = timestamp[:8] if len(timestamp) >= 8 else timestamp

    # Build status indicator (case-insensitive)
    status_lower = status.lower() if status else ""
    status_icon = {
        "allowed": "[OK]",
        "approved": "[OK]",
        "blocked": "[X]",
        "passed": "[OK]",
        "failed": "[X]",
        "warning": "[!]",
        "info": "[i]",
    }.get(status_lower, f"[{status}]" if status else "")

    # Build main line
    parts = [time_str, event_type.upper()]
    if status_icon:
        parts.append(status_icon)
    if filepath:
        parts.append(filepath)

    main_line = " ".join(parts)

    if verbose and data:
        # Add data details
        data_str = json.dumps(data, indent=2)
        return f"{main_line}\n{data_str}"

    # Add brief data summary
    if "reason" in data:
        main_line += f" - {data['reason']}"
    elif "message" in data:
        main_line += f" - {data['message']}"
    elif "phase" in data:
        main_line += f" - {data['phase']}"

    return main_line


def get_audit_summary(
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Get a summary of audit log statistics.

    Returns:
        Dictionary with counts by event type and status
    """
    entries = get_audit_log(last_n=1000, project_root=project_root)

    summary = {
        "total_entries": len(entries),
        "by_event_type": {},
        "by_status": {},
        "recent_errors": [],
    }

    for entry in entries:
        event_type = entry.get("event_type", "unknown")
        status = entry.get("status", "unknown")

        summary["by_event_type"][event_type] = summary["by_event_type"].get(event_type, 0) + 1
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1

        if event_type == "error" and len(summary["recent_errors"]) < 5:
            summary["recent_errors"].append(entry)

    return summary
