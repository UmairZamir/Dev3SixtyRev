"""
E2E Tests for Registry System
=============================

Tests the complete registry workflow:
1. Load YAML registry files
2. Parse fields and patterns
3. Extract values from conversation text
4. Validate extracted values
5. Generate TypeScript types
"""

import pytest
from pathlib import Path


class TestRegistryE2E:
    """End-to-end tests for the registry system."""
    
    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent
    
    def test_full_registry_load_and_validate(self, project_root):
        """
        E2E: Load registry from actual YAML files and validate.
        
        Steps:
        1. Load all COMPREHENSIVE_REGISTRY_*.yaml files
        2. Validate registry structure
        3. Check statistics
        """
        from sdk.registry import get_registry, validate_registry, reload_registry
        
        # Force reload to use actual files
        registry = reload_registry(project_root)
        
        # Verify enums loaded
        stats = registry.get_statistics()
        assert stats["enums"] > 0, "No enums loaded from registry files"
        
        # Validate registry
        result = validate_registry(project_root)
        
        # Should not have critical errors (warnings OK)
        critical_errors = [
            e for e in result.errors 
            if "Required" in e.message or "not defined" in e.message
        ]
        assert len(critical_errors) == 0, f"Critical errors: {critical_errors}"
        
        print(f"\n✓ Registry loaded: {stats}")
    
    def test_enum_access_and_validation(self, project_root):
        """
        E2E: Access enums and validate values.
        
        Steps:
        1. Load registry
        2. Access ai_mode enum
        3. Validate known values
        """
        from sdk.registry import reload_registry
        
        registry = reload_registry(project_root)
        
        # Get ai_mode enum
        ai_mode = registry.get_enum("ai_mode")
        assert ai_mode is not None, "ai_mode enum not found"
        
        # Validate known values
        assert ai_mode.is_valid("assistant"), "assistant should be valid"
        assert ai_mode.is_valid("agent"), "agent should be valid"
        assert ai_mode.is_valid("service"), "service should be valid"
        assert not ai_mode.is_valid("invalid_mode"), "invalid_mode should not be valid"
        
        # Get channel enum
        channel = registry.get_enum("channel")
        assert channel is not None, "channel enum not found"
        
        # Validate channel values
        assert channel.is_valid("voice"), "voice should be valid"
        assert channel.is_valid("sms"), "sms should be valid"
        assert channel.is_valid("email"), "email should be valid"
        assert channel.is_valid("chat"), "chat should be valid"
        
        print(f"\n✓ Enums validated: ai_mode has {len(ai_mode.values)} values")
    
    def test_typescript_generation(self, project_root):
        """
        E2E: Generate TypeScript types from registry.
        
        Steps:
        1. Load registry
        2. Generate TypeScript
        3. Verify output contains expected structures
        """
        from sdk.registry import reload_registry, TypeScriptGenerator
        
        registry = reload_registry(project_root)
        generator = TypeScriptGenerator(registry)
        
        # Generate types
        ts_output = generator.generate_all()
        
        # Verify output
        assert len(ts_output) > 500, "TypeScript output too short"
        assert "AUTO-GENERATED" in ts_output, "Missing generation header"
        assert "export type" in ts_output, "Missing type exports"
        assert "export interface" in ts_output, "Missing interface exports"
        
        # Check for specific expected types
        assert "AiMode" in ts_output or "Channel" in ts_output, "Missing enum types"
        
        print(f"\n✓ TypeScript generated: {len(ts_output)} characters")
    
    def test_extraction_standard_tests(self, project_root):
        """
        E2E: Run standard extraction tests.
        
        Steps:
        1. Load registry
        2. Run standard extraction tests
        3. Report results
        """
        from sdk.registry import reload_registry, run_standard_tests
        
        # Reload registry
        reload_registry(project_root)
        
        # Run tests
        result = run_standard_tests(project_root)
        
        # Report results
        print(f"\n✓ Extraction tests: {result.passed}/{result.total} passed")
        
        # Show failures if any
        for test_result in result.results:
            if not test_result.passed:
                tc = test_result.test_case
                print(f"  ✗ {tc.name}: expected {tc.expected_value}, got {test_result.extracted_value}")


