"""
Tests for Package Hallucination Detection Enhancement.

TDD approach: Tests written FIRST, then implementation.

Tests cover:
- PackageStatus dataclass
- PackageCache (SQLite-based)
- Typosquat detection (Damerau-Levenshtein)
- Registry verification (PyPI)
"""

import sqlite3
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest


class TestPackageStatus:
    """Tests for PackageStatus dataclass."""

    def test_basic_creation(self):
        """Test basic PackageStatus creation."""
        from sdk.guards.hallucination import PackageStatus

        status = PackageStatus(exists=True)
        assert status.exists is True
        assert status.created_at is None
        assert status.typosquat_of is None
        assert status.typosquat_distance == 0
        assert status.malicious is False
        assert status.source == "cache"
        assert status.error is None

    def test_full_creation(self):
        """Test PackageStatus with all fields."""
        from sdk.guards.hallucination import PackageStatus

        now = datetime.now()
        status = PackageStatus(
            exists=True,
            created_at=now,
            typosquat_of="requests",
            typosquat_distance=1,
            malicious=False,
            source="pypi",
            error=None,
        )
        assert status.exists is True
        assert status.created_at == now
        assert status.typosquat_of == "requests"
        assert status.typosquat_distance == 1
        assert status.source == "pypi"

    def test_nonexistent_package(self):
        """Test status for nonexistent package."""
        from sdk.guards.hallucination import PackageStatus

        status = PackageStatus(
            exists=False,
            typosquat_of="requests",
            typosquat_distance=1,
            source="pypi",
        )
        assert status.exists is False
        assert status.typosquat_of == "requests"

    def test_offline_status(self):
        """Test status when offline."""
        from sdk.guards.hallucination import PackageStatus

        status = PackageStatus(
            exists=True,  # Assume exists when offline
            source="offline",
            error="Connection timeout",
        )
        assert status.source == "offline"
        assert status.error == "Connection timeout"


class TestDamerauLevenshtein:
    """Tests for Damerau-Levenshtein distance calculation."""

    def test_identical_strings(self):
        """Test distance of identical strings is 0."""
        from sdk.guards.hallucination import damerau_levenshtein_distance

        assert damerau_levenshtein_distance("requests", "requests") == 0

    def test_single_deletion(self):
        """Test single character deletion."""
        from sdk.guards.hallucination import damerau_levenshtein_distance

        # requets -> requests (missing 's')
        assert damerau_levenshtein_distance("requets", "requests") == 1

    def test_single_insertion(self):
        """Test single character insertion."""
        from sdk.guards.hallucination import damerau_levenshtein_distance

        # requestss -> requests (extra 's')
        assert damerau_levenshtein_distance("requestss", "requests") == 1

    def test_single_substitution(self):
        """Test single character substitution."""
        from sdk.guards.hallucination import damerau_levenshtein_distance

        # requists -> requests ('i' instead of 'e')
        assert damerau_levenshtein_distance("requists", "requests") == 1

    def test_transposition(self):
        """Test adjacent character transposition."""
        from sdk.guards.hallucination import damerau_levenshtein_distance

        # reqeusts -> requests (transposition of 'ue' to 'eu')
        assert damerau_levenshtein_distance("reqeusts", "requests") == 1

    def test_multiple_edits(self):
        """Test multiple edits."""
        from sdk.guards.hallucination import damerau_levenshtein_distance

        # requst -> requests (2 edits)
        assert damerau_levenshtein_distance("requst", "requests") == 2

    def test_completely_different(self):
        """Test completely different strings."""
        from sdk.guards.hallucination import damerau_levenshtein_distance

        assert damerau_levenshtein_distance("abc", "xyz") == 3

    def test_empty_strings(self):
        """Test with empty strings."""
        from sdk.guards.hallucination import damerau_levenshtein_distance

        assert damerau_levenshtein_distance("", "") == 0
        assert damerau_levenshtein_distance("abc", "") == 3
        assert damerau_levenshtein_distance("", "abc") == 3

    def test_case_sensitive(self):
        """Test case sensitivity."""
        from sdk.guards.hallucination import damerau_levenshtein_distance

        assert damerau_levenshtein_distance("Requests", "requests") == 1


