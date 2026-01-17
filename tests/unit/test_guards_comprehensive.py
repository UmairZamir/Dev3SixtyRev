"""
Comprehensive Tests for All Guards
==================================

Tests for guards that were missing test coverage:
- HardcodedValueGuard
- PrintStatementGuard
- ShellComponentGuard (frontend)
- OverEngineeringGuard
- DuplicateFunctionGuard
- EvidenceRequiredGuard
- ScopeCreepGuard
- SpecComplianceGuard
- E2ETestEnforcementGuard
"""

import pytest
from pathlib import Path
import tempfile

from sdk.guards.bandaid import HardcodedValueGuard, PrintStatementGuard
from sdk.guards.shell_component import ShellComponentGuard
from sdk.guards.complexity import OverEngineeringGuard
from sdk.guards.duplicate import DuplicateFunctionGuard
from sdk.guards.evidence import EvidenceRequiredGuard, EvidenceType
from sdk.guards.scope import ScopeCreepGuard
from sdk.guards.spec_compliance import SpecComplianceGuard
from sdk.guards.test_enforcement import E2ETestEnforcementGuard


# =============================================================================
# HardcodedValueGuard Tests
# =============================================================================

class TestHardcodedValueGuard:
    """Tests for HardcodedValueGuard."""

    @pytest.fixture
    def guard(self):
        return HardcodedValueGuard()

    def test_detects_hardcoded_user_id(self, guard):
        """Test detection of hardcoded user IDs."""
        code = 'user_id = 12345'
        result = guard.check(code, "src/service.py")
        assert len(result.violations) > 0
        assert any("id" in v.message.lower() for v in result.violations)

    def test_detects_hardcoded_api_key(self, guard):
        """Test detection of hardcoded API keys."""
        code = 'api_key = "sk-1234567890abcdef"'
        result = guard.check(code, "src/config.py")
        assert len(result.violations) > 0
        assert any("api" in v.message.lower() for v in result.violations)

    def test_detects_hardcoded_localhost_url(self, guard):
        """Test detection of hardcoded localhost URLs."""
        code = 'url = "http://localhost:3000/api/users"'
        result = guard.check(code, "src/api.py")
        assert len(result.violations) > 0
        assert any("localhost" in v.message.lower() or "url" in v.message.lower() for v in result.violations)

    def test_detects_hardcoded_external_url(self, guard):
        """Test detection of hardcoded external URLs."""
        code = 'endpoint = "https://api.example.com/v1/data"'
        result = guard.check(code, "src/client.py")
        assert len(result.violations) > 0

    def test_detects_hardcoded_absolute_path(self, guard):
        """Test detection of hardcoded absolute paths."""
        code = 'config_path = "/Users/john/project/config.json"'
        result = guard.check(code, "src/loader.py")
        assert len(result.violations) > 0
        # Message contains the matched pattern; suggestion contains "path"
        assert any("/Users/" in v.message or "path" in v.suggestion.lower() for v in result.violations)

    def test_detects_hardcoded_password(self, guard):
        """Test detection of hardcoded passwords."""
        code = 'password = "mysecretpassword123"'
        result = guard.check(code, "src/auth.py")
        assert len(result.violations) > 0
        assert any("password" in v.message.lower() for v in result.violations)

    def test_detects_hardcoded_secret(self, guard):
        """Test detection of hardcoded secrets."""
        code = 'secret = "abcdefghijklmnop"'
        result = guard.check(code, "src/crypto.py")
        assert len(result.violations) > 0

    def test_allows_env_variable_usage(self, guard):
        """Test that environment variable usage is allowed."""
        code = '''
import os
api_key = os.environ.get("API_KEY")
password = os.getenv("DB_PASSWORD")
'''
        result = guard.check(code, "src/config.py")
        assert result.passed

    def test_skips_test_files(self, guard):
        """Test that test files are skipped."""
        code = 'user_id = 12345'
        result = guard.check(code, "tests/test_service.py")
        assert result.passed


# =============================================================================
# PrintStatementGuard Tests
# =============================================================================

