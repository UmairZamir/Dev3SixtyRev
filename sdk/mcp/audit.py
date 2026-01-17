"""
Audit Logging
=============

Logs all MCP tool decisions for accountability and debugging.
Writes to .dev-guardian-audit.jsonl in project root.
"""

# Implementation in Phase 2


def log_decision(event_type: str, data: dict, filepath: str = None, status: str = None):
    """Log a decision to the audit file."""
    raise NotImplementedError("Implementation in Phase 2")


def get_audit_log(last_n: int = 20, event_type: str = None, filepath_contains: str = None):
    """Retrieve recent audit log entries."""
    raise NotImplementedError("Implementation in Phase 2")
