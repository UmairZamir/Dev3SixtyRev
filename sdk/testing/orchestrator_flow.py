"""
Conversation Flow Testing
=========================

Testing framework for the 3SixtyRev Two-Level State Machine Architecture.

Architecture:
- Level 1: Sales Stage (persists across conversations)
  INITIAL → RAPPORT → DISCOVERY → QUALIFY → PRESENT → NEGOTIATE → CLOSE → NURTURE
  
- Level 2: Conversation State (per-session)
  INIT → GREETING → DISCOVERY → QUALIFICATION → OBJECTION_HANDLING → SCHEDULING → CLOSING

Core Behavioral Principles Tested:
1. Goals, Not Just Responses
2. Invisible Tool Execution
3. Never Ask Twice (Unless Warranted)
4. Channel-Native Communication
5. Graceful Degradation
6. Compliance by Design
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import time


# =============================================================================
# LEVEL 1: SALES STAGES (Persistent)
# =============================================================================

class SalesStage(str, Enum):
    """Sales stages that persist across conversations."""
    INITIAL = "initial"       # Lead created, no engagement
    RAPPORT = "rapport"       # Initial contact, building relationship
    DISCOVERY = "discovery"   # Understanding needs
    QUALIFY = "qualify"       # Collecting qualification details
    PRESENT = "present"       # Solution presented
    NEGOTIATE = "negotiate"   # Working through objections/terms
    CLOSE = "close"          # Deal closed
    NURTURE = "nurture"      # Post-sale relationship
    LOST = "lost"            # Did not convert


# =============================================================================
# LEVEL 2: CONVERSATION STATES (Per-Session)
# =============================================================================

class ConversationState(str, Enum):
    """Conversation states within a single session."""
    # Initialization
    INIT = "init"
    WAITING_GREETING = "waiting_greeting"
    
    # Opening
    GREETING = "greeting"
    IDENTITY_QUESTION = "identity_question"  # "Are you AI?"
    
    # Core Flow
    DISCOVERY = "discovery"
    QUALIFICATION = "qualification"
    OBJECTION_HANDLING = "objection_handling"
    TIMING_OBJECTION = "timing_objection"
    
    # Cross-Sell
    CROSS_SELL_OPPORTUNITY = "cross_sell_opportunity"
    CROSS_SELL_OFFER = "cross_sell_offer"
    CROSS_SELL_QUALIFICATION = "cross_sell_qualification"
    
    # Referral
    REFERRAL_OPPORTUNITY = "referral_opportunity"
    REFERRAL_ASK = "referral_ask"
    REFERRAL_COLLECTION = "referral_collection"
    
    # Scheduling & Handoff
    SCHEDULING = "scheduling"
    HUMAN_TRANSFER = "human_transfer"
    
    # Closing
    CLOSING_POSITIVE = "closing_positive"
    CLOSING_NEUTRAL = "closing_neutral"
    CLOSING_NEGATIVE = "closing_negative"
    HARD_STOP = "hard_stop"
    SEED_PLANTED = "seed_planted"


# =============================================================================
# AI OPERATING MODES
# =============================================================================

class AIMode(str, Enum):
    """AI operating modes."""
    ASSISTANT = "assistant"   # All industries, qualitative only
    AGENT = "agent"          # Non-regulated only, can quote/discount
    SERVICE = "service"      # Service requests


class IndustryType(str, Enum):
    """Industry classification for mode availability."""
    REGULATED = "regulated"      # Insurance, mortgage, real estate, healthcare, legal
    NON_REGULATED = "non_regulated"  # SaaS, retail, services


# =============================================================================
# TEST CONTRACTS
# =============================================================================

@dataclass
class BehavioralContract:
    """Contract for behavioral principle compliance."""
    principle: str
    description: str
    validators: List[Callable[[Dict], bool]] = field(default_factory=list)
    max_latency_ms: Optional[float] = None

    def validate(self, context: Dict) -> bool:
        """Validate all contract conditions."""
        for validator in self.validators:
            if not validator(context):
                return False
        return True


@dataclass
class StateTransition:
    """Expected state transition."""
    from_state: ConversationState
    to_state: ConversationState
    trigger_intent: str
    required_action: str
    

@dataclass
class FlowTestResult:
    """Result from a flow test."""
    passed: bool
    test_name: str
    latency_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    state_path: List[ConversationState] = field(default_factory=list)
    sales_stage_change: Optional[tuple] = None  # (from, to)


@dataclass
class FlowTest:
    """A single flow test case."""
    name: str
    description: str
    
    # Input
    channel: str  # voice, sms, email, chat
    ai_mode: AIMode
    industry_type: IndustryType
    initial_sales_stage: SalesStage
    user_messages: List[str]
    
    # Expected
    expected_states: List[ConversationState]
    expected_final_sales_stage: SalesStage
    expected_fields_collected: List[str] = field(default_factory=list)
    
    # Behavioral contracts to verify
    contracts: List[BehavioralContract] = field(default_factory=list)
    
    # Latency
    max_latency_ms: Optional[float] = None

    def run(self, engine: Any) -> FlowTestResult:
        """Run the flow test against an engine."""
        start = time.time()
        errors = []
        warnings = []
        state_path = []
        
        # This would integrate with actual engine
        # For now, return placeholder
        
        latency = (time.time() - start) * 1000
        
        return FlowTestResult(
            passed=len(errors) == 0,
            test_name=self.name,
            latency_ms=latency,
            errors=errors,
            warnings=warnings,
            state_path=state_path,
        )


# =============================================================================
# DEFAULT BEHAVIORAL CONTRACTS
# =============================================================================

DEFAULT_CONTRACTS = {
    "goals_not_responses": BehavioralContract(
        principle="Goals, Not Just Responses",
        description="AI operates with explicit goals, not just reactions",
        validators=[
            lambda ctx: ctx.get("has_active_goal", False),
            lambda ctx: ctx.get("goal_progress_tracked", False),
        ],
    ),
    "invisible_tool_execution": BehavioralContract(
        principle="Invisible Tool Execution",
        description="Tool calls happen without verbal acknowledgment",
        validators=[
            lambda ctx: "let me look" not in ctx.get("response", "").lower(),
            lambda ctx: "checking" not in ctx.get("response", "").lower(),
            lambda ctx: "searching" not in ctx.get("response", "").lower(),
        ],
    ),
    "never_ask_twice": BehavioralContract(
        principle="Never Ask Twice",
        description="Don't ask for information already collected",
        validators=[
            lambda ctx: not ctx.get("duplicate_question", False),
        ],
    ),
    "channel_native": BehavioralContract(
        principle="Channel-Native Communication",
        description="Response matches channel conventions",
        validators=[
            lambda ctx: ctx.get("channel_appropriate", True),
        ],
    ),
    "graceful_degradation": BehavioralContract(
        principle="Graceful Degradation",
        description="Always has a next action, even on failure",
        validators=[
            lambda ctx: ctx.get("has_next_action", False),
        ],
    ),
    "compliance_by_design": BehavioralContract(
        principle="Compliance by Design",
        description="Mode restrictions enforced",
        validators=[
            lambda ctx: not ctx.get("mode_violation", False),
            lambda ctx: ctx.get("ai_disclosed_when_asked", True),
        ],
    ),
}


# =============================================================================
# TEST SUITE
# =============================================================================

class FlowTestSuite:
    """Suite of flow tests for the conversation engine."""
    
    # Latency budgets by channel
    LATENCY_BUDGETS = {
        "voice": 500,    # P95 < 500ms
        "sms": 2000,     # P95 < 2s
        "email": 5000,   # P95 < 5s
        "chat": 2000,    # P95 < 2s
    }

    def __init__(self):
        self.tests: List[FlowTest] = []
        self.contracts = dict(DEFAULT_CONTRACTS)

    def add_test(self, test: FlowTest) -> None:
        """Add a test to the suite."""
        self.tests.append(test)

    def run_all(self, engine: Any) -> Dict[str, FlowTestResult]:
        """Run all tests."""
        results = {}
        for test in self.tests:
            results[test.name] = test.run(engine)
        return results

    def format_results(self, results: Dict[str, FlowTestResult]) -> str:
        """Format test results for display."""
        lines = [
            "",
            "═" * 60,
            "          CONVERSATION FLOW TEST RESULTS",
            "═" * 60,
            "",
        ]
        
        passed = sum(1 for r in results.values() if r.passed)
        total = len(results)
        
        for name, result in results.items():
            status = "✅" if result.passed else "❌"
            lines.append(f"{status} {name} ({result.latency_ms:.0f}ms)")
            for error in result.errors:
                lines.append(f"   ❌ {error}")
            for warning in result.warnings:
                lines.append(f"   ⚠️  {warning}")
        
        lines.append("")
        lines.append(f"Summary: {passed}/{total} tests passed")
        lines.append("═" * 60)
        
        return "\n".join(lines)


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_qualification_flow_test(
    name: str,
    description: str,
    user_input: str,
    channel: str = "voice",
    ai_mode: AIMode = AIMode.ASSISTANT,
    industry: IndustryType = IndustryType.REGULATED,
) -> FlowTest:
    """Create a standard qualification flow test."""
    return FlowTest(
        name=name,
        description=description,
        channel=channel,
        ai_mode=ai_mode,
        industry_type=industry,
        initial_sales_stage=SalesStage.INITIAL,
        user_messages=[user_input],
        expected_states=[
            ConversationState.GREETING,
            ConversationState.DISCOVERY,
            ConversationState.QUALIFICATION,
        ],
        expected_final_sales_stage=SalesStage.QUALIFY,
        contracts=list(DEFAULT_CONTRACTS.values()),
        max_latency_ms=FlowTestSuite.LATENCY_BUDGETS.get(channel, 2000),
    )


def create_objection_flow_test(
    name: str,
    objection_type: str,
    objection_text: str,
    channel: str = "voice",
    ai_mode: AIMode = AIMode.ASSISTANT,
) -> FlowTest:
    """Create an objection handling flow test."""
    return FlowTest(
        name=name,
        description=f"Handle {objection_type} objection",
        channel=channel,
        ai_mode=ai_mode,
        industry_type=IndustryType.REGULATED,
        initial_sales_stage=SalesStage.QUALIFY,
        user_messages=["I'm interested", objection_text],
        expected_states=[
            ConversationState.QUALIFICATION,
            ConversationState.OBJECTION_HANDLING,
        ],
        expected_final_sales_stage=SalesStage.QUALIFY,  # Stays in qualify
        contracts=list(DEFAULT_CONTRACTS.values()),
    )


def create_cross_sell_flow_test(
    name: str,
    trigger_field: str,
    trigger_value: Any,
) -> FlowTest:
    """Create a cross-sell detection flow test."""
    return FlowTest(
        name=name,
        description=f"Cross-sell triggered by {trigger_field}={trigger_value}",
        channel="voice",
        ai_mode=AIMode.ASSISTANT,
        industry_type=IndustryType.REGULATED,
        initial_sales_stage=SalesStage.QUALIFY,
        user_messages=[f"Yes, I {trigger_value}"],
        expected_states=[
            ConversationState.QUALIFICATION,
            ConversationState.CROSS_SELL_OPPORTUNITY,
        ],
        expected_final_sales_stage=SalesStage.QUALIFY,
        expected_fields_collected=[trigger_field],
        contracts=list(DEFAULT_CONTRACTS.values()),
    )


# =============================================================================
# STANDARD TEST CASES
# =============================================================================

STANDARD_FLOW_TESTS = [
    # Qualification flows
    create_qualification_flow_test(
        name="insurance_qualification_voice",
        description="Inbound insurance inquiry via voice",
        user_input="Hi, I'm looking for auto insurance",
        channel="voice",
    ),
    create_qualification_flow_test(
        name="insurance_qualification_sms",
        description="Insurance inquiry via SMS",
        user_input="Need a quote for car insurance",
        channel="sms",
    ),
    
    # Objection handling
    create_objection_flow_test(
        name="price_objection_assistant",
        objection_type="price",
        objection_text="That sounds too expensive",
    ),
    create_objection_flow_test(
        name="timing_objection",
        objection_type="timing",
        objection_text="I don't have time right now",
    ),
    create_objection_flow_test(
        name="trust_objection",
        objection_type="trust",
        objection_text="I've never heard of you guys",
    ),
    
    # Cross-sell triggers
    create_cross_sell_flow_test(
        name="home_owner_cross_sell",
        trigger_field="home_owner",
        trigger_value="own my home",
    ),
    create_cross_sell_flow_test(
        name="business_owner_cross_sell",
        trigger_field="business_owner",
        trigger_value="run a small business",
    ),
    
    # AI disclosure (must pass)
    FlowTest(
        name="ai_disclosure_when_asked",
        description="AI must disclose identity when directly asked",
        channel="voice",
        ai_mode=AIMode.ASSISTANT,
        industry_type=IndustryType.REGULATED,
        initial_sales_stage=SalesStage.RAPPORT,
        user_messages=["Wait, am I talking to a robot?"],
        expected_states=[
            ConversationState.IDENTITY_QUESTION,  # Must enter this state
            ConversationState.GREETING,  # Continue after disclosure
        ],
        expected_final_sales_stage=SalesStage.RAPPORT,
        contracts=[DEFAULT_CONTRACTS["compliance_by_design"]],
    ),
    
    # Mode enforcement (Agent mode blocked for regulated)
    FlowTest(
        name="agent_mode_blocked_regulated",
        description="Agent mode cannot be used for regulated industries",
        channel="voice",
        ai_mode=AIMode.AGENT,  # Attempt agent mode
        industry_type=IndustryType.REGULATED,  # But regulated industry
        initial_sales_stage=SalesStage.QUALIFY,
        user_messages=["How much would it cost?"],
        expected_states=[
            ConversationState.QUALIFICATION,
            ConversationState.SCHEDULING,  # Must handoff, not quote
        ],
        expected_final_sales_stage=SalesStage.QUALIFY,
        contracts=[DEFAULT_CONTRACTS["compliance_by_design"]],
    ),
]
