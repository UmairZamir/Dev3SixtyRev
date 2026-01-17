"""
Registry Module
===============

Central module for working with COMPREHENSIVE_REGISTRY files.

Components:
- loader: Load and parse registry YAML files
- validator: Validate registry consistency
- extraction_tester: Test extraction patterns
- typescript_generator: Generate frontend types

Usage:
    from sdk.registry import get_registry, validate_registry, run_standard_tests

    # Get registry
    registry = get_registry()
    
    # Get a field
    field = registry.get_field("auto_insurance", "driver_age")
    
    # Extract value from text
    result = field.extract_value("I'm 35 years old")
    if result:
        value, confidence = result
        print(f"Extracted: {value} (confidence: {confidence})")
    
    # Validate registry
    result = validate_registry()
    print(result.format_report())
    
    # Test extraction patterns
    result = run_standard_tests()
    print(result.format_report())
"""

from .loader import (
    Registry,
    get_registry,
    reload_registry,
    FieldDefinition,
    FieldType,
    FieldPriority,
    ProductDefinition,
    EnumDefinition,
    ExtractionPattern,
    SelectOption,
)

from .validator import (
    RegistryValidator,
    validate_registry,
    ValidationResult,
    ValidationIssue,
)

from .extraction_tester import (
    ExtractionTester,
    ExtractionTestCase,
    ExtractionTestResult,
    ExtractionTestSuiteResult,
    get_standard_test_cases,
    run_standard_tests,
)

from .typescript_generator import (
    TypeScriptGenerator,
    FieldUsageTracker,
    generate_typescript_types,
)

__all__ = [
    # Loader
    "Registry",
    "get_registry",
    "reload_registry",
    "FieldDefinition",
    "FieldType",
    "FieldPriority",
    "ProductDefinition",
    "EnumDefinition",
    "ExtractionPattern",
    "SelectOption",
    # Validator
    "RegistryValidator",
    "validate_registry",
    "ValidationResult",
    "ValidationIssue",
    # Extraction Tester
    "ExtractionTester",
    "ExtractionTestCase",
    "ExtractionTestResult",
    "ExtractionTestSuiteResult",
    "get_standard_test_cases",
    "run_standard_tests",
    # TypeScript Generator
    "TypeScriptGenerator",
    "FieldUsageTracker",
    "generate_typescript_types",
]