class TestVerificationProtocolE2E:
    """End-to-end tests for the verification protocol."""
    
    def test_complete_verification_workflow(self, tmp_path):
        """
        E2E: Complete verification workflow.
        
        Steps:
        1. Create protocol
        2. Start phase
        3. Add tasks with evidence
        4. Verify tasks
        5. Pass phase gate
        6. Save and restore state
        """
        from sdk.verification import (
            VerificationProtocol,
            TaskStatus,
        )
        from sdk.verification.task_protocol import EvidenceType
        
        # Create protocol with temp directory
        protocol = VerificationProtocol(tmp_path)
        
        # Phase 1: Core Implementation
        phase1 = protocol.start_phase(1, "Core Implementation", "Implement core features")
        
        # Add tasks
        task1 = phase1.add_task("Add booking patterns to classifier")
        task2 = phase1.add_task("Update intent router")
        
        # Work on Task 1
        task1.add_change(
            file_path="core/intent/classifier.py",
            line_range="138-145",
            description="Added BOOKING_PATTERNS list with 7 patterns",
        )
        task1.add_evidence(
            evidence_type=EvidenceType.GREP_OUTPUT,
            description="Pattern count verification",
            content="7",
            command='grep -c "schedule.*call" core/intent/classifier.py',
        )
        task1.add_evidence(
            evidence_type=EvidenceType.TEST_OUTPUT,
            description="Unit tests pass",
            content="===== 5 passed in 0.3s =====",
            command="pytest tests/unit/test_classifier.py -v",
        )
        
        # Mark for verification
        task1.mark_awaiting_verification()
        assert task1.status == TaskStatus.AWAITING_VERIFICATION
        
        # Generate report
        report = task1.format_completion_report()
        assert "Task 1.1 Complete" in report
        assert "core/intent/classifier.py:138-145" in report
        assert "Confirm to proceed" in report
        
        # Verify task 1
        task1.verify("Confirmed")
        assert task1.status == TaskStatus.VERIFIED
        assert task1.user_confirmed
        
        # Work on Task 2
        task2.add_change(
            file_path="core/intent/router.py",
            line_range="50-65",
            description="Added booking intent routing",
        )
        task2.add_evidence(
            evidence_type=EvidenceType.TEST_OUTPUT,
            description="Integration tests pass",
            content="===== 3 passed in 0.5s =====",
        )
        task2.verify("Looks good")
        
        # Check phase gate
        assert phase1.all_tasks_verified()
        
        # Generate gate checklist
        checklist = phase1.format_gate_checklist()
        assert "PHASE 1 GATE" in checklist
        assert "Task 1.1: ✅" in checklist
        assert "Task 1.2: ✅" in checklist
        
        # Pass gate
        phase1.pass_gate("abc123def456")
        assert phase1.gate_passed
        assert phase1.git_commit_hash == "abc123def456"
        
        # Save state
        protocol.save_state()
        
        # Create new protocol and load state
        protocol2 = VerificationProtocol(tmp_path)
        protocol2.load_state()
        
        # Verify state restored
        assert protocol2.current_phase_number == 1
        assert 1 in protocol2.phases
        restored_phase = protocol2.phases[1]
        assert restored_phase.gate_passed
        assert len(restored_phase.tasks) == 2
        assert restored_phase.tasks[0].status == TaskStatus.VERIFIED
        
        # Generate session handoff
        handoff = protocol.format_session_handoff()
        assert "Phase 1 Complete" in handoff
        assert "abc123def456" in handoff
        
        print("\n✓ Verification protocol workflow complete")
        print(f"  - 2 tasks verified")
        print(f"  - Phase gate passed")
        print(f"  - State saved and restored")


