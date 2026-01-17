"""
Hallucination Guard
===================

Detects AI hallucinations in code.

From research:
- "AI models suggested software packages that did not exist 5.2% of the time"
- "AI hallucinations sometimes just make up nonexistent functions"
- "Generated code may reference documentation, but the described behavior doesn't match"
- "5.2-21.7% of AI-suggested packages don't exist (slopsquatting risk)"

This guard detects:
- Non-existent imports from standard library
- Common AI-hallucinated APIs
- Invented function names that don't exist
- Deprecated or renamed APIs
- Non-existent package imports
- Typosquatting attempts (packages 1-2 chars from popular packages)
- Packages created after AI training cutoff
"""

import ast
import re
import sqlite3
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Generator, List, Literal, Optional, Set, Tuple

import httpx

from sdk.guards.base import (
    Guard,
    GuardCategory,
    GuardLevel,
    GuardResult,
    GuardSeverity,
    GuardViolation,
)


# Known hallucinated imports - APIs that AI commonly invents
HALLUCINATED_IMPORTS: Dict[str, str] = {
    # FastAPI hallucinations
    "fastapi.validate_request": "FastAPI doesn't have validate_request. Use Pydantic models.",
    "fastapi.auth": "FastAPI doesn't have auth module. Use fastapi.security.",
    "fastapi.middleware.auth": "This doesn't exist. Use custom middleware.",
    "fastapi.validate": "FastAPI doesn't have validate. Use Pydantic for validation.",
    # Python standard library hallucinations
    "typing.Json": "Json is not in typing. Use dict or create a TypeAlias.",
    "typing.Nullable": "Nullable doesn't exist. Use Optional[T] instead.",
    "json.decode": "json.decode doesn't exist. Use json.loads().",
    "json.encode": "json.encode doesn't exist. Use json.dumps().",
    "os.read_file": "os.read_file doesn't exist. Use open().read() or Path.read_text().",
    "os.write_file": "os.write_file doesn't exist. Use open().write() or Path.write_text().",
    "pathlib.read": "pathlib.read doesn't exist. Use Path.read_text() or Path.read_bytes().",
    "datetime.now": "datetime.now doesn't exist as function. Use datetime.datetime.now().",
    "time.now": "time.now doesn't exist. Use time.time() or datetime.datetime.now().",
    "collections.HashMap": "HashMap doesn't exist. Use dict.",
    "collections.ArrayList": "ArrayList doesn't exist. Use list.",
    # SQLAlchemy hallucinations
    "sqlalchemy.execute": "Direct execute doesn't exist. Use session.execute() or engine.execute().",
    "sqlalchemy.query": "Direct query doesn't exist. Use session.query() or select().",
    # Pydantic hallucinations
    "pydantic.validate": "pydantic.validate doesn't exist. Use validators or model_validator.",
    "pydantic.Field.required": "Field.required doesn't exist. Omit default to make required.",
    # Requests hallucinations
    "requests.fetch": "requests.fetch doesn't exist. Use requests.get() or requests.post().",
    "requests.send": "requests.send doesn't exist. Use requests.request().",
    # Pandas hallucinations
    "pandas.read": "pandas.read doesn't exist. Use pandas.read_csv(), read_json(), etc.",
    "pandas.write": "pandas.write doesn't exist. Use df.to_csv(), df.to_json(), etc.",
    "pandas.DataFrame.select": "DataFrame.select doesn't exist. Use df[] or df.loc[].",
    # Redis hallucinations
    "redis.connect": "redis.connect doesn't exist. Use redis.Redis() or redis.from_url().",
    "redis.query": "redis.query doesn't exist. Use specific methods like get(), set(), etc.",
    # AWS hallucinations
    "boto3.s3": "boto3.s3 doesn't exist. Use boto3.client('s3') or boto3.resource('s3').",
    "boto3.dynamodb": "boto3.dynamodb doesn't exist. Use boto3.resource('dynamodb').",
    # React hallucinations (for JS/TS files)
    "react.useState": "Should be: import { useState } from 'react'",
    "react.useEffect": "Should be: import { useEffect } from 'react'",
    "@react/hooks": "This package doesn't exist. Hooks are in 'react'.",
}

