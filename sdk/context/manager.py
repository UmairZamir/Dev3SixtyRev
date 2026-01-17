"""
Context Management
==================

Tools for managing AI context and preventing context-related issues.

From research:
- "Context exhaustion is the #1 failure mode"
- "Lost-in-the-Middle Problem: LLMs recall info from beginning/end but forget middle"
- "Context poisoning: hallucination early in chat gets referenced repeatedly"
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import hashlib


@dataclass
class ContextItem:
    """A single item in context."""
    id: str
    content: str
    source: str  # file, memory, user, system
    added_at: datetime
    tokens_estimate: int
    priority: int = 5  # 1-10, higher = more important
    tags: List[str] = field(default_factory=list)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimation (4 chars per token)."""
        return len(text) // 4


@dataclass
class ContextWindow:
    """Manages context window for AI interactions."""
    max_tokens: int = 200_000
    warning_threshold: float = 0.7  # Warn at 70%
    critical_threshold: float = 0.9  # Critical at 90%

    items: List[ContextItem] = field(default_factory=list)
    _token_count: int = 0

    @property
    def token_count(self) -> int:
        """Current token count."""
        return sum(item.tokens_estimate for item in self.items)

    @property
    def utilization(self) -> float:
        """Context utilization percentage."""
        return self.token_count / self.max_tokens

    @property
    def is_warning(self) -> bool:
        """Check if at warning threshold."""
        return self.utilization >= self.warning_threshold

    @property
    def is_critical(self) -> bool:
        """Check if at critical threshold."""
        return self.utilization >= self.critical_threshold

    def add(
        self,
        content: str,
        source: str,
        priority: int = 5,
        tags: Optional[List[str]] = None,
    ) -> ContextItem:
        """Add item to context."""
        item = ContextItem(
            id=hashlib.sha256(content.encode()).hexdigest()[:8],
            content=content,
            source=source,
            added_at=datetime.now(),
            tokens_estimate=ContextItem.estimate_tokens(content),
            priority=priority,
            tags=tags or [],
        )
        self.items.append(item)
        return item

    def remove(self, item_id: str) -> bool:
        """Remove item from context."""
        for i, item in enumerate(self.items):
            if item.id == item_id:
                self.items.pop(i)
                return True
        return False

    def clear(self) -> None:
        """Clear all context."""
        self.items.clear()

    def compact(self, target_utilization: float = 0.5) -> int:
        """
        Compact context to target utilization.
        Removes lowest priority items first.
        Returns number of items removed.
        """
        if self.utilization <= target_utilization:
            return 0

        # Sort by priority (keep high priority)
        sorted_items = sorted(self.items, key=lambda x: x.priority)

        removed = 0
        while self.utilization > target_utilization and sorted_items:
            item = sorted_items.pop(0)
            self.remove(item.id)
            removed += 1

        return removed

    def get_by_source(self, source: str) -> List[ContextItem]:
        """Get items by source."""
        return [item for item in self.items if item.source == source]

    def get_by_tag(self, tag: str) -> List[ContextItem]:
        """Get items by tag."""
        return [item for item in self.items if tag in item.tags]

    def status(self) -> Dict[str, Any]:
        """Get context status."""
        return {
            "total_tokens": self.token_count,
            "max_tokens": self.max_tokens,
            "utilization": f"{self.utilization * 100:.1f}%",
            "item_count": len(self.items),
            "is_warning": self.is_warning,
            "is_critical": self.is_critical,
            "by_source": {
                source: sum(1 for i in self.items if i.source == source)
                for source in set(i.source for i in self.items)
            },
        }


