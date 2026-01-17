"""
SDK Verification Package
========================

Tools for verifying task completion and enforcing quality gates.

Includes:
- Evidence collection for task verification
- Phase gates for development milestones
- Task verification protocol for step-by-step verification
"""

from sdk.verification.evidence_collector import (
    Evidence,
    EvidenceCollector,
    EvidenceType,
    EvidenceStatus,
    Task,
    get_collector,
)

from sdk.verification.phase_gate import (
    Phase,
    PhaseGate,
    PhaseRequirement,
    PhaseResult,
    get_phase_gate,
)

from sdk.verification.task_protocol import (
    TaskStatus,
    EvidenceType as TaskEvidenceType,
    TaskEvidence,
    FileChange,
    VerifiableTask,
    Phase as VerificationPhase,
    VerificationProtocol,
    get_verification_protocol,
    reset_verification_protocol,
)

__all__ = [
    # Evidence Collector
    "Evidence",
    "EvidenceCollector",
    "EvidenceType",
    "EvidenceStatus",
    "Task",
    "get_collector",
    # Phase Gate
    "Phase",
    "PhaseGate",
    "PhaseRequirement",
    "PhaseResult",
    "get_phase_gate",
    # Task Protocol
    "TaskStatus",
    "TaskEvidenceType",
    "TaskEvidence",
    "FileChange",
    "VerifiableTask",
    "VerificationPhase",
    "VerificationProtocol",
    "get_verification_protocol",
    "reset_verification_protocol",
]
