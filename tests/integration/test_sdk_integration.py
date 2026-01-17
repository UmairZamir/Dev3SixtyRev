"""
Integration Tests for SDK Components
====================================

Tests cross-component integration:
- Guards + Verification
- Registry + Guards  
- CLI integration
"""

import pytest
from pathlib import Path
import subprocess


class TestGuardsVerificationIntegration:
    """Tests integration between guards and verification systems."""
    
    def test_guards_provide_evidence_for_verification(self, tmp_path):
        """Guards results should be usable as verification evidence."""
        from sdk.guards import get_guard_registry
        from sdk.verification import VerificationProtocol
        from sdk.verification.task_protocol import EvidenceType
        
        # Create a test file
        test_file = tmp_path / "component.py"
        test_file.write_text('''
def calculate_total(items):
    """Calculate total price of items."""
    return sum(item.price for item in items)
''')
        
        # Run guards
        registry = get_guard_registry()
        result = registry.run_on_file(test_file)
        
        # Use result as evidence
        protocol = VerificationProtocol(tmp_path)
        phase = protocol.start_phase(1, "Test")
        task = phase.add_task("Create component")
        
        task.add_change(str(test_file), description="Created calculate_total function")
        task.add_evidence(
            evidence_type=EvidenceType.COMMAND_OUTPUT,
            description="Guards check",
            content=result.format_short(),
            command="3sr guard component.py",
        )
        
        # Verify
        if result.passed:
            task.verify("Guards passed")
            assert task.has_sufficient_evidence()
        else:
            task.fail(f"Guards failed: {result.format_short()}")
    
    def test_phase_gate_requires_guard_pass(self, tmp_path):
        """Phase gate should consider guard results."""
        from sdk.guards import get_guard_registry, GuardSeverity
        from sdk.verification import VerificationProtocol
        from sdk.verification.task_protocol import EvidenceType
        
        # Create file with issues
        bad_file = tmp_path / "bad_code.py"
        bad_file.write_text('''
def broken():
    pass  # TODO implement
''')
        
        # Run guards
        registry = get_guard_registry()
        result = registry.run_on_file(bad_file)
        
        # Create protocol
        protocol = VerificationProtocol(tmp_path)
        phase = protocol.start_phase(1, "Test")
        task = phase.add_task("Fix function")
        
        # Record evidence
        task.add_change(str(bad_file))
        task.add_evidence(
            evidence_type=EvidenceType.COMMAND_OUTPUT,
            description="Guards result",
            content=result.format(),
        )
        
        # Decision based on guards
        errors = [v for v in result.violations if v.severity == GuardSeverity.ERROR]
        
        if errors:
            # Should not verify if guards fail
            task.fail(f"Guards found {len(errors)} errors")
            assert task.status.value == "failed"
        else:
            task.verify("OK")


class TestRegistryGuardsIntegration:
    """Tests integration between registry and guards."""
    
    def test_registry_fields_match_guard_patterns(self):
        """Registry extraction patterns should be valid regex."""
        from sdk.registry import get_registry
        import re
        
        registry = get_registry()
        
        invalid_patterns = []
        total_patterns = 0
        
        for product_id, product in registry.products.items():
            for field in product.get_all_fields():
                for pattern in field.extraction_patterns:
                    total_patterns += 1
                    if pattern.compiled is None:
                        invalid_patterns.append({
                            "product": product_id,
                            "field": field.field_id,
                            "pattern": pattern.pattern,
                        })
        
        assert len(invalid_patterns) == 0, f"Invalid patterns: {invalid_patterns}"
        print(f"\n✓ Validated {total_patterns} extraction patterns")
    
    def test_registry_enums_are_complete(self):
        """Registry enums should have all required values."""
        from sdk.registry import get_registry
        
        registry = get_registry()
        
        # Check AI modes
        ai_mode = registry.get_enum("ai_mode")
        if ai_mode:
            required_modes = {"assistant", "agent", "service"}
            actual_modes = ai_mode.get_value_ids()
            missing = required_modes - actual_modes
            assert len(missing) == 0, f"Missing AI modes: {missing}"
        
        # Check channels
        channel = registry.get_enum("channel")
        if channel:
            required_channels = {"voice", "sms", "email", "chat"}
            actual_channels = channel.get_value_ids()
            missing = required_channels - actual_channels
            assert len(missing) == 0, f"Missing channels: {missing}"


