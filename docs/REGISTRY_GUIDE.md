# Registry System Guide

This guide covers how to work with the COMPREHENSIVE_REGISTRY files in the 3SixtyRev platform.

## Overview

The registry system provides:
1. **Type-safe access** to all platform fields, enums, and products
2. **Extraction pattern testing** to validate field extraction from conversation text
3. **Validation** to ensure registry consistency
4. **TypeScript generation** for frontend/backend alignment
5. **Usage tracking** to ensure fields are used consistently

## Registry Files

The registry is split across 5 YAML files:

| File | Contents |
|------|----------|
| `COMPREHENSIVE_REGISTRY_PART1.yaml` | Core enums (ai_mode, channel, etc.), conversation outcomes |
| `COMPREHENSIVE_REGISTRY_PART2.yaml` | Insurance product fields, Real Estate fields |
| `COMPREHENSIVE_REGISTRY_PART3.yaml` | AI mode configurations, channel constraints, personas |
| `COMPREHENSIVE_REGISTRY_PART4.yaml` | Sales intelligence, persuasion tactics |
| `COMPREHENSIVE_REGISTRY_PART5.yaml` | Additional products and configurations |

## Quick Start

### Loading the Registry

```python
from sdk.registry import get_registry

# Get singleton registry instance
registry = get_registry()

# Get statistics
stats = registry.get_statistics()
print(f"Loaded {stats['products']} products with {stats['product_fields']} fields")
```

### Accessing Enums

```python
# Get AI mode enum
ai_mode = registry.get_enum("ai_mode")
assert ai_mode.is_valid("assistant")

# Get all valid values
valid_modes = ai_mode.get_value_ids()
# {'assistant', 'agent', 'service'}
```

### Accessing Products and Fields

```python
# Get a product
auto_insurance = registry.get_product("auto_insurance")
print(f"Required fields: {len(auto_insurance.required_fields)}")

# Get a specific field
driver_age = registry.get_field("auto_insurance", "driver_age")
print(f"Field type: {driver_age.field_type}")
print(f"Valid range: {driver_age.valid_range}")
```

### Extracting Values from Text

```python
# Extract field value from conversation text
field = registry.get_field("auto_insurance", "driver_age")
result = field.extract_value("I'm 35 years old")

if result:
    value, confidence = result
    print(f"Extracted: {value} (confidence: {confidence})")
# Output: Extracted: 35 (confidence: 0.95)
```

### Validating the Registry

```python
from sdk.registry import validate_registry

result = validate_registry()
print(result.format_report())

if not result.passed:
    for error in result.errors:
        print(f"ERROR: {error}")
```

### Testing Extraction Patterns

```python
from sdk.registry import run_standard_tests

result = run_standard_tests()
print(result.format_report())

print(f"Pass rate: {result.pass_rate:.1%}")
```

### Generating TypeScript Types

```python
from sdk.registry import generate_typescript_types
from pathlib import Path

# Generate and write to file
generate_typescript_types(output_path=Path("src/types/registry.ts"))

# Or get as string
ts_code = generate_typescript_types()
print(ts_code)
```

## CLI Commands

The registry module provides CLI commands:

```bash
# Validate registry
3sr registry validate

# Test extraction patterns
3sr registry test-extraction

# Generate TypeScript types
3sr registry generate-types -o src/types/registry.ts

# Show statistics
3sr registry stats

# List enums
3sr registry list-enums

# List products
3sr registry list-products

# Show field details
3sr registry show-field auto_insurance driver_age

# Check field usage consistency
3sr registry check-usage --backend src/ --frontend frontend/src/
```

## Field Definitions

### Structure

Each field has:

```yaml
field:
  field_id: "driver_age"
  display_name: "Driver Age"
  field_type: number
  priority: 1  # 1=blocker, 2=qualifier, 3=enrichment, 4=optional
  required: true
  
  extraction_patterns:
    explicit:
      patterns:
        - "(\d+)\s*years?\s*old"
        - "age\s*(?:is|:)?\s*(\d+)"
      confidence: 0.95
      
  valid_range: [16, 120]
  
  context_patterns:
    positive: ["primary driver", "driver age"]
    negative: ["car", "vehicle", "model"]  # Prevent confusion with vehicle year
    
  question_variations:
    - "How old is the primary driver?"
    - "And what's your age?"
```

### Field Types

