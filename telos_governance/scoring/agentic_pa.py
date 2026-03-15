"""
Agentic Primacy Attractor
==========================
Multi-dimensional governance specification for AI agents.

Unlike the conversational PA (single text + embedding), the agentic PA
defines governance across 6 independent dimensions:

1. Purpose  - What the agent is FOR (fidelity target)
2. Scope    - What domain the agent operates in
3. Boundaries - What the agent must NOT do (anti-fidelity)
4. Tool Authorization - Which tools are allowed and at what risk
5. Action Tiers - Categorized authorization requirements
6. Operational Constraints - Chain length, escalation rules

First Principles
-----------------
1. **Guardian-Ward Model**: The PA encodes the agent's constitutional
   authority -- not what the user wants, but what the agent is authorized
   to do. This inverts the classical Principal-Agent problem (Jensen &
   Meckling, 1976): the AI agent has no misaligned incentives; governance
   protects against user-driven drift outside the agent's mandate. The
   PA is the ward's charter, and the fidelity engine is the guardian.

2. **Semantic Density Hypothesis** (TELOS Research Program, 2026): Tool
   definitions, boundary specifications, and scope constraints are
   semantically denser than natural language conversation. A tool
   description like "Execute SQL SELECT queries" occupies a tighter
   region in embedding space than conversational text about databases.
   This density produces higher discriminative power in cosine similarity
   measurements -- the core hypothesis under empirical investigation.

3. **SAAI Framework** (Watson and Hessami, 2026): Boundaries map to SAAI
   Safety Foundational Requirements (SFRs). The inverted boundary
   scoring (high similarity = violation) implements SAAI's principle
   that safety constraints must be encoded as hard limits, not
   preferences. See SAAI §G1 (Goal Alignment), §G3 (Security).

4. **NIST AI 600-1** (Generative AI Profile, 2024 -- MAP 1.1, MAP 2.2):
   The AgenticPA is the concrete implementation of MAP 1.1 (documenting
   intended purpose) and MAP 2.2 (documenting system capabilities and
   limitations). Purpose, scope, boundaries, and tools define the agent's
   operational envelope -- the documented capability profile NIST 600-1
   requires for generative AI systems. The PA IS the governance document.

5. **OWASP LLM Top 10** (2025 -- LLM07, Insecure Plugin Design): Tool
   authorization with risk levels (low/medium/high/critical) and boundary
   specifications directly mitigate LLM07. Each tool's capabilities and
   constraints are explicitly defined in the PA, preventing unauthorized
   or unintended tool invocation. The require_human_above_risk threshold
   enforces human oversight for high-risk tool execution.

6. **IEEE P7000** (Model Process for Addressing Ethical Concerns, 2021):
   The 6-dimension PA embodies IEEE P7000's requirement that ethical
   considerations (boundaries, scope limits, escalation rules) are
   first-class architectural elements, not afterthought constraints.
   Each dimension is a structural governance property, not a comment
   or documentation annotation.

Uses "Detect and Direct" pattern:
- DETECT drift via multi-dimensional fidelity measurement
- DIRECT graduated response based on which dimension triggered
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np

# Percentile of member-to-centroid cosine similarity used to set per-cluster
# thresholds. 25th percentile means: a query must be at least as close to the
# sub-centroid as the bottom 25% of known violation phrasings. Lower values
# are more permissive (catch more violations, risk more false positives).
# Higher values are stricter (fewer false positives, may miss subtle violations).
# Recommended by Data Scientist agent, 2026-02-12.
SUB_CENTROID_THRESHOLD_PERCENTILE = 25


@dataclass
class BoundarySpec:
    """
    Something the agent should NOT do (anti-fidelity).

    Unlike purpose/scope (where high similarity = GOOD),
    boundaries use INVERTED scoring: high similarity = BAD.
    This operates on semantic meaning in embedding space, not
    keywords -- "DELETE FROM users" and "remove all user records"
    trigger the same boundary because cosine similarity measures
    intent, not phrasing.

    Severity levels map to Ostrom's graduated sanctions (DP5):
    - "soft": Warn but allow (log + direction) -- minor sanction
    - "hard": Block immediately (HARD_BLOCK) -- severe sanction

    Boundary Augmentation (2026-02-12):
    Boundaries can optionally use a centroid embedding computed from
    60-100 diverse violation phrasings instead of a single text embedding.
    This addresses the deontic logic limitation where prohibition text
    ("No binding underwriting decisions") occupies a different semantic
    neighborhood than action text ("approve this claim"). The centroid
    bypasses this by representing the boundary as the mean of affirmative
    violation phrasings -- what the embedding model handles well.
    See: research team synthesis, 2026-02-12.

    Sub-Centroid Clustering (2026-02-12):
    When the total corpus across all layers exceeds ~25 phrasings, a single
    centroid loses discriminative power ("centroid blurring" -- averaging
    many diverse unit vectors in 384 dimensions drifts toward the domain
    center). Sub-centroid clustering (K-means, K=3) preserves tight semantic
    clusters. At runtime, max-over-sub-centroids detects proximity to ANY
    violation pattern without single-centroid blurring.
    See: TELOS Research Team unanimous recommendation, 2026-02-12.
    """
    text: str
    embedding: Optional[np.ndarray] = None
    centroid_embedding: Optional[np.ndarray] = None  # Augmented centroid from corpus
    corpus_embeddings: Optional[np.ndarray] = None  # Individual phrasing embeddings (N x D)
    corpus_texts: List[str] = field(default_factory=list)  # All augmentation phrasings
    sub_centroids: Optional[np.ndarray] = None  # K x D sub-centroid embeddings from K-means
    sub_centroid_thresholds: Optional[np.ndarray] = None  # K thresholds (raw cosine), one per cluster
    safe_centroid: Optional[np.ndarray] = None  # Legitimate operations centroid for contrastive detection
    severity: str = "hard"  # "soft" (warn) or "hard" (block)

    @property
    def effective_embedding(self) -> Optional[np.ndarray]:
        """Return centroid if available, else single-text embedding.

        This property ensures backward compatibility: existing code that
        constructs BoundarySpec with only text + embedding continues to
        work unchanged. When a centroid is available (from corpus
        augmentation), it takes precedence because it covers a broader
        region of the violation surface in embedding space.
        """
        if self.centroid_embedding is not None:
            return self.centroid_embedding
        return self.embedding


def _kmeans_centroids(
    embeddings: np.ndarray, k: int = 3, max_iter: int = 20
) -> Tuple[np.ndarray, np.ndarray]:
    """K-means clustering on L2-normalized embeddings.

    Returns K sub-centroids and cluster assignments for per-cluster
    threshold calibration. Preserves tight semantic clusters that a
    single mean centroid blurs when the corpus exceeds ~25 phrasings
    in 384 dimensions.

    Args:
        embeddings: (N, D) array of phrasing embeddings
        k: Number of clusters (default 3: direct, indirect, formal)
        max_iter: Maximum iterations

    Returns:
        Tuple of:
        - centroids: (K, D) array of L2-normalized cluster centroids
        - assignments: (N,) array of cluster indices per embedding
    """
    n = embeddings.shape[0]
    k = min(k, n)

    # L2 normalize input
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = embeddings / norms

    # Max-min initialization: pick k diverse seed points
    rng = np.random.RandomState(42)
    indices = [rng.randint(n)]
    for _ in range(k - 1):
        selected = normed[indices]
        sims = normed @ selected.T  # (n, num_selected)
        max_sims = sims.max(axis=1)
        next_idx = int(np.argmin(max_sims))
        indices.append(next_idx)

    centroids = normed[indices].copy()

    for _ in range(max_iter):
        sims = normed @ centroids.T  # (n, k)
        assignments = np.argmax(sims, axis=1)

        new_centroids = np.zeros_like(centroids)
        for j in range(k):
            mask = assignments == j
            if np.any(mask):
                mean = normed[mask].mean(axis=0)
                norm_val = np.linalg.norm(mean)
                new_centroids[j] = mean / norm_val if norm_val > 0 else centroids[j]
            else:
                new_centroids[j] = centroids[j]

        if np.allclose(centroids, new_centroids, atol=1e-6):
            break
        centroids = new_centroids

    # Recompute assignments against final centroids for threshold calibration
    final_sims = normed @ centroids.T
    final_assignments = np.argmax(final_sims, axis=1)

    return centroids, final_assignments


@dataclass
class ToolAuth:
    """
    Per-tool authorization specification.

    Pre-computed alignment to purpose avoids repeated embedding
    computation at runtime. Risk level determines escalation rules.
    """
    tool_name: str
    description: str
    risk_level: str = "low"  # "low", "medium", "high", "critical"
    requires_confirmation: bool = False
    pa_alignment: float = 0.0  # Pre-computed alignment to purpose


@dataclass
class ActionTierSpec:
    """
    Categories of actions with authorization requirements.

    Tier system for fast path/slow path decisions:
    - always_allowed: No governance check needed (read-only, safe)
    - requires_confirmation: Governance passes but human confirms
    - always_blocked: Rejected regardless of fidelity score
    """
    always_allowed: List[str] = field(default_factory=list)
    requires_confirmation: List[str] = field(default_factory=list)
    always_blocked: List[str] = field(default_factory=list)


@dataclass
class AgenticPA:
    """
    Multi-dimensional Primacy Attractor for agent governance.

    Extends the conversational PA (single embedding) to 6 dimensions
    that capture the full governance surface for agentic AI. Think of
    it as a complete job description encoded in embedding space -- every
    action the agent considers is measured against all 6 dimensions.

    Each dimension is independently measurable, enabling fine-grained
    governance decisions (e.g., purpose-aligned but out-of-scope, or
    in-scope but boundary-violating). This multi-dimensional measurement
    is what enables graduated sanctions -- the system knows not just
    "how far" from alignment, but "in which direction" the drift occurs.

    Theoretical basis: The PA implements what Ostrom (1990) calls the
    "clearly defined boundaries" principle (DP1) -- the resource (agent
    capability) has explicit boundaries, and the governance system
    enforces them through measurement rather than prohibition.
    """

    # Dimension 1: Purpose -- what the agent is FOR
    purpose_text: str
    purpose_embedding: Optional[np.ndarray] = None
    # Individual example embeddings for max-pool scoring (Cat C accuracy)
    purpose_example_embeddings: Optional[List[np.ndarray]] = None
    # Sub-centroid clusters from K-means on purpose examples (K=3).
    # Mirrors boundary sub-centroid architecture: tighter clusters avoid
    # centroid blurring when many diverse examples are averaged.
    # Only activated when >= 6 examples are available.
    purpose_sub_centroids: Optional[np.ndarray] = None  # (K, D) array
    purpose_sub_centroid_thresholds: Optional[np.ndarray] = None  # (K,) raw cosine thresholds

    # Dimension 2: Scope -- what domain the agent operates in
    scope_text: str = ""
    scope_embedding: Optional[np.ndarray] = None
    # Individual example embeddings for max-pool scoring (Cat C accuracy)
    scope_example_embeddings: Optional[List[np.ndarray]] = None
    # Sub-centroid clusters for scope examples (same pattern as purpose)
    scope_sub_centroids: Optional[np.ndarray] = None
    scope_sub_centroid_thresholds: Optional[np.ndarray] = None

    # Dimension 3: Boundaries -- what the agent must NOT do (anti-fidelity)
    boundaries: List[BoundarySpec] = field(default_factory=list)

    # Dimension 4: Tool Authorization -- per-tool governance
    tool_manifest: Dict[str, ToolAuth] = field(default_factory=dict)

    # Dimension 5: Action Tiers -- categorical authorization
    action_tiers: ActionTierSpec = field(default_factory=ActionTierSpec)

    # Dimension 6: Operational Constraints
    max_chain_length: int = 20
    max_tool_calls_per_step: int = 5
    escalation_threshold: float = 0.50
    require_human_above_risk: str = "high"

    # Confirmer safety gate: MPNet boundary embeddings for secondary check.
    # Built lazily via build_confirmer_centroids() when confirmer is enabled.
    # Stores per-boundary MPNet embeddings for boundary-only re-scoring.
    confirmer_boundary_embeddings: Optional[List[np.ndarray]] = None
    confirmer_purpose_embedding: Optional[np.ndarray] = None

    @classmethod
    def create_from_template(
        cls,
        purpose: str,
        scope: str,
        boundaries: List,
        tools: List,
        embed_fn: Callable[[str], np.ndarray],
        example_requests: Optional[List[str]] = None,
        scope_example_requests: Optional[List[str]] = None,
        template_id: Optional[str] = None,
        boundary_augmentation: Optional[Dict[str, List[str]]] = None,
        safe_exemplars: Optional[List[str]] = None,
        max_chain_length: int = 20,
        max_tool_calls_per_step: int = 5,
        escalation_threshold: float = 0.50,
        require_human_above_risk: str = "high",
    ) -> "AgenticPA":
        """
        Factory: create AgenticPA from template data, auto-embedding all text.

        Args:
            purpose: Agent's purpose statement (Dimension 1)
            scope: Agent's operational scope (Dimension 2)
            boundaries: List of boundary strings or dicts with text/severity
            tools: List of objects with .name and .description attributes.
                Optional .risk_level and .requires_confirmation are read via
                getattr and passed through to ToolAuth (Dimension 4).
            embed_fn: Function to embed text -> np.ndarray
            example_requests: Optional list of example on-topic requests used
                to build a centroid embedding for the purpose dimension. This
                dramatically improves discrimination in lower-dimensional
                models (MiniLM 384-dim) where single-text embeddings produce
                near-identical scores for on-topic and off-topic queries.
            scope_example_requests: Optional list of example in-scope requests
                used to build a centroid embedding for the scope dimension.
                Same principle as purpose centroid: multi-text averaging
                dramatically improves discrimination vs single-text embedding.
                If not provided, scope uses a single embedding (legacy behavior).
            template_id: Optional template identifier for loading boundary
                augmentation corpus (e.g., "property_intel")
            boundary_augmentation: Optional dict mapping boundary text to
                list of violation phrasings. If provided, overrides the
                static corpus lookup. Used for testing and custom corpora.
            safe_exemplars: Optional list of legitimate requests that use
                boundary-adjacent vocabulary (e.g., "score", "assess",
                "decision"). Used to build a safe centroid for contrastive
                boundary detection, reducing false positives on legitimate
                requests that superficially resemble boundary violations.
            max_chain_length: Dimension 6 -- max action chain length (default 20)
            max_tool_calls_per_step: Dimension 6 -- max tools per step (default 5)
            escalation_threshold: Dimension 6 -- fidelity threshold for escalation (default 0.50)
            require_human_above_risk: Dimension 6 -- risk level requiring human review (default "high")

        Returns:
            Fully initialized AgenticPA with all embeddings pre-computed
        """
        # Build purpose centroid from purpose + scope + example requests
        # This dramatically improves discrimination in lower-dimensional models (MiniLM 384-dim)
        centroid_texts = [purpose]
        if scope:
            centroid_texts.append(scope)
        if example_requests:
            centroid_texts.extend(example_requests[:5])  # Use up to 5 examples

        centroid_embeddings = [embed_fn(text) for text in centroid_texts]
        purpose_emb = np.mean(centroid_embeddings, axis=0)
        purpose_emb = purpose_emb / np.linalg.norm(purpose_emb)  # L2 normalize

        # Preserve individual example embeddings for max-pool scoring.
        # The centroid averages away specificity; max-pool against individual
        # examples recovers it for Cat C (legitimate operations that score
        # low against the broad centroid but high against specific examples).
        # Store ALL examples (not just first 5 used for centroid) because
        # max-pool benefits from broader tool-group coverage.
        purpose_example_embs: Optional[List[np.ndarray]] = None
        if example_requests:
            purpose_example_embs = [embed_fn(text) for text in example_requests]

        # Purpose sub-centroid clustering: mirrors boundary sub-centroid architecture.
        # When >= 6 purpose examples exist, K-means (K=3) preserves tight semantic
        # clusters that a single mean centroid blurs. At runtime, max-over-qualified-
        # sub-centroids recovers the specificity that centroid averaging destroys.
        # This selectively boosts Cat C (legitimate operations matching known example
        # clusters) without boosting Cat A (boundary violations don't cluster well
        # with legitimate examples). PAs with < 6 examples are unaffected.
        purpose_sub_cents = None
        purpose_sub_thresholds = None
        if purpose_example_embs and len(purpose_example_embs) >= 6:
            example_arr = np.array(purpose_example_embs)
            purpose_sub_cents, sub_assignments = _kmeans_centroids(example_arr, k=3)

            # Per-cluster threshold calibration (25th percentile of member similarities)
            e_norms = np.linalg.norm(example_arr, axis=1, keepdims=True)
            e_norms[e_norms == 0] = 1.0
            example_normed = example_arr / e_norms

            purpose_sub_thresholds = np.zeros(purpose_sub_cents.shape[0])
            for j in range(purpose_sub_cents.shape[0]):
                mask = sub_assignments == j
                if np.any(mask):
                    member_sims = example_normed[mask] @ purpose_sub_cents[j]
                    purpose_sub_thresholds[j] = float(np.percentile(
                        member_sims, SUB_CENTROID_THRESHOLD_PERCENTILE
                    ))
                else:
                    purpose_sub_thresholds[j] = 1.0  # No members → never match

        # Scope embedding: centroid if examples provided, single embedding otherwise
        scope_example_embs: Optional[List[np.ndarray]] = None
        if scope and scope_example_requests:
            scope_centroid_texts = [scope]
            scope_centroid_texts.extend(scope_example_requests[:5])
            scope_centroid_embeddings = [embed_fn(text) for text in scope_centroid_texts]
            scope_emb = np.mean(scope_centroid_embeddings, axis=0)
            scope_emb = scope_emb / np.linalg.norm(scope_emb)
            scope_example_embs = [embed_fn(text) for text in scope_example_requests]
        elif scope:
            scope_emb = embed_fn(scope)
        else:
            scope_emb = None

        # Scope sub-centroid clustering (same pattern as purpose)
        scope_sub_cents = None
        scope_sub_thresholds = None
        if scope_example_embs and len(scope_example_embs) >= 6:
            scope_arr = np.array(scope_example_embs)
            scope_sub_cents, scope_sub_assign = _kmeans_centroids(scope_arr, k=3)

            s_norms = np.linalg.norm(scope_arr, axis=1, keepdims=True)
            s_norms[s_norms == 0] = 1.0
            scope_normed = scope_arr / s_norms

            scope_sub_thresholds = np.zeros(scope_sub_cents.shape[0])
            for j in range(scope_sub_cents.shape[0]):
                mask = scope_sub_assign == j
                if np.any(mask):
                    member_sims = scope_normed[mask] @ scope_sub_cents[j]
                    scope_sub_thresholds[j] = float(np.percentile(
                        member_sims, SUB_CENTROID_THRESHOLD_PERCENTILE
                    ))
                else:
                    scope_sub_thresholds[j] = 1.0

        # Build boundary specs with embeddings (and optional centroid augmentation)
        # Layer 1: Hand-crafted anchor phrasings (weight 1.0 in centroid)
        # Layer 2: LLM-generated gap-fillers (integrated via sub-centroid clustering)
        # Layer 3: Regulatory text extractions (weight 0.5 in centroid)
        from telos_governance.boundary_corpus_static import get_boundary_corpus
        layer1_corpus = boundary_augmentation or get_boundary_corpus(template_id or "")

        # Load Layer 3 regulatory corpus (skip if custom augmentation provided)
        layer3_corpus: dict = {}
        if not boundary_augmentation:
            try:
                from telos_governance.boundary_corpus_regulatory import get_regulatory_corpus
                layer3_corpus = get_regulatory_corpus(template_id or "")
            except ImportError:
                pass  # No regulatory corpus available

        # Load Layer 2 LLM-generated corpus for sub-centroid clustering
        layer2_corpus: dict = {}
        if not boundary_augmentation:
            try:
                from telos_governance.boundary_corpus_llm import get_llm_corpus
                layer2_corpus = get_llm_corpus(template_id or "")
            except ImportError:
                pass  # No LLM corpus available

        boundary_specs = []
        for b in boundaries:
            b_text = b if isinstance(b, str) else b["text"]
            b_severity = "hard" if isinstance(b, str) else b.get("severity", "hard")

            # Always compute single-text embedding (fallback)
            single_emb = embed_fn(b_text)

            # Get phrasings from Layer 1 + Layer 3
            l1_texts = layer1_corpus.get(b_text, [])
            l3_texts = layer3_corpus.get(b_text, [])
            all_corpus_texts = l1_texts + l3_texts
            centroid_emb = None
            all_embeddings = []

            if l1_texts or l3_texts:
                # Weighted centroid: L1 at 1.0, L3 at 0.5
                # L1 anchors the centroid core. L3 expands with
                # regulatory-grounded violations at reduced weight.
                l1_embeddings = [embed_fn(t) for t in l1_texts]
                l3_embeddings = [embed_fn(t) for t in l3_texts]

                weights = (
                    [1.0] * len(l1_embeddings)
                    + [0.5] * len(l3_embeddings)
                )
                all_embeddings = l1_embeddings + l3_embeddings

                # Weighted mean
                weighted_sum = sum(
                    w * e for w, e in zip(weights, all_embeddings)
                )
                centroid_emb = weighted_sum / sum(weights)
                norm = np.linalg.norm(centroid_emb)
                if norm > 0:
                    centroid_emb = centroid_emb / norm  # L2 normalize

            # Store individual embeddings for potential future use
            individual_embs = None
            if all_embeddings:
                individual_embs = np.array(all_embeddings)

            # Sub-centroid clustering: L1 + L2 + L3 → K-means → K tight clusters
            # Solves centroid blurring at 50+ phrasings in 384-dim space.
            # Per-cluster thresholds gate runtime matching to prevent false positives.
            l2_texts = layer2_corpus.get(b_text, [])
            sub_cents = None
            sub_thresholds = None
            cluster_embs = list(all_embeddings)  # L1 + L3 already computed
            if l2_texts:
                cluster_embs.extend(embed_fn(t) for t in l2_texts)

            if len(cluster_embs) >= 6:  # K=3 needs >= 2K samples
                cluster_arr = np.array(cluster_embs)
                sub_cents, sub_assignments = _kmeans_centroids(cluster_arr, k=3)

                # Per-cluster threshold calibration: for each cluster, compute
                # cosine similarity of every member to its centroid. The Nth
                # percentile becomes the cluster's minimum match threshold.
                # Tight clusters (direct violations) → high threshold.
                # Loose clusters (indirect/jargon) → lower threshold.
                c_norms = np.linalg.norm(cluster_arr, axis=1, keepdims=True)
                c_norms[c_norms == 0] = 1.0
                cluster_normed = cluster_arr / c_norms

                sub_thresholds = np.zeros(sub_cents.shape[0])
                for j in range(sub_cents.shape[0]):
                    mask = sub_assignments == j
                    if np.any(mask):
                        member_sims = cluster_normed[mask] @ sub_cents[j]
                        sub_thresholds[j] = float(np.percentile(
                            member_sims, SUB_CENTROID_THRESHOLD_PERCENTILE
                        ))
                    else:
                        sub_thresholds[j] = 1.0  # No members → never match

            # Include L2 in corpus texts for auditability
            if l2_texts:
                all_corpus_texts = l1_texts + l2_texts + l3_texts

            boundary_specs.append(BoundarySpec(
                text=b_text,
                embedding=single_emb,
                centroid_embedding=centroid_emb,
                corpus_embeddings=individual_embs,
                corpus_texts=all_corpus_texts,
                sub_centroids=sub_cents,
                sub_centroid_thresholds=sub_thresholds,
                severity=b_severity,
            ))

        # Per-boundary safe centroids for contrastive boundary detection.
        # Phase 2 fix (2026-02-12): Each boundary gets its OWN safe centroid
        # built from boundary-specific legitimate exemplars, not a shared centroid.
        # Shared centroids caused 21.8% Cat A regression due to vocabulary
        # contamination -- the safe centroid for "no PII access" was diluted by
        # exemplars about "underwriting decisions", pulling it toward boundary 1's
        # violation space. Per-boundary centroids keep each safe region tight.
        #
        # Priority: per-boundary corpus > shared safe_exemplars > nothing
        safe_centroid_shared = None  # Lazy-built shared fallback
        per_boundary_corpus: dict = {}
        if template_id:
            try:
                from telos_governance.boundary_corpus_safe import get_safe_corpus
                per_boundary_corpus = get_safe_corpus(template_id)
            except ImportError:
                pass  # No per-boundary corpus available

        for bs in boundary_specs:
            # Try per-boundary safe exemplars first (Phase 2)
            boundary_safe_texts = per_boundary_corpus.get(bs.text, [])
            if boundary_safe_texts:
                safe_embs = [embed_fn(t) for t in boundary_safe_texts]
                sc = np.mean(safe_embs, axis=0)
                sc_norm = np.linalg.norm(sc)
                if sc_norm > 0:
                    sc = sc / sc_norm
                bs.safe_centroid = sc
            elif safe_exemplars:
                # Fallback: shared safe_exemplars (Phase 1 backward compat)
                if safe_centroid_shared is None:
                    safe_embs = [embed_fn(t) for t in safe_exemplars]
                    safe_centroid_shared = np.mean(safe_embs, axis=0)
                    sc_norm = np.linalg.norm(safe_centroid_shared)
                    if sc_norm > 0:
                        safe_centroid_shared = safe_centroid_shared / sc_norm
                bs.safe_centroid = safe_centroid_shared

        # Build tool manifest with pre-computed PA alignment
        tool_manifest = {}
        purpose_norm = np.linalg.norm(purpose_emb)
        for tool in tools:
            tool_text = f"{tool.name}: {tool.description}"
            tool_emb = embed_fn(tool_text)
            tool_norm = np.linalg.norm(tool_emb)

            if purpose_norm > 0 and tool_norm > 0:
                alignment = float(
                    np.dot(tool_emb, purpose_emb) / (tool_norm * purpose_norm)
                )
            else:
                alignment = 0.0

            tool_manifest[tool.name] = ToolAuth(
                tool_name=tool.name,
                description=tool.description,
                risk_level=getattr(tool, 'risk_level', 'low'),
                requires_confirmation=getattr(tool, 'requires_confirmation', False),
                pa_alignment=alignment,
            )

        return cls(
            purpose_text=purpose,
            purpose_embedding=purpose_emb,
            purpose_example_embeddings=purpose_example_embs,
            purpose_sub_centroids=purpose_sub_cents,
            purpose_sub_centroid_thresholds=purpose_sub_thresholds,
            scope_text=scope or "",
            scope_embedding=scope_emb,
            scope_example_embeddings=scope_example_embs,
            scope_sub_centroids=scope_sub_cents,
            scope_sub_centroid_thresholds=scope_sub_thresholds,
            boundaries=boundary_specs,
            tool_manifest=tool_manifest,
            max_chain_length=max_chain_length,
            max_tool_calls_per_step=max_tool_calls_per_step,
            escalation_threshold=escalation_threshold,
            require_human_above_risk=require_human_above_risk,
        )

    def build_confirmer_centroids(
        self,
        confirmer_embed_fn: Callable[[str], np.ndarray],
    ) -> None:
        """Build MPNet boundary centroids for the confirmer safety gate.

        Called lazily on first confirmer activation. Embeds each boundary's
        text with the confirmer model (MPNet 768-dim) and stores the
        embeddings for boundary-only re-scoring.

        Also builds a confirmer purpose embedding for contrastive checks.

        Args:
            confirmer_embed_fn: MPNet embedding function (encode text -> np.ndarray)
        """
        self.confirmer_boundary_embeddings = []
        for boundary in self.boundaries:
            emb = confirmer_embed_fn(boundary.text)
            self.confirmer_boundary_embeddings.append(emb)
        self.confirmer_purpose_embedding = confirmer_embed_fn(self.purpose_text)