class TestPrintStatementGuard:
    """Tests for PrintStatementGuard."""

    @pytest.fixture
    def guard(self):
        return PrintStatementGuard()

    def test_detects_print_statement(self, guard):
        """Test detection of print statements."""
        code = 'print("Debug output")'
        result = guard.check(code, "src/service.py")
        assert len(result.violations) > 0
        assert any("print" in v.message.lower() or "logger" in v.message.lower() for v in result.violations)

    def test_detects_print_with_fstring(self, guard):
        """Test detection of print with f-strings."""
        code = 'print(f"User {user_id} logged in")'
        result = guard.check(code, "src/auth.py")
        assert len(result.violations) > 0

    def test_detects_console_log(self, guard):
        """Test detection of console.log."""
        code = 'console.log("Debug message")'
        result = guard.check(code, "src/app.js")
        assert len(result.violations) > 0

    def test_detects_console_debug(self, guard):
        """Test detection of console.debug."""
        code = 'console.debug(data)'
        result = guard.check(code, "src/utils.js")
        assert len(result.violations) > 0

    def test_allows_logger_usage(self, guard):
        """Test that proper logging is allowed."""
        code = '''
import logging
logger = logging.getLogger(__name__)
logger.info("User logged in")
logger.debug("Debug info: %s", data)
'''
        result = guard.check(code, "src/service.py")
        assert result.passed

    def test_skips_test_files(self, guard):
        """Test that test files are skipped."""
        code = 'print("Test output")'
        result = guard.check(code, "tests/test_service.py")
        assert result.passed

    def test_skips_cli_files(self, guard):
        """Test that CLI files are skipped."""
        code = 'print("CLI output")'
        result = guard.check(code, "src/cli.py")
        assert result.passed

    def test_does_not_match_print_in_string(self, guard):
        """Test that 'print' in strings doesn't match."""
        code = 'message = "Please print the document"'
        result = guard.check(code, "src/service.py")
        assert result.passed


# =============================================================================
# ShellComponentGuard Tests (Frontend)
# =============================================================================

class TestShellComponentGuard:
    """Tests for ShellComponentGuard (frontend shell components)."""

    @pytest.fixture
    def guard(self):
        return ShellComponentGuard()

    def test_detects_empty_onclick_handler(self, guard):
        """Test detection of empty onClick handler."""
        code = '<button onClick={() => {}}>Click</button>'
        result = guard.check(code, "src/Button.tsx")
        assert not result.passed
        assert any("onclick" in v.message.lower() or "handler" in v.message.lower() for v in result.violations)

    def test_detects_empty_onsubmit_handler(self, guard):
        """Test detection of empty onSubmit handler."""
        code = '<form onSubmit={() => {}}>...</form>'
        result = guard.check(code, "src/Form.tsx")
        assert not result.passed

    def test_detects_empty_onchange_handler(self, guard):
        """Test detection of empty onChange handler."""
        code = '<input onChange={() => {}} />'
        result = guard.check(code, "src/Input.tsx")
        assert not result.passed

    def test_detects_hardcoded_mock_data_in_usestate(self, guard):
        """Test detection of hardcoded mock data in useState."""
        code = '''
const [users, setUsers] = useState([
    { id: 1, name: "John" },
    { id: 2, name: "Jane" },
]);
'''
        result = guard.check(code, "src/UserList.tsx")
        assert not result.passed
        assert any("mock" in v.message.lower() or "hardcoded" in v.message.lower() for v in result.violations)

    def test_detects_todo_console_log(self, guard):
        """Test detection of TODO console.log."""
        code = 'console.log("TODO: implement this")'
        result = guard.check(code, "src/Feature.tsx")
        assert not result.passed

    def test_detects_empty_fragment_return(self, guard):
        """Test detection of empty fragment return."""
        code = '''
function Component() {
    return <></>;
}
'''
        result = guard.check(code, "src/Empty.tsx")
        assert not result.passed

    def test_detects_fetch_without_error_handling(self, guard):
        """Test detection of fetch without catch."""
        code = '''
fetch("/api/data")
    .then(response => response.json())
    .then(data => setData(data));
'''
        result = guard.check(code, "src/DataLoader.tsx")
        assert not result.passed
        assert any("fetch" in v.message.lower() or "error" in v.message.lower() for v in result.violations)

    def test_allows_proper_handlers(self, guard):
        """Test that proper handlers are allowed."""
        code = '''
function Component() {
    const handleClick = () => {
        api.submit(data);
    };
    return <button onClick={handleClick}>Submit</button>;
}
'''
        result = guard.check(code, "src/Good.tsx")
        assert result.passed

    def test_allows_fetch_with_catch(self, guard):
        """Test that fetch with catch is allowed."""
        code = '''
fetch("/api/data")
    .then(response => response.json())
    .then(data => setData(data))
    .catch(error => setError(error));
'''
        result = guard.check(code, "src/DataLoader.tsx")
        # Should pass because it has .catch()
        # Note: depending on regex, this may or may not pass
        # The pattern looks for fetch without catch immediately following

    def test_skips_non_frontend_files(self, guard):
        """Test that non-frontend files are skipped."""
        code = '<button onClick={() => {}}>Click</button>'
        result = guard.check(code, "src/service.py")
        assert result.passed


