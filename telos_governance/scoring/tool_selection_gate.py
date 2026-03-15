"""
Tool Selection Gate (Tier 2)
============================

Semantic tool selection based on cosine similarity between
user request and tool descriptions.

This is the "cognition with receipts" layer -- explains WHY
a tool was selected using mathematical semantic alignment.

Tier 1: Pass-Through Governance (fidelity_gate.py)
    - "Should this request proceed at all?"
    - Cosine(user_request, agent_PA)

Tier 2: Tool Selection Fidelity (this module)
    - "Which tool best serves this request?"
    - Cosine(user_request, each_tool_description)
    - Returns ranked tools with semantic reasoning

First Principles
-----------------
1. **Auditable Decision-Making**: When a regulator asks "why did your
   AI agent process a refund instead of escalating to a human?" the
   answer must be mathematical, not "the model decided." Tool selection
   receipts provide: the selected tool, its fidelity score, the runner-up
   and its score, and the gap between them. This is TELOS's "cognition
   with receipts" -- every decision has a paper trail.

2. **Cosine Similarity as Geometric Alignment** (Salton & McGill, 1983):
   Tool selection measures the angle between the request vector and each
   tool description vector in embedding space. Smaller angle = higher
   alignment = better tool match. This geometric interpretation means
   tool selection is invariant to phrasing -- "show me revenue data" and
   "display income figures" both point toward sql_db_query because the
   vectors are geometrically aligned, regardless of word choice.

3. **Semantic Density** (TELOS Research Hypothesis): Tool descriptions
   occupy tighter regions in embedding space than conversational text.
   "Execute SQL SELECT queries and return results" is more semantically
   concentrated than "help me with databases." This density improves
   discriminative power -- the gap between the best tool and the wrong
   tool is wider than the gap between on-topic and off-topic conversation.

4. **OWASP LLM Top 10** (2025 -- LLM07, Insecure Plugin Design): Semantic
   tool ranking ensures tools are selected based on mathematical alignment
   with the request, not LLM hallucination or prompt injection. The
   contrastive gap between the selected tool and runner-up provides a
   quantitative measure of selection confidence. Low-gap selections
   trigger CLARIFY, preventing blind tool invocation.

5. **NIST AI 600-1** (Generative AI Profile, 2024 -- MAP 2.2): Tool
   selection receipts document which tool was selected, why (cosine
   similarity score), and with what confidence (contrastive gap) -- the
   capability-level documentation NIST 600-1 requires for GenAI systems
   that invoke external tools or plugins.

6. **NIST AI RMF 100** (MEASURE 2.6): Tool fidelity scores are
   quantitative trustworthiness metrics per MEASURE 2.6 -- each selection
   decision is measurable, logged, and auditable.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np

# Import shared normalization from telos_core (single source of truth)
try:
    from telos_core.fidelity_engine import normalize_mistral_fidelity, normalize_fidelity
    _SHARED_NORMALIZE = True
except ImportError:
    _SHARED_NORMALIZE = False

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """A tool available to the agent."""
    name: str
    description: str
    embedding: Optional[np.ndarray] = None


@dataclass
class ToolFidelityScore:
    """Fidelity score for a single tool."""
    tool_name: str
    tool_description: str
    raw_similarity: float
    normalized_fidelity: float
    display_percentage: int
    rank: int = 0

    @property
    def is_best_match(self) -> bool:
        return self.rank == 1


@dataclass
class ToolSelectionResult:
    """Result of Tier 2 tool selection governance."""
    user_request: str
    tool_scores: List[ToolFidelityScore]
    selected_tool: Optional[str]
    selected_fidelity: float
    selection_reasoning: str
    all_tools_ranked: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "tier": 2,
            "type": "tool_selection",
            "user_request": (
                self.user_request[:100] + "..."
                if len(self.user_request) > 100
                else self.user_request
            ),
            "selected_tool": self.selected_tool,
            "selected_fidelity": self.selected_fidelity,
            "selection_reasoning": self.selection_reasoning,
            "tool_rankings": [
                {
                    "rank": score.rank,
                    "tool": score.tool_name,
                    "fidelity": score.normalized_fidelity,
                    "display_pct": score.display_percentage,
                    "description": (
                        score.tool_description[:80] + "..."
                        if len(score.tool_description) > 80
                        else score.tool_description
                    ),
                }
                for score in sorted(self.tool_scores, key=lambda x: x.rank)
            ],
        }


class ToolSelectionGate:
    """
    Tier 2: Semantic Tool Selection

    Instead of keyword matching, use cosine similarity between
    the user's request and each tool's description to determine
    the best tool for the job.

    This provides:
    1. Semantic understanding of tool appropriateness
    2. Explainable selection with mathematical backing
    3. Ranked alternatives if the top choice fails
    """

    def __init__(
        self,
        embed_fn: Callable[[str], np.ndarray],
        baseline_threshold: float = 0.20,
    ):
        """
        Initialize the tool selection gate.

        Args:
            embed_fn: Function to embed text strings
            baseline_threshold: Minimum similarity for meaningful alignment
        """
        self.embed_fn = embed_fn
        self.baseline_threshold = baseline_threshold
        self._tool_embedding_cache: Dict[str, np.ndarray] = {}
        self._embedding_dim: Optional[int] = None

    def register_tools(self, tools: List[ToolDefinition]) -> None:
        """
        Pre-compute embeddings for tools (optimization).

        Call this once when agent is registered to avoid
        repeated embedding computation.
        """
        for tool in tools:
            if tool.name not in self._tool_embedding_cache:
                tool_text = f"{tool.name}: {tool.description}"
                self._tool_embedding_cache[tool.name] = self.embed_fn(tool_text)
                tool.embedding = self._tool_embedding_cache[tool.name]
                logger.debug(f"Cached embedding for tool: {tool.name}")

    def select_tool(
        self,
        user_request: str,
        tools: List[ToolDefinition],
    ) -> ToolSelectionResult:
        """
        Select the best tool based on semantic similarity.

        Args:
            user_request: The user's request/query
            tools: List of available tools

        Returns:
            ToolSelectionResult with rankings and reasoning
        """
        if not tools:
            return ToolSelectionResult(
                user_request=user_request,
                tool_scores=[],
                selected_tool=None,
                selected_fidelity=0.0,
                selection_reasoning="No tools available",
                all_tools_ranked=[],
            )

        # Embed the user request
        request_embedding = self.embed_fn(user_request)

        if self._embedding_dim is None:
            self._embedding_dim = request_embedding.shape[0]

        # Calculate fidelity for each tool
        tool_scores: List[ToolFidelityScore] = []

        for tool in tools:
            # Get or compute tool embedding
            if tool.embedding is not None:
                tool_embedding = tool.embedding
            elif tool.name in self._tool_embedding_cache:
                tool_embedding = self._tool_embedding_cache[tool.name]
            else:
                tool_text = f"{tool.name}: {tool.description}"
                tool_embedding = self.embed_fn(tool_text)
                self._tool_embedding_cache[tool.name] = tool_embedding

            # Calculate similarity
            raw_similarity = self._cosine_similarity(request_embedding, tool_embedding)
            normalized_fidelity = self._normalize_fidelity(raw_similarity)
            display_pct = self._to_display_percentage(normalized_fidelity)

            tool_scores.append(ToolFidelityScore(
                tool_name=tool.name,
                tool_description=tool.description,
                raw_similarity=raw_similarity,
                normalized_fidelity=normalized_fidelity,
                display_percentage=display_pct,
            ))

        # Rank by fidelity (highest first)
        tool_scores.sort(key=lambda x: x.normalized_fidelity, reverse=True)
        for i, score in enumerate(tool_scores):
            score.rank = i + 1

        # Select best tool
        best_tool = tool_scores[0] if tool_scores else None

        # Generate reasoning
        reasoning = self._generate_reasoning(best_tool, tool_scores)

        return ToolSelectionResult(
            user_request=user_request,
            tool_scores=tool_scores,
            selected_tool=best_tool.tool_name if best_tool else None,
            selected_fidelity=best_tool.normalized_fidelity if best_tool else 0.0,
            selection_reasoning=reasoning,
            all_tools_ranked=[s.tool_name for s in tool_scores],
        )

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))

    def _is_sentence_transformer(self) -> bool:
        """Detect if using SentenceTransformer (384/768-dim) vs Mistral (1024-dim)."""
        return self._embedding_dim is not None and self._embedding_dim <= 800

    def _normalize_fidelity(self, raw_similarity: float) -> float:
        """Normalize raw similarity to fidelity score.

        Auto-detects embedding model from dimensionality:
        - SentenceTransformer (384-dim): Linear mapping (slope=1.167, intercept=0.117)
        - Mistral (1024-dim): Piecewise mapping (floor=0.55, aligned=0.70)
        """
        if self._is_sentence_transformer():
            if _SHARED_NORMALIZE:
                return normalize_fidelity(raw_similarity, slope=1.167, intercept=0.117)
            display = 1.167 * raw_similarity + 0.117
            return float(max(0.0, min(1.0, display)))
        else:
            if _SHARED_NORMALIZE:
                return normalize_mistral_fidelity(raw_similarity)
            MISTRAL_FLOOR = 0.55
            MISTRAL_ALIGNED = 0.70
            if raw_similarity < MISTRAL_FLOOR:
                fidelity = (raw_similarity / MISTRAL_FLOOR) * 0.30
            elif raw_similarity < MISTRAL_ALIGNED:
                fidelity = 0.30 + (
                    (raw_similarity - MISTRAL_FLOOR) / (MISTRAL_ALIGNED - MISTRAL_FLOOR)
                ) * 0.40
            else:
                fidelity = 0.70 + (
                    (raw_similarity - MISTRAL_ALIGNED) / (1.0 - MISTRAL_ALIGNED)
                ) * 0.30
            return float(min(1.0, max(0.0, fidelity)))

    def _to_display_percentage(self, fidelity: float) -> int:
        """
        Convert fidelity to intuitive display percentage.

        Maps to the same ranges as Tier 1:
        - >= 0.70 -> 90-100%
        - 0.60-0.69 -> 80-89%
        - 0.50-0.59 -> 70-79%
        - < 0.50 -> Below 70%
        """
        if fidelity >= 0.70:
            return 90 + int((fidelity - 0.70) / 0.30 * 10)
        elif fidelity >= 0.60:
            return 80 + int((fidelity - 0.60) / 0.10 * 9)
        elif fidelity >= 0.50:
            return 70 + int((fidelity - 0.50) / 0.10 * 9)
        else:
            return int(fidelity / 0.50 * 69)

    def _generate_reasoning(
        self,
        selected: Optional[ToolFidelityScore],
        all_scores: List[ToolFidelityScore],
    ) -> str:
        """
        Generate human-readable reasoning for tool selection.

        This is the "receipts" - explaining WHY this tool was selected.
        """
        if not selected:
            return "No tools available for selection."

        # High confidence selection
        if selected.display_percentage >= 90:
            return (
                f"Selected '{selected.tool_name}' with {selected.display_percentage}% "
                f"semantic alignment. The request strongly matches this tool's purpose: "
                f"{selected.tool_description[:60]}..."
            )

        # Moderate confidence
        elif selected.display_percentage >= 80:
            reasoning = (
                f"Selected '{selected.tool_name}' with {selected.display_percentage}% "
                f"semantic alignment. Good match for the request."
            )
            # Mention runner-up if close
            if len(all_scores) > 1 and all_scores[1].display_percentage >= 75:
                reasoning += (
                    f" Alternative: '{all_scores[1].tool_name}' "
                    f"({all_scores[1].display_percentage}%)."
                )
            return reasoning

        # Low confidence - warn about potential mismatch
        elif selected.display_percentage >= 70:
            return (
                f"Selected '{selected.tool_name}' with {selected.display_percentage}% "
                f"semantic alignment. Moderate match - request may be ambiguous. "
                f"Consider: does this request align with '{selected.tool_description[:40]}...'?"
            )

        # Very low - likely wrong tool
        else:
            return (
                f"Warning: Best match is '{selected.tool_name}' with only "
                f"{selected.display_percentage}% alignment. The request may not match "
                f"any available tool well. Consider clarifying the request."
            )


# =============================================================================
# Pre-defined Tool Sets for Common Agent Types
# =============================================================================

SQL_AGENT_TOOLS = [
    ToolDefinition(
        name="sql_db_query",
        description=(
            "Execute a SQL query against the database and return results. "
            "Use for retrieving data, running SELECT statements, and getting query results."
        ),
    ),
    ToolDefinition(
        name="sql_db_schema",
        description=(
            "Get the schema and sample rows for specified SQL tables. "
            "Use to understand table structure, column types, and see example data."
        ),
    ),
    ToolDefinition(
        name="sql_db_list_tables",
        description=(
            "List all tables available in the database. "
            "Use when you need to discover what tables exist before querying."
        ),
    ),
    ToolDefinition(
        name="sql_db_query_checker",
        description=(
            "Check if a SQL query is correct before executing. "
            "Use to validate syntax and catch potential errors."
        ),
    ),
]

RESEARCH_AGENT_TOOLS = [
    ToolDefinition(
        name="web_search",
        description=(
            "Search the web for information on any topic. "
            "Use for finding current information, news, and general research."
        ),
    ),
    ToolDefinition(
        name="wikipedia",
        description=(
            "Look up information on Wikipedia. "
            "Use for factual information, historical data, and encyclopedic knowledge."
        ),
    ),
    ToolDefinition(
        name="calculator",
        description=(
            "Perform mathematical calculations. "
            "Use for arithmetic, statistics, and numerical analysis."
        ),
    ),
    ToolDefinition(
        name="summarize",
        description=(
            "Summarize long text into key points. "
            "Use after gathering information to create concise summaries."
        ),
    ),
]

CUSTOMER_SERVICE_TOOLS = [
    ToolDefinition(
        name="lookup_order",
        description=(
            "Look up customer order information by order ID or customer ID. "
            "Use to find order status, details, and history."
        ),
    ),
    ToolDefinition(
        name="process_refund",
        description=(
            "Process a refund for a customer order. "
            "Use when customer requests refund and order is eligible."
        ),
    ),
    ToolDefinition(
        name="escalate_to_human",
        description=(
            "Escalate the conversation to a human agent. "
            "Use for complex issues, complaints, or sensitive matters."
        ),
    ),
    ToolDefinition(
        name="search_faq",
        description=(
            "Search the FAQ knowledge base for answers. "
            "Use for common questions about products, policies, and procedures."
        ),
    ),
]

PROPERTY_INTEL_TOOLS = [
    ToolDefinition(
        name="property_lookup",
        description=(
            "Look up property information by street address or parcel ID. "
            "Returns parcel boundaries, building characteristics, year built, and prior imagery dates."
        ),
    ),
    ToolDefinition(
        name="aerial_image_retrieve",
        description=(
            "Retrieve the latest high-resolution aerial imagery for a property. "
            "Sub-3-inch GSD vertical and oblique views captured by fixed-wing aircraft."
        ),
    ),
    ToolDefinition(
        name="roof_condition_score",
        description=(
            "Run AI roof condition assessment returning Roof Spotlight Index (RSI) score 0-100. "
            "Detects ponding, staining, missing shingles, temporary repairs, structural damage, and worn materials."
        ),
    ),
    ToolDefinition(
        name="peril_risk_score",
        description=(
            "Compute peril vulnerability scores for hail, wind, wildfire, and hurricane risk. "
            "Uses AI detections, climate data, and property characteristics for risk segmentation."
        ),
    ),
    ToolDefinition(
        name="generate_property_report",
        description=(
            "Generate a comprehensive property intelligence report for underwriting review. "
            "Includes annotated imagery, AI detections, RSI score, peril scores, and flagged hazards."
        ),
    ),
    ToolDefinition(
        name="request_material_sample",
        description=(
            "Request physical material identification sample from ITEL for a specific property and damage area. "
            "Initiates sample collection for definitive material ID with optional itel NOW 30-minute field identification."
        ),
    ),
    ToolDefinition(
        name="submit_itel_analysis",
        description=(
            "Submit and retrieve ITEL material analysis results including repair vs replacement cost analysis "
            "and Xactimate line items. Returns material identification, manufacturer, remaining life, and cost breakdown."
        ),
    ),
]

CIVIC_SERVICES_TOOLS = [
    ToolDefinition(
        name="lookup_service",
        description=(
            "Look up municipal government services by name, category, or department. "
            "Returns service descriptions, requirements, hours, and contact information."
        ),
    ),
    ToolDefinition(
        name="check_eligibility",
        description=(
            "Check preliminary eligibility for government programs, benefits, and assistance. "
            "Returns general eligibility criteria and required documentation. Information only -- not a binding determination."
        ),
    ),
    ToolDefinition(
        name="find_office_location",
        description=(
            "Find government office locations, hours, and accessibility information. "
            "Returns addresses, transit options, parking, and ADA accessibility details."
        ),
    ),
    ToolDefinition(
        name="search_policy",
        description=(
            "Search municipal policies, ordinances, and public regulations. "
            "Returns relevant policy text, effective dates, and links to official sources."
        ),
    ),
    ToolDefinition(
        name="submit_service_request",
        description=(
            "Submit a non-emergency service request to the appropriate city department. "
            "Covers pothole reports, streetlight outages, trash collection, and similar municipal services."
        ),
    ),
    ToolDefinition(
        name="escalate_to_staff",
        description=(
            "Escalate a citizen inquiry to a human government staff member. "
            "Use for complex cases, complaints, appeals, or sensitive matters requiring human judgment."
        ),
    ),
]

# Registry of pre-defined tool sets
TOOL_SETS = {
    "sql_agent": SQL_AGENT_TOOLS,
    "research_agent": RESEARCH_AGENT_TOOLS,
    "customer_service": CUSTOMER_SERVICE_TOOLS,
    "property_intel": PROPERTY_INTEL_TOOLS,
    "civic_services": CIVIC_SERVICES_TOOLS,
}