class ContextTracker:
    """
    Tracks context across sessions to prevent context loss.
    
    Records:
    - Task requirements
    - Implementation decisions
    - Open questions
    - Verified completions
    """

    def __init__(self):
        self.requirements: Dict[str, Dict] = {}
        self.decisions: List[Dict] = []
        self.open_questions: List[str] = []
        self.completions: List[Dict] = []

    def add_requirement(
        self,
        req_id: str,
        description: str,
        source: str = "prd",
        priority: str = "must",
    ) -> None:
        """Add a requirement to track."""
        self.requirements[req_id] = {
            "description": description,
            "source": source,
            "priority": priority,
            "implemented": False,
            "verified": False,
            "added_at": datetime.now().isoformat(),
        }

    def mark_implemented(self, req_id: str, evidence: str = "") -> bool:
        """Mark requirement as implemented."""
        if req_id in self.requirements:
            self.requirements[req_id]["implemented"] = True
            self.requirements[req_id]["evidence"] = evidence
            return True
        return False

    def mark_verified(self, req_id: str) -> bool:
        """Mark requirement as verified."""
        if req_id in self.requirements:
            self.requirements[req_id]["verified"] = True
            return True
        return False

    def add_decision(
        self,
        decision: str,
        rationale: str,
        alternatives: Optional[List[str]] = None,
    ) -> None:
        """Record an implementation decision."""
        self.decisions.append({
            "decision": decision,
            "rationale": rationale,
            "alternatives": alternatives or [],
            "timestamp": datetime.now().isoformat(),
        })

    def add_question(self, question: str) -> None:
        """Add an open question."""
        self.open_questions.append(question)

    def resolve_question(self, question: str) -> bool:
        """Resolve an open question."""
        if question in self.open_questions:
            self.open_questions.remove(question)
            return True
        return False

    def get_unimplemented(self) -> List[Dict]:
        """Get unimplemented requirements."""
        return [
            {"id": k, **v}
            for k, v in self.requirements.items()
            if not v["implemented"]
        ]

    def get_unverified(self) -> List[Dict]:
        """Get implemented but unverified requirements."""
        return [
            {"id": k, **v}
            for k, v in self.requirements.items()
            if v["implemented"] and not v["verified"]
        ]

    def get_completion_rate(self) -> Dict[str, float]:
        """Get completion statistics."""
        total = len(self.requirements)
        if total == 0:
            return {"implemented": 0.0, "verified": 0.0}

        implemented = sum(1 for r in self.requirements.values() if r["implemented"])
        verified = sum(1 for r in self.requirements.values() if r["verified"])

        return {
            "implemented": implemented / total,
            "verified": verified / total,
        }

    def format_status(self) -> str:
        """Format tracker status."""
        rates = self.get_completion_rate()
        unimpl = self.get_unimplemented()
        unver = self.get_unverified()

        lines = [
            "",
            "═" * 50,
            "          CONTEXT TRACKER STATUS",
            "═" * 50,
            "",
            f"Requirements: {len(self.requirements)} total",
            f"  Implemented: {rates['implemented'] * 100:.1f}%",
            f"  Verified: {rates['verified'] * 100:.1f}%",
            "",
        ]

        if unimpl:
            lines.append("Unimplemented:")
            for r in unimpl[:5]:
                lines.append(f"  ❌ {r['id']}: {r['description'][:50]}")
            if len(unimpl) > 5:
                lines.append(f"  ... and {len(unimpl) - 5} more")

        if unver:
            lines.append("\nNeed verification:")
            for r in unver[:5]:
                lines.append(f"  ⚠️  {r['id']}: {r['description'][:50]}")

        if self.open_questions:
            lines.append("\nOpen questions:")
            for q in self.open_questions[:3]:
                lines.append(f"  ❓ {q}")

        lines.append("")
        lines.append("═" * 50)

        return "\n".join(lines)


# Global instances
_context_window: Optional[ContextWindow] = None
_context_tracker: Optional[ContextTracker] = None


def get_context_window() -> ContextWindow:
    """Get global context window."""
    global _context_window
    if _context_window is None:
        _context_window = ContextWindow()
    return _context_window


def get_context_tracker() -> ContextTracker:
    """Get global context tracker."""
    global _context_tracker
    if _context_tracker is None:
        _context_tracker = ContextTracker()
    return _context_tracker
