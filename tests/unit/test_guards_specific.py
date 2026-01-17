"""Tests for specific guards."""

import pytest
from sdk.guards.bandaid import BandaidPatternsGuard, HardcodedValueGuard
from sdk.guards.shell_component import PythonShellGuard
from sdk.guards.security import SecurityGuard
from sdk.guards.hallucination import HallucinationGuard
from sdk.guards.context_loss import ContextLossGuard


class TestBandaidPatternsGuard:
    """Tests for BandaidPatternsGuard."""

    @pytest.fixture
    def guard(self):
        return BandaidPatternsGuard()

    def test_detects_type_ignore(self, guard):
        """Test detection of type: ignore."""
        code = "x: int = 'hello'  # type: ignore"
        result = guard.check(code)
        assert not result.passed
        assert any("type" in v.message.lower() for v in result.violations)

    def test_detects_noqa(self, guard):
        """Test detection of noqa."""
        code = "import *  # noqa"
        result = guard.check(code)
        assert not result.passed

    def test_detects_bare_except(self, guard):
        """Test detection of bare except."""
        code = """
try:
    foo()
except: pass
"""
        result = guard.check(code)
        assert not result.passed

    def test_detects_todo(self, guard):
        """Test detection of TODO patterns."""
        code = "# TODO: fix this later"
        result = guard.check(code)
        assert not result.passed

    def test_allows_clean_code(self, guard):
        """Test clean code passes."""
        code = """
def foo() -> int:
    try:
        return bar()
    except ValueError as e:
        logger.error("Error: %s", e)
        raise
"""
        result = guard.check(code)
        assert result.passed


class TestPythonShellGuard:
    """Tests for PythonShellGuard."""

    @pytest.fixture
    def guard(self):
        return PythonShellGuard()

    def test_detects_not_implemented(self, guard):
        """Test detection of NotImplementedError."""
        code = """
def foo():
    raise NotImplementedError()
"""
        result = guard.check(code, "src/app.py")
        assert not result.passed

    def test_detects_pass_placeholder(self, guard):
        """Test detection of pass placeholder."""
        code = """
def foo():
    pass  # TODO: implement
"""
        result = guard.check(code, "src/app.py")
        assert not result.passed

    def test_allows_abstract_methods(self, guard):
        """Test that abstract base classes are allowed."""
        code = """
from abc import ABC, abstractmethod

class Base(ABC):
    @abstractmethod
    def foo(self):
        raise NotImplementedError("Subclass must implement")
"""
        result = guard.check(code, "src/interfaces.py")
        # Should pass because it's an abstract class
        assert result.passed


class TestSecurityGuard:
    """Tests for SecurityGuard."""

    @pytest.fixture
    def guard(self):
        return SecurityGuard()

    def test_detects_hardcoded_password(self, guard):
        """Test detection of hardcoded password."""
        code = 'password = "supersecret123"'
        result = guard.check(code, "src/config.py")
        assert not result.passed
        assert any("password" in v.message.lower() for v in result.violations)

    def test_detects_sql_injection(self, guard):
        """Test detection of SQL injection patterns."""
        code = '''
def get_user(user_id):
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
'''
        result = guard.check(code, "src/db.py")
        assert not result.passed

    def test_detects_eval(self, guard):
        """Test detection of eval with user input."""
        code = "result = eval(request.data)"
        result = guard.check(code, "src/app.py")
        assert not result.passed

    def test_allows_safe_code(self, guard):
        """Test safe code passes."""
        code = """
import os

def get_config():
    password = os.environ.get('DB_PASSWORD')
    return {'password': password}
"""
        result = guard.check(code, "src/config.py")
        assert result.passed


class TestHallucinationGuard:
    """Tests for HallucinationGuard."""

    @pytest.fixture
    def guard(self):
        return HallucinationGuard()

    def test_detects_hallucinated_import(self, guard):
        """Test detection of non-existent imports."""
        code = "from fastapi import validate_request"
        result = guard.check(code, "src/app.py")
        assert not result.passed
        assert any("hallucinated" in v.message.lower() for v in result.violations)

    def test_detects_javascript_patterns(self, guard):
        """Test detection of JavaScript patterns in Python."""
        code = "result = json.parse(data)"
        result = guard.check(code, "src/utils.py")
        # Should have a warning about JavaScript pattern
        assert any("parse" in v.message.lower() for v in result.violations)

    def test_detects_deprecated_api(self, guard):
        """Test detection of deprecated APIs."""
        code = "loop = asyncio.get_event_loop()"
        result = guard.check(code, "src/async.py")
        # Should warn about deprecated API
        assert any("deprecated" in v.message.lower() for v in result.violations)

    def test_allows_valid_imports(self, guard):
        """Test valid imports pass."""
        code = """
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
import json
"""
        result = guard.check(code, "src/app.py")
        assert result.passed


class TestContextLossGuard:
    """Tests for ContextLossGuard."""

    @pytest.fixture
    def guard(self):
        return ContextLossGuard()

    def test_detects_untracked_todo(self, guard):
        """Test detection of untracked TODO."""
        code = "# TODO: implement user auth"
        result = guard.check(code, "src/auth.py")
        assert not result.passed

    def test_detects_wip_marker(self, guard):
        """Test detection of WIP marker."""
        code = "# WIP: still working on this"
        result = guard.check(code, "src/feature.py")
        assert not result.passed

    def test_detects_placeholder_return(self, guard):
        """Test detection of placeholder returns."""
        code = """
def get_users():
    return []  # TODO: fetch from database
"""
        result = guard.check(code, "src/users.py")
        assert not result.passed

    def test_allows_complete_code(self, guard):
        """Test complete code passes."""
        code = """
def get_users() -> list[User]:
    return db.query(User).all()
"""
        result = guard.check(code, "src/users.py")
        assert result.passed
