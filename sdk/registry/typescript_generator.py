"""
Frontend Type Generator
=======================

Generates TypeScript types from the registry for frontend/backend consistency.
Ensures the frontend uses the same field definitions, enums, and products.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)

from .loader import Registry, get_registry, FieldDefinition, FieldType


class TypeScriptGenerator:
    """Generates TypeScript types from the registry."""
    
    TYPE_MAPPINGS = {
        FieldType.STRING: "string",
        FieldType.NUMBER: "number",
        FieldType.CURRENCY: "number",
        FieldType.DATE: "string",  # ISO date string
        FieldType.YEAR: "number",
        FieldType.BOOLEAN: "boolean",
        FieldType.SELECT: "string",  # Will be union type
        FieldType.MULTI_SELECT: "string[]",  # Will be union type array
        FieldType.ADDRESS: "Address",
        FieldType.PHONE: "string",
        FieldType.EMAIL: "string",
        FieldType.TEXT: "string",
    }
    
    def __init__(self, registry: Optional[Registry] = None):
        self.registry = registry or get_registry()
    
    def generate_all(self) -> str:
        """Generate all TypeScript types."""
        lines = [
            "// =============================================================================",
            "// AUTO-GENERATED FROM COMPREHENSIVE_REGISTRY - DO NOT EDIT MANUALLY",
            f"// Generated: {datetime.now().isoformat()}",
            "// =============================================================================",
            "",
            "// eslint-disable-next-line @typescript-eslint/no-unused-vars",
            "",
        ]
        
        # Generate common types
        lines.extend(self._generate_common_types())
        lines.append("")
        
        # Generate enums
        lines.extend(self._generate_enums())
        lines.append("")
        
        # Generate field interfaces for each product
        lines.extend(self._generate_product_types())
        lines.append("")
        
        # Generate channel configurations
        lines.extend(self._generate_channel_types())
        lines.append("")
        
        # Generate AI mode types
        lines.extend(self._generate_ai_mode_types())
        
        return "\n".join(lines)
    
    def _generate_common_types(self) -> List[str]:
        """Generate common shared types."""
        return [
            "// =============================================================================",
            "// COMMON TYPES",
            "// =============================================================================",
            "",
            "export interface Address {",
            "  streetAddress: string;",
            "  city: string;",
            "  provinceState: string;",
            "  postalCode: string;",
            "  country?: string;",
            "}",
            "",
            "export interface FieldValue<T = unknown> {",
            "  value: T;",
            "  confidence: number;",
            "  source: 'extracted' | 'user_provided' | 'inferred' | 'default';",
            "  timestamp: string;",
            "}",
            "",
            "export interface CollectedFields {",
            "  [fieldId: string]: FieldValue;",
            "}",
            "",
            "export type Priority = 1 | 2 | 3 | 4;",
        ]
    
    def _generate_enums(self) -> List[str]:
        """Generate TypeScript enums from registry enums."""
        lines = [
            "// =============================================================================",
            "// ENUMS",
            "// =============================================================================",
            "",
        ]
        
        for enum_id, enum_def in self.registry.enums.items():
            # Convert to PascalCase
            type_name = self._to_pascal_case(enum_id)
            
            # Get all value IDs
            value_ids = []
            for value in enum_def.values:
                if isinstance(value, dict) and "id" in value:
                    value_ids.append(value["id"])
            
            if value_ids:
                # Generate union type
                union_values = " | ".join(f"'{v}'" for v in value_ids)
                lines.append(f"export type {type_name} = {union_values};")
                lines.append("")
                
                # Generate enum object for runtime access
                lines.append(f"export const {type_name}Values = [")
                for v in value_ids:
                    lines.append(f"  '{v}',")
                lines.append(f"] as const;")
                lines.append("")
        
        return lines
    
    def _generate_product_types(self) -> List[str]:
        """Generate TypeScript interfaces for each product's fields."""
        lines = [
            "// =============================================================================",
            "// PRODUCT FIELD TYPES",
            "// =============================================================================",
            "",
        ]
        
        for product_id, product in self.registry.products.items():
            type_name = self._to_pascal_case(product_id) + "Fields"
            
            lines.append(f"/** Fields for {product.display_name} */")
            lines.append(f"export interface {type_name} {{")
            
            for f in product.required_fields:
                ts_type = self._get_ts_type(f)
                lines.append(f"  /** {f.display_name} (required) */")
                lines.append(f"  {self._to_camel_case(f.field_id)}: {ts_type};")
            
            for f in product.optional_fields:
                ts_type = self._get_ts_type(f)
                lines.append(f"  /** {f.display_name} (optional) */")
                lines.append(f"  {self._to_camel_case(f.field_id)}?: {ts_type};")
            
            lines.append("}")
            lines.append("")
        
        # Generate union of all products
        if self.registry.products:
            product_type_names = [
                self._to_pascal_case(p) + "Fields" 
                for p in self.registry.products.keys()
            ]
            lines.append("export type ProductFields = " + " | ".join(product_type_names) + ";")
            lines.append("")
        
        return lines
    
    def _generate_channel_types(self) -> List[str]:
        """Generate TypeScript types for channel configurations."""
        lines = [
            "// =============================================================================",
            "// CHANNEL CONFIGURATION TYPES",
            "// =============================================================================",
            "",
            "export interface ChannelConstraints {",
            "  /** Maximum characters per message */",
            "  maxChars?: number;",
            "  /** Minimum word count */",
            "  wordCountMin?: number;",
            "  /** Maximum word count */",
            "  wordCountMax?: number;",
            "  /** Whether fillers are enabled (voice) */",
            "  fillersEnabled?: boolean;",
            "  /** Target response duration in minutes (voice) */",
            "  targetDurationMin?: number;",
            "  /** Max duration in minutes (voice) */",
            "  maxDurationMin?: number;",
            "  /** Typing indicators enabled (chat) */",
            "  typingIndicators?: boolean;",
            "  /** Delay before response in ms */",
            "  delayBeforeResponseMs?: number;",
            "}",
            "",
            "export interface ChannelConfig {",
            "  id: Channel;",
            "  displayName: string;",
            "  constraints: ChannelConstraints;",
            "}",
            "",
        ]
        
        return lines
    
    def _generate_ai_mode_types(self) -> List[str]:
        """Generate TypeScript types for AI mode configurations."""
        lines = [
            "// =============================================================================",
            "// AI MODE TYPES",
            "// =============================================================================",
            "",
            "export type AuthorityLevel = ",
            "  | 'cannot_quote'",
            "  | 'cannot_recommend'",
            "  | 'cannot_bind'",
            "  | 'can_schedule'",
            "  | 'full'",
            "  | 'limited'",
            "  | 'always_required'",
            "  | 'as_needed'",
            "  | 'optional';",
            "",
            "export interface AuthorityMatrix {",
            "  pricing: { level: AuthorityLevel; allowedActions: string[]; forbiddenActions: string[]; };",
            "  recommendations: { level: AuthorityLevel; allowedActions: string[]; forbiddenActions: string[]; };",
            "  binding: { level: AuthorityLevel; allowedActions: string[]; forbiddenActions: string[]; };",
            "  appointments: { level: AuthorityLevel; allowedActions: string[]; };",
            "  handoff: { level: AuthorityLevel; };",
            "}",
            "",
            "export interface AIModeConfig {",
            "  id: AiMode;",
            "  displayName: string;",
            "  description: string;",
            "  type: 'qualitative' | 'quantitative' | 'reactive';",
            "  authorityMatrix: AuthorityMatrix;",
            "  maxAggressiveness: number;",
            "  allowedIndustries: string[];",
            "  blockedIndustries: string[];",
            "  forbiddenPhrases: Record<string, string[]>;",
            "}",
            "",
        ]
        
        return lines
    
    def _get_ts_type(self, field: FieldDefinition) -> str:
        """Get TypeScript type for a field."""
        if field.field_type in (FieldType.SELECT, FieldType.MULTI_SELECT):
            # Generate union type from options
            if field.options:
                option_ids = [opt.id for opt in field.options]
                union = " | ".join(f"'{id}'" for id in option_ids)
                if field.field_type == FieldType.MULTI_SELECT:
                    return f"({union})[]"
                return union
        
        return self.TYPE_MAPPINGS.get(field.field_type, "unknown")
    
    def _to_pascal_case(self, snake_str: str) -> str:
        """Convert snake_case to PascalCase."""
        components = snake_str.split("_")
        return "".join(x.title() for x in components)
    
    def _to_camel_case(self, snake_str: str) -> str:
        """Convert snake_case to camelCase."""
        components = snake_str.split("_")
        return components[0] + "".join(x.title() for x in components[1:])


