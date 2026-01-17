"""
Task Verification Protocol
==========================

Enforces the verification-focused development protocol:
- Task-level verification with evidence
- Phase gates with mandatory checkpoints
- Session handoff support
- Failure handling procedures
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import json
import hashlib


class TaskStatus(str, Enum):
    """Task completion status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_VERIFICATION = "awaiting_verification"
    VERIFIED = "verified"
    FAILED = "failed"
    BLOCKED = "blocked"


class EvidenceType(str, Enum):
    """Types of evidence for verification."""
    GREP_OUTPUT = "grep_output"
    TEST_OUTPUT = "test_output"
    COMMAND_OUTPUT = "command_output"
    FILE_DIFF = "file_diff"
    CURL_RESPONSE = "curl_response"
    SCREENSHOT = "screenshot"
    LOG_OUTPUT = "log_output"
    GIT_COMMIT = "git_commit"


@dataclass
class TaskEvidence:
    """Evidence for task verification."""
    evidence_type: EvidenceType
    description: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    command: Optional[str] = None
    file_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.evidence_type.value,
            "description": self.description,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "command": self.command,
            "file_path": self.file_path,
        }
    
    def format_for_report(self) -> str:
        """Format evidence for task report."""
        lines = [f"**{self.evidence_type.value}**: {self.description}"]
        if self.command:
            lines.append(f"```bash\n$ {self.command}\n```")
        lines.append(f"```\n{self.content[:500]}{'...' if len(self.content) > 500 else ''}\n```")
        return "\n".join(lines)


@dataclass
class FileChange:
    """Record of a file change."""
    file_path: str
    line_range: Optional[str] = None  # e.g., "138-145"
    description: str = ""
    change_type: str = "modified"  # added, modified, deleted