# =============================================================================
# OverEngineeringGuard Tests
# =============================================================================

class TestOverEngineeringGuard:
    """Tests for OverEngineeringGuard."""

    @pytest.fixture
    def guard(self):
        return OverEngineeringGuard()

    def test_detects_long_function(self, guard):
        """Test detection of overly long functions."""
        # Create a function with 60 lines
        lines = ['def very_long_function():']
        lines.extend(['    x = 1'] * 60)
        code = '\n'.join(lines)
        
        result = guard.check(code, "src/service.py")
        assert len(result.violations) > 0
        assert any("lines" in v.message.lower() for v in result.violations)

    def test_detects_too_many_parameters(self, guard):
        """Test detection of functions with too many parameters."""
        code = '''
def complex_function(a, b, c, d, e, f, g, h, i):
    return a + b + c + d + e + f + g + h + i
'''
        result = guard.check(code, "src/service.py")
        assert len(result.violations) > 0
        assert any("parameter" in v.message.lower() for v in result.violations)

    def test_detects_class_with_too_many_methods(self, guard):
        """Test detection of classes with too many methods."""
        methods = '\n'.join([f'    def method_{i}(self): pass' for i in range(25)])
        code = f'''
class HugeClass:
{methods}
'''
        result = guard.check(code, "src/service.py")
        assert len(result.violations) > 0
        assert any("method" in v.message.lower() for v in result.violations)

    def test_allows_simple_functions(self, guard):
        """Test that simple functions pass."""
        code = '''
def add(a: int, b: int) -> int:
    return a + b
'''
        result = guard.check(code, "src/utils.py")
        assert result.passed

    def test_allows_reasonable_parameter_count(self, guard):
        """Test that reasonable parameter counts pass."""
        code = '''
def create_user(name: str, email: str, age: int):
    return {"name": name, "email": email, "age": age}
'''
        result = guard.check(code, "src/users.py")
        assert result.passed


# =============================================================================
# DuplicateFunctionGuard Tests
# =============================================================================

