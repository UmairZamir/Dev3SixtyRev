"""
MCP Server Module
=================

Exposes SDK guards as MCP tools for Claude Code integration.

Usage:
    # Start MCP server
    3sr-mcp

    # Or programmatically
    from sdk.mcp import serve_mcp
    serve_mcp()
"""

from sdk.mcp.server import serve as serve_mcp
from sdk.mcp.phase import (
    Phase,
    get_phase,
    set_phase,
    check_file_allowed,
    get_expected_test_path,
    get_phase_info,
    PHASE_RESTRICTIONS,
)
from sdk.mcp.audit import (
    log_decision,
    get_audit_log,
    clear_audit_log,
    format_audit_entry,
    get_audit_summary,
)

__all__ = [
    # Server
    "serve_mcp",
    # Phase management
    "Phase",
    "get_phase",
    "set_phase",
    "check_file_allowed",
    "get_expected_test_path",
    "get_phase_info",
    "PHASE_RESTRICTIONS",
    # Audit
    "log_decision",
    "get_audit_log",
    "clear_audit_log",
    "format_audit_entry",
    "get_audit_summary",
]