class FieldUsageTracker:
    """
    Tracks field usage across codebase for consistency checking.
    Helps ensure frontend and backend use the same field IDs.
    """
    
    def __init__(self, registry: Optional[Registry] = None):
        self.registry = registry or get_registry()
        self.backend_usage: Dict[str, Set[str]] = {}  # field_id -> set of file paths
        self.frontend_usage: Dict[str, Set[str]] = {}  # field_id -> set of file paths
    
    def scan_python_files(self, directory: Path) -> None:
        """Scan Python files for field ID usage."""
        import re
        
        # Patterns to match field ID usage
        patterns = [
            r'field_id\s*=\s*["\'](\w+)["\']',
            r'get_field\([^,]+,\s*["\'](\w+)["\']',
            r'\[["\']([\w_]+)["\']\]',  # Dictionary access
        ]
        
        valid_field_ids = self.registry.get_all_field_ids()
        
        for py_file in directory.rglob("*.py"):
            try:
                content = py_file.read_text()
                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    for match in matches:
                        if match in valid_field_ids:
                            if match not in self.backend_usage:
                                self.backend_usage[match] = set()
                            self.backend_usage[match].add(str(py_file))
            except (OSError, UnicodeDecodeError) as e:
                logger.debug("Could not read %s: %s", py_file, e)
    
    def scan_typescript_files(self, directory: Path) -> None:
        """Scan TypeScript/JavaScript files for field ID usage."""
        import re
        
        patterns = [
            r'fieldId:\s*["\'](\w+)["\']',
            r'fields\.["\']?(\w+)["\']?',
            r'\[["\']([\w_]+)["\']\]',
        ]
        
        valid_field_ids = self.registry.get_all_field_ids()
        
        for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
            for ts_file in directory.rglob(ext):
                try:
                    content = ts_file.read_text()
                    for pattern in patterns:
                        matches = re.findall(pattern, content)
                        for match in matches:
                            # Convert camelCase to snake_case
                            snake_case = self._to_snake_case(match)
                            if snake_case in valid_field_ids:
                                if snake_case not in self.frontend_usage:
                                    self.frontend_usage[snake_case] = set()
                                self.frontend_usage[snake_case].add(str(ts_file))
                except (OSError, UnicodeDecodeError) as e:
                    logger.debug("Could not read %s: %s", ts_file, e)
    
    def get_consistency_report(self) -> Dict[str, any]:
        """Generate a consistency report."""
        all_field_ids = self.registry.get_all_field_ids()
        
        used_in_backend = set(self.backend_usage.keys())
        used_in_frontend = set(self.frontend_usage.keys())
        
        return {
            "total_fields": len(all_field_ids),
            "backend_usage": len(used_in_backend),
            "frontend_usage": len(used_in_frontend),
            "backend_only": used_in_backend - used_in_frontend,
            "frontend_only": used_in_frontend - used_in_backend,
            "unused": all_field_ids - used_in_backend - used_in_frontend,
            "consistent": used_in_backend & used_in_frontend,
        }
    
    def _to_snake_case(self, camel_str: str) -> str:
        """Convert camelCase to snake_case."""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def generate_typescript_types(
    registry_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> str:
    """Generate TypeScript types and optionally write to file."""
    registry = get_registry(registry_dir)
    generator = TypeScriptGenerator(registry)
    types = generator.generate_all()
    
    if output_path:
        output_path.write_text(types)
    
    return types
