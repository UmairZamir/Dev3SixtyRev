"""
Extraction Pattern Tester
=========================

Tests extraction patterns against sample conversation text.
Ensures field extraction works correctly for:
- All defined patterns
- Edge cases
- Cross-field disambiguation
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from .loader import Registry, get_registry, FieldDefinition, ExtractionPattern


@dataclass
class ExtractionTestCase:
    """A single extraction test case."""
    name: str
    input_text: str
    field_id: str
    product_id: str
    expected_value: Optional[Any] = None
    expected_extracted: bool = True
    min_confidence: float = 0.7
    description: Optional[str] = None


@dataclass
class ExtractionTestResult:
    """Result of a single extraction test."""
    test_case: ExtractionTestCase
    passed: bool
    extracted_value: Optional[Any] = None
    confidence: float = 0.0
    error: Optional[str] = None
    pattern_matched: Optional[str] = None


@dataclass
class ExtractionTestSuiteResult:
    """Result of running a test suite."""
    passed: int
    failed: int
    total: int
    results: List[ExtractionTestResult] = field(default_factory=list)
    
    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0
    
    def format_report(self) -> str:
        """Format test results as a report."""
        lines = [
            "",
            "═" * 60,
            "        EXTRACTION PATTERN TEST REPORT",
            "═" * 60,
            "",
            f"Total: {self.total} | Passed: {self.passed} | Failed: {self.failed}",
            f"Pass Rate: {self.pass_rate:.1%}",
            "",
        ]
        
        # Failed tests
        failed_results = [r for r in self.results if not r.passed]
        if failed_results:
            lines.append("❌ FAILED TESTS:")
            for result in failed_results:
                tc = result.test_case
                lines.append(f"  • {tc.name}")
                lines.append(f"    Input: \"{tc.input_text[:50]}...\"" if len(tc.input_text) > 50 else f"    Input: \"{tc.input_text}\"")
                lines.append(f"    Expected: {tc.expected_value}")
                lines.append(f"    Got: {result.extracted_value} (conf: {result.confidence:.2f})")
                if result.error:
                    lines.append(f"    Error: {result.error}")
                lines.append("")
        
        # Passed tests summary
        passed_results = [r for r in self.results if r.passed]
        if passed_results:
            lines.append(f"✅ PASSED TESTS: {len(passed_results)}")
            for result in passed_results[:5]:  # Show first 5
                lines.append(f"  • {result.test_case.name}")
            if len(passed_results) > 5:
                lines.append(f"  ... and {len(passed_results) - 5} more")
        
        lines.append("")
        lines.append("═" * 60)
        return "\n".join(lines)


class ExtractionTester:
    """Tests extraction patterns against sample inputs."""
    
    def __init__(self, registry: Optional[Registry] = None):
        self.registry = registry or get_registry()
        self.test_cases: List[ExtractionTestCase] = []
        
    def add_test(self, test_case: ExtractionTestCase) -> None:
        """Add a test case."""
        self.test_cases.append(test_case)
    
    def add_tests_from_registry(self) -> None:
        """
        Add test cases from extraction_examples in the registry.

        Extraction examples would be defined in the YAML as:
            extraction_examples:
              - input: "I'm 35 years old"
                expected: "35"
              - input: "I'll be 40 next month"
                expected: "39"
        """
        for product_id, product in self.registry.products.items():
            for f in product.get_all_fields():
                # Look for extraction_examples in field's question_variations
                # as a fallback, we can test that patterns extract something from variations
                if f.extraction_patterns and f.question_variations:
                    for i, variation in enumerate(f.question_variations[:3]):
                        # Create test case using question variation as context
                        # These are exploratory tests - just checking patterns don't error
                        test_case = ExtractionTestCase(
                            name=f"{product_id}.{f.field_id}_variation_{i}",
                            input_text=variation,
                            field_id=f.field_id,
                            product_id=product_id,
                            expected_extracted=False,  # Variations are questions, not answers
                            min_confidence=0.0,
                        )
                        self.test_cases.append(test_case)
    
    def run_test(self, test_case: ExtractionTestCase) -> ExtractionTestResult:
        """Run a single extraction test."""
        # Get the field
        field = self.registry.get_field(test_case.product_id, test_case.field_id)
        if not field:
            return ExtractionTestResult(
                test_case=test_case,
                passed=False,
                error=f"Field '{test_case.field_id}' not found in product '{test_case.product_id}'",
            )
        
        # Try to extract
        result = field.extract_value(test_case.input_text)
        
        if result is None:
            extracted_value = None
            confidence = 0.0
        else:
            extracted_value, confidence = result
        
        # Determine if test passed
        passed = False
        error = None
        
        if test_case.expected_extracted:
            # We expected extraction
            if extracted_value is None:
                error = "Expected extraction but got None"
            elif test_case.expected_value is not None:
                # Check specific value
                if str(extracted_value).lower() == str(test_case.expected_value).lower():
                    if confidence >= test_case.min_confidence:
                        passed = True
                    else:
                        error = f"Confidence {confidence:.2f} below minimum {test_case.min_confidence}"
                else:
                    error = f"Value mismatch: expected '{test_case.expected_value}', got '{extracted_value}'"
            else:
                # Just check something was extracted
                if confidence >= test_case.min_confidence:
                    passed = True
                else:
                    error = f"Confidence {confidence:.2f} below minimum {test_case.min_confidence}"
        else:
            # We expected NO extraction
            if extracted_value is None:
                passed = True
            else:
                error = f"Expected no extraction but got '{extracted_value}'"
        
        return ExtractionTestResult(
            test_case=test_case,
            passed=passed,
            extracted_value=extracted_value,
            confidence=confidence,
            error=error,
        )
    
    def run_all(self) -> ExtractionTestSuiteResult:
        """Run all test cases."""
        results = []
        passed = 0
        failed = 0
        
        for test_case in self.test_cases:
            result = self.run_test(test_case)
            results.append(result)
            if result.passed:
                passed += 1
            else:
                failed += 1
        
        return ExtractionTestSuiteResult(
            passed=passed,
            failed=failed,
            total=len(results),
            results=results,
        )
    
    def test_field_patterns(
        self, 
        product_id: str, 
        field_id: str, 
        test_inputs: List[Tuple[str, Any]]
    ) -> ExtractionTestSuiteResult:
        """
        Test a specific field with multiple inputs.
        
        Args:
            product_id: Product containing the field
            field_id: Field to test
            test_inputs: List of (input_text, expected_value) tuples
        """
        results = []
        
        for i, (input_text, expected_value) in enumerate(test_inputs):
            test_case = ExtractionTestCase(
                name=f"{product_id}.{field_id}_test_{i}",
                input_text=input_text,
                field_id=field_id,
                product_id=product_id,
                expected_value=expected_value,
            )
            result = self.run_test(test_case)
            results.append(result)
        
        passed = sum(1 for r in results if r.passed)
        
        return ExtractionTestSuiteResult(
            passed=passed,
            failed=len(results) - passed,
            total=len(results),
            results=results,
        )


# =============================================================================
# STANDARD TEST CASES
# =============================================================================

def get_standard_test_cases() -> List[ExtractionTestCase]:
    """Get standard extraction test cases from the registry."""
    return [
        # Driver Age Tests
        ExtractionTestCase(
            name="driver_age_explicit",
            input_text="I'm 35 years old",
            field_id="driver_age",
            product_id="auto_insurance",
            expected_value="35",
        ),
        ExtractionTestCase(
            name="driver_age_natural",
            input_text="Well, I'll be 40 next month",
            field_id="driver_age",
            product_id="auto_insurance",
            expected_value="39",  # Should extract current age
        ),
        ExtractionTestCase(
            name="driver_age_conversational",
            input_text="My husband is the primary driver and he's thirty-five",
            field_id="driver_age",
            product_id="auto_insurance",
            expected_value="35",
        ),
        
        # Year Built Tests
        ExtractionTestCase(
            name="year_built_explicit",
            input_text="The house was built in 1995",
            field_id="year_built",
            product_id="home_insurance",
            expected_value="1995",
        ),
        ExtractionTestCase(
            name="year_built_contextual",
            input_text="It's a 1980 construction",
            field_id="year_built",
            product_id="home_insurance",
            expected_value="1980",
        ),
        ExtractionTestCase(
            name="year_built_negative_car",
            input_text="I drive a 2020 Honda",
            field_id="year_built",
            product_id="home_insurance",
            expected_extracted=False,  # Should NOT extract vehicle year
        ),
        
        # Roof Age Tests
        ExtractionTestCase(
            name="roof_age_years_old",
            input_text="The roof is about 5 years old",
            field_id="roof_age",
            product_id="home_insurance",
            expected_value="5",
        ),
        ExtractionTestCase(
            name="roof_age_replaced",
            input_text="We replaced the roof 3 years ago",
            field_id="roof_age",
            product_id="home_insurance",
            expected_value="3",
        ),
        ExtractionTestCase(
            name="roof_age_new",
            input_text="Brand new roof, just installed this year",
            field_id="roof_age",
            product_id="home_insurance",
            expected_value="0",
        ),
        
        # Square Footage Tests
        ExtractionTestCase(
            name="sqft_explicit",
            input_text="The home is 2500 square feet",
            field_id="square_footage",
            product_id="home_insurance",
            expected_value="2500",
        ),
        ExtractionTestCase(
            name="sqft_abbreviated",
            input_text="About 1800 sq ft",
            field_id="square_footage",
            product_id="home_insurance",
            expected_value="1800",
        ),
        
        # Vehicle Year Tests (should NOT confuse with house year)
        ExtractionTestCase(
            name="vehicle_year_explicit",
            input_text="I have a 2020 Toyota Camry",
            field_id="vehicle_year",
            product_id="auto_insurance",
            expected_value="2020",
        ),
        
        # Property Type Tests (select field)
        ExtractionTestCase(
            name="property_type_single_family",
            input_text="It's a single family home",
            field_id="property_type",
            product_id="home_insurance",
            expected_value="single_family",
        ),
        ExtractionTestCase(
            name="property_type_condo",
            input_text="I live in a condo",
            field_id="property_type",
            product_id="home_insurance",
            expected_value="condo",
        ),
    ]


def run_standard_tests(registry_dir: Optional[Path] = None) -> ExtractionTestSuiteResult:
    """Run standard extraction tests."""
    registry = get_registry(registry_dir)
    tester = ExtractionTester(registry)
    tester.test_cases = get_standard_test_cases()
    return tester.run_all()
