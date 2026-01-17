# CLAUDE.md - 3SixtyRev Development Standards
> This file provides guidance to Claude Code when working with code in this repository.
> Last updated: January 2025

---

## 🎯 PROJECT OVERVIEW

**3SixtyRev** is an AI-powered Sales Development Representative (SDR) platform that operates 24/7 to maximize sales opportunities across regulated and non-regulated industries.

### Core Mission
Unlike chatbots that wait for user input, 3SixtyRev operates with **GOALS and INTENTIONS**:
- Qualifies leads before they go cold
- Follows up on stale opportunities
- Handles objections that would kill deals
- Asks for referrals at optimal moments
- Cross-sells based on detected signals
- Wins back churned customers

**The AI is PROACTIVELY STRATEGIC, not reactive.**

### Platform Structure
```
dev.3sixtyrev.com     → Platform Owner Portal (3SixtyRev internal)
app.3sixtyrev.com     → Tenant Portal (businesses using 3SixtyRev)
partner.3sixtyrev.com → Partner Network Portal (cross-industry referrals)
```

---

## 🏗️ ARCHITECTURE OVERVIEW

### Two-Level State Machine

**Level 1: Sales Stage** (Persists across conversations)
```
INITIAL → RAPPORT → DISCOVERY → QUALIFY → PRESENT → NEGOTIATE → CLOSE → NURTURE
                                                                    ↓
                                                                  LOST → (winback)
```

**Level 2: Conversation State** (Per-session)
```
INIT → GREETING → DISCOVERY → QUALIFICATION → SCHEDULING → CLOSING
                       ↓              ↓
                 OBJECTION_HANDLING ←─┘
                       ↓
              CROSS_SELL_OPPORTUNITY → REFERRAL_ASK
```

### Voice Pipeline Latency Budget (Target: 430ms)
```
STT (90ms) + SLMs parallel (50ms) + Memory (15ms) + LLM (200ms) + TTS (75ms) = 430ms
```

### AI Operating Modes

| Mode | Available To | Can Do | Cannot Do |
|------|--------------|--------|-----------|
| **Assistant** | ALL industries | Qualify, schedule, soft objections | Quote prices, offer discounts, commit |
| **Agent** | Non-regulated ONLY | + Quote prices, offer discounts, close | Exceed thresholds, regulated industries |
| **Service** | ALL industries | Service requests, scheduling | Process actual changes, access sensitive data |

**CRITICAL**: Mode is assigned at account signup based on industry classification. Regulated industries (insurance, mortgage, real estate, healthcare, legal, automotive sales) NEVER get Agent Mode.

---

## 🚨 GOLDEN RULES (NON-NEGOTIABLE)

### Rule 1: NEVER TRUST "DONE" WITHOUT PROOF
```
❌ FORBIDDEN: "I've completed all 15 tasks!"
   (User discovers issues later)

✅ REQUIRED: "Task 1 complete. Evidence: [actual output]. Confirm?"
   User: "Confirmed"
   "Task 2 complete. Evidence: [actual output]. Confirm?"
   (Issues caught in real-time)
```

### Rule 2: EVIDENCE BEFORE COMPLETION
```
EVERY task completion MUST include:
1. WHAT CHANGED - File path, line numbers, function names
2. VERIFICATION RUN - Execute test/grep/check command
3. ACTUAL OUTPUT - Copy-paste real output (not summary)
4. WAIT - "Confirm to proceed to next task?"

No task is "done" without:
- ✅ Tests pass (show actual pytest output)
- ✅ Code compiles/type-checks (show actual output)
- ✅ Behavior verified (grep output, curl response, log)
- ❌ "I've implemented X" without evidence = NOT DONE
```

### Rule 3: PLAN BEFORE CODE
```
Vibe coding = technical debt. Always:
1. Research: Read relevant files first (don't write yet)
2. Plan: Create step-by-step implementation plan
3. Review: Human approves plan before execution
4. Implement: Execute one step at a time
5. Verify: Test after each step
```

### Rule 4: CONTEXT MANAGEMENT
```
Context exhaustion is the #1 failure mode:
- Use /clear between distinct tasks
- Compact at 70% context usage (not 90%)
- One feature per session
- Don't @-file large docs (reference paths instead)
- External memory > context window
```

