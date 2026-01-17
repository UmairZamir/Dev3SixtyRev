# 🏢 Enterprise Code Quality Automation

This document explains the automated code quality systems in place, similar to what Google, Stripe, and Meta use.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CODE QUALITY AUTOMATION PIPELINE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   LAYER 1: LOCAL (Real-time)                                                │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│   │ File Watcher    │  │ IDE Integration │  │ Copilot Rules   │            │
│   │ • Auto-guards   │  │ • Linting       │  │ • Smart suggest │            │
│   │ • Instant       │  │ • Type check    │  │ • Pattern aware │            │
│   │   feedback      │  │ • Format        │  │                 │            │
│   └────────┬────────┘  └────────┬────────┘  └────────┬────────┘            │
│            │                    │                    │                      │
│            └────────────────────┼────────────────────┘                      │
│                                 │                                           │
│   LAYER 2: PRE-COMMIT (Before commit)                                       │
│   ┌─────────────────────────────┴─────────────────────────────┐            │
│   │ Pre-commit Hooks                                          │            │
│   │ • Ruff (format + lint)  • MyPy (types)  • SDK Guards      │            │
│   │ • Bandit (security)     • Tests (fast)  • Block on error  │            │
│   └─────────────────────────────┬─────────────────────────────┘            │
│                                 │                                           │
│   LAYER 3: CI/CD (On push/PR)                                               │
│   ┌─────────────────────────────┴─────────────────────────────┐            │
│   │ GitHub Actions                                            │            │
│   │ • Full test suite       • Coverage check   • Security scan│            │
│   │ • All guards run        • Quality report   • Auto-label   │            │
│   └─────────────────────────────┬─────────────────────────────┘            │
│                                 │                                           │
│   LAYER 4: MERGE GATE (Branch protection)                                   │
│   ┌─────────────────────────────┴─────────────────────────────┐            │
│   │ Required before merge:                                    │            │
│   │ • All CI checks pass    • Code review approved            │            │
│   │ • No merge conflicts    • Up-to-date with main            │            │
│   └───────────────────────────────────────────────────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Enable Real-Time Guard Watching

```bash
# Terminal 1: Start the file watcher
python scripts/watch_guards.py --sound

# Now edit any .py file - guards run automatically!
```

### 2. VS Code Tasks (⌘ + ⇧ + P → "Run Task")

| Task | What it does |
|------|--------------|
| 👁️ Watch Guards | Real-time monitoring |
| 🛡️ Run Guards on Current File | Check open file |
| 🛡️ Run All Guards (SDK) | Check entire SDK |
| 🧪 Run Tests | Run pytest |
| 🔒 Pre-commit Check | Full pre-commit |

### 3. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `⌘ + ⇧ + G` | Run guards on current file |
| `⌘ + ⇧ + T` | Run tests |

## Automation Layers Explained

### Layer 1: Local Development (Instant)

**File Watcher** (`scripts/watch_guards.py`)
- Monitors all `.py` files in real-time
- Runs guards immediately when you save
- Shows errors/warnings in terminal
- Optional sound alerts on errors

**IDE Integration** (`.vscode/settings.json`)
- Auto-format on save
- Real-time linting with Ruff
- Type checking with Pylance

**Copilot Instructions** (`.github/copilot-instructions.md`)
- Teaches Copilot your coding standards
- Prevents suggesting bad patterns
- Generates compliant code

### Layer 2: Pre-Commit (Before Git)

**Pre-commit Hooks** (`.pre-commit-config.yaml`)

| Hook | Level | What it checks |
|------|-------|----------------|
| `ruff` | ERROR | Linting violations |
| `ruff-format` | ERROR | Formatting |
| `mypy` | WARNING | Type errors |
| `bandit` | ERROR | Security vulnerabilities |
| `bandaid-guard` | ERROR | Placeholder code |
| `security-guard` | ERROR | Hardcoded secrets |
| `hallucination-guard` | ERROR | Non-existent imports |

```bash
# Install hooks (one-time)
pre-commit install

# Run manually
pre-commit run --all-files
```

### Layer 3: CI/CD Pipeline

**On every push/PR** (`.github/workflows/ci.yml`):

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Quick Checks │────▶│ Guards Check │────▶│ Unit Tests   │
│ (format,lint)│     │ (SDK guards) │     │ (+ coverage) │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
┌──────────────┐     ┌──────────────┐     ┌──────▼───────┐
│ CI Success   │◀────│Security Scan │◀────│Integration   │
│ ✅ or ❌     │     │(bandit,audit)│     │Tests         │
└──────────────┘     └──────────────┘     └──────────────┘
```

**Nightly Scans** (`.github/workflows/nightly.yml`):
- Full codebase analysis
- Dependency audit
- Complexity metrics
- Quality trends

**PR Automation** (`.github/workflows/pr-automation.yml`):
- Auto-labels PRs by type
- Size labels (xs, s, m, l, xl)
- Posts guard analysis as comment
- Auto-requests reviewers

### Layer 4: Branch Protection

**Recommended settings** (configure in GitHub repo settings):

```
Settings → Branches → Add rule for "main"

✅ Require a pull request before merging
   ✅ Require approvals (1)
   ✅ Dismiss stale PR approvals

✅ Require status checks to pass
   ✅ ci-success
   ✅ guards-check
   ✅ unit-tests

✅ Require branches to be up to date

✅ Do not allow bypassing
```

## Guard Severity Levels

| Level | Behavior | Example |
|-------|----------|---------|
| **ERROR** | Blocks commit/merge | Hardcoded password |
| **WARNING** | Shown but allowed | Print statement |
| **INFO** | Suggestions only | Missing docstring |

## Files Reference

```
.
├── .github/
│   ├── copilot-instructions.md   # Copilot coding rules
│   ├── CODEOWNERS                # Auto-assign reviewers
│   ├── labeler.yml               # Auto-label PRs
│   ├── pull_request_template.md  # PR checklist
│   └── workflows/
│       ├── ci.yml                # Main CI pipeline
│       ├── nightly.yml           # Nightly scans
│       └── pr-automation.yml     # PR labeling/comments
├── .vscode/
│   ├── settings.json             # Editor settings
│   ├── tasks.json                # Run tasks
│   └── extensions.json           # Recommended extensions
├── .pre-commit-config.yaml       # Git hooks
├── scripts/
│   └── watch_guards.py           # Real-time watcher
└── sdk/
    └── guards/                   # Guard implementations
```

## Metrics Tracked

The system automatically tracks:

| Metric | Where | Purpose |
|--------|-------|---------|
| Guard violations | CI, Nightly | Code quality |
| Test coverage | CI | Code completeness |
| Cyclomatic complexity | Nightly | Maintainability |
| Security vulnerabilities | CI, Nightly | Security posture |
| PR size | PR labels | Review efficiency |

## FAQ

**Q: Why did my commit get rejected?**
A: Pre-commit hooks found ERROR-level violations. Run `pre-commit run --all-files` to see them.

**Q: How do I skip a check temporarily?**
A: Use `git commit --no-verify` (not recommended) or fix the issue.

**Q: How do I add a new guard?**
A: Create a new guard in `sdk/guards/` and register it in `sdk/guards/registry.py`.

**Q: How do I exclude a file from guards?**
A: Add it to the guard's `exceptions` list or use path-based exclusions.

---

*This setup ensures consistent, high-quality code across the entire team.*
