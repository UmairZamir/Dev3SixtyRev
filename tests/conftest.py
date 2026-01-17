"""Pytest configuration for SDK tests."""

import sys
from pathlib import Path

# Ensure we import from the local SDK, not any other installed version
# This fixes the path conflict when venv is in a different directory
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture
def sample_python_code():
    """Sample Python code for testing."""
    return '''
def hello_world():
    """A simple function."""
    return "Hello, World!"


class Calculator:
    """A simple calculator."""
    
    def add(self, a: int, b: int) -> int:
        return a + b
    
    def subtract(self, a: int, b: int) -> int:
        return a - b
'''


@pytest.fixture
def bad_python_code():
    """Python code with issues for testing guards."""
    return '''
import os
from typing import *  # noqa

def process_user(user_id):
    # TODO: fix this later
    password = "hardcoded123"  # type: ignore
    
    try:
        result = eval(user_id)  # dangerous!
    except:
        pass  # bad practice
    
    return None  # placeholder


class DataProcessor:
    def process(self):
        raise NotImplementedError()
    
    def validate(self, data):
        pass  # implement later
'''


@pytest.fixture
def project_dir(tmp_path):
    """Create a temporary project directory."""
    src = tmp_path / "src"
    src.mkdir()
    
    tests = tmp_path / "tests"
    tests.mkdir()
    
    # Create sample files
    (src / "app.py").write_text('''
def main():
    print("Hello")
''')
    
    (src / "__init__.py").write_text("")
    (tests / "__init__.py").write_text("")
    (tests / "test_app.py").write_text('''
def test_main():
    assert True
''')
    
    return tmp_path


@pytest.fixture
def sdk_config(tmp_path):
    """Create SDK config for testing."""
    from sdk.core.config import SDKConfig
    
    return SDKConfig(
        project_name="TestProject",
        project_root=tmp_path,
        verbose=True,
    )