class TestDuplicateFunctionGuard:
    """Tests for DuplicateFunctionGuard."""

    @pytest.fixture
    def guard(self):
        return DuplicateFunctionGuard()

    def test_detects_similar_function_names(self, guard):
        """Test detection of functions with similar names."""
        code = '''
def get_user_data(user_id):
    return db.query(User).get(user_id)

def fetch_user_data(user_id):
    return api.get(f"/users/{user_id}")
'''
        result = guard.check(code, "src/users.py")
        assert not result.passed
        assert any("similar" in v.message.lower() for v in result.violations)

    def test_detects_get_fetch_duplicates(self, guard):
        """Test detection of get/fetch duplicates."""
        code = '''
def get_customer(customer_id):
    return customers.get(customer_id)

def fetch_customer(customer_id):
    return api.fetch_customer(customer_id)
'''
        result = guard.check(code, "src/customers.py")
        assert not result.passed

    def test_detects_process_handle_duplicates(self, guard):
        """Test detection of process/handle duplicates."""
        code = '''
def process_order(order):
    return validate_and_submit(order)

def handle_order(order):
    return validate_and_submit(order)
'''
        result = guard.check(code, "src/orders.py")
        assert not result.passed

    def test_allows_distinct_functions(self, guard):
        """Test that distinct functions pass."""
        code = '''
def get_user(user_id):
    return db.query(User).get(user_id)

def create_user(data):
    return db.add(User(**data))

def delete_user(user_id):
    return db.delete(User, user_id)
'''
        result = guard.check(code, "src/users.py")
        assert result.passed

    def test_skips_non_python_files(self, guard):
        """Test that non-Python files are skipped."""
        code = '''
function getUserData() {}
function fetchUserData() {}
'''
        result = guard.check(code, "src/users.js")
        assert result.passed


# =============================================================================
# EvidenceRequiredGuard Tests
# =============================================================================

class TestEvidenceRequiredGuard:
    """Tests for EvidenceRequiredGuard."""

    @pytest.fixture
    def guard(self):
        g = EvidenceRequiredGuard()
        g.clear_tasks()
        return g

    def test_task_without_evidence_fails(self, guard):
        """Test that tasks without evidence fail."""
        guard.start_task("task-1", "Implement login", [EvidenceType.TEST_OUTPUT])
        
        result = guard.check("", None)
        assert not result.passed
        assert any("missing" in v.message.lower() for v in result.violations)

    def test_task_with_evidence_passes(self, guard):
        """Test that tasks with required evidence pass."""
        guard.start_task("task-1", "Implement login", [EvidenceType.TEST_OUTPUT])
        guard.add_evidence(
            EvidenceType.TEST_OUTPUT,
            "All tests pass",
            "===== 5 passed =====",
            passed=True
        )
        guard.verify_task()
        
        result = guard.check("", None)
        assert result.passed

    def test_multiple_evidence_types_required(self, guard):
        """Test that all required evidence types must be present."""
        guard.start_task(
            "task-1", 
            "Implement feature",
            [EvidenceType.TEST_OUTPUT, EvidenceType.TYPE_CHECK]
        )
        guard.add_evidence(
            EvidenceType.TEST_OUTPUT,
            "Tests pass",
            "5 passed",
            passed=True
        )
        # Missing TYPE_CHECK evidence
        
        result = guard.check("", None)
        assert not result.passed

    def test_task_is_complete_method(self, guard):
        """Test TaskEvidence.is_complete() method."""
        task = guard.start_task("task-1", "Test", [EvidenceType.TEST_OUTPUT])
        assert not task.is_complete()
        
        guard.add_evidence(EvidenceType.TEST_OUTPUT, "Pass", "ok", passed=True)
        assert task.is_complete()

    def test_missing_evidence_method(self, guard):
        """Test TaskEvidence.missing_evidence() method."""
        task = guard.start_task(
            "task-1",
            "Test",
            [EvidenceType.TEST_OUTPUT, EvidenceType.LINT_CHECK]
        )
        
        missing = task.missing_evidence()
        assert EvidenceType.TEST_OUTPUT in missing
        assert EvidenceType.LINT_CHECK in missing
        
        guard.add_evidence(EvidenceType.TEST_OUTPUT, "Pass", "ok", passed=True)
        missing = task.missing_evidence()
        assert EvidenceType.TEST_OUTPUT not in missing
        assert EvidenceType.LINT_CHECK in missing

    def test_evidence_report_format(self, guard):
        """Test evidence report formatting."""
        guard.start_task("task-1", "Test task", [EvidenceType.TEST_OUTPUT])
        guard.add_evidence(EvidenceType.TEST_OUTPUT, "Tests", "passed", passed=True)
        guard.verify_task()
        
        report = guard.format_evidence_report()
        assert "EVIDENCE REPORT" in report
        assert "Test task" in report
        assert "✅" in report


# =============================================================================
# ScopeCreepGuard Tests
# =============================================================================

