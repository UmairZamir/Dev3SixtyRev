"""Tests for evidence collection and phase gates."""

import pytest
from pathlib import Path
from sdk.verification.evidence_collector import (
    Evidence,
    EvidenceCollector,
    EvidenceType,
    EvidenceStatus,
)
from sdk.verification.phase_gate import Phase, PhaseGate


class TestEvidence:
    """Tests for Evidence dataclass."""

    def test_create_evidence(self):
        """Test creating evidence."""
        evidence = Evidence(
            id="ev_123",
            evidence_type=EvidenceType.TEST_RESULT,
            description="Test results",
        )
        assert evidence.id == "ev_123"
        assert evidence.evidence_type == EvidenceType.TEST_RESULT
        assert evidence.status == EvidenceStatus.PENDING

    def test_passing_evidence(self):
        """Test evidence is passing."""
        evidence = Evidence(
            id="ev_123",
            evidence_type=EvidenceType.TEST_RESULT,
            description="Test",
            status=EvidenceStatus.COLLECTED,
            exit_code=0,
        )
        assert evidence.is_passing()

    def test_failing_evidence(self):
        """Test evidence is failing."""
        evidence = Evidence(
            id="ev_123",
            evidence_type=EvidenceType.TEST_RESULT,
            description="Test",
            status=EvidenceStatus.COLLECTED,
            exit_code=1,
        )
        assert not evidence.is_passing()


class TestEvidenceCollector:
    """Tests for EvidenceCollector."""

    @pytest.fixture
    def collector(self, tmp_path):
        return EvidenceCollector(evidence_dir=tmp_path / "evidence")

    def test_create_task(self, collector):
        """Test creating a task."""
        task = collector.create_task(
            "task-1",
            "Implement feature X",
            required_evidence=[EvidenceType.TEST_RESULT],
        )
        assert task.id == "task-1"
        assert task.description == "Implement feature X"
        assert not task.is_complete()

    def test_add_evidence(self, collector):
        """Test adding evidence to task."""
        task = collector.create_task("task-1", "Test task")
        
        evidence = Evidence(
            id="ev_1",
            evidence_type=EvidenceType.TEST_RESULT,
            description="Tests passed",
            status=EvidenceStatus.COLLECTED,
            exit_code=0,
        )
        collector.add_evidence(evidence)
        
        assert len(task.evidence) == 1
        assert task.is_complete()

    def test_task_missing_evidence(self, collector):
        """Test task with missing evidence."""
        task = collector.create_task(
            "task-1",
            "Test task",
            required_evidence=[
                EvidenceType.TEST_RESULT,
                EvidenceType.TYPE_CHECK,
            ],
        )
        
        # Add only test result
        evidence = Evidence(
            id="ev_1",
            evidence_type=EvidenceType.TEST_RESULT,
            description="Tests",
            status=EvidenceStatus.COLLECTED,
        )
        collector.add_evidence(evidence)
        
        assert not task.is_complete()
        missing = task.missing_evidence()
        assert EvidenceType.TYPE_CHECK in missing

    def test_manual_evidence(self, collector):
        """Test adding manual evidence."""
        task = collector.create_task(
            "task-1",
            "Manual verification needed",
            required_evidence=[EvidenceType.MANUAL_VERIFICATION],
        )
        
        evidence = collector.add_manual_evidence(
            "Verified UI looks correct",
            "Screenshot reviewed, all elements aligned",
            passed=True,
        )
        collector.add_evidence(evidence)
        
        assert task.is_complete()


class TestPhaseGate:
    """Tests for PhaseGate."""

    @pytest.fixture
    def gate(self):
        return PhaseGate()

    def test_initial_phase(self, gate):
        """Test initial phase is RESEARCH."""
        assert gate.current_phase == Phase.RESEARCH

    def test_set_phase(self, gate):
        """Test setting phase."""
        gate.set_phase(Phase.IMPLEMENT)
        assert gate.current_phase == Phase.IMPLEMENT

    def test_get_next_phase(self, gate):
        """Test getting next phase."""
        assert gate.get_next_phase() == Phase.PLAN
        
        gate.set_phase(Phase.IMPLEMENT)
        assert gate.get_next_phase() == Phase.TEST

    def test_mark_requirement_complete(self, gate):
        """Test marking requirements complete."""
        gate.mark_requirement_complete("Read architecture docs")
        gate.mark_requirement_complete("Understand requirements")
        
        result = gate.check_transition(Phase.PLAN)
        assert len(result.requirements_met) == 2

    def test_advance_blocked(self, gate):
        """Test advance is blocked without requirements."""
        result = gate.advance()
        assert not result
        assert gate.current_phase == Phase.RESEARCH

    def test_advance_forced(self, gate):
        """Test forced advance."""
        result = gate.advance(force=True)
        assert result
        assert gate.current_phase == Phase.PLAN

    def test_phase_order(self, gate):
        """Test phase order is correct."""
        expected = [
            Phase.RESEARCH,
            Phase.PLAN,
            Phase.IMPLEMENT,
            Phase.TEST,
            Phase.REVIEW,
            Phase.COMPLETE,
        ]
        assert gate.PHASE_ORDER == expected

    def test_final_phase_no_next(self, gate):
        """Test no next phase at COMPLETE."""
        gate.set_phase(Phase.COMPLETE)
        assert gate.get_next_phase() is None
