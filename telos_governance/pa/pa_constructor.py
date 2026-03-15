"""
PA Constructor -- Builds tool-grounded Purpose Anchors with two-gate support.

This module constructs AgenticPAs where the purpose centroid is grounded in
canonical tool definitions rather than abstract mission text. Each tool gets
its own centroid in embedding space, and the overall purpose centroid is the
risk-weighted mean of all per-tool centroids.

Architecture: Two Sequential Gates
───────────────────────────────────
Gate 1 -- Tool Selection Fidelity: "Is this the right tool for this purpose?"
    Per-tool centroids built from canonical tool definitions (tool_semantics.py).
    Each tool's centroid is the L2-normalized mean of:
        1. The tool's semantic_description embedding
        2. All legitimate_exemplar embeddings
    Scored via cosine(action_embedding, tool_centroids[tool_name]).

Gate 2 -- Behavioral Fidelity: "How are you planning to use it?"
    Scope centroid from aggregated scope_constraints (grounded in tool context).
    Boundary corpus unchanged (existing 15+ boundaries with contrastive detection).
    Chain continuity unchanged.
    This is where TELOS methodology lives -- scoring the HOW, not the WHAT.

Provenance:
    Tool definitions sourced from first-party platform documentation:
    - Claude Code tools → Anthropic system prompt
    - OpenClaw tools → docs.openclaw.ai
    See tool_semantics.py for per-definition provenance citations.

Consumed by:
    telos_adapters/openclaw/config_loader.py → _build_pa() when
    construction_mode == "tool_grounded"
"""

import logging
from typing import Callable, Dict, List, Optional

import numpy as np

from telos_governance.tool_semantics import (
    TOOL_DEFINITIONS,
    ToolDefinition,
    get_all_definitions,
    get_risk_weight,
)

logger = logging.getLogger(__name__)


