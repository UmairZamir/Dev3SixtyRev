"""
Tests for Verification Protocol
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import json

from sdk.verification.task_protocol import (
    TaskStatus,
    EvidenceType,
    TaskEvidence,
    FileChange,
    VerifiableTask,
    Phase,
    VerificationProtocol,
    get_verification_protocol,
    reset_verification_protocol,
)


@pytest.fixture
def protocol():
    """Get a fresh protocol instance."""
    return reset_verification_protocol()


@pytest.fixture
def sample_task():
    """Create a sample task."""
    return VerifiableTask(
        task_id="test_task_1",
        phase=1,
        sequence=1,
        description="Add booking patterns",
    )


class TestTaskEvidence:
    """Tests for TaskEvidence."""
    
    def test_evidence_creation(self):
        """Should create evidence with all fields."""
        evidence = TaskEvidence(
            evidence_type=EvidenceType.GREP_OUTPUT,
            description="Patterns exist",
            content="7",
            command='grep -c "pattern" file.py',
        )
        assert evidence.evidence_type == EvidenceType.GREP_OUTPUT
        assert evidence.description == "Patterns exist"
        assert evidence.content == "7"
        assert evidence.command is not None
    
    def test_evidence_to_dict(self):
        """Should convert to dict."""
        evidence = TaskEvidence(
            evidence_type=EvidenceType.TEST_OUTPUT,
            description="Tests pass",
            content="OK",
        )
        data = evidence.to_dict()
        assert data["type"] == "test_output"
        assert data["description"] == "Tests pass"
    
    def test_evidence_format_for_report(self):
        """Should format for report."""
        evidence = TaskEvidence(
            evidence_type=EvidenceType.COMMAND_OUTPUT,
            description="Check output",
            content="Success!",
            command="./check.sh",
        )
        report = evidence.format_for_report()
        assert "command_output" in report
        assert "./check.sh" in report
        assert "Success!" in report


class TestVerifiableTask:
    """Tests for VerifiableTask."""
    
    def test_task_number(self, sample_task):
        """Should format task number correctly."""
        assert sample_task.task_number == "1.1"
    
    def test_add_change(self, sample_task):
        """Should record file changes."""
        sample_task.add_change(
            "core/classifier.py",
            "138-145",
            "Added BOOKING_PATTERNS",
        )
        assert len(sample_task.file_changes) == 1
        assert sample_task.file_changes[0].file_path == "core/classifier.py"
        assert sample_task.file_changes[0].line_range == "138-145"
    
    def test_add_evidence(self, sample_task):
        """Should add evidence."""
        sample_task.add_evidence(
            EvidenceType.GREP_OUTPUT,
            "Pattern count",
            "7",
            command='grep -c "pattern" file.py',
        )
        assert len(sample_task.evidence) == 1
        assert sample_task.evidence[0].evidence_type == EvidenceType.GREP_OUTPUT
    
    def test_has_sufficient_evidence_empty(self, sample_task):
        """Should return False with no evidence."""
        assert not sample_task.has_sufficient_evidence()
    
    def test_has_sufficient_evidence_with_data(self, sample_task):
        """Should return True with evidence and changes."""
        sample_task.add_change("file.py")
        sample_task.add_evidence(EvidenceType.GREP_OUTPUT, "test", "output")
        assert sample_task.has_sufficient_evidence()
    
    def test_mark_awaiting_verification(self, sample_task):
        """Should update status correctly."""
        sample_task.mark_awaiting_verification()
        assert sample_task.status == TaskStatus.AWAITING_VERIFICATION
        assert sample_task.completed_at is not None
    
    def test_verify(self, sample_task):
        """Should mark as verified."""
        sample_task.verify("Confirmed")
        assert sample_task.status == TaskStatus.VERIFIED
        assert sample_task.user_confirmed
        assert sample_task.confirmation_message == "Confirmed"
    
    def test_fail(self, sample_task):
        """Should mark as failed."""
        sample_task.fail("Test failed")
        assert sample_task.status == TaskStatus.FAILED
        assert sample_task.confirmation_message == "Test failed"
    
    def test_format_completion_report(self, sample_task):
        """Should format completion report."""
        sample_task.add_change("file.py", "10-20", "Added function")
        sample_task.add_evidence(EvidenceType.TEST_OUTPUT, "Tests pass", "OK")
        
        report = sample_task.format_completion_report()
        
        assert "Task 1.1 Complete" in report
        assert "Add booking patterns" in report
        assert "file.py:10-20" in report
        assert "Confirm to proceed" in report


class TestPhase:
    """Tests for Phase."""
    
    def test_add_task(self):
        """Should add tasks with correct sequence."""
        phase = Phase(phase_number=1, name="Core Implementation")
        task1 = phase.add_task("First task")
        task2 = phase.add_task("Second task")
        
        assert len(phase.tasks) == 2
        assert task1.sequence == 1
        assert task2.sequence == 2
        assert task1.task_number == "1.1"
        assert task2.task_number == "1.2"
    
    def test_get_current_task(self):
        """Should return first non-verified task."""
        phase = Phase(phase_number=1, name="Test")
        task1 = phase.add_task("Task 1")
        task2 = phase.add_task("Task 2")
        
        assert phase.get_current_task() == task1
        
        task1.verify()
        assert phase.get_current_task() == task2
    
    def test_all_tasks_verified(self):
        """Should check all tasks are verified."""
        phase = Phase(phase_number=1, name="Test")
        task1 = phase.add_task("Task 1")
        task2 = phase.add_task("Task 2")
        
        assert not phase.all_tasks_verified()
        
        task1.verify()
        assert not phase.all_tasks_verified()
        
        task2.verify()
        assert phase.all_tasks_verified()
    
    def test_format_gate_checklist(self):
        """Should format gate checklist."""
        phase = Phase(phase_number=1, name="Core")
        task = phase.add_task("Task 1")
        task.add_evidence(EvidenceType.GREP_OUTPUT, "check", "ok")
        task.verify()
        
        checklist = phase.format_gate_checklist()
        
        assert "PHASE 1 GATE" in checklist
        assert "Verification Summary" in checklist
        assert "Git Checkpoint" in checklist
        assert "Gate Approval Required" in checklist
    
    def test_pass_gate(self):
        """Should pass gate when all tasks verified."""
        phase = Phase(phase_number=1, name="Test")
        task = phase.add_task("Task 1")
        task.verify()
        
        phase.pass_gate("abc123")
        
        assert phase.gate_passed
        assert phase.git_commit_hash == "abc123"
    
    def test_pass_gate_fails_if_not_verified(self):
        """Should not pass gate if tasks not verified."""
        phase = Phase(phase_number=1, name="Test")
        phase.add_task("Task 1")  # Not verified
        
        with pytest.raises(ValueError):
            phase.pass_gate("abc123")


class TestVerificationProtocol:
    """Tests for VerificationProtocol."""
    
    def test_start_phase(self, protocol):
        """Should start a new phase."""
        phase = protocol.start_phase(1, "Core Implementation")
        
        assert protocol.current_phase_number == 1
        assert phase.name == "Core Implementation"
        assert 1 in protocol.phases
    
    def test_get_current_phase(self, protocol):
        """Should return current phase."""
        protocol.start_phase(1, "Phase 1")
        
        current = protocol.get_current_phase()
        assert current.phase_number == 1
    
    def test_get_current_task(self, protocol):
        """Should return current task."""
        phase = protocol.start_phase(1, "Phase 1")
        task = phase.add_task("First task")
        
        current = protocol.get_current_task()
        assert current == task
    
    def test_can_proceed_to_next_phase(self, protocol):
        """Should check if can proceed."""
        phase = protocol.start_phase(1, "Phase 1")
        task = phase.add_task("Task 1")
        
        assert not protocol.can_proceed_to_next_phase()
        
        task.verify()
        phase.pass_gate("abc123")
        
        assert protocol.can_proceed_to_next_phase()
    
    def test_format_session_handoff(self, protocol):
        """Should format session handoff."""
        phase = protocol.start_phase(1, "Phase 1")
        task = phase.add_task("Task 1")
        task.add_evidence(EvidenceType.TEST_OUTPUT, "test", "pass")
        task.verify()
        phase.pass_gate("abc123")
        
        handoff = protocol.format_session_handoff()
        
        assert "Phase 1 Complete" in handoff
        assert "Task 1.1" in handoff
        assert "abc123" in handoff
        assert "Continue from Phase 2" in handoff
    
    def test_save_and_load_state(self, protocol):
        """Should save and load state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            protocol.project_root = Path(tmpdir)
            
            # Create some state
            phase = protocol.start_phase(1, "Test Phase")
            task = phase.add_task("Test Task")
            task.add_change("file.py", "10-20")
            task.add_evidence(EvidenceType.TEST_OUTPUT, "test", "pass")
            task.verify()
            
            # Save
            protocol.save_state()
            
            # Create new protocol and load
            new_protocol = VerificationProtocol(Path(tmpdir))
            new_protocol.load_state()
            
            # Verify state restored
            assert new_protocol.current_phase_number == 1
            assert 1 in new_protocol.phases
            assert len(new_protocol.phases[1].tasks) == 1
            assert new_protocol.phases[1].tasks[0].status == TaskStatus.VERIFIED