### Rule 5: ATOMIC COMMITS
```
Small, verified commits:
- Commit after each completed task
- Never commit untested code
- Meaningful commit messages: type(scope): description
- Types: feat, fix, refactor, test, docs, chore
```

### Rule 6: NO SHELL COMPONENTS (ZERO TOLERANCE)
```
❌ SHELL COMPONENTS (Will be rejected):
- Buttons that console.log('TODO')
- Charts with mock/hardcoded data
- Forms that don't submit to real API
- UI components not connected to backend
- "Placeholder" implementations

✅ REQUIRED (Every feature):
- Frontend → Real API → Real database
- Working buttons with actual actions
- Charts from real endpoints
- Forms with validation + real submission
- Loading/error states

Before ANY Frontend Work:
1. VERIFY backend endpoint exists (grep -r "endpoint" api/)
2. TEST endpoint returns expected data
3. CONNECT frontend to real endpoint
4. VERIFY in DevTools Network tab
5. CONFIRM data persists after refresh

If backend missing → Create backend FIRST, then frontend
```

### Rule 7: NO DUPLICATE FILES
```
❌ FORBIDDEN:
- Creating new file when similar exists
- Two files with overlapping code
- Orphaned old files after creating new

✅ REQUIRED:
- SEARCH for existing similar files first
- ENHANCE existing file instead of creating new
- If new file needed, MIGRATE all references
- DELETE/deprecate old file explicitly

Before Creating Any New File:
1. SEARCH: grep -r "similar_function" src/
2. If EXISTS → Enhance existing file
3. If TRULY NEW → Create + document why
```

---

## 🔒 VERIFICATION PROTOCOL

### Task-Level Response Format

**Every task response MUST follow this format:**

```markdown
✅ Task X.Y Complete: [Brief description]

**Changes:**
- [file_path]:[line_numbers]
- [What was added/modified]

**Verification:**
$ [command run]
[ACTUAL OUTPUT - copy-paste, not summary]

**Confirm to proceed to Task X.Z?**
```

**Example GOOD Response:**
```markdown
✅ Task 1.1 Complete: Added booking patterns

**Changes:**
- core/intent/unified_classifier.py:138-145
- Added BOOKING_PATTERNS list (7 patterns)

**Verification:**
$ grep -c "schedule.*call\|book.*appointment" core/intent/unified_classifier.py
7

$ python -c "
from core.intent.unified_classifier import UnifiedClassifier
result = UnifiedClassifier().classify('Can I schedule a call?')
print(f'Intent: {result.intent}, Confidence: {result.confidence}')
"
Intent: booking, Confidence: 0.89

**Confirm to proceed to Task 1.2?**
```

**Example BAD Response (REJECTED):**
```markdown
✅ Tasks 1.1-1.4 complete! Added all the patterns and fixed the classifier.
Ready for Phase 2?

[NO VERIFICATION OUTPUT - REJECTED]
```

### Evidence Requirements Table

| Claim | Required Proof |
|-------|----------------|
| "Added patterns" | `grep` output showing patterns exist |
| "Fixed function" | Test output showing pass |
| "Updated config" | `cat` or `head` showing new values |
| "Created endpoint" | `curl` output showing response |
| "Phase complete" | Full pytest output + git commit hash |

---

## 🚧 PHASE GATES (Mandatory Checkpoints)

### Phase Gate Structure
```
PHASE 1
  ├── Task 1.1 → Verify → User ✓
  ├── Task 1.2 → Verify → User ✓
  └── Task 1.3 → Verify → User ✓
        │
        ▼
  ═══ PHASE 1 GATE ═══
  □ All verification outputs shown
  □ Test suite passes (show output)
  □ Git committed
  □ User says: "Phase 1 approved"
        │
        ▼ (Only after gate passes)
PHASE 2
  ...
```

### Phase Gate Checklist (Required after each phase)

```markdown
## ═══ PHASE X GATE ═══

### Verification Summary
- Task X.1: ✅ [one-line evidence summary]
- Task X.2: ✅ [one-line evidence summary]
- Task X.3: ✅ [one-line evidence summary]

### Test Suite
$ pytest tests/unit/test_[relevant].py -v
[PASTE FULL OUTPUT]

### Git Checkpoint
$ git add -p && git commit -m "feat(scope): phase X complete"
$ git log --oneline -1
[COMMIT HASH] feat(scope): phase X complete

### Gate Approval Required
⚠️ DO NOT PROCEED WITHOUT: "Phase X approved"
```