# Commonly hallucinated function patterns
HALLUCINATED_PATTERNS: Dict[str, str] = {
    r"\.to_dict\(\)\.json\(\)": "to_dict() returns dict, not an object with json() method.",
    r"json\.parse\(": "json.parse() is JavaScript. Use json.loads() in Python.",
    r"JSON\.stringify\(": "JSON.stringify() is JavaScript. Use json.dumps() in Python.",
    r"\.forEach\(": "forEach is JavaScript. Use 'for item in list:' in Python.",
    r"\.map\(lambda": "map() returns iterator, not list. Consider list comprehension.",
    r"list\.add\(": "Python lists use .append(), not .add().",
    r"dict\.add\(": "Python dicts use d[key] = value, not .add().",
    r"str\.contains\(": "Python strings use 'in' operator: 'x in s', not .contains().",
    r"array\.push\(": "array.push is JavaScript. Use list.append() in Python.",
    r"array\.length": "array.length is JavaScript. Use len(array) in Python.",
    r"string\.length": "string.length is JavaScript. Use len(string) in Python.",
    r"\.size\(\)": "Most Python collections use len(), not .size().",
    r"\.isEmpty\(\)": "Use 'not collection' or 'len(collection) == 0' in Python.",
    r"\.isNull\(\)": "Use 'is None' in Python, not .isNull().",
    r"console\.log\(": "console.log is JavaScript. Use print() or logging in Python.",
    r"println\(": "println is Java/Kotlin. Use print() in Python.",
    r"System\.out\.print": "System.out is Java. Use print() in Python.",
    r"fmt\.Println\(": "fmt.Println is Go. Use print() in Python.",
    r"\.toString\(\)": "In Python, use str() function: str(obj).",
    r"Integer\.parseInt\(": "parseInt is Java. Use int() in Python.",
    r"Double\.parseDouble\(": "parseDouble is Java. Use float() in Python.",
    r"new\s+\w+\(": "'new' keyword is not Python. Just call the class: ClassName().",
    r"\.equals\(": "Python uses == for equality, not .equals().",
    r"(?<!\w)&&(?!\w)": "Use 'and' in Python, not &&.",
    r"(?<!\w)\|\|(?!\w)": "Use 'or' in Python, not ||.",
    r"(?<![!=<>])!(?=[a-zA-Z_]\w*)": "Use 'not' in Python for negation, not !.",
    r"(?<![\w\"\'=])null(?![\w\"\'\[])": "Python uses None, not null.",
    r"(?<![\w\"\'=])true(?![\w\"\'\[])": "Python uses True (capitalized), not true.",
    r"(?<![\w\"\'=])false(?![\w\"\'\[])": "Python uses False (capitalized), not false.",
}

# Deprecated/renamed APIs that AI might use
DEPRECATED_APIS: Dict[str, str] = {
    r"asyncio\.get_event_loop\(\)": "Deprecated in 3.10+. Use asyncio.get_running_loop() or asyncio.run().",
    r"collections\.Mapping": "Moved in 3.3+. Use collections.abc.Mapping.",
    r"collections\.MutableMapping": "Moved in 3.3+. Use collections.abc.MutableMapping.",
    r"collections\.Iterable": "Moved in 3.3+. Use collections.abc.Iterable.",
    r"collections\.Callable": "Moved in 3.3+. Use collections.abc.Callable or typing.Callable.",
    r"typing\.Dict\[": "In 3.9+, use dict[] instead of typing.Dict[].",
    r"typing\.List\[": "In 3.9+, use list[] instead of typing.List[].",
    r"typing\.Set\[": "In 3.9+, use set[] instead of typing.Set[].",
    r"typing\.Tuple\[": "In 3.9+, use tuple[] instead of typing.Tuple[].",
    r"@asyncio\.coroutine": "Deprecated. Use 'async def' instead.",
    r"loop\.run_until_complete": "Prefer asyncio.run() in Python 3.7+.",
    r"imp\.": "imp module deprecated in 3.4. Use importlib.",
    r"optparse\.": "optparse deprecated. Use argparse.",
    r"distutils\.": "distutils deprecated in 3.10+. Use setuptools.",
}

