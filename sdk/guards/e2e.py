"""
E2E Guard - No Shell Components
================================

Detects and blocks shell/placeholder implementations:
- Buttons with console.log('TODO')
- Mock/hardcoded data in charts
- Forms without real API submission
- UI components not connected to backend
- Placeholder implementations

ZERO TOLERANCE for shell components.
"""

import re
import time
from pathlib import Path
from typing import List, Optional, Set

from .base import Guard, GuardResult, GuardViolation, GuardLevel, GuardCategory, GuardSeverity


class E2EGuard(Guard):
    """
    Ensures all components are fully implemented E2E.
    No shell components, no placeholders, no mock data.
    """
    
    # Patterns that indicate shell/placeholder implementations
    SHELL_PATTERNS = [
        # TODO/placeholder patterns
        (r'console\.log\s*\(\s*[\'"]TODO', "console.log('TODO') - shell component"),
        (r'console\.log\s*\(\s*[\'"]PLACEHOLDER', "console.log('PLACEHOLDER') - shell component"),
        (r'console\.log\s*\(\s*[\'"]FIXME', "console.log('FIXME') - shell component"),
        (r'console\.log\s*\(\s*[\'"]Not implemented', "console.log('Not implemented') - shell component"),
        (r'alert\s*\(\s*[\'"]TODO', "alert('TODO') - shell component"),
        (r'alert\s*\(\s*[\'"]Not implemented', "alert('Not implemented') - shell component"),
        
        # Empty handlers
        (r'onClick\s*=\s*\{\s*\(\s*\)\s*=>\s*\{\s*\}\s*\}', "Empty onClick handler - shell component"),
        (r'onSubmit\s*=\s*\{\s*\(\s*\)\s*=>\s*\{\s*\}\s*\}', "Empty onSubmit handler - shell component"),
        (r'onChange\s*=\s*\{\s*\(\s*\)\s*=>\s*\{\s*\}\s*\}', "Empty onChange handler - shell component"),
        
        # Mock data patterns
        (r'const\s+\w+\s*=\s*\[\s*\{[^}]*mock', "Mock data in component"),
        (r'const\s+\w+\s*=\s*\[\s*\{[^}]*placeholder', "Placeholder data in component"),
        (r'const\s+\w+\s*=\s*\[\s*\{[^}]*dummy', "Dummy data in component"),
        (r'data\s*:\s*\[\s*\{[^}]*hardcoded', "Hardcoded data instead of API"),
        
        # Fake/mock API calls
        (r'//\s*TODO:\s*connect\s+to\s+(?:real\s+)?API', "TODO: connect to API - shell component"),
        (r'//\s*FIXME:\s*implement\s+API', "FIXME: implement API - shell component"),
        (r'fetch\s*\(\s*[\'"]#', "Fake fetch URL - shell component"),
        (r'axios\.\w+\s*\(\s*[\'"]#', "Fake axios URL - shell component"),
        
        # Explicit shell markers
        (r'//\s*SHELL', "Explicit SHELL marker"),
        (r'//\s*PLACEHOLDER', "Explicit PLACEHOLDER marker"),
        (r'/\*\s*SHELL', "Explicit SHELL block comment"),
        (r'/\*\s*PLACEHOLDER', "Explicit PLACEHOLDER block comment"),
        
        # Python placeholders
        (r'pass\s*#\s*TODO', "pass statement with unfinished work marker"),
        (r'raise\s+NotImplementedError\s*\(\s*\)', "NotImplementedError - incomplete implementation"),
        (r'\.\.\.  # TODO', "ellipsis with unfinished work marker"),

        # Return dummy data
        (r'return\s+\[\s*\]  #\s*TODO', "empty list return with unfinished work marker"),
        (r'return\s+\{\s*\}  #\s*TODO', "empty dict return with unfinished work marker"),
        (r'return\s+None\s*#\s*TODO', "None return with unfinished work marker"),
    ]
    
    # Patterns that indicate hardcoded data that should come from API
    HARDCODED_DATA_PATTERNS = [
        # Chart data
        (r'data\s*:\s*\[\s*\d+\s*,\s*\d+\s*,\s*\d+', "Hardcoded numeric data - should come from API"),
        (r'labels\s*:\s*\[\s*[\'"][^\]]+[\'"]\s*,', "Hardcoded labels - should come from API"),
        
        # Table data
        (r'rows\s*:\s*\[\s*\{[^}]+name\s*:', "Hardcoded table rows - should come from API"),
        (r'items\s*:\s*\[\s*\{[^}]+id\s*:', "Hardcoded items list - should come from API"),
    ]
    
    # File extensions to check
    CHECK_EXTENSIONS = {'.js', '.jsx', '.ts', '.tsx', '.py', '.vue', '.svelte'}
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="e2e",
            description="Block shell components and placeholder implementations",
            level=GuardLevel.INSTANT,
            category=GuardCategory.QUALITY,
            enabled=enabled,
            severity=GuardSeverity.ERROR,
        )
    
    def check(self, content: str, file_path: Optional[str] = None) -> GuardResult:
        """Check for shell components and placeholders."""
        start_time = time.time()
        violations = []
        
        # Convert string path to Path object if provided
        path = Path(file_path) if file_path else None
        
        # Skip non-applicable files
        if path and path.suffix not in self.CHECK_EXTENSIONS:
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        
        # Skip test files (may have mock data intentionally)
        if path and ('test' in path.name.lower() or 'spec' in path.name.lower()):
            return GuardResult(
                guard_name=self.name,
                passed=True,
                violations=[],
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        
        # Skip fixture/mock directories
        if path:
            path_parts = set(path.parts)
            if path_parts & {'__mocks__', 'fixtures', 'mocks', '__fixtures__', 'test_data'}:
                return GuardResult(
                    guard_name=self.name,
                    passed=True,
                    violations=[],
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        
        lines = content.split('\n')
        
        # Check each pattern
        for line_num, line in enumerate(lines, 1):
            # Shell patterns (high severity)
            for pattern, description in self.SHELL_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(GuardViolation(
                        guard_name=self.name,
                        severity=GuardSeverity.ERROR,
                        category=self.category,
                        message=f"Shell component detected: {description}",
                        file_path=file_path,
                        line_number=line_num,
                        column=0,
                        code_snippet=line.strip()[:100],
                        suggestion="Implement full E2E functionality or remove the component",
                    ))
            
            # Hardcoded data patterns (warning - context dependent)
            # Only check in component files, not config files
            if path and not any(x in path.name.lower() for x in ['config', 'constant', 'mock', 'fixture']):
                for pattern, description in self.HARDCODED_DATA_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        violations.append(GuardViolation(
                            guard_name=self.name,
                            severity=GuardSeverity.WARNING,
                            category=self.category,
                            message=f"Potential hardcoded data: {description}",
                            file_path=file_path,
                            line_number=line_num,
                            column=0,
                            code_snippet=line.strip()[:100],
                            suggestion="Fetch data from API instead of hardcoding",
                        ))
        
        # Check for forms without action
        if path and path.suffix in {'.jsx', '.tsx', '.vue'}:
            form_violations = self._check_forms(content, lines, file_path)
            violations.extend(form_violations)
        
        passed = not any(v.severity == GuardSeverity.ERROR for v in violations)
        
        return GuardResult(
            guard_name=self.name,
            passed=passed,
            violations=violations,
            execution_time_ms=(time.time() - start_time) * 1000,
            files_checked=1,
            metadata={
                "file": file_path,
                "shell_patterns_checked": len(self.SHELL_PATTERNS),
            }
        )
    
    def _check_forms(self, content: str, lines: List[str], file_path: Optional[str]) -> List[GuardViolation]:
        """Check for forms that don't submit to real endpoints."""
        violations = []
        
        # Find form tags
        form_pattern = re.compile(r'<form[^>]*>', re.IGNORECASE)
        for line_num, line in enumerate(lines, 1):
            match = form_pattern.search(line)
            if match:
                form_tag = match.group(0)
                
                # Check if form has action or onSubmit
                has_action = 'action=' in form_tag or 'onSubmit=' in form_tag
                
                if not has_action:
                    violations.append(GuardViolation(
                        guard_name=self.name,
                        severity=GuardSeverity.WARNING,
                        category=self.category,
                        message="Form without action or onSubmit handler",
                        file_path=file_path,
                        line_number=line_num,
                        column=match.start(),
                        code_snippet=form_tag[:80],
                        suggestion="Add onSubmit handler that submits to real API",
                    ))
                
                # Check for preventDefault without actual submission
                if 'preventDefault' in content:
                    # Look for fetch/axios call after the form
                    form_section = content[match.start():match.start() + 2000]
                    if 'preventDefault' in form_section and not any(
                        api in form_section for api in ['fetch(', 'axios.', 'api.', 'submitForm', 'handleSubmit']
                    ):
                        violations.append(GuardViolation(
                            guard_name=self.name,
                            severity=GuardSeverity.WARNING,
                            category=self.category,
                            message="Form with preventDefault but no API submission",
                            file_path=file_path,
                            line_number=line_num,
                            column=match.start(),
                            code_snippet="Form blocks default but doesn't submit to API",
                            suggestion="Add API call to submit form data",
                        ))
        
        return violations


# Create the guard instance (for convenience)
def create_e2e_guard() -> E2EGuard:
    """Create an E2E guard instance."""
    return E2EGuard()
