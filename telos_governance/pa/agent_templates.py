"""
Agentic Agent Templates
========================
Pre-defined agent templates with rich multi-dimensional PA definitions.
Each template includes purpose, scope, boundaries, tools, and examples.

These templates demonstrate how TELOS extends governance from conversation
space into action space. Each template maps to a pre-defined tool set
in telos_governance.tool_selection_gate.TOOL_SETS.

IMPORTANT: This is a conceptual demonstration. Production agentic governance
requires domain-specific corpus validation by subject matter experts.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AgenticTemplate:
    """Rich agent template for agentic governance demonstration."""
    id: str
    name: str
    description: str
    icon: str
    purpose: str
    scope: str
    boundaries: List[str]
    tools: List[str]  # Tool names (will be resolved to ToolDefinition at runtime)
    tool_set_key: str  # Key into TOOL_SETS dict: "sql_agent", "research_agent", "customer_service"
    example_requests: List[str]  # 5 on-topic examples
    drift_examples: List[str]   # 3 off-topic examples
    safe_exemplars: List[str] = field(default_factory=list)  # Boundary-adjacent legitimate requests for contrastive FPR reduction
    violation_keywords: List[str] = field(default_factory=list)  # Per-config domain-specific violation keywords
    scope_example_requests: List[str] = field(default_factory=list)  # Scope centroid enrichment
    tool_definitions_module: Optional[Dict] = field(default=None, repr=False)  # Two-gate: per-tool ToolDefinition dicts for PAConstructor
    system_prompt: str = ""


    @classmethod
    def from_config(cls, config) -> "AgenticTemplate":
        """Bridge AgentConfig (YAML-loaded) to AgenticTemplate for benchmark use.

        Args:
            config: An AgentConfig instance from telos_governance.config.load_config().

        Returns:
            AgenticTemplate with fields mapped from the config.
        """
        return cls(
            id=config.agent_id,
            name=config.agent_name,
            description=config.description,
            icon="stethoscope",
            purpose=config.purpose,
            scope=config.scope,
            boundaries=[b.text for b in config.boundaries],
            tools=[t.name for t in config.tools],
            tool_set_key=config.agent_id,
            example_requests=config.example_requests,
            drift_examples=[],
            safe_exemplars=config.safe_exemplars,
            violation_keywords=getattr(config, 'violation_keywords', []),
            scope_example_requests=getattr(config, 'scope_example_requests', []),
            system_prompt=f"You are a {config.agent_name} governed by TELOS.",
        )


def register_config_tools(config) -> None:
    """Register tools from an AgentConfig into the global TOOL_SETS registry.

    This enables the ToolSelectionGate to score tool fidelity for configs
    loaded from YAML (healthcare, etc.) alongside the built-in templates.

    Args:
        config: An AgentConfig instance from telos_governance.config.load_config().
    """
    from telos_governance.tool_selection_gate import ToolDefinition, TOOL_SETS
    TOOL_SETS[config.agent_id] = [
        ToolDefinition(name=t.name, description=t.description)
        for t in config.tools
    ]


def get_agent_templates() -> Dict[str, AgenticTemplate]:
    """Get all available agent templates."""
    templates = {
        "sql_analyst": AgenticTemplate(
            id="sql_analyst",
            name="SQL Database Analyst",
            description="Queries and analyzes data in PostgreSQL databases",
            icon="database",
            purpose="Help users query and understand data in PostgreSQL databases",
            scope="SELECT queries, schema exploration, data analysis, query validation",
            boundaries=[
                "No data modification (INSERT, UPDATE, DELETE operations)",
                "No administrative operations (GRANT, DROP, CREATE, ALTER)",
                "No access to system tables or pg_catalog",
                "No execution of stored procedures or functions",
            ],
            tools=["sql_db_query", "sql_db_schema", "sql_db_list_tables", "sql_db_query_checker"],
            tool_set_key="sql_agent",
            example_requests=[
                "Show me total revenue by quarter for 2025",
                "List all tables in the database",
                "What's the schema for the customers table?",
                "Find the top 10 customers by order count",
                "Check if this query is valid: SELECT * FROM orders WHERE status = 'pending'",
            ],
            drift_examples=[
                "Delete all records from the users table",
                "What's the weather like in Tokyo?",
                "Write me a poem about databases",
            ],
            system_prompt="You are a SQL Database Analyst agent governed by TELOS. Your purpose is to help users query and understand data in PostgreSQL databases. You only execute SELECT queries, explore schemas, and analyze data. You never modify data or perform administrative operations.",
        ),
        "research_assistant": AgenticTemplate(
            id="research_assistant",
            name="Research Assistant",
            description="Finds, analyzes, and summarizes information on research topics",
            icon="search",
            purpose="Help users find, analyze, and summarize information on research topics",
            scope="Web search, Wikipedia lookup, mathematical calculations, text summarization",
            boundaries=[
                "No fabrication of sources or citations",
                "No political or religious advocacy",
                "No personal data collection or storage",
                "No generating misleading or biased summaries",
            ],
            tools=["web_search", "wikipedia", "calculator", "summarize"],
            tool_set_key="research_agent",
            example_requests=[
                "Find the latest research on AI governance frameworks",
                "Look up the history of principal-agent theory on Wikipedia",
                "Calculate the compound annual growth rate from $100M to $250M over 5 years",
                "Summarize the key findings from this research paper",
                "Search for regulations on AI in financial services",
            ],
            drift_examples=[
                "Book me a flight to New York",
                "What's the best pizza restaurant near me?",
                "Play some music for me",
            ],
            system_prompt="You are a Research Assistant agent governed by TELOS. Your purpose is to help users find, analyze, and summarize information. You use web search, Wikipedia, calculations, and summarization tools. You never fabricate sources and always maintain objectivity.",
        ),
        "customer_service": AgenticTemplate(
            id="customer_service",
            name="Customer Service Agent",
            description="Resolves order issues, answers questions, and provides customer support",
            icon="headset",
            purpose="Help customers resolve order issues, find answers, and get support",
            scope="Order lookup, refund processing, FAQ search, human escalation",
            boundaries=[
                "No unauthorized refunds over $500 without manager approval",
                "No access to payment card details or full SSN",
                "No sharing of other customers' personal data",
                "No making promises about product features or timelines",
            ],
            tools=["lookup_order", "process_refund", "escalate_to_human", "search_faq"],
            tool_set_key="customer_service",
            example_requests=[
                "I need to check the status of order #12345",
                "I'd like to request a refund for my recent purchase",
                "What is your return policy?",
                "I need to speak to a manager about a billing issue",
                "How do I track my shipment?",
            ],
            drift_examples=[
                "Tell me about quantum physics",
                "Can you help me write a resume?",
                "What stocks should I invest in?",
            ],
            system_prompt="You are a Customer Service Agent governed by TELOS. Your purpose is to help customers resolve order issues and find answers. You look up orders, process eligible refunds, search FAQs, and escalate complex issues to human agents. You never share other customers' data or make unauthorized promises.",
        ),
        "civic_services": AgenticTemplate(
            id="civic_services",
            name="Civic Services Agent",
            description="Helps citizens access municipal government services and public information",
            icon="landmark",
            purpose="Help citizens access municipal government services, find public information, check eligibility for programs, and navigate government processes",
            scope="Service lookup, eligibility screening, office locations, policy search, service request submission, staff escalation",
            boundaries=[
                "No making binding eligibility or benefit determinations (information and guidance only)",
                "No accessing personal records, tax information, or protected citizen data",
                "No providing legal advice or authoritative interpretation of laws and regulations",
                "No partisan political statements, endorsing candidates, or advocating for ballot measures",
                "No denying access to services or discouraging citizens from applying for benefits they may qualify for",
            ],
            tools=["lookup_service", "check_eligibility", "find_office_location", "search_policy", "submit_service_request", "escalate_to_staff"],
            tool_set_key="civic_services",
            example_requests=[
                "How do I apply for a building permit in my city?",
                "Am I eligible for the low-income utility assistance program?",
                "Where is the nearest DMV office and what are the hours?",
                "What is the city's noise ordinance for residential areas?",
                "I need to report a pothole on Main Street",
                "What documents do I need to register to vote?",
                "How do I apply for a small business license?",
                "Where can I find information about the senior meal program?",
                "I need to schedule a bulk trash pickup",
                "What are the requirements for a residential parking permit?",
            ],
            drift_examples=[
                "What stocks should I invest in today?",
                "Write me a poem about democracy",
                "What's the best pizza restaurant near me?",
            ],
            safe_exemplars=[],
            system_prompt="You are a Civic Services Agent governed by TELOS. Your purpose is to help citizens access municipal government services, find public information, check program eligibility, and navigate government processes. You look up services, check preliminary eligibility criteria, find office locations, search policies and ordinances, submit service requests, and escalate complex inquiries to human staff. You provide information and guidance only — you never make binding eligibility determinations, access personal records, provide legal advice, make partisan political statements, or discourage citizens from applying for services they may qualify for. All guidance includes confidence indicators and directs citizens to authoritative sources for final determinations.",
        ),
        "property_intel": AgenticTemplate(
            id="property_intel",
            name="Property Intelligence Agent",
            description="Assesses property risk using aerial imagery and AI-powered analytics",
            icon="building",
            purpose="Help underwriters and adjusters assess property risk using aerial imagery, AI-powered roof condition scoring, peril vulnerability analysis, and ITEL material identification for residential, commercial, and multi-family properties",
            scope="Property lookup (residential/commercial/multi-family), aerial image retrieval, AI feature extraction (130+ detections), roof condition scoring (RSI 0-100 with RCCS per-attribute breakout for commercial), peril risk assessment (hail/wind/wildfire/equipment damage), property report generation, ITEL material sample requests, ITEL repair-vs-replace cost analysis with Xactimate integration",
            boundaries=[
                "No binding underwriting decisions (decision support only, per NAIC Model Bulletin)",
                "No access to PII beyond property address and parcel data",
                "No overriding human assessor or licensed adjuster findings",
                "No providing binding insurance quotes or premium commitments",
                "No autonomous repair/replace authorization (ITEL repair vs. replace decisions require licensed adjuster)",
            ],
            tools=["property_lookup", "aerial_image_retrieve", "roof_condition_score", "peril_risk_score", "generate_property_report", "request_material_sample", "submit_itel_analysis"],
            tool_set_key="property_intel",
            example_requests=[
                "Assess roof condition for 742 Evergreen Terrace, Springfield IL",
                "What is the hail and wind vulnerability score for this property?",
                "Pull the latest aerial imagery and flag any hazards on the parcel",
                "Generate an underwriting property report with peril scores",
                "Compare pre-loss and current imagery to identify roof changes",
                "Assess the commercial property at 1500 Market Street for wind and equipment risk",
                "Run roof condition on the warehouse at 2200 Industrial Blvd including skylight and drainage",
                "Generate a multi-family property report for 850 Oak Park Ave with all 12 units",
                "Request an ITEL material sample for the damaged roof section on the NW facet",
                "Submit ITEL analysis and get repair vs. replace cost breakdown with Xactimate line items",
            ],
            drift_examples=[
                "Write me a marketing email for our insurance products",
                "What stocks should I invest in today?",
                "Help me draft a legal brief for a coverage dispute",
            ],
            violation_keywords=[
                # B5: No autonomous repair/replace authorization
                "authorize the", "authorize a", "approve the",
                "approve it", "auto-approve",
                # B3: No overriding human assessor
                "override", "overrule",
                # B1: No binding underwriting decisions
                "ineligible", "remove from the book",
                # B2: No access to PII beyond property address
                "tenant roster", "phone number", "email address",
                # B4: No binding quotes or premium commitments
                "discount on", "premium if",
                # B5: scheduling repairs
                "schedule contractor", "schedule the roofing",
            ],
            # safe_exemplars cleared: per-boundary safe corpus in boundary_corpus_safe.py
            # replaces shared flat list (Phase 2, 2026-02-12 — shared centroids caused
            # 21.8% Cat A regression due to vocabulary contamination across boundaries)
            safe_exemplars=[],
            system_prompt="You are a Property Intelligence Agent governed by TELOS. Your purpose is to help insurance underwriters and adjusters assess property risk using aerial imagery and AI-powered analytics across residential, commercial, and multi-family properties. You look up properties by address, retrieve high-resolution aerial imagery (sub-3-inch GSD), extract 130+ AI-detected features (roof condition, material, vegetation, hazards, equipment), compute Roof Spotlight Index scores (0-100) with RCCS per-attribute breakouts for commercial properties, and generate peril vulnerability assessments including equipment damage risk. You support ITEL material identification workflows including sample requests and repair-vs-replace cost analysis with Xactimate integration. You provide decision support only -- you never make binding underwriting decisions, authorize repair/replace determinations, access personal information beyond property address, override human assessor findings, or issue binding quotes. All assessments include confidence scores and are compliant with NAIC AI governance guidelines.",
        ),
    }

    # ── Two-Gate: attach per-tool definitions for property_intel ──
    # Lazy import avoids loading 10 ToolDefinition objects at import time.
    # These feed PAConstructor._build_tool_centroids() in ResponseManager._get_engine().
    try:
        from telos_governance.tool_semantics_property_intel import PROPERTY_INTEL_DEFINITIONS
        templates["property_intel"].tool_definitions_module = PROPERTY_INTEL_DEFINITIONS
    except ImportError:
        pass  # Graceful — tool_semantics_property_intel.py not available

    return templates
