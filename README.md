# 3SixtyRev Development SDK

Enterprise-grade AI development enforcement SDK for the 3SixtyRev conversational AI platform.

## Overview

This SDK prevents common AI coding pitfalls identified from research on "vibe coding" failures:

| Problem | Solution |
|---------|----------|
| Context loss / forgetting | Context Loss Guard detects incomplete implementations |
| Hallucinated APIs (5.2% rate) | Hallucination Guard verifies imports exist |
| "Almost right" code (66% of devs) | Evidence-based task completion |
| Shell components | Shell Guard detects placeholders |
| Missing tests | E2E Test Enforcement Guard |
| Scope creep | Scope Guard tracks expected files |

## Quick Start

```bash
# Install SDK
pip install -e ".[dev]"

# Initialize in project
3sr init

# Install pre-commit hooks
pre-commit install

# Run guards on code
3sr guard src/

# Check specific guard
3sr guard --guard security src/

# List available guards
3sr guard --list
```

## Guard Levels

| Level | When | Time Budget |
|-------|------|-------------|
| INSTANT | Every edit | <100ms |
| TASK | After each task | <30s |
| PHASE | End of phase | <5min |
| CONTINUOUS | Background | Async |

## Available Guards

### Tier 1: INSTANT Guards
- `bandaid_patterns` - Detects type: ignore, noqa, except: pass
- `hardcoded_values` - Detects hardcoded secrets, passwords
- `print_statements` - Detects print() in production code
- `shell_component` - Detects empty handlers in frontend
- `python_shell` - Detects NotImplementedError, placeholder pass
- `security` - Detects SQL injection, hardcoded credentials
- `hallucination` - Detects non-existent imports, deprecated APIs
- `duplicate_function` - Detects similar function names

### Tier 2: TASK Guards
- `context_loss` - Detects untracked TODOs, incomplete implementations
- `over_engineering` - Detects excessive complexity
- `scope_creep` - Detects modifications outside expected scope

### Tier 3: PHASE Guards
- `evidence_required` - Enforces test evidence before completion
- `spec_compliance` - Verifies implementation matches specs
- `e2e_test_enforcement` - Ensures tests exist for new code

## Evidence Collection

Every task requires evidence before completion:

```python
from sdk.verification import get_collector, EvidenceType

collector = get_collector()

# Create task
task = collector.create_task(
    "implement-login",
    "Implement user login",
    required_evidence=[EvidenceType.TEST_RESULT, EvidenceType.TYPE_CHECK],
)

# Run tests and collect evidence
evidence = collector.run_tests("tests/test_login.py")
collector.add_evidence(evidence)

# Verify task
if collector.verify_task():
    print("Task verified!")
```

## Phase Gates

Development happens in phases with quality gates:

```
RESEARCH → PLAN → IMPLEMENT → TEST → REVIEW → COMPLETE
```

Each transition requires meeting requirements:

```python
from sdk.verification import get_phase_gate, Phase

gate = get_phase_gate()

# Mark requirements complete
gate.mark_requirement_complete("Read architecture docs")
gate.mark_requirement_complete("Understand requirements")

# Check if we can advance
result = gate.check_transition(Phase.PLAN)
if result.passed:
    gate.advance()
```

## Development Modes

```python
from sdk.core import set_mode, Mode

# Set mode
set_mode(Mode.BUILD)  # Full capabilities
set_mode(Mode.DEBUG)  # Relaxed guards
set_mode(Mode.TEST)   # Limited to test files
```

| Mode | Write | Commands | Commit | Guards |
|------|-------|----------|--------|--------|
| CHAT | ❌ | ❌ | ❌ | ❌ |
| PLAN | ❌ | ❌ | ❌ | ❌ |
| BUILD | ✅ | ✅ | ✅ | ✅ |
| REVIEW | ✅ | ✅ | ✅ | ✅ |
| TEST | ✅ | ✅ | ✅ | ✅ |
| DEBUG | ✅ | ✅ | ❌ | ❌ |

## CLAUDE.md Integration

The SDK integrates with Claude Code via `CLAUDE.md` at project root. This file:
- Defines project context and conventions
- Lists available commands
- Specifies quality requirements
- References architecture docs

## Pre-commit Hooks

Guards run automatically on commit:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: bandaid-guard
        name: Bandaid Patterns Guard
        entry: python -m sdk.guards.run --guard bandaid
        language: python
        types: [python]
```

## CLI Commands

```bash
# Guards
3sr guard [files]              # Run all guards
3sr guard --guard NAME [files] # Run specific guard
3sr guard --level instant .    # Run guards at level
3sr guard --list               # List guards

# Verification
3sr verify [task_id]           # Verify task completion
3sr run-tests [path]           # Run tests with evidence

# Phase Gates
3sr gate                       # Show gate status
3sr gate plan                  # Check transition to plan
3sr gate --force plan          # Force advance

# Modes
3sr mode                       # Show current mode
3sr mode build                 # Set mode

# General
3sr status                     # Show SDK status
3sr init                       # Initialize SDK
```

## Project Structure

```
sdk/
├── guards/                    # Quality enforcement
│   ├── base.py               # Guard base classes
│   ├── registry.py           # Guard registry
│   ├── bandaid.py            # Bandaid pattern detection
│   ├── shell_component.py    # Shell component detection
│   ├── security.py           # Security vulnerability detection
│   ├── hallucination.py      # AI hallucination detection
│   ├── context_loss.py       # Context loss detection
│   ├── evidence.py           # Evidence requirements
│   └── run.py                # CLI runner
├── verification/              # Task verification
│   ├── evidence_collector.py # Evidence collection
│   └── phase_gate.py         # Phase gate enforcement
├── core/                      # Core functionality
│   ├── config.py             # Configuration
│   └── modes.py              # Development modes
└── cli.py                     # Command-line interface
```

## Configuration

Create `.3sr.yaml` in project root:

```yaml
project_name: 3SixtyRev
verbose: false

guards:
  enabled: []  # Enable specific guards only
  disabled: [print_statements]  # Disable specific guards
  severity:
    hardcoded_values: warning  # Override severity

evidence:
  dir: .3sr/evidence
  required: [test_result]

phases:
  enforce: true
```

## License

MIT License - See LICENSE file for details.
