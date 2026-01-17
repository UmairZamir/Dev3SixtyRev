"""
Security Guard
==============

Detects security vulnerabilities in code.

From research: "AI-assisted developers produced 3-4x more code but generated 10x more security issues"

This guard detects:
- Hardcoded secrets (API keys, passwords, tokens)
- SQL injection patterns
- Command injection risks
- Insecure random usage
- Hardcoded cryptographic keys
- Unsafe deserialization
"""

from typing import Dict, List

from sdk.guards.base import (
    GuardCategory,
    GuardLevel,
    GuardSeverity,
    PatternGuard,
)


class SecurityGuard(PatternGuard):
    """Detects security vulnerabilities in code."""

    SECURITY_PATTERNS: Dict[str, str] = {
        # Hardcoded secrets
        r"(?:api[_-]?key|apikey)\s*[=:]\s*['\"][a-zA-Z0-9_\-]{20,}['\"]": (
            "Hardcoded API key detected! Use environment variables: os.environ['API_KEY']"
        ),
        r"(?:secret[_-]?key|secretkey)\s*[=:]\s*['\"][^'\"]{10,}['\"]": (
            "Hardcoded secret key! Use environment variables or secrets manager."
        ),
        r"(?:password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{4,}['\"]": (
            "Hardcoded password detected! NEVER hardcode passwords. Use secrets manager."
        ),
        r"(?:auth[_-]?token|access[_-]?token|bearer)\s*[=:]\s*['\"][^'\"]{10,}['\"]": (
            "Hardcoded auth token! Use environment variables."
        ),
        r"(?:private[_-]?key|priv[_-]?key)\s*[=:]\s*['\"]-----BEGIN": (
            "Hardcoded private key! Store in secure vault, never in code."
        ),
        r"(?:aws[_-]?secret|aws[_-]?access)\s*[=:]\s*['\"][A-Za-z0-9/+=]{20,}['\"]": (
            "Hardcoded AWS credentials! Use IAM roles or environment variables."
        ),
        # Database connection strings with credentials
        r"(?:mysql|postgres|mongodb)://\w+:[^@]+@": (
            "Database credentials in connection string! Use environment variables."
        ),
        r"(?:redis|amqp)://:[^@]+@": (
            "Hardcoded credentials in connection URI! Use environment variables."
        ),
        # SQL injection patterns
        r"(?:execute|cursor\.execute)\s*\(\s*['\"].*%s": (
            "Potential SQL injection with string formatting. Use parameterized queries."
        ),
        r"(?:execute|cursor\.execute)\s*\(\s*f['\"]": (
            "SQL injection risk with f-string! Use parameterized queries instead."
        ),
        r"(?:execute|cursor\.execute)\s*\(\s*['\"].*\+\s*\w+": (
            "SQL injection risk with string concatenation! Use parameterized queries."
        ),
        r"(?:execute|cursor\.execute)\s*\(\s*['\"].*\.format\s*\(": (
            "SQL injection risk with .format()! Use parameterized queries."
        ),
        r"(?:SELECT|INSERT|UPDATE|DELETE)\s+.*\+\s*(?:request|user|input)": (
            "SQL injection: user input concatenated into query!"
        ),
        # Command injection
        r"os\.system\s*\(\s*f['\"]": (
            "Command injection risk with f-string in os.system! Use subprocess with list args."
        ),
        r"os\.system\s*\(\s*['\"].*\+": (
            "Command injection risk! Use subprocess.run() with list arguments."
        ),
        r"subprocess\.(?:call|run|Popen)\s*\(\s*f['\"].*shell\s*=\s*True": (
            "Command injection with shell=True and f-string! Use list args, no shell."
        ),
        r"subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True": (
            "Avoid shell=True in subprocess. Pass command as list instead."
        ),
        r"eval\s*\(\s*(?:request|user|input|data)": (
            "Code injection: eval() with user input! Never eval untrusted data."
        ),
        r"exec\s*\(\s*(?:request|user|input|data)": (
            "Code injection: exec() with user input! Never exec untrusted data."
        ),
        # Unsafe deserialization
        r"pickle\.loads?\s*\(": (
            "Unsafe deserialization with pickle! Use json or validated data formats."
        ),
        r"yaml\.load\s*\([^)]*(?!Loader)": (
            "Unsafe YAML loading! Use yaml.safe_load() or specify Loader=SafeLoader."
        ),
        r"yaml\.load\s*\(\s*[^,]+\s*\)": (
            "yaml.load without Loader is unsafe! Use yaml.safe_load() instead."
        ),
        # Insecure randomness
        r"random\.(?:random|randint|choice|shuffle)\s*\(": (
            "Using random module for security-sensitive operation? Use secrets module instead."
        ),
        # Weak cryptography
        r"hashlib\.(?:md5|sha1)\s*\(": (
            "MD5/SHA1 are cryptographically weak. Use SHA-256 or better for security."
        ),
        r"DES\s*\(|Blowfish\s*\(|RC4\s*\(": (
            "Weak encryption algorithm! Use AES-256 or ChaCha20 instead."
        ),
        # Hardcoded IVs/salts
        r"(?:iv|salt|nonce)\s*=\s*b['\"][^'\"]{8,}['\"]": (
            "Hardcoded IV/salt/nonce! Generate randomly for each operation."
        ),
        # Debug mode in production
        r"DEBUG\s*=\s*True": (
            "DEBUG mode enabled! Ensure this is only in development settings."
        ),
        r"app\.run\s*\([^)]*debug\s*=\s*True": (
            "Flask debug mode enabled! Never use in production."
        ),
        # Insecure file operations
        r"open\s*\(\s*(?:request|user|input)": (
            "Path traversal risk! Validate and sanitize file paths from user input."
        ),
        # CORS misconfiguration
        r"Access-Control-Allow-Origin['\"]:\s*['\"]\\*['\"]": (
            "CORS allows all origins! Specify allowed domains explicitly."
        ),
        r"cors\s*\(\s*[^)]*origins?\s*=\s*['\"]\\*['\"]": (
            "CORS misconfiguration! Don't allow all origins in production."
        ),
        # JWT issues
        r"jwt\.decode\s*\([^)]*verify\s*=\s*False": (
            "JWT signature verification disabled! Always verify JWT signatures."
        ),
        r"jwt\.decode\s*\([^)]*algorithms\s*=\s*\[['\"]none['\"]": (
            "JWT 'none' algorithm allowed! This bypasses signature verification."
        ),
        # Insecure cookies
        r"set_cookie\s*\([^)]*secure\s*=\s*False": (
            "Cookie without Secure flag! Set secure=True for HTTPS."
        ),
        r"set_cookie\s*\([^)]*httponly\s*=\s*False": (
            "Cookie without HttpOnly flag! Set httponly=True to prevent XSS access."
        ),
    }

    def __init__(self, enabled: bool = True):
        patterns = list(self.SECURITY_PATTERNS.keys())
        suggestions = self.SECURITY_PATTERNS

        super().__init__(
            name="security",
            description="Detects security vulnerabilities in code",
            level=GuardLevel.INSTANT,
            category=GuardCategory.SECURITY,
            enabled=enabled,
            severity=GuardSeverity.ERROR,
            patterns=patterns,
            suggestions=suggestions,
        )

        # Exclude test files and example files
        self.add_exception("/tests/")
        self.add_exception("test_")
        self.add_exception("_test.py")
        self.add_exception("/examples/")
        self.add_exception("/docs/")
        self.add_exception("conftest.py")

        # Limit to code files
        self.add_file_extensions([
            ".py", ".js", ".ts", ".jsx", ".tsx",
            ".go", ".java", ".rb", ".php",
            ".yml", ".yaml", ".json",
        ])


def create_security_guards() -> List[PatternGuard]:
    """Create all security guards."""
    return [SecurityGuard()]