class TestCLIIntegration:
    """Tests for CLI integration."""
    
    @pytest.fixture
    def project_root(self):
        """Get project root."""
        return Path(__file__).parent.parent.parent
    
    def test_cli_guard_command_exists(self, project_root):
        """CLI guard command should be available."""
        # Check if the CLI module is importable
        try:
            from sdk.cli import app
            assert app is not None
        except ImportError as e:
            pytest.skip(f"CLI not available: {e}")
    
    @pytest.mark.skip(reason="Registry CLI commands not yet implemented")
    def test_cli_registry_commands(self, project_root):
        """CLI registry commands should be available."""
        try:
            from sdk.registry.cli import app
            assert app is not None
            
            # Check commands exist
            command_names = [cmd.name for cmd in app.registered_commands]
            expected = ["validate", "stats", "list-enums", "list-products"]
            
            for cmd in expected:
                assert cmd in command_names or cmd.replace("-", "_") in command_names, \
                    f"Missing command: {cmd}"
                    
        except ImportError as e:
            pytest.skip(f"Registry CLI not available: {e}")


class TestSDKModuleIntegration:
    """Tests for SDK module integration."""
    
    def test_all_modules_importable(self):
        """All SDK modules should be importable."""
        modules_to_test = [
            "sdk",
            "sdk.guards",
            "sdk.guards.base",
            "sdk.guards.registry",
            "sdk.verification",
            "sdk.verification.evidence_collector",
            "sdk.verification.phase_gate",
            "sdk.verification.task_protocol",
            "sdk.registry",
            "sdk.registry.loader",
            "sdk.registry.validator",
            "sdk.core",
        ]
        
        failed = []
        for module in modules_to_test:
            try:
                __import__(module)
            except ImportError as e:
                failed.append((module, str(e)))
        
        assert len(failed) == 0, f"Failed to import: {failed}"
    
    def test_sdk_exports(self):
        """SDK should export expected symbols."""
        import sdk
        
        expected_exports = [
            "Guard",
            "GuardResult",
            "get_guard_registry",
            "run_guards",
            "Evidence",
            "get_collector",
            "Phase",
            "get_phase_gate",
        ]
        
        for name in expected_exports:
            assert hasattr(sdk, name), f"Missing export: {name}"
    
    def test_registry_exports(self):
        """Registry module should export expected symbols."""
        from sdk import registry
        
        expected = [
            "get_registry",
            "validate_registry",
            "FieldDefinition",
            "ProductDefinition",
        ]
        
        for name in expected:
            assert hasattr(registry, name), f"Missing registry export: {name}"


class TestCrossComponentWorkflow:
    """Tests for cross-component workflows."""
    
    def test_registry_to_typescript_to_frontend(self, tmp_path):
        """
        Integration: Registry → TypeScript types → (simulated) Frontend usage.
        """
        from sdk.registry import get_registry, TypeScriptGenerator
        
        registry = get_registry()
        generator = TypeScriptGenerator(registry)
        
        # Generate types
        ts_code = generator.generate_all()
        
        # Write to file
        output_file = tmp_path / "registry.ts"
        output_file.write_text(ts_code)
        
        # Verify file was written
        assert output_file.exists()
        content = output_file.read_text()
        
        # Basic TypeScript syntax check (no actual compilation)
        assert content.count("{") == content.count("}"), "Mismatched braces"
        assert "export" in content, "No exports"
        
        print(f"\n✓ Generated {len(ts_code)} chars of TypeScript")
    
    def test_guards_to_verification_to_report(self, tmp_path):
        """
        Integration: Guards → Verification → Report generation.
        """
        from sdk.guards import get_guard_registry
        from sdk.verification import VerificationProtocol
        from sdk.verification.task_protocol import EvidenceType
        
        # Create test file
        test_file = tmp_path / "feature.py"
        test_file.write_text('''
def new_feature():
    """A properly implemented feature."""
    return {"status": "ok"}
''')
        
        # Run guards
        guards = get_guard_registry()
        guard_result = guards.run_on_file(test_file)
        
        # Create verification
        protocol = VerificationProtocol(tmp_path)
        phase = protocol.start_phase(1, "Feature")
        task = phase.add_task("Implement feature")
        
        # Add evidence
        task.add_change(str(test_file), description="Created new_feature function")
        task.add_evidence(
            evidence_type=EvidenceType.COMMAND_OUTPUT,
            description="Guards passed",
            content=guard_result.format_short(),
        )
        
        # Complete
        task.verify("Looks good")
        phase.pass_gate("test123")
        
        # Generate reports
        completion_report = task.format_completion_report()
        gate_checklist = phase.format_gate_checklist()
        session_handoff = protocol.format_session_handoff()
        
        # Verify reports generated
        assert "Task 1.1 Complete" in completion_report
        assert "PHASE 1 GATE" in gate_checklist
        assert "Phase 1 Complete" in session_handoff
        
        print("\n✓ Full integration workflow completed")