class TestTyposquatDetection:
    """Tests for typosquat detection logic."""

    def test_detects_requets_typosquat(self):
        """Test detection of 'requets' as typosquat of 'requests'."""
        from sdk.guards.hallucination import HallucinationGuard

        guard = HallucinationGuard(verify_registry=False, check_typosquats=True)
        is_typo, similar, dist = guard._is_typosquat("requets")
        assert is_typo is True
        assert similar == "requests"
        assert dist == 1

    def test_detects_transposition_typosquat(self):
        """Test detection of transposition typosquat."""
        from sdk.guards.hallucination import HallucinationGuard

        guard = HallucinationGuard(verify_registry=False, check_typosquats=True)
        is_typo, similar, dist = guard._is_typosquat("reqeusts")
        assert is_typo is True
        assert similar == "requests"
        assert dist == 1

    def test_detects_numppy_typosquat(self):
        """Test detection of 'numppy' as typosquat of 'numpy'."""
        from sdk.guards.hallucination import HallucinationGuard

        guard = HallucinationGuard(verify_registry=False, check_typosquats=True)
        is_typo, similar, dist = guard._is_typosquat("numppy")
        assert is_typo is True
        assert similar == "numpy"
        assert dist == 1

    def test_short_package_ignored(self):
        """Test that packages < 5 chars are not flagged as typosquats."""
        from sdk.guards.hallucination import HallucinationGuard

        guard = HallucinationGuard(verify_registry=False, check_typosquats=True)
        is_typo, similar, dist = guard._is_typosquat("req")
        assert is_typo is False
        assert similar is None

    def test_valid_package_not_typosquat(self):
        """Test that valid packages are not flagged."""
        from sdk.guards.hallucination import HallucinationGuard

        guard = HallucinationGuard(verify_registry=False, check_typosquats=True)
        is_typo, similar, dist = guard._is_typosquat("requests")
        assert is_typo is False

    def test_completely_different_not_typosquat(self):
        """Test that unrelated names are not flagged."""
        from sdk.guards.hallucination import HallucinationGuard

        guard = HallucinationGuard(verify_registry=False, check_typosquats=True)
        is_typo, similar, dist = guard._is_typosquat("myuniquepkg123")
        assert is_typo is False

    def test_adaptive_distance_short_package(self):
        """Test adaptive distance for short packages (5-7 chars)."""
        from sdk.guards.hallucination import HallucinationGuard

        guard = HallucinationGuard(verify_registry=False, check_typosquats=True)
        # 'flassk' is 6 chars, distance 1 from 'flask'
        is_typo, similar, dist = guard._is_typosquat("flassk")
        assert is_typo is True
        assert similar == "flask"
        assert dist == 1

    def test_adaptive_distance_long_package(self):
        """Test adaptive distance for longer packages (>= 8 chars)."""
        from sdk.guards.hallucination import HallucinationGuard

        guard = HallucinationGuard(verify_registry=False, check_typosquats=True)
        # 'sqlalchmy' is 9 chars, distance 2 from 'sqlalchemy' (missing 'e')
        is_typo, similar, dist = guard._is_typosquat("sqlalchmy")
        assert is_typo is True
        assert similar == "sqlalchemy"

    def test_case_insensitive(self):
        """Test typosquat detection is case insensitive."""
        from sdk.guards.hallucination import HallucinationGuard

        guard = HallucinationGuard(verify_registry=False, check_typosquats=True)
        is_typo, similar, dist = guard._is_typosquat("Requets")
        assert is_typo is True
        assert similar.lower() == "requests"


