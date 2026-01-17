#!/usr/bin/env python3
"""
Quick verification script for SDK tests.
Run this from the Dev3SixtyRev directory to verify imports work correctly.
"""

import sys
from pathlib import Path

# Ensure we're importing from the local SDK
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def verify_imports():
    """Verify all SDK imports work correctly."""
    print("=" * 60)
    print("SDK Import Verification")
    print("=" * 60)
    print()
    
    errors = []
    success = []
    
    # Test base guard imports
    try:
        from sdk.guards.base import (
            Guard, GuardCategory, GuardLevel, GuardResult,
            GuardSeverity, GuardViolation, PatternGuard
        )
        success.append("✅ sdk.guards.base")
    except Exception as e:
        errors.append(f"❌ sdk.guards.base: {e}")
    
    # Test E2E guard
    try:
        from sdk.guards.e2e import E2EGuard
        guard = E2EGuard()
        assert guard.name == "e2e"
        success.append("✅ sdk.guards.e2e.E2EGuard")
    except Exception as e:
        errors.append(f"❌ sdk.guards.e2e: {e}")
    
    # Test bandaid guards
    try:
        from sdk.guards.bandaid import BandaidPatternsGuard, HardcodedValueGuard
        guard = BandaidPatternsGuard()
        success.append("✅ sdk.guards.bandaid")
    except Exception as e:
        errors.append(f"❌ sdk.guards.bandaid: {e}")
    
    # Test shell component guards
    try:
        from sdk.guards.shell_component import PythonShellGuard, ShellComponentGuard
        guard = PythonShellGuard()
        success.append("✅ sdk.guards.shell_component")
    except Exception as e:
        errors.append(f"❌ sdk.guards.shell_component: {e}")
    
    # Test security guard
    try:
        from sdk.guards.security import SecurityGuard
        guard = SecurityGuard()
        success.append("✅ sdk.guards.security")
    except Exception as e:
        errors.append(f"❌ sdk.guards.security: {e}")
    
    # Test hallucination guard
    try:
        from sdk.guards.hallucination import HallucinationGuard
        guard = HallucinationGuard()
        success.append("✅ sdk.guards.hallucination")
    except Exception as e:
        errors.append(f"❌ sdk.guards.hallucination: {e}")
    
    # Test context loss guard
    try:
        from sdk.guards.context_loss import ContextLossGuard
        guard = ContextLossGuard()
        success.append("✅ sdk.guards.context_loss")
    except Exception as e:
        errors.append(f"❌ sdk.guards.context_loss: {e}")
    
    # Test registry module
    try:
        from sdk.registry import (
            Registry, get_registry, validate_registry,
            ExtractionTester, TypeScriptGenerator
        )
        success.append("✅ sdk.registry")
    except Exception as e:
        errors.append(f"❌ sdk.registry: {e}")
    
    # Test telemetry module
    try:
        from sdk.telemetry import (
            ViolationRecord, MetricRecord, TelemetryEvent,
            QualitySnapshot, SQLiteTelemetryStore, TelemetryAnalytics
        )
        success.append("✅ sdk.telemetry")
    except Exception as e:
        errors.append(f"❌ sdk.telemetry: {e}")
    
    # Test verification module
    try:
        from sdk.verification import (
            Evidence, EvidenceCollector, EvidenceType,
            Phase, PhaseGate, get_phase_gate
        )
        success.append("✅ sdk.verification (phase_gate)")
    except Exception as e:
        errors.append(f"❌ sdk.verification: {e}")
    
    # Test task protocol
    try:
        from sdk.verification.task_protocol import (
            TaskStatus, VerifiableTask, VerificationProtocol,
            get_verification_protocol, reset_verification_protocol
        )
        # Also test Phase from task_protocol (it's a dataclass, not enum)
        from sdk.verification.task_protocol import Phase as TaskPhase
        success.append("✅ sdk.verification.task_protocol")
    except Exception as e:
        errors.append(f"❌ sdk.verification.task_protocol: {e}")
    
    # Test guard registry
    try:
        from sdk.guards.registry import (
            GuardRegistry, AggregatedResult, get_guard_registry
        )
        success.append("✅ sdk.guards.registry")
    except Exception as e:
        errors.append(f"❌ sdk.guards.registry: {e}")
    
    # Print results
    print("Successful imports:")
    for s in success:
        print(f"  {s}")
    
    if errors:
        print()
        print("Failed imports:")
        for e in errors:
            print(f"  {e}")
    
    print()
    print("=" * 60)
    if errors:
        print(f"❌ {len(errors)} import(s) failed, {len(success)} succeeded")
        return False
    else:
        print(f"✅ All {len(success)} imports successful!")
        return True


def test_e2e_guard():
    """Quick functional test of E2E guard."""
    print()
    print("=" * 60)
    print("E2E Guard Quick Test")
    print("=" * 60)
    print()
    
    try:
        from sdk.guards.e2e import E2EGuard
    except ImportError as e:
        print(f"❌ Cannot import E2EGuard: {e}")
        return False
    
    guard = E2EGuard()
    
    # Test with shell code
    shell_code = """
function handleClick() {
    console.log('TODO: implement this');
}
"""
    result = guard.check(shell_code, "component.tsx")
    
    if not result.passed:
        print("✅ Correctly detected shell component")
        print(f"   Violations: {len(result.violations)}")
        for v in result.violations:
            print(f"   - {v.message}")
    else:
        print("❌ Failed to detect shell component")
        return False
    
    # Test with clean code
    clean_code = """
function handleClick() {
    api.submitForm(formData);
}
"""
    result = guard.check(clean_code, "component.tsx")
    
    if result.passed:
        print("✅ Correctly passed clean code")
    else:
        print(f"❌ Incorrectly flagged clean code: {[v.message for v in result.violations]}")
        return False
    
    return True


if __name__ == "__main__":
    print(f"Python path: {sys.path[0]}")
    print(f"Project root: {project_root}")
    print()
    
    imports_ok = verify_imports()
    
    if imports_ok:
        test_ok = test_e2e_guard()
    else:
        print("\n⚠️  Skipping functional tests due to import failures")
        test_ok = False
    
    print()
    if imports_ok and test_ok:
        print("🎉 All checks passed! You can now run: pytest tests/unit/ -v")
        sys.exit(0)
    else:
        print("⚠️  Some checks failed. Review the errors above.")
        sys.exit(1)