# ============================================================================
# PACKAGE REGISTRY VERIFICATION (Supply Chain Security)
# ============================================================================

# Top Python packages for typosquat detection (from PyPI download stats)
# These are the most commonly targeted for typosquatting attacks
TOP_PYTHON_PACKAGES: Set[str] = {
    # Top 50 most downloaded (high-confidence typosquats are ERROR)
    "requests", "boto3", "urllib3", "botocore", "setuptools",
    "certifi", "typing-extensions", "charset-normalizer", "idna", "numpy",
    "python-dateutil", "s3transfer", "packaging", "pyyaml", "six",
    "cryptography", "cffi", "jmespath", "pip", "wheel",
    "pycparser", "pyasn1", "attrs", "platformdirs", "grpcio",
    "google-api-core", "pytz", "fsspec", "protobuf", "pandas",
    "filelock", "importlib-metadata", "zipp", "click", "aiohttp",
    "colorama", "virtualenv", "markupsafe", "jinja2", "pyparsing",
    "pydantic", "jsonschema", "pillow", "tomlkit", "tqdm",
    "decorator", "soupsieve", "beautifulsoup4", "lxml", "scipy",
    # 51-100 (lower-confidence typosquats are WARNING)
    "flask", "django", "fastapi", "sqlalchemy", "pytest",
    "httpx", "aiofiles", "redis", "celery", "uvicorn",
    "starlette", "gunicorn", "psycopg2", "pymongo", "elasticsearch",
    "httplib2", "google-auth", "google-cloud-storage", "tensorflow", "torch",
    "scikit-learn", "matplotlib", "seaborn", "plotly", "networkx",
    "nltk", "spacy", "transformers", "openai", "anthropic",
    "langchain", "streamlit", "gradio", "rich", "typer",
    "black", "ruff", "mypy", "isort", "flake8",
    "pre-commit", "coverage", "pytest-cov", "mock", "faker",
    "factory-boy", "hypothesis", "responses", "httpretty", "vcrpy",
}

# Top 50 packages for high-confidence ERROR-level typosquat detection
TOP_50_PACKAGES: Set[str] = {
    "requests", "boto3", "urllib3", "botocore", "setuptools",
    "certifi", "typing-extensions", "charset-normalizer", "idna", "numpy",
    "python-dateutil", "s3transfer", "packaging", "pyyaml", "six",
    "cryptography", "cffi", "jmespath", "pip", "wheel",
    "pycparser", "pyasn1", "attrs", "platformdirs", "grpcio",
    "google-api-core", "pytz", "fsspec", "protobuf", "pandas",
    "filelock", "importlib-metadata", "zipp", "click", "aiohttp",
    "colorama", "virtualenv", "markupsafe", "jinja2", "pyparsing",
    "pydantic", "jsonschema", "pillow", "tomlkit", "tqdm",
    "decorator", "soupsieve", "beautifulsoup4", "lxml", "scipy",
}

# Python standard library modules (skip verification - always exist)
STDLIB_MODULES: Set[str] = {
    # Built-in modules
    "abc", "aifc", "argparse", "array", "ast", "asyncio",
    "atexit", "base64", "bdb", "binascii", "bisect", "builtins",
    "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath",
    "cmd", "code", "codecs", "codeop", "collections", "colorsys",
    "compileall", "concurrent", "configparser", "contextlib", "contextvars",
    "copy", "copyreg", "cProfile", "crypt", "csv", "ctypes",
    "curses", "dataclasses", "datetime", "dbm", "decimal", "difflib",
    "dis", "doctest", "email", "encodings", "enum", "errno",
    "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch",
    "fractions", "ftplib", "functools", "gc", "getopt", "getpass",
    "gettext", "glob", "graphlib", "grp", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "idlelib", "imaplib",
    "imghdr", "importlib", "inspect", "io", "ipaddress", "itertools",
    "json", "keyword", "lib2to3", "linecache", "locale", "logging",
    "lzma", "mailbox", "mailcap", "marshal", "math", "mimetypes",
    "mmap", "modulefinder", "multiprocessing", "netrc", "nis", "nntplib",
    "numbers", "operator", "optparse", "os", "ossaudiodev", "pathlib",
    "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform",
    "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
    "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc",
    "queue", "quopri", "random", "re", "readline", "reprlib",
    "resource", "rlcompleter", "runpy", "sched", "secrets", "select",
    "selectors", "shelve", "shlex", "shutil", "signal", "site",
    "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "spwd",
    "sqlite3", "ssl", "stat", "statistics", "string", "stringprep",
    "struct", "subprocess", "sunau", "symtable", "sys", "sysconfig",
    "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile", "termios",
    "test", "textwrap", "threading", "time", "timeit", "tkinter",
    "token", "tokenize", "tomllib", "trace", "traceback", "tracemalloc",
    "tty", "turtle", "turtledemo", "types", "typing", "unicodedata",
    "unittest", "urllib", "uu", "uuid", "venv", "warnings",
    "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref",
    "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
}