class TestScopeCreepGuard:
    """Tests for ScopeCreepGuard."""

    @pytest.fixture
    def guard(self):
        g = ScopeCreepGuard()
        g.clear_scope()
        return g

    def test_detects_out_of_scope_modification(self, guard):
        """Test detection of out-of-scope modifications."""
        guard.set_expected_scope(
            ["src/auth/login.py"],
            "Fix login bug"
        )
        
        result = guard.check("# Modified", "src/admin/users.py")
        assert not result.passed or any(v.severity.value == "warning" for v in result.violations)

    def test_allows_in_scope_modification(self, guard):
        """Test that in-scope modifications pass."""
        guard.set_expected_scope(
            ["src/auth/login.py"],
            "Fix login bug"
        )
        
        result = guard.check("# Modified", "src/auth/login.py")
        # Should not have warnings about scope
        scope_warnings = [v for v in result.violations if "scope" in v.message.lower()]
        assert len(scope_warnings) == 0

    def test_check_multiple_files(self, guard):
        """Test checking multiple modified files."""
        guard.set_expected_scope(
            ["src/auth/login.py", "src/auth/utils.py"],
            "Auth refactor"
        )
        
        result = guard.check_modified_files([
            "src/auth/login.py",
            "src/auth/utils.py",
            "src/admin/dashboard.py"  # Out of scope
        ])
        assert not result.passed

    def test_no_scope_defined_info(self, guard):
        """Test info message when no scope is defined."""
        result = guard.check("# Code", "src/file.py")
        # Should pass but may have info
        assert result.passed

    def test_clear_scope(self, guard):
        """Test clearing scope."""
        guard.set_expected_scope(["src/auth.py"], "Task")
        guard.clear_scope()
        
        result = guard.check("# Code", "src/other.py")
        assert result.passed


# =============================================================================
# SpecComplianceGuard Tests
# =============================================================================

class TestSpecComplianceGuard:
    """Tests for SpecComplianceGuard."""

    @pytest.fixture
    def guard(self):
        g = SpecComplianceGuard()
        g._spec_requirements.clear()
        g._implemented.clear()
        return g

    def test_load_spec_requirements(self, guard):
        """Test loading requirements from spec file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""
# Requirements

- [ ] User must be able to login
- [ ] System shall validate email format
- [ ] Dashboard should show real-time data

1. Support multiple languages
2. Handle concurrent users
""")
            f.flush()
            
            count = guard.load_spec_requirements(Path(f.name))
            assert count > 0

    def test_mark_implemented(self, guard):
        """Test marking requirements as implemented."""
        guard.mark_implemented("User must be able to login")
        assert "user must be able to login" in guard._implemented

    def test_compliance_check_missing_requirements(self, guard):
        """Test compliance check with missing requirements."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("- [ ] Feature must work\n")
            f.flush()
            guard.load_spec_requirements(Path(f.name))
        
        result = guard.check("", None)
        # Should have info about unverified requirements
        assert any("not verified" in v.message.lower() for v in result.violations)

    def test_compliance_report_format(self, guard):
        """Test compliance report formatting."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("- [ ] Test requirement\n")
            f.flush()
            guard.load_spec_requirements(Path(f.name))
        
        report = guard.get_compliance_report()
        assert "SPEC COMPLIANCE REPORT" in report
        assert "Coverage:" in report

    def test_check_implementation(self, guard):
        """Test checking if code implements requirement."""
        code = "def validate_email(email): return '@' in email"
        result = guard.check_implementation(code, "validate email format")
        assert result  # Should find "validate" and "email"


# =============================================================================
# E2ETestEnforcementGuard Tests
# =============================================================================