class TestPackageCache:
    """Tests for SQLite-based package cache."""

    @pytest.fixture
    def temp_cache(self, tmp_path):
        """Create a temporary cache for testing."""
        from sdk.guards.hallucination import PackageCache

        db_path = tmp_path / "test-cache.db"
        cache = PackageCache(db_path=db_path)
        return cache

    def test_cache_miss_returns_none(self, temp_cache):
        """Test cache miss returns None."""
        result = temp_cache.get("nonexistent-package")
        assert result is None

    def test_cache_set_and_get(self, temp_cache):
        """Test setting and getting cached value."""
        from sdk.guards.hallucination import PackageStatus

        status = PackageStatus(exists=True, source="pypi")
        temp_cache.set("requests", status)

        result = temp_cache.get("requests")
        assert result is not None
        assert result.exists is True
        assert result.source == "pypi"

    def test_cache_expiry_valid(self, temp_cache):
        """Test valid packages expire after 7 days."""
        from sdk.guards.hallucination import PackageStatus

        status = PackageStatus(exists=True, source="pypi")
        temp_cache.set("requests", status)

        # Should not be expired immediately
        assert temp_cache.is_expired("requests") is False

    def test_cache_expiry_invalid(self, temp_cache):
        """Test invalid packages expire after 1 hour."""
        from sdk.guards.hallucination import PackageStatus

        status = PackageStatus(exists=False, source="pypi")
        temp_cache.set("fakepackage", status)

        # Should not be expired immediately
        assert temp_cache.is_expired("fakepackage") is False

    def test_cache_nonexistent_not_expired(self, temp_cache):
        """Test nonexistent package is not considered expired."""
        assert temp_cache.is_expired("never-cached") is False

    def test_concurrent_access(self, tmp_path):
        """Test concurrent access from multiple threads."""
        from sdk.guards.hallucination import PackageCache, PackageStatus

        db_path = tmp_path / "concurrent-test.db"

        def worker(pkg_name: str):
            cache = PackageCache(db_path=db_path)
            status = PackageStatus(exists=True, source="pypi")
            cache.set(pkg_name, status)
            result = cache.get(pkg_name)
            return result is not None and result.exists

        # Run concurrent writes/reads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, f"pkg-{i}") for i in range(20)]
            results = [f.result() for f in futures]

        # All operations should succeed
        assert all(results)

    def test_cache_with_all_fields(self, temp_cache):
        """Test caching PackageStatus with all fields populated."""
        from sdk.guards.hallucination import PackageStatus

        now = datetime.now()
        status = PackageStatus(
            exists=False,
            created_at=now,
            typosquat_of="requests",
            typosquat_distance=1,
            malicious=False,
            source="pypi",
            error=None,
        )
        temp_cache.set("requets", status)

        result = temp_cache.get("requets")
        assert result is not None
        assert result.exists is False
        assert result.typosquat_of == "requests"
        assert result.typosquat_distance == 1


class TestRegistryVerification:
    """Tests for PyPI/npm registry verification."""

    @pytest.fixture
    def guard_with_mocked_cache(self, tmp_path):
        """Create guard with mocked cache."""
        from sdk.guards.hallucination import HallucinationGuard

        guard = HallucinationGuard(
            verify_registry=True,
            check_typosquats=True,
            cache_dir=str(tmp_path),
        )
        return guard

    def test_valid_package_exists(self, guard_with_mocked_cache, monkeypatch):
        """Test that valid package is verified as existing."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "info": {"name": "requests"},
            "releases": {"2.0.0": [{"upload_time": "2013-06-01T00:00:00"}]},
        }

        monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: mock_response)

        status = guard_with_mocked_cache._verify_pypi("requests")
        assert status.exists is True
        assert status.source == "pypi"

    def test_nonexistent_package(self, guard_with_mocked_cache, monkeypatch):
        """Test that nonexistent package returns exists=False."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 404

        monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: mock_response)

        status = guard_with_mocked_cache._verify_pypi("totally-fake-package-xyz")
        assert status.exists is False
        assert status.source == "pypi"

    def test_offline_graceful_handling(self, guard_with_mocked_cache, monkeypatch):
        """Test graceful handling when network is unavailable."""
        import httpx

        def raise_timeout(*args, **kwargs):
            raise httpx.TimeoutException("Connection timeout")

        monkeypatch.setattr(httpx, "get", raise_timeout)

        status = guard_with_mocked_cache._verify_pypi("requests")
        # Should return exists=True (fail open) with offline source
        assert status.source == "offline"
        assert status.error is not None

    def test_network_error_graceful(self, guard_with_mocked_cache, monkeypatch):
        """Test graceful handling of network errors."""
        import httpx

        def raise_error(*args, **kwargs):
            raise httpx.ConnectError("Network unreachable")

        monkeypatch.setattr(httpx, "get", raise_error)

        status = guard_with_mocked_cache._verify_pypi("requests")
        assert status.source == "offline"
        assert status.error is not None

    def test_cache_hit_skips_network(self, guard_with_mocked_cache, monkeypatch):
        """Test that cache hit doesn't make network request."""
        import httpx
        from sdk.guards.hallucination import PackageStatus

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"info": {}, "releases": {}}
            return response

        monkeypatch.setattr(httpx, "get", mock_get)

        # First call should hit network
        guard_with_mocked_cache._verify_pypi("requests")
        assert call_count == 1

        # Second call should use cache
        guard_with_mocked_cache._verify_pypi("requests")
        assert call_count == 1  # Still 1, no new network call

    def test_stdlib_skips_verification(self, guard_with_mocked_cache, monkeypatch):
        """Test that stdlib modules skip verification."""
        import httpx

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return MagicMock()

        monkeypatch.setattr(httpx, "get", mock_get)

        # stdlib modules should not trigger network call
        status = guard_with_mocked_cache._verify_pypi("os")
        assert call_count == 0
        assert status.exists is True
        assert status.source == "stdlib"


