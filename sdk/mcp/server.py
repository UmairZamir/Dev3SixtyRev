"""
MCP Server
==========

Main MCP server exposing SDK guards as tools for Claude Code.

Tools:
- check_imports: Run HallucinationGuard on code
- check_security: Run SecurityGuard on code
- full_check: Run all guards on a file
- get_phase: Get current development phase
- set_phase: Switch development phase
- check_before_create: Validate before creating new file
- find_similar_code: Search for similar existing code
- view_audit: View recent audit log entries
"""

import asyncio
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from sdk.guards import get_guard_registry
from sdk.guards.hallucination import HallucinationGuard
from sdk.guards.security import SecurityGuard
from sdk.mcp.audit import (
    format_audit_entry,
    get_audit_log,
    get_audit_summary,
    log_decision,
)
from sdk.mcp.phase import (
    Phase,
    check_file_allowed,
    get_expected_test_path,
    get_phase,
    get_phase_info,
    set_phase,
)

# Initialize MCP server
server = Server("3sixtyrev-guardian")

# Initialize guards
hallucination_guard = HallucinationGuard()
security_guard = SecurityGuard()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="check_imports",
            description="Check code for hallucinated imports (non-existent packages/modules)",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to check for import issues",
                    },
                    "filepath": {
                        "type": "string",
                        "description": "Optional file path for context",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="check_security",
            description="Check code for security vulnerabilities (hardcoded secrets, injection, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to check for security issues",
                    },
                    "filepath": {
                        "type": "string",
                        "description": "Optional file path for context",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="full_check",
            description="Run all guards on code (hallucination + security + patterns)",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to check with all guards",
                    },
                    "filepath": {
                        "type": "string",
                        "description": "Optional file path for context",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="get_phase",
            description="Get the current development phase and its restrictions",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="set_phase",
            description="Switch to a different development phase",
            inputSchema={
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "enum": ["planning", "testing", "implementation", "review"],
                        "description": "The phase to switch to",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for switching phases",
                    },
                },
                "required": ["phase", "reason"],
            },
        ),
        Tool(
            name="check_before_create",
            description="Check if a file can be created in the current phase",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Path of the file to create",
                    },
                },
                "required": ["filepath"],
            },
        ),
        Tool(
            name="find_similar_code",
            description="Search for similar existing code to avoid duplication",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Function name, class name, or code pattern to search for",
                    },
                    "file_type": {
                        "type": "string",
                        "description": "File extension to search (e.g., '.py', '.ts')",
                        "default": ".py",
                    },
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="view_audit",
            description="View recent audit log entries",
            inputSchema={
                "type": "object",
                "properties": {
                    "last_n": {
                        "type": "integer",
                        "description": "Number of entries to show (default 10)",
                        "default": 10,
                    },
                    "event_type": {
                        "type": "string",
                        "description": "Filter by event type (phase_change, file_check, guard_run, etc.)",
                    },
                },
            },
        ),
        Tool(
            name="override_block",
            description="Override a blocked operation with justification (use sparingly)",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Path of the blocked file",
                    },
                    "justification": {
                        "type": "string",
                        "description": "Detailed justification for the override",
                    },
                },
                "required": ["filepath", "justification"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "check_imports":
            return await _check_imports(arguments)
        elif name == "check_security":
            return await _check_security(arguments)
        elif name == "full_check":
            return await _full_check(arguments)
        elif name == "get_phase":
            return await _get_phase(arguments)
        elif name == "set_phase":
            return await _set_phase(arguments)
        elif name == "check_before_create":
            return await _check_before_create(arguments)
        elif name == "find_similar_code":
            return await _find_similar_code(arguments)
        elif name == "view_audit":
            return await _view_audit(arguments)
        elif name == "override_block":
            return await _override_block(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        log_decision("error", {"tool": name, "error": str(e)}, status="failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _check_imports(arguments: dict[str, Any]) -> list[TextContent]:
    """Check code for hallucinated imports."""
    code = arguments.get("code", "")
    filepath = arguments.get("filepath")

    result = hallucination_guard.check(code, filepath)

    log_decision(
        "guard_run",
        {
            "guard": "hallucination",
            "passed": result.passed,
            "violations": len(result.violations),
        },
        filepath=filepath,
        status="passed" if result.passed else "failed",
    )

    if result.passed:
        return [TextContent(type="text", text="No hallucinated imports found.")]

    violations_text = "\n".join(
        f"- Line {v.line_number}: {v.message}" for v in result.violations
    )
    return [
        TextContent(
            type="text",
            text=f"Found {len(result.violations)} import issues:\n{violations_text}",
        )
    ]


async def _check_security(arguments: dict[str, Any]) -> list[TextContent]:
    """Check code for security vulnerabilities."""
    code = arguments.get("code", "")
    filepath = arguments.get("filepath")

    result = security_guard.check(code, filepath)

    log_decision(
        "guard_run",
        {
            "guard": "security",
            "passed": result.passed,
            "violations": len(result.violations),
        },
        filepath=filepath,
        status="passed" if result.passed else "failed",
    )

    if result.passed:
        return [TextContent(type="text", text="No security issues found.")]

    violations_text = "\n".join(
        f"- Line {v.line_number}: {v.message}\n  Suggestion: {v.suggestion}"
        for v in result.violations
    )
    return [
        TextContent(
            type="text",
            text=f"Found {len(result.violations)} security issues:\n{violations_text}",
        )
    ]


async def _full_check(arguments: dict[str, Any]) -> list[TextContent]:
    """Run all guards on code."""
    code = arguments.get("code", "")
    filepath = arguments.get("filepath")

    registry = get_guard_registry()
    result = registry.run_all(code, filepath)

    log_decision(
        "guard_run",
        {
            "guard": "all",
            "passed": result.passed,
            "violations": len(result.violations),
        },
        filepath=filepath,
        status="passed" if result.passed else "failed",
    )

    if result.passed:
        return [TextContent(type="text", text="All guards passed.")]

    violations_text = "\n".join(
        f"- [{v.guard_name}] Line {v.line_number}: {v.message}" for v in result.violations
    )
    return [
        TextContent(
            type="text",
            text=f"Found {len(result.violations)} issues:\n{violations_text}",
        )
    ]


async def _get_phase(arguments: dict[str, Any]) -> list[TextContent]:
    """Get current development phase."""
    info = get_phase_info()
    text = f"""Current Phase: {info['phase'].upper()}

Description: {info['description']}

Allowed file patterns:
{chr(10).join(f'  - {p}' for p in info['allowed_patterns']) or '  (none)'}

Blocked file patterns:
{chr(10).join(f'  - {p}' for p in info['blocked_patterns']) or '  (none)'}

Test-first required: {info['requires_tests']}"""

    return [TextContent(type="text", text=text)]


async def _set_phase(arguments: dict[str, Any]) -> list[TextContent]:
    """Switch development phase."""
    phase_str = arguments.get("phase", "planning")
    reason = arguments.get("reason", "No reason provided")

    try:
        phase = Phase(phase_str)
    except ValueError:
        return [
            TextContent(
                type="text",
                text=f"Invalid phase: {phase_str}. Valid: planning, testing, implementation, review",
            )
        ]

    result = set_phase(phase, reason)
    return [
        TextContent(
            type="text",
            text=f"Phase changed: {result['old_phase']} -> {result['new_phase']}\nReason: {reason}\nRestrictions: {result['restrictions']}",
        )
    ]


async def _check_before_create(arguments: dict[str, Any]) -> list[TextContent]:
    """Check if file creation is allowed."""
    filepath = arguments.get("filepath", "")

    allowed, reason = check_file_allowed(filepath)

    if allowed:
        return [TextContent(type="text", text=f"ALLOWED: {filepath}\n{reason}")]

    # Check for test requirement
    test_path = get_expected_test_path(filepath)
    if test_path:
        return [
            TextContent(
                type="text",
                text=f"BLOCKED: {filepath}\n{reason}\n\nTo proceed, first create: {test_path}",
            )
        ]

    return [TextContent(type="text", text=f"BLOCKED: {filepath}\n{reason}")]


async def _find_similar_code(arguments: dict[str, Any]) -> list[TextContent]:
    """Search for similar existing code."""
    import subprocess

    pattern = arguments.get("pattern", "")
    file_type = arguments.get("file_type", ".py")

    # Use grep to search
    try:
        result = subprocess.run(
            ["grep", "-rn", "--include", f"*{file_type}", pattern, "."],
            capture_output=True,
            text=True,
            timeout=10,
        )
        matches = result.stdout.strip()

        if not matches:
            return [
                TextContent(
                    type="text",
                    text=f"No similar code found for pattern: {pattern}",
                )
            ]

        lines = matches.split("\n")[:20]  # Limit to 20 matches
        return [
            TextContent(
                type="text",
                text=f"Found {len(lines)} matches for '{pattern}':\n\n" + "\n".join(lines),
            )
        ]
    except subprocess.TimeoutExpired:
        return [TextContent(type="text", text="Search timed out")]
    except Exception as e:
        return [TextContent(type="text", text=f"Search error: {e}")]


async def _view_audit(arguments: dict[str, Any]) -> list[TextContent]:
    """View recent audit log entries."""
    last_n = arguments.get("last_n", 10)
    event_type = arguments.get("event_type")

    entries = get_audit_log(last_n=last_n, event_type=event_type)

    if not entries:
        return [TextContent(type="text", text="No audit entries found.")]

    formatted = "\n".join(format_audit_entry(e) for e in entries)

    # Add summary
    summary = get_audit_summary()
    summary_text = f"\nTotal: {summary['total_entries']} entries"

    return [TextContent(type="text", text=f"Recent audit log:\n\n{formatted}\n{summary_text}")]


async def _override_block(arguments: dict[str, Any]) -> list[TextContent]:
    """Override a blocked operation with justification."""
    filepath = arguments.get("filepath", "")
    justification = arguments.get("justification", "")

    if len(justification) < 20:
        return [
            TextContent(
                type="text",
                text="Justification must be at least 20 characters. Explain why this override is necessary.",
            )
        ]

    log_decision(
        "override",
        {
            "filepath": filepath,
            "justification": justification,
        },
        filepath=filepath,
        status="approved",
    )

    return [
        TextContent(
            type="text",
            text=f"Override approved for: {filepath}\nJustification logged: {justification[:100]}...",
        )
    ]


def serve():
    """Start the MCP server."""
    asyncio.run(_run_server())


async def _run_server():
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """CLI entry point."""
    serve()


if __name__ == "__main__":
    main()