@dataclass
class PackageStatus:
    """Result of package verification against PyPI/npm registry."""

    exists: bool
    created_at: Optional[datetime] = None
    typosquat_of: Optional[str] = None
    typosquat_distance: int = 0
    malicious: bool = False
    source: Literal["cache", "pypi", "npm", "stdlib", "offline"] = "cache"
    error: Optional[str] = None


def damerau_levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Damerau-Levenshtein distance between two strings.

    Unlike standard Levenshtein, this treats adjacent transpositions
    as a single edit operation, which is important for detecting
    typosquatting (e.g., 'reqeusts' -> 'requests' = 1 edit).

    Args:
        s1: First string
        s2: Second string

    Returns:
        Edit distance (0 = identical, 1 = one edit, etc.)
    """
    len1, len2 = len(s1), len(s2)

    # Handle empty strings
    if len1 == 0:
        return len2
    if len2 == 0:
        return len1

    # Create distance matrix
    d: Dict[Tuple[int, int], int] = {}

    # Initialize
    for i in range(-1, len1 + 1):
        d[(i, -1)] = i + 1
    for j in range(-1, len2 + 1):
        d[(-1, j)] = j + 1

    for i in range(len1):
        for j in range(len2):
            cost = 0 if s1[i] == s2[j] else 1

            d[(i, j)] = min(
                d[(i - 1, j)] + 1,      # Deletion
                d[(i, j - 1)] + 1,      # Insertion
                d[(i - 1, j - 1)] + cost,  # Substitution
            )

            # Transposition
            if i > 0 and j > 0 and s1[i] == s2[j - 1] and s1[i - 1] == s2[j]:
                d[(i, j)] = min(d[(i, j)], d[(i - 2, j - 2)] + cost)

    return d[(len1 - 1, len2 - 1)]


class PackageCache:
    """
    SQLite-based cache for package verification results.

    Thread-safe with connection pooling (thread-local connections).
    Follows the pattern from sdk/telemetry/store.py.
    """

    TTL_VALID_SECONDS = 86400 * 7  # 7 days for known-good packages
    TTL_INVALID_SECONDS = 3600     # 1 hour for unknown packages

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".3sr" / "package-cache.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._initialize_schema()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._local.connection.row_factory = sqlite3.Row
        try:
            yield self._local.connection
        except Exception:
            self._local.connection.rollback()
            raise

    def _initialize_schema(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Note: 'pkg_exists' instead of 'exists' since 'exists' is a SQLite keyword
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS packages (
                    name TEXT PRIMARY KEY,
                    pkg_exists BOOLEAN NOT NULL,
                    created_at TIMESTAMP,
                    typosquat_of TEXT,
                    typosquat_distance INTEGER DEFAULT 0,
                    malicious BOOLEAN DEFAULT FALSE,
                    source TEXT NOT NULL,
                    error TEXT,
                    verified_at TIMESTAMP NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_verified_at
                ON packages(verified_at)
            """)
            conn.commit()

    def get(self, package: str) -> Optional[PackageStatus]:
        """Get cached package status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM packages WHERE name = ?",
                (package.lower(),)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return PackageStatus(
                exists=bool(row["pkg_exists"]),
                created_at=row["created_at"],
                typosquat_of=row["typosquat_of"],
                typosquat_distance=row["typosquat_distance"] or 0,
                malicious=bool(row["malicious"]),
                source=row["source"],
                error=row["error"],
            )

    def set(self, package: str, status: PackageStatus) -> None:
        """Cache package status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO packages
                (name, pkg_exists, created_at, typosquat_of, typosquat_distance,
                 malicious, source, error, verified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                package.lower(),
                status.exists,
                status.created_at,
                status.typosquat_of,
                status.typosquat_distance,
                status.malicious,
                status.source,
                status.error,
                datetime.now(),
            ))
            conn.commit()

    def is_expired(self, package: str) -> bool:
        """Check if cached entry is expired."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT pkg_exists, verified_at FROM packages WHERE name = ?",
                (package.lower(),)
            )
            row = cursor.fetchone()

            if row is None:
                return False  # Not in cache, not expired

            verified_at = row["verified_at"]
            if isinstance(verified_at, str):
                verified_at = datetime.fromisoformat(verified_at)

            pkg_exists = bool(row["pkg_exists"])
            ttl = self.TTL_VALID_SECONDS if pkg_exists else self.TTL_INVALID_SECONDS

            return (datetime.now() - verified_at).total_seconds() > ttl


class HallucinationGuard(Guard):
    """Detects AI hallucinations in code - invented APIs, non-existent imports.

    Enhanced with:
    - Real-time PyPI registry verification
    - Typosquat detection using Damerau-Levenshtein distance
    - Historical package validation (post-training-cutoff detection)
    """

    def __init__(
        self,
        enabled: bool = True,
        verify_registry: bool = True,
        check_typosquats: bool = True,
        training_cutoff: str = "2024-01-01",
        cache_dir: Optional[str] = None,
    ):
        """
        Initialize HallucinationGuard.

        Args:
            enabled: Whether the guard is active
            verify_registry: Enable real-time PyPI verification
            check_typosquats: Enable typosquat detection
            training_cutoff: Date string (YYYY-MM-DD) for historical validation
            cache_dir: Custom cache directory (default: ~/.3sr/)
        """
        super().__init__(
            name="hallucination",
            description="Detects AI hallucinations: invented APIs, non-existent imports, typosquats",
            level=GuardLevel.INSTANT,
            category=GuardCategory.HALLUCINATION,
            enabled=enabled,
            severity=GuardSeverity.ERROR,
        )

        # Configuration
        self._verify_registry = verify_registry
        self._check_typosquats = check_typosquats
        self._training_cutoff = datetime.fromisoformat(training_cutoff)

        # Initialize cache
        if verify_registry:
            cache_path = Path(cache_dir) / "package-cache.db" if cache_dir else None
            self._cache = PackageCache(db_path=cache_path)
        else:
            self._cache = None

        # Compile patterns
        self._pattern_checks = {
            re.compile(pattern, re.MULTILINE): msg
            for pattern, msg in HALLUCINATED_PATTERNS.items()
        }
        self._deprecated_checks = {
            re.compile(pattern, re.MULTILINE): msg
            for pattern, msg in DEPRECATED_APIS.items()
        }

        # Python files only
        self.add_file_extensions([".py"])
        self.add_exception("/tests/")
        self.add_exception("test_")

    def _is_typosquat(self, package: str) -> Tuple[bool, Optional[str], int]:
        """
        Check if package name is a typosquat of a popular package.

        Uses Damerau-Levenshtein distance with adaptive thresholds:
        - < 5 chars: not checked (too short)
        - 5-7 chars: max distance 1
        - >= 8 chars: max distance 2

        Args:
            package: Package name to check

        Returns:
            Tuple of (is_typosquat, similar_package, distance)
        """
        if not self._check_typosquats:
            return (False, None, 0)

        pkg_lower = package.lower()

        # Too short - high false positive risk
        if len(pkg_lower) < 5:
            return (False, None, 0)

        # If it's an exact match to a known package, not a typosquat
        if pkg_lower in TOP_PYTHON_PACKAGES or pkg_lower.replace("-", "_") in TOP_PYTHON_PACKAGES:
            return (False, None, 0)

        # Adaptive distance threshold
        max_dist = 1 if len(pkg_lower) < 8 else 2

        # Check against popular packages
        for popular in TOP_PYTHON_PACKAGES:
            dist = damerau_levenshtein_distance(pkg_lower, popular.lower())
            if 0 < dist <= max_dist:
                return (True, popular, dist)

        return (False, None, 0)

    def _verify_pypi(self, package: str) -> PackageStatus:
        """
        Verify package exists on PyPI with caching.

        Fails open (returns exists=True) on network errors to avoid
        blocking development when offline.

        Args:
            package: Package name to verify

        Returns:
            PackageStatus with verification result
        """
        pkg_lower = package.lower()

        # Skip stdlib modules
        if pkg_lower in STDLIB_MODULES:
            return PackageStatus(exists=True, source="stdlib")

        # Check cache first
        if self._cache:
            cached = self._cache.get(pkg_lower)
            if cached and not self._cache.is_expired(pkg_lower):
                return cached

        # Verify against PyPI
        try:
            url = f"https://pypi.org/pypi/{urllib.parse.quote(pkg_lower)}/json"
            response = httpx.get(url, timeout=5.0, follow_redirects=True)

            if response.status_code == 404:
                # Package doesn't exist
                is_typo, similar, dist = self._is_typosquat(pkg_lower)
                status = PackageStatus(
                    exists=False,
                    typosquat_of=similar,
                    typosquat_distance=dist,
                    source="pypi",
                )
                if self._cache:
                    self._cache.set(pkg_lower, status)
                return status

            if response.status_code == 200:
                # Package exists - parse release dates
                data = response.json()
                releases = data.get("releases", {})

                created_at = None
                if releases:
                    try:
                        # Find earliest release
                        earliest_version = min(releases.keys(), key=lambda v: v)
                        release_info = releases.get(earliest_version, [])
                        if release_info:
                            upload_time = release_info[0].get("upload_time")
                            if upload_time:
                                created_at = datetime.fromisoformat(
                                    upload_time.replace("Z", "+00:00")
                                )
                    except (ValueError, KeyError, IndexError):
                        pass

                status = PackageStatus(
                    exists=True,
                    created_at=created_at,
                    source="pypi",
                )
                if self._cache:
                    self._cache.set(pkg_lower, status)
                return status

            # Unexpected status - fail open
            return PackageStatus(
                exists=True,
                source="offline",
                error=f"Unexpected status: {response.status_code}",
            )

        except httpx.TimeoutException:
            return PackageStatus(
                exists=True,  # Fail open
                source="offline",
                error="Connection timeout",
            )
        except httpx.ConnectError as e:
            return PackageStatus(
                exists=True,  # Fail open
                source="offline",
                error=f"Connection error: {e}",
            )
        except Exception as e:
            return PackageStatus(
                exists=True,  # Fail open
                source="offline",
                error=str(e),
            )

    def _verify_batch(
        self, packages: List[str]
    ) -> Dict[str, PackageStatus]:
        """
        Verify multiple packages in parallel using thread pool.

        Args:
            packages: List of package names to verify

        Returns:
            Dict mapping package name to PackageStatus
        """
        if not packages:
            return {}

        # Filter out stdlib
        to_verify = [p for p in packages if p.lower() not in STDLIB_MODULES]

        results: Dict[str, PackageStatus] = {}

        # Add stdlib as existing
        for pkg in packages:
            if pkg.lower() in STDLIB_MODULES:
                results[pkg] = PackageStatus(exists=True, source="stdlib")

        if not to_verify:
            return results

        # Verify in parallel with max 5 workers
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._verify_pypi, pkg): pkg
                for pkg in to_verify
            }
            for future in as_completed(futures):
                pkg = futures[future]
                try:
                    results[pkg] = future.result()
                except Exception as e:
                    results[pkg] = PackageStatus(
                        exists=True,
                        source="offline",
                        error=str(e),
                    )

        return results

    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check for hallucinated APIs and imports."""
        start = time.time()

        if file_path and not self.should_check_file(file_path):
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                execution_time_ms=(time.time() - start) * 1000,
            )

        violations: List[GuardViolation] = []
        lines = content.split("\n")

        # Check for hallucinated imports using AST
        try:
            tree = ast.parse(content)
            violations.extend(self._check_imports(tree, file_path, lines))
        except SyntaxError:
            # If AST parsing fails, fall back to regex
            violations.extend(self._check_imports_regex(content, file_path, lines))

        # Check for hallucinated patterns
        violations.extend(self._check_patterns(content, file_path, lines))

        # Check for deprecated APIs
        violations.extend(self._check_deprecated(content, file_path, lines))

        has_errors = any(v.severity == GuardSeverity.ERROR for v in violations)

        return GuardResult(
            guard_name=self.name,
            passed=not has_errors,
            violations=violations,
            execution_time_ms=(time.time() - start) * 1000,
            files_checked=1,
        )

    def _check_imports(
        self, tree: ast.AST, file_path: Optional[str], lines: List[str]
    ) -> List[GuardViolation]:
        """Check imports using AST for hallucinated modules and typosquats."""
        violations = []

        # Collect all imported package names for batch verification
        imported_packages: Dict[str, int] = {}  # package -> line number

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    # Check for hallucinated specific imports
                    for alias in node.names:
                        full_import = f"{node.module}.{alias.name}"
                        if full_import in HALLUCINATED_IMPORTS:
                            violations.append(
                                GuardViolation(
                                    guard_name=self.name,
                                    severity=GuardSeverity.ERROR,
                                    category=GuardCategory.HALLUCINATION,
                                    message=f"Hallucinated import: {full_import}",
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    suggestion=HALLUCINATED_IMPORTS[full_import],
                                    code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                                )
                            )

                    # Track the base module for typosquat/registry check
                    base_module = node.module.split(".")[0]
                    if base_module not in imported_packages:
                        imported_packages[base_module] = node.lineno

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in HALLUCINATED_IMPORTS:
                        violations.append(
                            GuardViolation(
                                guard_name=self.name,
                                severity=GuardSeverity.ERROR,
                                category=GuardCategory.HALLUCINATION,
                                message=f"Hallucinated import: {alias.name}",
                                file_path=file_path,
                                line_number=node.lineno,
                                suggestion=HALLUCINATED_IMPORTS[alias.name],
                                code_snippet=lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                            )
                        )

                    # Track the base module for typosquat/registry check
                    base_module = alias.name.split(".")[0]
                    if base_module not in imported_packages:
                        imported_packages[base_module] = node.lineno

        # Check for typosquats (no network required)
        if self._check_typosquats:
            violations.extend(
                self._check_typosquats_for_packages(imported_packages, file_path, lines)
            )

        # Verify against PyPI registry (requires network)
        if self._verify_registry:
            violations.extend(
                self._check_registry_for_packages(imported_packages, file_path, lines)
            )

        return violations

    def _check_typosquats_for_packages(
        self,
        packages: Dict[str, int],
        file_path: Optional[str],
        lines: List[str],
    ) -> List[GuardViolation]:
        """Check packages for potential typosquatting."""
        violations = []

        for package, line_num in packages.items():
            # Skip stdlib
            if package.lower() in STDLIB_MODULES:
                continue

            is_typo, similar, dist = self._is_typosquat(package)

            if is_typo and similar:
                # High-confidence: distance 1 from top-50 package = ERROR
                # Lower-confidence: distance 2 or less popular = WARNING
                is_high_confidence = (
                    dist == 1 and similar.lower() in TOP_50_PACKAGES
                )
                severity = (
                    GuardSeverity.ERROR if is_high_confidence
                    else GuardSeverity.WARNING
                )

                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=severity,
                        category=GuardCategory.HALLUCINATION,
                        message=f"Potential typosquat: '{package}' is {dist} edit(s) from '{similar}'",
                        file_path=file_path,
                        line_number=line_num,
                        suggestion=f"Did you mean '{similar}'? Typosquatted packages may contain malware.",
                        code_snippet=lines[line_num - 1].strip() if line_num <= len(lines) else "",
                    )
                )

        return violations

    def _check_registry_for_packages(
        self,
        packages: Dict[str, int],
        file_path: Optional[str],
        lines: List[str],
    ) -> List[GuardViolation]:
        """Verify packages against PyPI registry."""
        violations = []

        # Filter out stdlib
        to_check = {
            pkg: line for pkg, line in packages.items()
            if pkg.lower() not in STDLIB_MODULES
        }

        if not to_check:
            return violations

        # Verify in batch
        statuses = self._verify_batch(list(to_check.keys()))

        for package, line_num in to_check.items():
            status = statuses.get(package)
            if not status:
                continue

            # Skip if verified offline (fail open)
            if status.source == "offline":
                continue

            # Package doesn't exist on PyPI
            if not status.exists:
                # Already flagged as typosquat? Skip duplicate
                if status.typosquat_of:
                    continue

                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=GuardSeverity.WARNING,
                        category=GuardCategory.HALLUCINATION,
                        message=f"Package '{package}' not found on PyPI",
                        file_path=file_path,
                        line_number=line_num,
                        suggestion="Verify the package name is correct. Unknown packages may be hallucinated.",
                        code_snippet=lines[line_num - 1].strip() if line_num <= len(lines) else "",
                    )
                )

            # Package exists but created after training cutoff
            elif status.created_at and status.created_at > self._training_cutoff:
                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=GuardSeverity.INFO,
                        category=GuardCategory.HALLUCINATION,
                        message=f"Package '{package}' created after {self._training_cutoff.date()}",
                        file_path=file_path,
                        line_number=line_num,
                        suggestion="This package was created after the AI training cutoff. Verify it's legitimate.",
                        code_snippet=lines[line_num - 1].strip() if line_num <= len(lines) else "",
                    )
                )

        return violations

    def _check_imports_regex(
        self, content: str, file_path: Optional[str], lines: List[str]
    ) -> List[GuardViolation]:
        """Fallback regex check for imports when AST fails."""
        violations = []

        for hallucinated, suggestion in HALLUCINATED_IMPORTS.items():
            # Convert module path to import pattern
            parts = hallucinated.rsplit(".", 1)
            if len(parts) == 2:
                module, name = parts
                pattern = rf"from\s+{re.escape(module)}\s+import\s+.*{re.escape(name)}"
            else:
                pattern = rf"import\s+{re.escape(hallucinated)}"

            for match in re.finditer(pattern, content, re.MULTILINE):
                line_num = content.count("\n", 0, match.start()) + 1
                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=GuardSeverity.ERROR,
                        category=GuardCategory.HALLUCINATION,
                        message=f"Potentially hallucinated import: {hallucinated}",
                        file_path=file_path,
                        line_number=line_num,
                        suggestion=suggestion,
                        code_snippet=lines[line_num - 1].strip() if line_num <= len(lines) else "",
                    )
                )

        return violations

    def _check_patterns(
        self, content: str, file_path: Optional[str], lines: List[str]
    ) -> List[GuardViolation]:
        """Check for hallucinated code patterns."""
        violations = []

        for pattern, suggestion in self._pattern_checks.items():
            for match in pattern.finditer(content):
                line_num = content.count("\n", 0, match.start()) + 1
                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=GuardSeverity.WARNING,  # Warning for patterns
                        category=GuardCategory.HALLUCINATION,
                        message=f"Possible hallucination: {match.group(0)[:40]}",
                        file_path=file_path,
                        line_number=line_num,
                        suggestion=suggestion,
                        code_snippet=lines[line_num - 1].strip() if line_num <= len(lines) else "",
                    )
                )

        return violations

    def _check_deprecated(
        self, content: str, file_path: Optional[str], lines: List[str]
    ) -> List[GuardViolation]:
        """Check for deprecated APIs that AI might suggest."""
        violations = []

        for pattern, suggestion in self._deprecated_checks.items():
            for match in pattern.finditer(content):
                line_num = content.count("\n", 0, match.start()) + 1
                violations.append(
                    GuardViolation(
                        guard_name=self.name,
                        severity=GuardSeverity.WARNING,  # Warning for deprecated
                        category=GuardCategory.HALLUCINATION,
                        message=f"Deprecated API: {match.group(0)[:40]}",
                        file_path=file_path,
                        line_number=line_num,
                        suggestion=suggestion,
                        code_snippet=lines[line_num - 1].strip() if line_num <= len(lines) else "",
                    )
                )

        return violations


def create_hallucination_guards() -> List[Guard]:
    """Create hallucination detection guards."""
    return [HallucinationGuard()]
