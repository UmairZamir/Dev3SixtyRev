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
from sdk.mcp.phase import get_phase, set_phase, Phase
from sdk.mcp.audit import (
    log_decision,
    get_audit_log,
    clear_audit_log,
    format_audit_entry,
    get_audit_summary,
)

__all__ = [
    "serve_mcp",
    "get_phase",
    "set_phase",
    "Phase",
    "log_decision",
    "get_audit_log",
    "clear_audit_log",
    "format_audit_entry",
    "get_audit_summary",
]