class PAConstructor:
    """Constructs a tool-grounded AgenticPA with per-tool centroids.

    The constructor takes an embedding function and builds centroids from
    canonical tool definitions. The resulting PA has:
        - tool_centroids: Dict[str, np.ndarray] -- per-tool Gate 1 centroids
        - purpose_embedding: np.ndarray -- aggregate centroid for backward compat
        - purpose_example_embeddings: List[np.ndarray] -- all exemplar embeddings
        - scope_embedding: np.ndarray -- scope centroid from tool constraints
    """

    def __init__(self, embed_fn: Callable[[str], np.ndarray]):
        """Initialize with embedding function.

        Args:
            embed_fn: Function that embeds text → np.ndarray (384-dim for MiniLM).
                Must be the same function used at scoring time for consistent
                cosine similarity (Gebru: model version pinning is critical).
        """
        self._embed_fn = embed_fn

    def construct(
        self,
        purpose: str,
        scope: str,
        boundaries: List,
        tools: List,
        example_requests: Optional[List[str]] = None,
        scope_example_requests: Optional[List[str]] = None,
        template_id: Optional[str] = None,
        boundary_augmentation: Optional[Dict[str, List[str]]] = None,
        safe_exemplars: Optional[List[str]] = None,
        max_chain_length: int = 20,
        max_tool_calls_per_step: int = 5,
        escalation_threshold: float = 0.50,
        require_human_above_risk: str = "high",
        tool_definitions: Optional[Dict[str, ToolDefinition]] = None,
    ) -> "AgenticPA":
        """Construct an AgenticPA with tool-grounded centroids.

        This replaces AgenticPA.create_from_template() for the tool_grounded
        construction mode. The interface is designed to be a drop-in at the
        config_loader.py integration point.

        Args:
            purpose: Agent's purpose statement (Dimension 1) -- used in combined
                centroid, but NOT as the primary Gate 1 signal.
            scope: Agent's operational scope (Dimension 2).
            boundaries: List of boundary strings or dicts with text/severity.
            tools: List of tool objects with .name, .description, .risk_level.
            example_requests: Optional legacy exemplars (merged into combined centroid).
            scope_example_requests: Optional scope exemplars.
            template_id: Template ID for boundary corpus lookup.
            boundary_augmentation: Optional custom boundary phrasings.
            safe_exemplars: Optional safe exemplars for contrastive detection.
            max_chain_length: Max action chain length.
            max_tool_calls_per_step: Max tools per step.
            escalation_threshold: Fidelity threshold for escalation.
            require_human_above_risk: Risk level requiring human review.
            tool_definitions: Override tool definitions (default: TOOL_DEFINITIONS).
                Pass None to use the canonical definitions from tool_semantics.py.

        Returns:
            Fully initialized AgenticPA with tool_centroids dict + standard fields.
        """
        from telos_governance.agentic_pa import AgenticPA

        defs = tool_definitions if tool_definitions is not None else get_all_definitions()

        # ── Gate 1: Build per-tool centroids ──
        tool_centroids = self._build_tool_centroids(defs)
        logger.info(
            f"Gate 1: Built {len(tool_centroids)} per-tool centroids "
            f"from canonical definitions"
        )

        # ── Combined purpose centroid (backward compat) ──
        # Risk-weighted mean of per-tool centroids. Low-risk tools contribute
        # more because they represent the operational center of gravity.
        if tool_centroids:
            purpose_emb = self._build_combined_centroid(defs, tool_centroids)
        else:
            purpose_emb = None

        # Merge legacy example_requests if provided
        all_exemplar_embeddings = self._collect_exemplar_embeddings(defs)
        if example_requests:
            for text in example_requests:
                all_exemplar_embeddings.append(self._embed_fn(text))

        # ── Gate 2: Build scope centroid from tool constraints ──
        scope_emb = self._build_scope_centroid(defs, scope)

        scope_example_embs = None
        if scope_example_requests:
            scope_example_embs = [
                self._embed_fn(text) for text in scope_example_requests
            ]

        # ── Delegate boundary construction to existing create_from_template ──
        # We build the PA via the standard factory, then attach tool_centroids.
        # This preserves ALL existing boundary logic (corpus, sub-centroids,
        # safe centroids, SetFit integration) without reimplementing it.
        from types import SimpleNamespace
        tool_objects = [
            SimpleNamespace(
                name=t.name if hasattr(t, "name") else t,
                description=t.description if hasattr(t, "description") else "",
                risk_level=getattr(t, "risk_level", "low"),
            )
            for t in tools
        ]

        pa = AgenticPA.create_from_template(
            purpose=purpose,
            scope=scope,
            boundaries=boundaries,
            tools=tool_objects,
            embed_fn=self._embed_fn,
            example_requests=example_requests,
            scope_example_requests=scope_example_requests,
            template_id=template_id,
            boundary_augmentation=boundary_augmentation,
            safe_exemplars=safe_exemplars,
            max_chain_length=max_chain_length,
            max_tool_calls_per_step=max_tool_calls_per_step,
            escalation_threshold=escalation_threshold,
            require_human_above_risk=require_human_above_risk,
        )

        # ── DO NOT override pa.purpose_embedding ──
        # Gate 2 behavioral scoring needs the abstract mission-text centroid
        # that create_from_template() set. The risk-weighted combined centroid
        # (purpose_emb) shifts into action-verb space, inflating off-topic
        # scores past thresholds. Gate 1 per-tool centroids handle tool
        # selection independently via pa.tool_centroids.
        # See: centroid separation fix (recalibration phase).

        # ── Attach per-tool centroids (Gate 1 data) ──
        pa.tool_centroids = tool_centroids  # type: ignore[attr-defined]

        # ── Merge tool exemplar embeddings into existing exemplars ──
        # Additive: extend the exemplar pool rather than replacing it.
        # This preserves the abstract exemplars from create_from_template()
        # while adding tool-grounded exemplars for sub-centroid clustering.
        if all_exemplar_embeddings:
            existing = getattr(pa, 'purpose_example_embeddings', None) or []
            pa.purpose_example_embeddings = existing + all_exemplar_embeddings

        # ── Override scope embedding if tool-grounded scope is better ──
        if scope_emb is not None:
            pa.scope_embedding = scope_emb

        logger.info(
            f"PAConstructor: Built tool-grounded PA with "
            f"{len(tool_centroids)} tool centroids, "
            f"{len(all_exemplar_embeddings)} exemplar embeddings, "
            f"{len(pa.boundaries)} boundaries"
        )

        return pa

    def _build_tool_centroids(
        self, defs: Dict[str, ToolDefinition]
    ) -> Dict[str, np.ndarray]:
        """Build per-tool centroids from canonical definitions.

        For each tool: embed semantic_description + all legitimate_exemplars,
        compute the L2-normalized mean. This centroid sits in the SAME
        embedding space as runtime action text because the exemplars are
        in build_action_text() format.

        Returns:
            Dict mapping telos_tool_name → L2-normalized centroid vector.
        """
        centroids: Dict[str, np.ndarray] = {}

        for tool_name, defn in defs.items():
            embeddings = []

            # Embed the semantic description
            desc_emb = self._embed_fn(defn.semantic_description)
            embeddings.append(desc_emb)

            # Embed each legitimate exemplar
            for exemplar in defn.legitimate_exemplars:
                emb = self._embed_fn(exemplar)
                embeddings.append(emb)

            # Compute centroid: mean of all embeddings, L2-normalized
            centroid = np.mean(embeddings, axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = centroid / norm

            centroids[tool_name] = centroid

            logger.debug(
                f"Tool centroid '{tool_name}': "
                f"{1 + len(defn.legitimate_exemplars)} embeddings → centroid"
            )

        return centroids

    def _build_combined_centroid(
        self,
        defs: Dict[str, ToolDefinition],
        tool_centroids: Dict[str, np.ndarray],
    ) -> np.ndarray:
        """Build the aggregate purpose centroid from per-tool centroids.

        Uses inverse risk weighting: low-risk tools contribute more because
        they represent the dominant operational center of gravity (reads,
        searches, edits) rather than rare high-risk operations.

        Returns:
            L2-normalized aggregate centroid vector.
        """
        weighted_sum = np.zeros_like(next(iter(tool_centroids.values())))
        total_weight = 0.0

        for tool_name, centroid in tool_centroids.items():
            defn = defs.get(tool_name)
            weight = get_risk_weight(defn.risk_level) if defn else 0.5
            weighted_sum += weight * centroid
            total_weight += weight

        if total_weight > 0:
            combined = weighted_sum / total_weight
        else:
            combined = weighted_sum

        norm = np.linalg.norm(combined)
        if norm > 0:
            combined = combined / norm

        return combined

    def _build_scope_centroid(
        self,
        defs: Dict[str, ToolDefinition],
        scope_text: str,
    ) -> Optional[np.ndarray]:
        """Build scope centroid from tool scope_constraints + scope text.

        Aggregates all scope_constraints across tool definitions with the
        main scope text to produce a grounded scope centroid.

        Returns:
            L2-normalized scope centroid, or None if no scope data.
        """
        scope_texts = []

        if scope_text:
            scope_texts.append(scope_text)

        for defn in defs.values():
            for constraint in defn.scope_constraints:
                scope_texts.append(constraint)

        if not scope_texts:
            return None

        embeddings = [self._embed_fn(text) for text in scope_texts]
        centroid = np.mean(embeddings, axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm

        return centroid

    def _collect_exemplar_embeddings(
        self, defs: Dict[str, ToolDefinition]
    ) -> List[np.ndarray]:
        """Collect all exemplar embeddings across all tool definitions.

        These feed into purpose_example_embeddings for max-pool scoring
        and sub-centroid clustering (Cat C accuracy).

        Returns:
            List of exemplar embedding vectors.
        """
        all_embs: List[np.ndarray] = []

        for defn in defs.values():
            for exemplar in defn.legitimate_exemplars:
                emb = self._embed_fn(exemplar)
                all_embs.append(emb)

        logger.debug(f"Collected {len(all_embs)} total exemplar embeddings")
        return all_embs
