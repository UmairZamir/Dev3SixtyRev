"""
Tests for E2E Guard - Shell Component Detection
"""

import pytest

from sdk.guards.e2e import E2EGuard
from sdk.guards.base import GuardSeverity


@pytest.fixture
def guard():
    return E2EGuard()


class TestE2EGuard:
    """Tests for shell component detection."""
    
    def test_detects_todo_console_log(self, guard):
        """Should detect console.log('TODO')."""
        code = '''
function handleClick() {
    console.log('TODO: implement this');
}
'''
        result = guard.check(code, "component.tsx")
        assert not result.passed
        assert any("TODO" in v.message for v in result.violations)
    
    def test_detects_empty_onclick(self, guard):
        """Should detect empty onClick handlers."""
        code = '''
<button onClick={() => {}}>Click me</button>
'''
        result = guard.check(code, "component.tsx")
        assert any("Empty onClick" in v.message for v in result.violations)
    
    def test_detects_placeholder_data(self, guard):
        """Should detect placeholder/mock data."""
        # The guard patterns look for 'placeholder', 'dummy', 'mock' after array/object start
        code = '''
const data = [{ placeholder: true, id: 1 }];
const items = [{ dummy: "test" }];
'''
        result = guard.check(code, "component.tsx")
        # Should have warnings about placeholder data
        assert any("placeholder" in v.message.lower() or "dummy" in v.message.lower() 
                   for v in result.violations)
    
    def test_detects_todo_connect_api(self, guard):
        """Should detect TODO comments about API connection."""
        code = '''
function fetchData() {
    // TODO: connect to real API
    return mockData;
}
'''
        result = guard.check(code, "component.tsx")
        assert not result.passed
        assert any("API" in v.message for v in result.violations)
    
    def test_detects_fake_fetch_url(self, guard):
        """Should detect fake fetch URLs."""
        code = '''
fetch('#fake-endpoint')
    .then(r => r.json());
'''
        result = guard.check(code, "component.tsx")
        assert not result.passed
        assert any("Fake fetch" in v.message for v in result.violations)
    
    def test_detects_python_placeholder(self, guard):
        """Should detect Python placeholder implementations."""
        code = '''
def handle_request():
    pass  # TODO implement
'''
        result = guard.check(code, "handler.py")
        assert not result.passed
        assert any("TODO" in v.message for v in result.violations)
    
    def test_detects_not_implemented_error(self, guard):
        """Should detect NotImplementedError."""
        code = '''
def process_data():
    raise NotImplementedError()
'''
        result = guard.check(code, "processor.py")
        assert not result.passed
        assert any("NotImplementedError" in v.message for v in result.violations)
    
    def test_allows_real_implementation(self, guard):
        """Should allow properly implemented components."""
        code = '''
function handleClick() {
    api.submitForm(formData)
        .then(response => {
            setResult(response.data);
        })
        .catch(error => {
            setError(error.message);
        });
}
'''
        result = guard.check(code, "component.tsx")
        # Should not have ERROR severity violations
        errors = [v for v in result.violations if v.severity == GuardSeverity.ERROR]
        assert len(errors) == 0
    
    def test_skips_test_files(self, guard):
        """Should skip test files."""
        code = '''
const mockData = [{ id: 1, placeholder: true }];
console.log('TODO: this is a test');
'''
        result = guard.check(code, "component.test.tsx")
        assert result.passed
    
    def test_skips_mock_directories(self, guard):
        """Should skip mock directories."""
        code = '''
const mockData = [{ id: 1, mock: true }];
'''
        result = guard.check(code, "__mocks__/api.ts")
        assert result.passed
    
    def test_skips_non_code_files(self, guard):
        """Should skip non-code files."""
        code = "Some markdown with TODO items"
        result = guard.check(code, "README.md")
        assert result.passed


class TestFormDetection:
    """Tests for form submission detection."""
    
    @pytest.fixture
    def guard(self):
        return E2EGuard()
    
    def test_detects_form_without_action(self, guard):
        """Should warn about forms without action or onSubmit."""
        code = '''
<form>
    <input type="text" />
    <button type="submit">Submit</button>
</form>
'''
        result = guard.check(code, "form.tsx")
        assert any("Form without action" in v.message for v in result.violations)
    
    def test_allows_form_with_onsubmit(self, guard):
        """Should allow forms with onSubmit."""
        code = '''
<form onSubmit={handleSubmit}>
    <input type="text" />
    <button type="submit">Submit</button>
</form>
'''
        result = guard.check(code, "form.tsx")
        # Should not complain about missing action
        assert not any(
            v.severity == GuardSeverity.ERROR and "Form without action" in v.message 
            for v in result.violations
        )


class TestHardcodedDataDetection:
    """Tests for hardcoded data detection."""
    
    @pytest.fixture
    def guard(self):
        return E2EGuard()
    
    def test_warns_about_hardcoded_chart_data(self, guard):
        """Should warn about hardcoded chart data."""
        code = '''
const chartData = {
    data: [10, 20, 30, 40],
    labels: ['Jan', 'Feb', 'Mar', 'Apr'],
};
'''
        result = guard.check(code, "chart.tsx")
        # Should have warnings about hardcoded data
        warnings = [v for v in result.violations if v.severity == GuardSeverity.WARNING]
        assert len(warnings) > 0
    
    def test_allows_config_files(self, guard):
        """Should not warn about config files."""
        code = '''
const config = {
    data: [10, 20, 30, 40],
    labels: ['Jan', 'Feb', 'Mar', 'Apr'],
};
'''
        result = guard.check(code, "chart.config.ts")
        # Should pass for config files
        assert result.passed