---

## 🛡️ GUARDS ENFORCEMENT

This project uses automated guards that BLOCK violations:

### Instant Guards (Every Edit)
- **bandaid_patterns**: No `# type: ignore`, `# noqa`, `except: pass`
- **shell_component**: No placeholder implementations, TODO buttons, mock data
- **security**: No hardcoded secrets, SQL injection patterns
- **hallucination**: No invented APIs or non-existent packages
- **duplicate_file**: No creating files when similar exists

### Task Guards (After Each Task)
- **context_loss**: Implementation must match task specification
- **evidence_required**: Tests must pass before marking complete
- **scope_creep**: Only modify files in task scope
- **e2e_required**: Frontend must connect to real backend

### Phase Guards (End of Phase)
- **spec_compliance**: Implementation matches architecture docs
- **e2e_tests**: Integration tests exist for features
- **no_orphans**: No unused/orphaned files

---

## ⚠️ FAILURE HANDLING

### If Verification Fails
```
1. STOP immediately (do not continue)
2. Show failure output
3. Analyze root cause
4. Fix the issue
5. Re-run verification
6. Show passing output
7. Only then proceed
```

### If Task Incomplete Discovered Later
```
1. STOP current work
2. Return to incomplete task
3. List what was missed
4. Complete with verification
5. Re-run phase gate
6. Get approval before continuing
```

### If Shell Component Found
```
STOP and ASK:
"Found shell component in [file]. Options:
  1. Remove entirely
  2. Implement E2E (needs: [list work])
  3. Keep as-is (not recommended)

To implement E2E:
  - Backend: [specific work]
  - Frontend: [specific work]
  - Verify: [how to test]

Which option?"
```

### If Duplicate Files Found
```
STOP and ASK:
"Found similar files:
  - [file1] - [description]
  - [file2] - [description]

Options:
  1. Consolidate into [recommended]
  2. Keep both (explain why needed)
  3. Delete [older/unused]

Which option?"
```

---

## 💡 PROACTIVE ENHANCEMENT SUGGESTIONS

When improvement opportunities are identified during work:

```markdown
**Enhancement Opportunity Noticed:**

While working on [task], I noticed:
- **Current:** [state/issue]
- **Enhancement:** [improvement]
- **Effort:** [low/medium/high]
- **Impact:** [benefits]

Options:
1. Implement now
2. Add to backlog
3. Skip

Which option?
```

---

## 📋 SESSION HANDOFF

After each phase, provide this summary for session continuity:

```markdown
## 📋 Phase X Complete - Checkpoint

### Completed (Verified)
- [x] Task X.1: [description] (verified: [evidence type])
- [x] Task X.2: [description] (verified: [evidence type])

### Git Status
- Branch: feature/[name]
- Latest commit: [hash] [message]

### Test Status
- [test file]: X/X passed

### Next
- Phase X+1: [name] ([count] tasks)

### To Continue in New Session
Paste this summary + say "Continue from Phase X+1"
```

---

## 📁 PROJECT STRUCTURE

```
Dev3SixtyRev/
├── docs/                    # Architecture documentation
│   └── *.md                 # Core Behaviors, Architecture specs
├── src/                     # Application source code
│   ├── core/               # Core platform components
│   │   ├── state_machine/  # Two-level state machine
│   │   ├── bdi_engine/     # Belief-Desire-Intention reasoning
│   │   ├── conversation/   # Conversation flow logic
│   │   ├── memory/         # Context persistence (Redis + PostgreSQL)
│   │   └── modes/          # AI mode enforcement (Assistant/Agent/Service)
│   ├── channels/           # Channel-specific implementations
│   ├── qualification/      # Lead qualification engine
│   ├── objections/         # Objection handling framework
│   ├── cross_sell/         # Cross-sell/upsell engine
│   ├── referrals/          # Referral solicitation
│   ├── integrations/       # CRM, Calendar, Communications
│   ├── api/                # FastAPI routes
│   └── shared/             # Common utilities, types
├── sdk/                     # Development enforcement SDK
│   ├── guards/             # Quality enforcement guards
│   ├── verification/       # Evidence collection, phase gates
│   ├── registry/           # Field registry management
│   ├── testing/            # Test frameworks
│   └── core/               # SDK core (modes, config)
├── tests/                   # Test suites
├── scripts/                 # Development utilities
├── .github/workflows/       # CI/CD pipelines
├── .claude/commands/        # Custom slash commands
└── CLAUDE.md               # This file
```