class TestGuardsE2E:
    """End-to-end tests for the guards system."""
    
    def test_guards_on_real_files(self, tmp_path):
        """
        E2E: Run guards on actual files.
        
        Steps:
        1. Create test files with known issues
        2. Run guards
        3. Verify issues detected
        """
        from sdk.guards import get_guard_registry, GuardSeverity
        
        # Create a file with shell component issues
        shell_file = tmp_path / "shell_component.tsx"
        shell_file.write_text('''
function handleClick() {
    console.log('TODO: implement this');
}

const mockData = [
    { id: 1, name: 'placeholder item' },
];

export default function Component() {
    return (
        <button onClick={() => {}}>Click me</button>
    );
}
''')
        
        # Create a clean file
        clean_file = tmp_path / "clean_component.tsx"
        clean_file.write_text('''
import { api } from './api';

function handleClick() {
    api.submitForm({ data: formData })
        .then(response => setResult(response))
        .catch(error => setError(error.message));
}

export default function Component() {
    return (
        <button onClick={handleClick}>Submit</button>
    );
}
''')
        
        # Run guards
        registry = get_guard_registry()
        
        # Check shell file - should have violations
        shell_result = registry.run_on_file(shell_file)
        shell_errors = [v for v in shell_result.violations if v.severity == GuardSeverity.ERROR]
        assert len(shell_errors) > 0, "Should detect shell component issues"
        
        # Check clean file - should pass
        clean_result = registry.run_on_file(clean_file)
        clean_errors = [v for v in clean_result.violations if v.severity == GuardSeverity.ERROR]
        assert len(clean_errors) == 0, f"Clean file should pass: {clean_errors}"
        
        print(f"\n✓ Guards E2E test:")
        print(f"  - Shell file: {len(shell_errors)} errors detected")
        print(f"  - Clean file: passed")
    
    def test_guards_on_python_files(self, tmp_path):
        """
        E2E: Run guards on Python files.
        """
        from sdk.guards import get_guard_registry, GuardSeverity
        
        # Create file with issues
        bad_file = tmp_path / "bad_module.py"
        bad_file.write_text('''
def process_data():
    pass  # TODO implement this
    
def handle_request():
    raise NotImplementedError()
    
def get_config():
    api_key = "sk-1234567890"  # hardcoded secret
    return {"key": api_key}
''')
        
        # Run guards
        registry = get_guard_registry()
        result = registry.run_on_file(bad_file)
        
        errors = [v for v in result.violations if v.severity == GuardSeverity.ERROR]
        
        # Should detect multiple issues
        assert len(errors) >= 1, f"Should detect issues: {result.violations}"
        
        print(f"\n✓ Python guards E2E: {len(errors)} errors detected")


class TestFullWorkflowE2E:
    """End-to-end test of complete development workflow."""
    
    def test_development_workflow(self, tmp_path):
        """
        E2E: Simulate complete development workflow.
        
        Simulates:
        1. Developer starts work
        2. Creates code
        3. Guards check code
        4. Verification protocol tracks progress
        5. Phase gate passed
        """
        from sdk.guards import get_guard_registry
        from sdk.verification import VerificationProtocol
        from sdk.verification.task_protocol import EvidenceType
        
        # Setup
        protocol = VerificationProtocol(tmp_path)
        guards = get_guard_registry()
        
        # Start phase
        phase = protocol.start_phase(1, "Feature Implementation")
        task = phase.add_task("Create API endpoint")
        
        # Developer writes code
        code_file = tmp_path / "api_endpoint.py"
        code_file.write_text('''
from fastapi import APIRouter

router = APIRouter()

@router.post("/bookings")
async def create_booking(data: BookingRequest):
    """Create a new booking."""
    booking = await BookingService.create(data)
    return {"id": booking.id, "status": "created"}
''')
        
        # Run guards on code
        guard_result = guards.run_on_file(code_file)
        
        # Record results
        task.add_change(
            file_path=str(code_file),
            description="Created booking API endpoint",
        )
        
        task.add_evidence(
            evidence_type=EvidenceType.COMMAND_OUTPUT,
            description="Guards passed",
            content=guard_result.format_short(),
            command="3sr guard api_endpoint.py",
        )
        
        # Verify and complete
        if guard_result.passed:
            task.verify("Guards passed, code looks good")
            phase.pass_gate("dev123")
            
            print("\n✓ Full workflow E2E:")
            print(f"  - Code written and checked")
            print(f"  - Guards: {guard_result.format_short()}")
            print(f"  - Task verified")
            print(f"  - Phase gate passed")
        else:
            task.fail("Guards failed")
            print(f"\n✗ Guards failed: {guard_result.format_short()}")
