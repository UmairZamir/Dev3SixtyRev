"""
Registry Loader & Validator
============================

Central module for loading, validating, and accessing the COMPREHENSIVE_REGISTRY files.
Provides type-safe access to all platform fields, enums, products, and configurations.

Key Features:
- Load all 5 registry parts into unified structure
- Validate field definitions and extraction patterns
- Track field usage for frontend/backend consistency
- Test extraction patterns against sample inputs
- Generate TypeScript types for frontend
"""

import logging
import re
import yaml

logger = logging.getLogger(__name__)
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Pattern
from enum import Enum


# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================

class FieldType(str, Enum):
    """Supported field types in the registry."""
    STRING = "string"
    NUMBER = "number"
    CURRENCY = "currency"
    DATE = "date"
    YEAR = "year"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"
    TEXT = "text"


class FieldPriority(str, Enum):
    """Field collection priority levels."""
    P0_BLOCKER = "P0_BLOCKER"      # Must collect, cannot proceed without
    P1_QUALIFIER = "P1_QUALIFIER"  # Important for qualification
    P2_ENRICHMENT = "P2_ENRICHMENT"  # Nice to have
    P3_OPTIONAL = "P3_OPTIONAL"    # Optional


@dataclass
class ExtractionPattern:
    """A pattern for extracting field values from conversation text."""
    pattern: str
    confidence: float
    compiled: Optional[Pattern] = None
    
    def __post_init__(self):
        """Compile the regex pattern."""
        try:
            self.compiled = re.compile(self.pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{self.pattern}': {e}")
    
    def extract(self, text: str) -> Optional[Tuple[str, float]]:
        """Extract value from text using this pattern."""
        if self.compiled is None:
            return None
        match = self.compiled.search(text)
        if match:
            # Return first capturing group or full match
            value = match.group(1) if match.groups() else match.group(0)
            return (value, self.confidence)
        return None


@dataclass
class SelectOption:
    """An option for select/multi-select fields."""
    id: str
    display: str
    description: Optional[str] = None
    indicators: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FieldDefinition:
    """Complete definition of a platform field."""
    field_id: str
    display_name: str
    field_type: FieldType
    priority: int = 2
    description: Optional[str] = None
    required: bool = False
    
    # Extraction
    extraction_patterns: List[ExtractionPattern] = field(default_factory=list)
    context_patterns_positive: List[str] = field(default_factory=list)
    context_patterns_negative: List[str] = field(default_factory=list)
    
    # Validation
    valid_range: Optional[Tuple[Any, Any]] = None
    validation_regex: Optional[str] = None
    
    # Options (for select types)
    options: List[SelectOption] = field(default_factory=list)
    
    # Metadata
    source: Optional[str] = None
    premium_impact: Optional[str] = None
    ui_component: Optional[str] = None
    api_parameter: Optional[str] = None
    database_column: Optional[str] = None
    
    # Question variations for conversation
    question_variations: List[str] = field(default_factory=list)
    
    # Related fields
    depends_on: Optional[str] = None
    equivalent_fields: List[str] = field(default_factory=list)
    
    def extract_value(self, text: str) -> Optional[Tuple[Any, float]]:
        """Extract field value from conversation text."""
        # Check negative context patterns first
        text_lower = text.lower()
        for neg_pattern in self.context_patterns_negative:
            if neg_pattern.lower() in text_lower:
                return None
        
        # Try each extraction pattern
        best_result = None
        best_confidence = 0.0
        
        for pattern in self.extraction_patterns:
            result = pattern.extract(text)
            if result and result[1] > best_confidence:
                best_result = result
                best_confidence = result[1]
        
        return best_result
    
    def validate_value(self, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate a field value."""
        if value is None:
            if self.required:
                return False, f"Field '{self.field_id}' is required"
            return True, None
        
        # Range validation
        if self.valid_range:
            min_val, max_val = self.valid_range
            try:
                num_val = float(value)
                if num_val < min_val or num_val > max_val:
                    return False, f"Value {value} outside range [{min_val}, {max_val}]"
            except (TypeError, ValueError):
                pass
        
        # Regex validation
        if self.validation_regex:
            if not re.match(self.validation_regex, str(value)):
                return False, f"Value '{value}' doesn't match pattern"
        
        # Select validation
        if self.field_type in (FieldType.SELECT, FieldType.MULTI_SELECT):
            valid_ids = {opt.id for opt in self.options}
            if isinstance(value, list):
                for v in value:
                    if v not in valid_ids:
                        return False, f"Invalid option '{v}'"
            elif value not in valid_ids:
                return False, f"Invalid option '{value}'"
        
        return True, None


@dataclass
class EnumDefinition:
    """Definition of a platform enum."""
    enum_id: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    values: List[Dict[str, Any]] = field(default_factory=list)
    source: Optional[str] = None
    ui_component: Optional[str] = None
    api_parameter: Optional[str] = None
    database_column: Optional[str] = None
    
    def get_value_ids(self) -> Set[str]:
        """Get all valid value IDs."""
        return {v.get("id") for v in self.values if v.get("id")}
    
    def is_valid(self, value: str) -> bool:
        """Check if a value is valid for this enum."""
        return value in self.get_value_ids()


@dataclass
class ProductDefinition:
    """Definition of a product with its fields."""
    product_id: str
    display_name: str
    category: Optional[str] = None
    description: Optional[str] = None
    
    required_fields: List[FieldDefinition] = field(default_factory=list)
    optional_fields: List[FieldDefinition] = field(default_factory=list)
    
    # Cross-sell configuration
    cross_sell_triggers: List[Dict[str, Any]] = field(default_factory=list)
    cross_sell_targets: List[str] = field(default_factory=list)
    
    def get_all_fields(self) -> List[FieldDefinition]:
        """Get all fields for this product."""
        return self.required_fields + self.optional_fields
    
    def get_field(self, field_id: str) -> Optional[FieldDefinition]:
        """Get a specific field by ID."""
        for f in self.get_all_fields():
            if f.field_id == field_id:
                return f
        return None


# =============================================================================
# REGISTRY LOADER
# =============================================================================

class RegistryLoader:
    """Loads and parses registry YAML files."""
    
    # Default patterns to exclude from loading (similar to .gitignore)
    # These are reference schemas for development, not runtime configuration
    DEFAULT_EXCLUDED_PATTERNS: List[str] = [
        "COMPREHENSIVE_REGISTRY_PART*.yaml",  # Root-level reference schemas
    ]
    
    def __init__(
        self, 
        registry_dir: Optional[Path] = None,
        excluded_patterns: Optional[List[str]] = None,
    ):
        self.registry_dir = registry_dir or Path(__file__).parent.parent.parent
        self.excluded_patterns = excluded_patterns if excluded_patterns is not None else self.DEFAULT_EXCLUDED_PATTERNS
        self.raw_data: Dict[str, Any] = {}
        self.enums: Dict[str, EnumDefinition] = {}
        self.products: Dict[str, ProductDefinition] = {}
        self.universal_fields: Dict[str, FieldDefinition] = {}
        self.ai_modes: Dict[str, Dict[str, Any]] = {}
        self.channels: Dict[str, Dict[str, Any]] = {}
    
    def _is_excluded(self, file_path: Path) -> bool:
        """Check if a file matches any exclusion pattern."""
        import fnmatch
        filename = file_path.name
        for pattern in self.excluded_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False
        
    def load_all(self) -> None:
        """Load all registry parts."""
        # Load from sdk/registry/data directory (contains minimal test registry)
        sdk_data_dir = Path(__file__).parent / "data"
        if sdk_data_dir.exists():
            for yaml_file in sdk_data_dir.glob("*.yaml"):
                if not self._is_excluded(yaml_file):
                    self._load_file(yaml_file)
        
        # Load from registry subdirectory if it exists
        registry_subdir = self.registry_dir / "registry"
        if registry_subdir.exists():
            for yaml_file in registry_subdir.glob("*.yaml"):
                if not self._is_excluded(yaml_file):
                    self._load_file(yaml_file)
        
        # Load from registry_dir root (respecting exclusions)
        if self.registry_dir.exists():
            for yaml_file in self.registry_dir.glob("*.yaml"):
                if not self._is_excluded(yaml_file):
                    self._load_file(yaml_file)
        
        self._parse_enums()
        self._parse_products()
        self._parse_universal_fields()
        self._parse_ai_modes()
        self._parse_channels()
    
    def _load_file(self, path: Path) -> None:
        """Load a single YAML file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if data:
                self.raw_data.update(data)
    
    def _parse_enums(self) -> None:
        """Parse enum definitions from raw data."""
        core_enums = self.raw_data.get("core_enums", {})
        for enum_id, enum_data in core_enums.items():
            if isinstance(enum_data, dict):
                values = enum_data.get("values", [])
                # Handle nested categories
                categories = enum_data.get("categories", {})
                for cat_values in categories.values():
                    if isinstance(cat_values, list):
                        values.extend(cat_values)
                
                self.enums[enum_id] = EnumDefinition(
                    enum_id=enum_id,
                    display_name=enum_data.get("display_name"),
                    description=enum_data.get("description"),
                    values=values,
                    source=enum_data.get("source"),
                    ui_component=enum_data.get("ui_component"),
                    api_parameter=enum_data.get("api_parameter"),
                    database_column=enum_data.get("database_column"),
                )
    
    def _parse_field(self, field_data: Dict[str, Any]) -> FieldDefinition:
        """Parse a single field definition."""
        # Parse extraction patterns
        patterns = []
        raw_patterns = field_data.get("extraction_patterns", [])
        if isinstance(raw_patterns, dict):
            for pattern_group in raw_patterns.values():
                if isinstance(pattern_group, dict):
                    for p in pattern_group.get("patterns", []):
                        conf = pattern_group.get("confidence", 0.8)
                        try:
                            patterns.append(ExtractionPattern(pattern=p, confidence=conf))
                        except ValueError as e:
                            logger.warning("Invalid extraction pattern '%s': %s", p, e)
        elif isinstance(raw_patterns, list):
            for p in raw_patterns:
                if isinstance(p, str):
                    patterns.append(ExtractionPattern(pattern=p, confidence=0.8))
        
        # Parse options
        options = []
        for opt_data in field_data.get("options", []):
            if isinstance(opt_data, dict):
                options.append(SelectOption(
                    id=opt_data.get("id", ""),
                    display=opt_data.get("display", opt_data.get("display_name", "")),
                    description=opt_data.get("description"),
                    indicators=opt_data.get("indicators", []),
                    metadata={k: v for k, v in opt_data.items() 
                             if k not in ("id", "display", "display_name", "description", "indicators")},
                ))
        
        # Parse context patterns
        context = field_data.get("context_patterns", {})
        positive = context.get("positive", []) if isinstance(context, dict) else []
        negative = context.get("negative", []) if isinstance(context, dict) else []
        
        # Parse valid range
        valid_range = None
        if "valid_range" in field_data:
            vr = field_data["valid_range"]
            if isinstance(vr, (list, tuple)) and len(vr) == 2:
                valid_range = (vr[0], vr[1])
        
        # Determine field type
        field_type_str = field_data.get("field_type", "string")
        try:
            field_type = FieldType(field_type_str)
        except ValueError:
            field_type = FieldType.STRING
        
        return FieldDefinition(
            field_id=field_data.get("field_id", ""),
            display_name=field_data.get("display_name", ""),
            field_type=field_type,
            priority=field_data.get("priority", 2),
            description=field_data.get("description"),
            required=field_data.get("required", False),
            extraction_patterns=patterns,
            context_patterns_positive=positive,
            context_patterns_negative=negative,
            valid_range=valid_range,
            validation_regex=field_data.get("validation_regex"),
            options=options,
            source=field_data.get("source"),
            premium_impact=field_data.get("premium_impact"),
            ui_component=field_data.get("ui_component"),
            api_parameter=field_data.get("api_parameter"),
            database_column=field_data.get("database_column"),
            question_variations=field_data.get("question_variations", []),
            depends_on=field_data.get("depends_on"),
            equivalent_fields=field_data.get("equivalent_fields", []),
        )
    
    def _parse_products(self) -> None:
        """Parse product definitions from raw data."""
        # Look for product definitions in raw data
        product_keys = [
            "auto_insurance", "home_insurance", "life_insurance", 
            "commercial_insurance", "umbrella_insurance",
            "real_estate_buyer", "real_estate_seller", "real_estate_rental",
            "mortgage", "healthcare", "financial_services"
        ]
        
        for key in product_keys:
            if key in self.raw_data:
                product_data = self.raw_data[key]
                if isinstance(product_data, dict):
                    required_fields = [
                        self._parse_field(f) for f in product_data.get("required_fields", [])
                        if isinstance(f, dict)
                    ]
                    optional_fields = [
                        self._parse_field(f) for f in product_data.get("optional_fields", [])
                        if isinstance(f, dict)
                    ]
                    
                    self.products[key] = ProductDefinition(
                        product_id=product_data.get("product_id", key),
                        display_name=product_data.get("display_name", key.replace("_", " ").title()),
                        category=product_data.get("category"),
                        description=product_data.get("description"),
                        required_fields=required_fields,
                        optional_fields=optional_fields,
                        cross_sell_triggers=product_data.get("cross_sell_triggers", []),
                        cross_sell_targets=product_data.get("cross_sell_targets", []),
                    )
    
    def _parse_universal_fields(self) -> None:
        """Parse universal fields that apply across products."""
        universal = self.raw_data.get("universal_fields", {})
        if isinstance(universal, dict):
            for field_id, field_data in universal.items():
                if isinstance(field_data, dict):
                    field_data["field_id"] = field_id
                    self.universal_fields[field_id] = self._parse_field(field_data)
    
    def _parse_ai_modes(self) -> None:
        """Parse AI mode configurations."""
        modes = self.raw_data.get("ai_mode_configuration", {})
        if isinstance(modes, dict):
            self.ai_modes = modes
    
    def _parse_channels(self) -> None:
        """Parse channel configurations."""
        channel_enum = self.enums.get("channel")
        if channel_enum:
            for value in channel_enum.values:
                if isinstance(value, dict) and "id" in value:
                    self.channels[value["id"]] = value


# =============================================================================
# SINGLETON REGISTRY
# =============================================================================

_registry: Optional["Registry"] = None


class Registry:
    """
    Central registry providing access to all platform definitions.
    
    Usage:
        registry = get_registry()
        field = registry.get_field("auto_insurance", "driver_age")
        value, confidence = field.extract_value("I'm 35 years old")
    """
    
    def __init__(
        self, 
        registry_dir: Optional[Path] = None,
        excluded_patterns: Optional[List[str]] = None,
    ):
        self.loader = RegistryLoader(registry_dir, excluded_patterns)
        self.loader.load_all()
        self._field_usage: Dict[str, Set[str]] = {}  # field_id -> set of usage locations
        
    @property
    def enums(self) -> Dict[str, EnumDefinition]:
        return self.loader.enums
    
    @property
    def products(self) -> Dict[str, ProductDefinition]:
        return self.loader.products
    
    @property
    def universal_fields(self) -> Dict[str, FieldDefinition]:
        return self.loader.universal_fields
    
    @property
    def ai_modes(self) -> Dict[str, Dict[str, Any]]:
        return self.loader.ai_modes
    
    @property
    def channels(self) -> Dict[str, Dict[str, Any]]:
        return self.loader.channels
    
    def get_enum(self, enum_id: str) -> Optional[EnumDefinition]:
        """Get an enum definition by ID."""
        return self.enums.get(enum_id)
    
    def get_product(self, product_id: str) -> Optional[ProductDefinition]:
        """Get a product definition by ID."""
        return self.products.get(product_id)
    
    def get_field(self, product_id: str, field_id: str) -> Optional[FieldDefinition]:
        """Get a field definition from a product."""
        product = self.get_product(product_id)
        if product:
            return product.get_field(field_id)
        return None
    
    def get_universal_field(self, field_id: str) -> Optional[FieldDefinition]:
        """Get a universal field definition."""
        return self.universal_fields.get(field_id)
    
    def get_ai_mode(self, mode_id: str) -> Optional[Dict[str, Any]]:
        """Get AI mode configuration."""
        return self.ai_modes.get(mode_id)
    
    def get_channel(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel configuration."""
        return self.channels.get(channel_id)
    
    def find_equivalent_fields(self, field_id: str) -> List[Tuple[str, str]]:
        """
        Find equivalent fields across products.
        Returns list of (product_id, field_id) tuples.
        """
        results = []
        for product_id, product in self.products.items():
            for f in product.get_all_fields():
                if field_id in f.equivalent_fields or f.field_id == field_id:
                    results.append((product_id, f.field_id))
        return results
    
    def track_field_usage(self, field_id: str, location: str) -> None:
        """Track where a field is being used (for consistency checking)."""
        if field_id not in self._field_usage:
            self._field_usage[field_id] = set()
        self._field_usage[field_id].add(location)
    
    def get_field_usage(self, field_id: str) -> Set[str]:
        """Get all locations where a field is used."""
        return self._field_usage.get(field_id, set())
    
    def get_all_field_ids(self) -> Set[str]:
        """Get all field IDs across all products."""
        field_ids = set(self.universal_fields.keys())
        for product in self.products.values():
            for f in product.get_all_fields():
                field_ids.add(f.field_id)
        return field_ids
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_fields = 0
        total_patterns = 0
        total_options = 0
        
        for product in self.products.values():
            for f in product.get_all_fields():
                total_fields += 1
                total_patterns += len(f.extraction_patterns)
                total_options += len(f.options)
        
        return {
            "enums": len(self.enums),
            "enum_values": sum(len(e.values) for e in self.enums.values()),
            "products": len(self.products),
            "universal_fields": len(self.universal_fields),
            "product_fields": total_fields,
            "extraction_patterns": total_patterns,
            "select_options": total_options,
            "ai_modes": len(self.ai_modes),
            "channels": len(self.channels),
        }


def get_registry(
    registry_dir: Optional[Path] = None,
    excluded_patterns: Optional[List[str]] = None,
) -> Registry:
    """Get the singleton registry instance."""
    global _registry
    if _registry is None:
        _registry = Registry(registry_dir, excluded_patterns)
    return _registry


def reload_registry(
    registry_dir: Optional[Path] = None,
    excluded_patterns: Optional[List[str]] = None,
) -> Registry:
    """Force reload of the registry."""
    global _registry
    _registry = Registry(registry_dir, excluded_patterns)
    return _registry