class TestWorkflow:
    """Integration tests for complete workflow."""
    
    def test_complete_workflow(self, protocol):
        """Test complete development workflow."""
        # Start Phase 1
        phase1 = protocol.start_phase(1, "Core Implementation")
        
        # Add tasks
        task1 = phase1.add_task("Add booking patterns")
        task2 = phase1.add_task("Update classifier")
        
        # Work on Task 1
        task1.add_change("core/classifier.py", "138-145", "Added BOOKING_PATTERNS")
        task1.add_evidence(
            EvidenceType.GREP_OUTPUT,
            "Patterns exist",
            "7",
            command='grep -c "pattern" file.py',
        )
        task1.mark_awaiting_verification()
        
        # Verify task 1
        report = task1.format_completion_report()
        assert "Task 1.1 Complete" in report
        task1.verify("Confirmed")
        
        # Work on Task 2
        task2.add_change("core/classifier.py", "200-210")
        task2.add_evidence(EvidenceType.TEST_OUTPUT, "Tests pass", "OK")
        task2.verify()
        
        # Check gate
        assert phase1.all_tasks_verified()
        checklist = phase1.format_gate_checklist()
        assert "PHASE 1 GATE" in checklist
        
        # Pass gate
        phase1.pass_gate("abc123")
        assert protocol.can_proceed_to_next_phase()
        
        # Start Phase 2
        phase2 = protocol.start_phase(2, "Integration")
        assert protocol.current_phase_number == 2