class TestHallucinationGuardIntegration:
    """Integration tests for the enhanced HallucinationGuard."""

    @pytest.fixture
    def guard(self, tmp_path):
        """Create guard for testing."""
        from sdk.guards.hallucination import HallucinationGuard

        return HallucinationGuard(
            verify_registry=False,  # Don't make real network calls
            check_typosquats=True,
            cache_dir=str(tmp_path),
        )

    def test_detects_typosquat_import(self, guard):
        """Test detection of typosquat in import statement."""
        code = "import requets"
        result = guard.check(code, "src/app.py")

        # Should have a violation for typosquat
        typo_violations = [
            v for v in result.violations if "typosquat" in v.message.lower()
        ]
        assert len(typo_violations) > 0

    def test_detects_from_import_typosquat(self, guard):
        """Test detection of typosquat in from...import statement."""
        code = "from requets import get"
        result = guard.check(code, "src/app.py")

        typo_violations = [
            v for v in result.violations if "typosquat" in v.message.lower()
        ]
        assert len(typo_violations) > 0

    def test_valid_imports_pass(self, guard):
        """Test that valid imports pass without typosquat warnings."""
        code = """
import os
import json
from pathlib import Path
"""
        result = guard.check(code, "src/app.py")

        typo_violations = [
            v for v in result.violations if "typosquat" in v.message.lower()
        ]
        assert len(typo_violations) == 0

    def test_multiple_imports_checked(self, guard):
        """Test that multiple imports in one file are all checked."""
        code = """
import requets  # typosquat
import numppy   # typosquat
import os       # valid
"""
        result = guard.check(code, "src/app.py")

        typo_violations = [
            v for v in result.violations if "typosquat" in v.message.lower()
        ]
        assert len(typo_violations) >= 2

    def test_severity_high_confidence_typosquat(self, guard):
        """Test ERROR severity for high-confidence typosquat."""
        from sdk.guards.base import GuardSeverity

        code = "import requets"  # distance 1 from top package
        result = guard.check(code, "src/app.py")

        error_violations = [
            v for v in result.violations
            if v.severity == GuardSeverity.ERROR and "typosquat" in v.message.lower()
        ]
        assert len(error_violations) > 0

    def test_disabled_typosquat_check(self, tmp_path):
        """Test that typosquat check can be disabled."""
        from sdk.guards.hallucination import HallucinationGuard

        guard = HallucinationGuard(
            verify_registry=False,
            check_typosquats=False,  # Disabled
            cache_dir=str(tmp_path),
        )

        code = "import requets"
        result = guard.check(code, "src/app.py")

        typo_violations = [
            v for v in result.violations if "typosquat" in v.message.lower()
        ]
        assert len(typo_violations) == 0