| Type | TypeScript | Description |
|------|------------|-------------|
| `string` | `string` | Basic text |
| `number` | `number` | Numeric value |
| `currency` | `number` | Money value |
| `date` | `string` | ISO date string |
| `year` | `number` | Year value |
| `boolean` | `boolean` | True/false |
| `select` | `string` (union) | Single selection |
| `multi_select` | `string[]` | Multiple selections |
| `address` | `Address` | Structured address |
| `phone` | `string` | Phone number |
| `email` | `string` | Email address |

### Extraction Patterns

Patterns use Python regex with capturing groups:

```yaml
extraction_patterns:
  explicit:
    patterns:
      - "(?:built|constructed)\s+(?:in\s+)?(\d{4})"
    confidence: 0.95
    
  context_based:
    patterns:
      - "(?:it's|it is)\s+(?:a\s+)?(\d{4})\s+(?:home|house)"
    confidence: 0.85
```

**Best Practices:**
- Use capturing groups `(\d+)` for the value
- Set appropriate confidence (0.0-1.0)
- Use context patterns to prevent false positives

## AI Mode Configurations

```python
# Get AI mode configuration
assistant = registry.get_ai_mode("assistant")

# Check authority
pricing_authority = assistant["authority_matrix"]["pricing"]
print(f"Pricing level: {pricing_authority['level']}")  # 'cannot_quote'

# Get forbidden phrases
forbidden = assistant.get("forbidden_phrases", {})
for category, phrases in forbidden.items():
    print(f"{category}: {phrases}")
```

## Channel Configurations

```python
# Get channel constraints
voice = registry.get_channel("voice")
constraints = voice.get("constraints", {})

print(f"Target duration: {constraints.get('target_duration_min')} minutes")
print(f"Fillers enabled: {constraints.get('fillers_enabled')}")
```

## Cross-Field Intelligence

### Equivalent Fields

Fields can declare equivalents to avoid re-asking:

```yaml
field:
  field_id: "driver_name"
  equivalent_fields:
    - "homeowner_name"
    - "contact_name"
```

```python
# Find equivalent fields across products
equivalents = registry.find_equivalent_fields("driver_name")
# [('home_insurance', 'homeowner_name'), ('life_insurance', 'contact_name')]
```

### Field Dependencies

```yaml
field:
  field_id: "rental_income"
  depends_on: "ownership_type"  # Only ask if ownership_type == "rental"
```

## Frontend Integration

### Generated Types

```typescript
// Auto-generated from registry
export type AiMode = 'assistant' | 'agent' | 'service';

export interface AutoInsuranceFields {
  /** Driver Age (required) */
  driverAge: number;
  /** Vehicle Year (required) */
  vehicleYear: number;
  /** Vehicle Make (optional) */
  vehicleMake?: string;
}

export interface FieldValue<T = unknown> {
  value: T;
  confidence: number;
  source: 'extracted' | 'user_provided' | 'inferred' | 'default';
  timestamp: string;
}
```

### Usage Tracking

```python
from sdk.registry import FieldUsageTracker, get_registry

tracker = FieldUsageTracker(get_registry())

# Scan codebase
tracker.scan_python_files(Path("src/"))
tracker.scan_typescript_files(Path("frontend/src/"))

# Get consistency report
report = tracker.get_consistency_report()
print(f"Fields only in backend: {report['backend_only']}")
print(f"Fields only in frontend: {report['frontend_only']}")
```

## Testing

### Standard Test Cases

The module includes standard test cases:

```python
from sdk.registry import get_standard_test_cases, ExtractionTester

# Get built-in test cases
cases = get_standard_test_cases()
print(f"Standard tests: {len(cases)}")

# Run them
tester = ExtractionTester()
tester.test_cases = cases
result = tester.run_all()
```

### Custom Test Cases

```python
from sdk.registry import ExtractionTester, ExtractionTestCase

tester = ExtractionTester()

# Add custom tests
tester.add_test(ExtractionTestCase(
    name="custom_age_test",
    input_text="My wife is the primary driver and she's 42",
    field_id="driver_age",
    product_id="auto_insurance",
    expected_value="42",
))

result = tester.run_all()
print(result.format_report())
```

### Negative Tests

Test that values are NOT extracted inappropriately:

```python
# Ensure vehicle year isn't extracted for home questions
tester.add_test(ExtractionTestCase(
    name="no_vehicle_year_for_home",
    input_text="I drive a 2020 Honda to my house",
    field_id="year_built",
    product_id="home_insurance",
    expected_extracted=False,  # Should NOT extract
))
```

## Best Practices

1. **Always validate** after registry changes
2. **Run extraction tests** to catch regressions
3. **Generate TypeScript** when fields change
4. **Use context patterns** to prevent cross-field confusion
5. **Track field usage** to ensure consistency
6. **Add test cases** for new extraction patterns