@dataclass
class VerifiableTask:
    """A task that requires verification before completion."""
    task_id: str
    phase: int
    sequence: int  # Task number within phase
    description: str
    status: TaskStatus = TaskStatus.PENDING
    
    # Changes made
    file_changes: List[FileChange] = field(default_factory=list)
    
    # Evidence collected
    evidence: List[TaskEvidence] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    
    # Verification
    user_confirmed: bool = False
    confirmation_message: Optional[str] = None
    
    @property
    def task_number(self) -> str:
        """Get task number like '1.2'."""
        return f"{self.phase}.{self.sequence}"
    
    def add_change(self, file_path: str, line_range: Optional[str] = None, 
                   description: str = "", change_type: str = "modified") -> None:
        """Record a file change."""
        self.file_changes.append(FileChange(
            file_path=file_path,
            line_range=line_range,
            description=description,
            change_type=change_type,
        ))
    
    def add_evidence(self, evidence_type: EvidenceType, description: str, 
                     content: str, command: Optional[str] = None,
                     file_path: Optional[str] = None) -> None:
        """Add verification evidence."""
        self.evidence.append(TaskEvidence(
            evidence_type=evidence_type,
            description=description,
            content=content,
            command=command,
            file_path=file_path,
        ))
    
    def mark_awaiting_verification(self) -> None:
        """Mark task as awaiting user verification."""
        self.status = TaskStatus.AWAITING_VERIFICATION
        self.completed_at = datetime.now()
    
    def verify(self, confirmation_message: str = "Confirmed") -> None:
        """Mark task as verified by user."""
        self.status = TaskStatus.VERIFIED
        self.user_confirmed = True
        self.confirmation_message = confirmation_message
        self.verified_at = datetime.now()
    
    def fail(self, reason: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.confirmation_message = reason
    
    def has_sufficient_evidence(self) -> bool:
        """Check if task has sufficient evidence for verification."""
        # Must have at least one piece of evidence
        if not self.evidence:
            return False
        
        # Must have at least one change recorded
        if not self.file_changes:
            return False
        
        return True
    
    def format_completion_report(self) -> str:
        """Format the task completion report for user review."""
        lines = [
            f"✅ Task {self.task_number} Complete: {self.description}",
            "",
            "**Changes:**",
        ]
        
        for change in self.file_changes:
            line_info = f":{change.line_range}" if change.line_range else ""
            lines.append(f"- {change.file_path}{line_info}")
            if change.description:
                lines.append(f"  {change.description}")
        
        lines.append("")
        lines.append("**Verification:**")
        
        for ev in self.evidence:
            lines.append(ev.format_for_report())
        
        lines.append("")
        lines.append(f"**Confirm to proceed to next task?**")
        
        return "\n".join(lines)


@dataclass
class Phase:
    """A development phase containing multiple tasks."""
    phase_number: int
    name: str
    description: str = ""
    tasks: List[VerifiableTask] = field(default_factory=list)
    
    # Gate status
    gate_passed: bool = False
    gate_passed_at: Optional[datetime] = None
    git_commit_hash: Optional[str] = None
    
    def add_task(self, description: str) -> VerifiableTask:
        """Add a task to this phase."""
        sequence = len(self.tasks) + 1
        task = VerifiableTask(
            task_id=f"phase{self.phase_number}_task{sequence}",
            phase=self.phase_number,
            sequence=sequence,
            description=description,
        )
        self.tasks.append(task)
        return task
    
    def get_current_task(self) -> Optional[VerifiableTask]:
        """Get the current task (first non-verified task)."""
        for task in self.tasks:
            if task.status != TaskStatus.VERIFIED:
                return task
        return None
    
    def all_tasks_verified(self) -> bool:
        """Check if all tasks in phase are verified."""
        return all(t.status == TaskStatus.VERIFIED for t in self.tasks)
    
    def format_gate_checklist(self) -> str:
        """Format the phase gate checklist."""
        lines = [
            f"## ═══ PHASE {self.phase_number} GATE ═══",
            "",
            "### Verification Summary",
        ]
        
        for task in self.tasks:
            status = "✅" if task.status == TaskStatus.VERIFIED else "❌"
            evidence_summary = task.evidence[0].description if task.evidence else "no evidence"
            lines.append(f"- Task {task.task_number}: {status} {task.description} (verified: {evidence_summary})")
        
        lines.extend([
            "",
            "### Test Suite",
            "```bash",
            "$ pytest tests/unit/test_[relevant].py -v",
            "[PASTE FULL OUTPUT]",
            "```",
            "",
            "### Git Checkpoint",
            "```bash",
            f'$ git add -p && git commit -m "feat(scope): phase {self.phase_number} complete"',
            "$ git log --oneline -1",
            f"[COMMIT HASH] feat(scope): phase {self.phase_number} complete",
            "```",
            "",
            "### Gate Approval Required",
            f'⚠️ DO NOT PROCEED WITHOUT: "Phase {self.phase_number} approved"',
        ])
        
        return "\n".join(lines)
    
    def pass_gate(self, commit_hash: str) -> None:
        """Mark the phase gate as passed."""
        if not self.all_tasks_verified():
            raise ValueError("Cannot pass gate: not all tasks verified")
        self.gate_passed = True
        self.gate_passed_at = datetime.now()
        self.git_commit_hash = commit_hash


class VerificationProtocol:
    """
    Manages the verification-focused development protocol.
    
    Usage:
        protocol = VerificationProtocol()
        
        # Start a new phase
        phase = protocol.start_phase(1, "Core Implementation")
        
        # Add tasks
        task1 = phase.add_task("Add booking patterns")
        task2 = phase.add_task("Update classifier")
        
        # Work on task
        task1.add_change("core/classifier.py", "138-145", "Added BOOKING_PATTERNS")
        task1.add_evidence(
            EvidenceType.GREP_OUTPUT,
            "Patterns exist in file",
            "7",
            command='grep -c "schedule.*call" core/classifier.py'
        )
        task1.mark_awaiting_verification()
        
        # Show completion report
        print(task1.format_completion_report())
        
        # User confirms
        task1.verify("Confirmed")
        
        # After all tasks, check gate
        if phase.all_tasks_verified():
            print(phase.format_gate_checklist())
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.phases: Dict[int, Phase] = {}
        self.current_phase_number: int = 0
        self.session_start: datetime = datetime.now()
        
    def start_phase(self, phase_number: int, name: str, description: str = "") -> Phase:
        """Start a new development phase."""
        if phase_number in self.phases:
            return self.phases[phase_number]
        
        phase = Phase(
            phase_number=phase_number,
            name=name,
            description=description,
        )
        self.phases[phase_number] = phase
        self.current_phase_number = phase_number
        return phase
    
    def get_current_phase(self) -> Optional[Phase]:
        """Get the current phase."""
        return self.phases.get(self.current_phase_number)
    
    def get_current_task(self) -> Optional[VerifiableTask]:
        """Get the current task being worked on."""
        phase = self.get_current_phase()
        if phase:
            return phase.get_current_task()
        return None
    
    def can_proceed_to_next_phase(self) -> bool:
        """Check if we can proceed to the next phase."""
        phase = self.get_current_phase()
        if not phase:
            return True
        return phase.gate_passed
    
    def format_session_handoff(self) -> str:
        """Format a session handoff summary."""
        lines = [
            f"## 📋 Phase {self.current_phase_number} Complete - Checkpoint",
            "",
            "### Completed (Verified)",
        ]
        
        for phase_num, phase in sorted(self.phases.items()):
            for task in phase.tasks:
                if task.status == TaskStatus.VERIFIED:
                    evidence_type = task.evidence[0].evidence_type.value if task.evidence else "manual"
                    lines.append(f"- [x] Task {task.task_number}: {task.description} (verified: {evidence_type})")
        
        phase = self.get_current_phase()
        if phase and phase.git_commit_hash:
            lines.extend([
                "",
                "### Git Status",
                f"- Branch: feature/[name]",
                f"- Latest commit: {phase.git_commit_hash}",
            ])
        
        lines.extend([
            "",
            "### Test Status",
            "- [test file]: X/X passed",
            "",
            "### Next",
            f"- Phase {self.current_phase_number + 1}: [name] ([count] tasks)",
            "",
            "### To Continue in New Session",
            f'Paste this summary + say "Continue from Phase {self.current_phase_number + 1}"',
        ])
        
        return "\n".join(lines)
    
    def save_state(self, path: Optional[Path] = None) -> None:
        """Save protocol state to file."""
        path = path or (self.project_root / ".3sr" / "verification_state.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        
        state = {
            "session_start": self.session_start.isoformat(),
            "current_phase": self.current_phase_number,
            "phases": {},
        }
        
        for phase_num, phase in self.phases.items():
            state["phases"][str(phase_num)] = {
                "name": phase.name,
                "description": phase.description,
                "gate_passed": phase.gate_passed,
                "git_commit_hash": phase.git_commit_hash,
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "description": t.description,
                        "status": t.status.value,
                        "user_confirmed": t.user_confirmed,
                        "file_changes": [
                            {
                                "file_path": c.file_path,
                                "line_range": c.line_range,
                                "description": c.description,
                            }
                            for c in t.file_changes
                        ],
                        "evidence": [e.to_dict() for e in t.evidence],
                    }
                    for t in phase.tasks
                ],
            }
        
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
    
    def load_state(self, path: Optional[Path] = None) -> None:
        """Load protocol state from file."""
        path = path or (self.project_root / ".3sr" / "verification_state.json")
        
        if not path.exists():
            return
        
        with open(path) as f:
            state = json.load(f)
        
        self.session_start = datetime.fromisoformat(state["session_start"])
        self.current_phase_number = state["current_phase"]
        
        for phase_num_str, phase_data in state.get("phases", {}).items():
            phase_num = int(phase_num_str)
            phase = Phase(
                phase_number=phase_num,
                name=phase_data["name"],
                description=phase_data.get("description", ""),
                gate_passed=phase_data.get("gate_passed", False),
                git_commit_hash=phase_data.get("git_commit_hash"),
            )
            
            for task_data in phase_data.get("tasks", []):
                task = VerifiableTask(
                    task_id=task_data["task_id"],
                    phase=phase_num,
                    sequence=len(phase.tasks) + 1,
                    description=task_data["description"],
                    status=TaskStatus(task_data["status"]),
                    user_confirmed=task_data.get("user_confirmed", False),
                )
                
                for change_data in task_data.get("file_changes", []):
                    task.file_changes.append(FileChange(**change_data))
                
                for ev_data in task_data.get("evidence", []):
                    task.evidence.append(TaskEvidence(
                        evidence_type=EvidenceType(ev_data["type"]),
                        description=ev_data["description"],
                        content=ev_data["content"],
                        command=ev_data.get("command"),
                        file_path=ev_data.get("file_path"),
                    ))
                
                phase.tasks.append(task)
            
            self.phases[phase_num] = phase


# Singleton instance
_protocol: Optional[VerificationProtocol] = None


def get_verification_protocol(project_root: Optional[Path] = None) -> VerificationProtocol:
    """Get the singleton verification protocol instance."""
    global _protocol
    if _protocol is None:
        _protocol = VerificationProtocol(project_root)
        _protocol.load_state()
    return _protocol


def reset_verification_protocol() -> VerificationProtocol:
    """Reset and return a fresh verification protocol."""
    global _protocol
    _protocol = VerificationProtocol()
    return _protocol