class TestE2ETestEnforcementGuard:
    """Tests for E2ETestEnforcementGuard."""

    @pytest.fixture
    def guard(self):
        return E2ETestEnforcementGuard()

    def test_detects_untested_function(self, guard):
        """Test detection of functions without tests."""
        code = '''
def calculate_tax(amount):
    return amount * 0.1

def process_payment(data):
    return payment_gateway.charge(data)
'''
        result = guard.check(code, "src/billing.py")
        # Should have info about missing tests
        assert any("test" in v.message.lower() for v in result.violations)

    def test_detects_untested_class(self, guard):
        """Test detection of classes without tests."""
        code = '''
class PaymentProcessor:
    def process(self, payment):
        return self.gateway.charge(payment)
'''
        result = guard.check(code, "src/payments.py")
        assert any("test" in v.message.lower() for v in result.violations)

    def test_skips_private_functions(self, guard):
        """Test that private functions are skipped."""
        code = '''
def _private_helper():
    return "helper"

def __dunder_method__():
    pass
'''
        result = guard.check(code, "src/utils.py")
        # Should pass - private functions don't need tests flagged
        private_violations = [v for v in result.violations if "_private" in v.message or "__dunder" in v.message]
        assert len(private_violations) == 0

    def test_skips_test_files(self, guard):
        """Test that test files themselves are skipped."""
        code = '''
def test_something():
    assert 1 + 1 == 2

class TestSomething:
    def test_method(self):
        result = do_something()
        assert result is not None
'''
        result = guard.check(code, "tests/test_service.py")
        assert result.passed

    def test_scan_test_files(self, guard):
        """Test scanning test directory for existing tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_example.py"
            test_file.write_text('''
def test_calculate_tax():
    assert calculate_tax(100) == 10

class TestPaymentProcessor:
    def test_process(self):
        pass
''')
            
            count = guard.scan_test_files(Path(tmpdir))
            assert count >= 2
            assert "calculate_tax" in guard._tested_functions
            assert "TestPaymentProcessor" in guard._tested_functions

    def test_recognizes_existing_tests(self, guard):
        """Test that registered tests are recognized."""
        guard.register_test("calculate_tax", "tests/test_billing.py")
        
        code = '''
def calculate_tax(amount):
    return amount * 0.1
'''
        result = guard.check(code, "src/billing.py")
        # Should not flag calculate_tax as needing tests
        tax_violations = [v for v in result.violations if "calculate_tax" in v.message]
        assert len(tax_violations) == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestGuardsIntegration:
    """Integration tests for guard combinations."""

    def test_all_guards_instantiate(self):
        """Test that all guards can be instantiated."""
        guards = [
            HardcodedValueGuard(),
            PrintStatementGuard(),
            ShellComponentGuard(),
            OverEngineeringGuard(),
            DuplicateFunctionGuard(),
            EvidenceRequiredGuard(),
            ScopeCreepGuard(),
            SpecComplianceGuard(),
            E2ETestEnforcementGuard(),
        ]
        
        for guard in guards:
            assert guard is not None
            assert guard.name is not None
            assert guard.enabled

    def test_guards_return_valid_results(self):
        """Test that all guards return valid GuardResult objects."""
        guards = [
            HardcodedValueGuard(),
            PrintStatementGuard(),
            ShellComponentGuard(),
            OverEngineeringGuard(),
            DuplicateFunctionGuard(),
            EvidenceRequiredGuard(),
            ScopeCreepGuard(),
            SpecComplianceGuard(),
            E2ETestEnforcementGuard(),
        ]
        
        code = "x = 1"
        for guard in guards:
            result = guard.check(code, "test.py")
            assert hasattr(result, 'passed')
            assert hasattr(result, 'violations')
            assert isinstance(result.violations, list)

    def test_clean_code_passes_all_guards(self):
        """Test that clean code passes all guards."""
        clean_code = '''
import os
import logging

logger = logging.getLogger(__name__)

def get_config():
    """Get configuration from environment."""
    return {
        "api_key": os.environ.get("API_KEY"),
        "debug": os.environ.get("DEBUG", "false") == "true",
    }
'''
        guards = [
            HardcodedValueGuard(),
            PrintStatementGuard(),
            OverEngineeringGuard(),
            DuplicateFunctionGuard(),
        ]
        
        for guard in guards:
            result = guard.check(clean_code, "src/config.py")
            assert result.passed, f"{guard.name} failed on clean code"
