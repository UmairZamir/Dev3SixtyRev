"""
Registry Validator
==================

Validates the registry for:
- Schema consistency
- Extraction pattern validity
- Field completeness
- Cross-reference integrity
- Frontend/backend alignment
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path

from .loader import (
    Registry, get_registry, FieldDefinition, ProductDefinition,
    EnumDefinition, ExtractionPattern, FieldType
)


@dataclass
class ValidationIssue:
    """A single validation issue."""
    severity: str  # "error", "warning", "info"
    category: str
    message: str
    location: Optional[str] = None
    field_id: Optional[str] = None
    product_id: Optional[str] = None
    
    def __str__(self) -> str:
        loc = f"[{self.location}] " if self.location else ""
        return f"[{self.severity.upper()}] {self.category}: {loc}{self.message}"


@dataclass
class ValidationResult:
    """Result of validation run."""
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    
    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]
    
    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]
    
    def format_report(self) -> str:
        """Format validation results as a report."""
        lines = [
            "",
            "═" * 60,
            "        REGISTRY VALIDATION REPORT",
            "═" * 60,
            "",
        ]
        
        # Summary
        lines.append(f"Status: {'✅ PASSED' if self.passed else '❌ FAILED'}")
        lines.append(f"Errors: {len(self.errors)}")
        lines.append(f"Warnings: {len(self.warnings)}")
        lines.append("")
        
        # Stats
        if self.stats:
            lines.append("Statistics:")
            for key, value in sorted(self.stats.items()):
                lines.append(f"  • {key}: {value}")
            lines.append("")
        
        # Issues by category
        if self.issues:
            categories: Dict[str, List[ValidationIssue]] = {}
            for issue in self.issues:
                if issue.category not in categories:
                    categories[issue.category] = []
                categories[issue.category].append(issue)
            
            for category, issues in sorted(categories.items()):
                lines.append(f"📁 {category}")
                for issue in issues:
                    icon = "❌" if issue.severity == "error" else "⚠️" if issue.severity == "warning" else "ℹ️"
                    loc = f" ({issue.location})" if issue.location else ""
                    lines.append(f"  {icon} {issue.message}{loc}")
                lines.append("")
        
        lines.append("═" * 60)
        return "\n".join(lines)


class RegistryValidator:
    """Validates registry definitions for consistency and completeness."""
    
    def __init__(self, registry: Optional[Registry] = None):
        self.registry = registry or get_registry()
        self.issues: List[ValidationIssue] = []
        
    def validate_all(self) -> ValidationResult:
        """Run all validations."""
        self.issues = []
        
        # Run all validation checks
        self._validate_enums()
        self._validate_products()
        self._validate_fields()
        self._validate_extraction_patterns()
        self._validate_cross_references()
        self._validate_ai_modes()
        self._validate_channels()
        
        # Build result
        passed = len([i for i in self.issues if i.severity == "error"]) == 0
        
        return ValidationResult(
            passed=passed,
            issues=self.issues,
            stats=self.registry.get_statistics(),
        )
    
    def _add_issue(
        self,
        severity: str,
        category: str,
        message: str,
        location: Optional[str] = None,
        field_id: Optional[str] = None,
        product_id: Optional[str] = None,
    ) -> None:
        """Add a validation issue."""
        self.issues.append(ValidationIssue(
            severity=severity,
            category=category,
            message=message,
            location=location,
            field_id=field_id,
            product_id=product_id,
        ))
    
    def _validate_enums(self) -> None:
        """Validate enum definitions."""
        for enum_id, enum_def in self.registry.enums.items():
            # Check for empty enums
            if not enum_def.values:
                self._add_issue(
                    "warning", "Enum Validation",
                    f"Enum '{enum_id}' has no values",
                    location=enum_id,
                )
            
            # Check for duplicate IDs
            seen_ids: Set[str] = set()
            for value in enum_def.values:
                if isinstance(value, dict):
                    val_id = value.get("id")
                    if val_id:
                        if val_id in seen_ids:
                            self._add_issue(
                                "error", "Enum Validation",
                                f"Duplicate value ID '{val_id}' in enum '{enum_id}'",
                                location=enum_id,
                            )
                        seen_ids.add(val_id)
            
            # Check required metadata
            required_enums = {"ai_mode", "channel", "conversation_outcome"}
            if enum_id in required_enums:
                if not enum_def.ui_component:
                    self._add_issue(
                        "warning", "Enum Validation",
                        f"Required enum '{enum_id}' missing ui_component",
                        location=enum_id,
                    )
    
    def _validate_products(self) -> None:
        """Validate product definitions."""
        for product_id, product in self.registry.products.items():
            # Check for required fields
            if not product.required_fields:
                self._add_issue(
                    "warning", "Product Validation",
                    f"Product '{product_id}' has no required fields",
                    location=product_id,
                    product_id=product_id,
                )
            
            # Check for display name
            if not product.display_name:
                self._add_issue(
                    "warning", "Product Validation",
                    f"Product '{product_id}' missing display_name",
                    location=product_id,
                    product_id=product_id,
                )
            
            # Check field IDs are unique within product
            seen_fields: Set[str] = set()
            for f in product.get_all_fields():
                if f.field_id in seen_fields:
                    self._add_issue(
                        "error", "Product Validation",
                        f"Duplicate field ID '{f.field_id}' in product '{product_id}'",
                        location=f"{product_id}.{f.field_id}",
                        field_id=f.field_id,
                        product_id=product_id,
                    )
                seen_fields.add(f.field_id)
    
    def _validate_fields(self) -> None:
        """Validate field definitions."""
        for product_id, product in self.registry.products.items():
            for f in product.get_all_fields():
                self._validate_single_field(f, product_id)
        
        for field_id, f in self.registry.universal_fields.items():
            self._validate_single_field(f, "universal")
    
    def _validate_single_field(self, field: FieldDefinition, product_id: str) -> None:
        """Validate a single field definition."""
        location = f"{product_id}.{field.field_id}"
        
        # Check for display name
        if not field.display_name:
            self._add_issue(
                "warning", "Field Validation",
                f"Field '{field.field_id}' missing display_name",
                location=location,
                field_id=field.field_id,
                product_id=product_id,
            )
        
        # Check select fields have options
        if field.field_type in (FieldType.SELECT, FieldType.MULTI_SELECT):
            if not field.options:
                self._add_issue(
                    "error", "Field Validation",
                    f"Select field '{field.field_id}' has no options",
                    location=location,
                    field_id=field.field_id,
                    product_id=product_id,
                )
        
        # Check numeric fields have ranges
        if field.field_type in (FieldType.NUMBER, FieldType.YEAR, FieldType.CURRENCY):
            if not field.valid_range:
                self._add_issue(
                    "info", "Field Validation",
                    f"Numeric field '{field.field_id}' has no valid_range",
                    location=location,
                    field_id=field.field_id,
                    product_id=product_id,
                )
        
        # Check required fields have extraction patterns
        if field.required and not field.extraction_patterns:
            self._add_issue(
                "warning", "Field Validation",
                f"Required field '{field.field_id}' has no extraction patterns",
                location=location,
                field_id=field.field_id,
                product_id=product_id,
            )
        
        # Check priority is valid
        if field.priority not in range(1, 5):
            self._add_issue(
                "warning", "Field Validation",
                f"Field '{field.field_id}' has invalid priority {field.priority}",
                location=location,
                field_id=field.field_id,
                product_id=product_id,
            )
    
    def _validate_extraction_patterns(self) -> None:
        """Validate extraction patterns are valid regex."""
        for product_id, product in self.registry.products.items():
            for f in product.get_all_fields():
                for i, pattern in enumerate(f.extraction_patterns):
                    if pattern.compiled is None:
                        self._add_issue(
                            "error", "Pattern Validation",
                            f"Invalid regex in field '{f.field_id}' pattern {i}: {pattern.pattern}",
                            location=f"{product_id}.{f.field_id}",
                            field_id=f.field_id,
                            product_id=product_id,
                        )
                    
                    # Check confidence is valid
                    if not 0.0 <= pattern.confidence <= 1.0:
                        self._add_issue(
                            "warning", "Pattern Validation",
                            f"Pattern confidence {pattern.confidence} out of range [0, 1]",
                            location=f"{product_id}.{f.field_id}",
                            field_id=f.field_id,
                            product_id=product_id,
                        )
    
    def _validate_cross_references(self) -> None:
        """Validate cross-references between fields and products."""
        all_field_ids = self.registry.get_all_field_ids()
        all_product_ids = set(self.registry.products.keys())
        
        for product_id, product in self.registry.products.items():
            # Check depends_on references exist
            for f in product.get_all_fields():
                if f.depends_on:
                    if f.depends_on not in all_field_ids:
                        self._add_issue(
                            "error", "Cross-Reference",
                            f"Field '{f.field_id}' depends_on non-existent field '{f.depends_on}'",
                            location=f"{product_id}.{f.field_id}",
                            field_id=f.field_id,
                            product_id=product_id,
                        )
                
                # Check equivalent_fields exist
                for eq_field in f.equivalent_fields:
                    if eq_field not in all_field_ids:
                        self._add_issue(
                            "warning", "Cross-Reference",
                            f"Equivalent field '{eq_field}' not found in registry",
                            location=f"{product_id}.{f.field_id}",
                            field_id=f.field_id,
                            product_id=product_id,
                        )
            
            # Check cross-sell targets exist
            for target in product.cross_sell_targets:
                if target not in all_product_ids:
                    self._add_issue(
                        "warning", "Cross-Reference",
                        f"Cross-sell target '{target}' not found",
                        location=product_id,
                        product_id=product_id,
                    )
    
    def _validate_ai_modes(self) -> None:
        """Validate AI mode configurations."""
        required_modes = {"assistant", "agent", "service"}
        
        for mode_id in required_modes:
            if mode_id not in self.registry.ai_modes:
                self._add_issue(
                    "error", "AI Mode Validation",
                    f"Required AI mode '{mode_id}' not defined",
                )
            else:
                mode = self.registry.ai_modes[mode_id]
                
                # Check authority matrix
                if "authority_matrix" not in mode:
                    self._add_issue(
                        "warning", "AI Mode Validation",
                        f"AI mode '{mode_id}' missing authority_matrix",
                        location=mode_id,
                    )
                
                # Check forbidden phrases for regulated modes
                if mode_id == "assistant":
                    if "forbidden_phrases" not in mode:
                        self._add_issue(
                            "warning", "AI Mode Validation",
                            f"Assistant mode missing forbidden_phrases",
                            location=mode_id,
                        )
    
    def _validate_channels(self) -> None:
        """Validate channel configurations."""
        required_channels = {"voice", "sms", "email", "chat"}
        
        for channel_id in required_channels:
            if channel_id not in self.registry.channels:
                self._add_issue(
                    "error", "Channel Validation",
                    f"Required channel '{channel_id}' not defined",
                )
            else:
                channel = self.registry.channels[channel_id]
                
                # Check constraints
                if "constraints" not in channel:
                    self._add_issue(
                        "warning", "Channel Validation",
                        f"Channel '{channel_id}' missing constraints",
                        location=channel_id,
                    )


def validate_registry(registry_dir: Optional[Path] = None) -> ValidationResult:
    """Convenience function to validate the registry."""
    registry = get_registry(registry_dir)
    validator = RegistryValidator(registry)
    return validator.validate_all()