---

## 🔑 CORE BEHAVIORAL PRINCIPLES

From the Core Behaviors Specification:

### 1. Goals, Not Just Responses
```
Every turn evaluated against:
- What is my current goal?
- Did this message advance or hinder it?
- What should my next action be?
```

### 2. Invisible Tool Execution
```
❌ BAD: "Let me look up your information..."
✅ GOOD: "Hey John! Good to hear from you again..."

All tool calls execute WITHOUT verbal acknowledgment.
```

### 3. Never Ask Twice (Unless Warranted)
```
Valid re-ask conditions ONLY:
- USER_CORRECTION: User explicitly corrects
- USER_INDICATED_CHANGE: "actually, that's changed"
- STALE_VALUE: Value outdated (configurable)
- LOW_CONFIDENCE_CRITICAL: P0 field with <0.7 confidence
- CONFLICTING_VALUES: Two incompatible values
- USER_EXPLICITLY_UNSURE: User said "I'm not sure"
```

### 4. Channel-Native Communication
```
Voice: Filler words OK, backchanneling, longer responses
SMS: 160 chars, casual, max 1 question
Email: Formal, 100-250 words, signature required
Chat: 15-50 words, conversational
```

### 5. Graceful Degradation
```
There is ALWAYS a next action - never dead end
```

### 6. Compliance by Design
```
NEVER: Deny AI identity, collect blocked PII, make binding commitments in Assistant mode
ALWAYS: Respect opt-out, offer human option, protect customer data
```

---

## 🔧 KEY COMMANDS

```bash
# Development
pip install -e ".[dev]"      # Install with dev dependencies
pytest tests/ -v             # Run all tests

# Guards & Registry
3sr guard                    # Run guards
3sr verify                   # Verify task completion
3sr gate                     # Run phase gate
3sr registry validate        # Validate field registry
3sr registry stats           # Show registry statistics
3sr status                   # Show SDK status
```

---

## 📋 QUICK REFERENCE: RULES SUMMARY

| MUST DO | MUST NOT DO |
|---------|-------------|
| Show actual command output | Batch tasks as "all done" |
| Wait for confirm after each task | Proceed without evidence |
| Stop immediately on failure | Skip to next phase without gate |
| Git commit after each phase | Assume success without tests |
| Provide session handoff | Mark complete without user confirm |
| Search before creating new files | Create duplicate files |
| Backend first, then frontend | Shell/placeholder implementations |
| Suggest enhancements proactively | Hide improvement opportunities |

---

## 🎯 TARGET SPECIFICATIONS

### Performance
| Metric | Target |
|--------|--------|
| Voice latency P95 | <500ms |
| Voice latency target | 430ms |
| Text latency P95 | <2000ms |

### Quality
| Metric | Target |
|--------|--------|
| Turing pass rate | >70% |
| Human likeness score | ≥4.0/5.0 |
| Duplicate question rate | ≤1% |

### Business
| Metric | Target |
|--------|--------|
| Lead qualification rate | ≥60% |
| Appointment set rate | ≥40% |
| Cross-sell acceptance | ≥15% |

---

## 📚 REFERENCE DOCS

- **Core behaviors**: `3SixtyRev_Platform_Core_Behaviors_v1.0.md`
- **Architecture**: `3SixtyRev_Platform_Architecture_v3.0_Part_*.md`
- **Registry**: `COMPREHENSIVE_REGISTRY_*.yaml`
- **Registry Guide**: `docs/REGISTRY_GUIDE.md`

---

## 🆘 WHEN STUCK

1. **Context exhausted?** → `/clear` and restart with fresh context
2. **Guards failing?** → Read the violation message, fix the root cause
3. **Tests failing?** → Show the error output, fix incrementally
4. **Unclear requirements?** → Check Core Behaviors spec first, then ask
5. **Complex task?** → Break into smaller subtasks, tackle one at a time
6. **Mode confusion?** → Remember: regulated = Assistant only, never Agent

---

*This file is automatically loaded into Claude's context. Keep it concise and focused.*
