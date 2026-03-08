"""
TELOSCOPE Interpreter Agent
=============================

Natural language frontend for the TELOSCOPE research instrument. Receives
researcher queries, routes them to the correct research tool via semantic
similarity (when available) or keyword matching (always available), extracts
parameters from the query text, and dispatches the tool call.

Architecture:
    Researcher query
        -> route_query()    [centroid cosine sim | keyword fallback]
        -> _extract_params() [regex/keyword extraction]
        -> execute()        [dispatch to tool function]
        -> TeloscopeAudit   [Gate 2 observation log]
        -> chain tracking   [suspicious pattern detection]

Import pattern: try telos_governance.* first, fallback to direct imports.

Routing:
    When sentence-transformers is available, builds per-tool centroids from
    the tool_semantics.py exemplars (same approach as test_semantic_routing.py).
    When not available, falls back to keyword matching -- the interpreter is
    fully functional without the embedding model.

Chain continuity:
    Tracks tool call sequence for the session. Detects suspicious patterns
    from the report quality specification:
      - 3+ sweeps without stats/inspect (parameter search without examining results)
      - 5+ rescores (iterative refinement, result-shopping risk)
      - 20+ tool calls without documented research question (open-ended fishing)
    Logs warnings but does NOT block (observation mode).

Usage:
    from telos_governance.interpreter import TeloscopeInterpreter

    interp = TeloscopeInterpreter(audit_dir="~/.telos/posthoc_audit/")

    # Route a query
    tool_name, confidence, top3 = interp.route_query("Show me the fidelity distribution")

    # Execute a query end-to-end
    result = interp.execute("Compare Bash to Read")

    # Session info
    print(interp.status())

    # Reset
    interp.reset()
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Imports: try telos_governance.* first, fallback to direct ──────────────

try:
    from telos_governance.corpus import AuditCorpus, load_corpus
except ImportError:
    from corpus import AuditCorpus, load_corpus

try:
    from telos_governance.teloscope_audit import (
        TeloscopeAudit,
        MethodologicalCheck,
        check_sample_size,
        check_denominator,
        check_comparison_balance,
        check_corpus_size,
        check_sweep_bounds,
    )
except ImportError:
    from teloscope_audit import (
        TeloscopeAudit,
        MethodologicalCheck,
        check_sample_size,
        check_denominator,
        check_comparison_balance,
        check_corpus_size,
        check_sweep_bounds,
    )

# Tool modules — each imported with fallback
# NOTE: The local inspect.py module shares a name with Python's stdlib
# inspect module. We use importlib.util to load the local file by path
# when the telos_governance package import fails, avoiding the stdlib
# name collision entirely.
try:
    from telos_governance.inspect import (
        inspect_event, inspect_window, root_cause_summary,
    )
except ImportError:
    try:
        import importlib.util as _ilu
        import os as _os
        _inspect_path = _os.path.join(
            _os.path.dirname(_os.path.abspath(__file__)), "inspect.py"
        )
        _spec = _ilu.spec_from_file_location("teloscope_inspect", _inspect_path)
        _inspect_mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_inspect_mod)
        inspect_event = _inspect_mod.inspect_event
        inspect_window = _inspect_mod.inspect_window
        root_cause_summary = _inspect_mod.root_cause_summary
        del _ilu, _os, _inspect_path, _spec, _inspect_mod
    except Exception:
        inspect_event = inspect_window = root_cause_summary = None

try:
    from telos_governance.stats import (
        corpus_stats, dimension_impact, histogram, cross_tabulate,
        format_cross_tab,
    )
except ImportError:
    try:
        from stats import (
            corpus_stats, dimension_impact, histogram, cross_tabulate,
            format_cross_tab,
        )
    except ImportError:
        corpus_stats = dimension_impact = histogram = None
        cross_tabulate = format_cross_tab = None

try:
    from telos_governance.rescore import rescore
except ImportError:
    try:
        from rescore import rescore
    except ImportError:
        rescore = None

try:
    from telos_governance.sweep import sweep, multi_sweep
except ImportError:
    try:
        from sweep import sweep, multi_sweep
    except ImportError:
        sweep = multi_sweep = None

try:
    from telos_governance.timeline import (
        timeline, session_timeline, detect_regime_change,
        format_regime_changes,
    )
except ImportError:
    try:
        from timeline import (
            timeline, session_timeline, detect_regime_change,
            format_regime_changes,
        )
    except ImportError:
        timeline = session_timeline = detect_regime_change = None
        format_regime_changes = None

try:
    from telos_governance.compare import (
        compare, compare_sessions, compare_tools, compare_periods,
    )
except ImportError:
    try:
        from compare import (
            compare, compare_sessions, compare_tools, compare_periods,
        )
    except ImportError:
        compare = compare_sessions = compare_tools = compare_periods = None

try:
    from telos_governance.validate import validate
except ImportError:
    try:
        from validate import validate
    except ImportError:
        validate = None

# Optional: sentence-transformers for semantic routing
_HAS_EMBEDDINGS = False
_embedding_model = None
try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    _HAS_EMBEDDINGS = True
except ImportError:
    np = None
    SentenceTransformer = None

# Optional: tool definitions for centroid construction
_TOOL_DEFINITIONS = None
try:
    from telos_governance.tool_semantics import TOOL_DEFINITIONS as _TD
    _TOOL_DEFINITIONS = _TD
except ImportError:
    try:
        from tool_semantics import TOOL_DEFINITIONS as _TD
        _TOOL_DEFINITIONS = _TD
    except ImportError:
        _TOOL_DEFINITIONS = None


# ── Constants ─────────────────────────────────────────────────────────────

# All 7 TELOSCOPE research tools
RESEARCH_TOOLS = [
    "research_audit_load",
    "research_audit_inspect",
    "research_audit_stats",
    "research_audit_rescore",
    "research_audit_sweep",
    "research_audit_timeline",
    "research_audit_compare",
    "research_audit_validate",
]

# Short names for display and keyword matching
SHORT_NAMES = {name: name.replace("research_audit_", "") for name in RESEARCH_TOOLS}
LONG_NAMES = {v: k for k, v in SHORT_NAMES.items()}

# Fidelity dimensions recognized in queries
DIMENSIONS = {"composite", "purpose", "scope", "boundary", "tool", "chain"}

# Verdicts recognized in queries
VERDICTS = {"EXECUTE", "CLARIFY", "INERT", "ESCALATE"}

# Known tool names from the audit data (for parameter extraction)
KNOWN_TOOLS = {
    "bash", "read", "edit", "write", "grep", "glob", "notebookedit",
    "webfetch", "websearch", "toolsearch", "listmcpresourcestool",
    "readmcpresourcetool",
}

# ── Operational Caps ─────────────────────────────────────────────────────

MAX_CORPUS_EVENTS = 50000
MAX_SWEEP_POINTS = 200
MAX_TOOL_CALLS_WITHOUT_QUESTION = 20
SWEEP_WARN_CONSECUTIVE = 3
RESCORE_WARN_CONSECUTIVE = 5


# ═══════════════════════════════════════════════════════════════════════════
# Keyword routing rules
# ═══════════════════════════════════════════════════════════════════════════

# Each rule: (keyword_set, tool_name, priority_boost)
# Higher priority_boost wins when multiple rules match.
# Rules are evaluated against the lowercased query.

_KEYWORD_RULES: List[Tuple[List[str], str, float]] = [
    # ── load ──
    (["load", "corpus"], "research_audit_load", 1.0),
    (["how many events"], "research_audit_load", 1.0),
    (["how many sessions"], "research_audit_load", 0.9),
    (["count"], "research_audit_load", 0.6),
    (["load"], "research_audit_load", 0.8),
    (["summarize", "corpus"], "research_audit_load", 0.7),
    (["summary"], "research_audit_load", 0.5),

    # ── inspect ──
    (["inspect"], "research_audit_inspect", 1.0),
    (["show me event"], "research_audit_inspect", 1.0),
    (["detail"], "research_audit_inspect", 0.8),
    (["why did"], "research_audit_inspect", 0.9),
    (["what happened"], "research_audit_inspect", 0.8),
    (["worst-scoring"], "research_audit_inspect", 0.9),
    (["worst scoring"], "research_audit_inspect", 0.9),
    (["lowest fidelity"], "research_audit_inspect", 0.9),
    (["show me", "event"], "research_audit_inspect", 0.9),
    (["context window"], "research_audit_inspect", 0.9),
    (["surrounding events"], "research_audit_inspect", 0.8),
    (["deep view"], "research_audit_inspect", 0.9),
    (["root cause"], "research_audit_inspect", 0.8),
    (["escalated"], "research_audit_inspect", 0.6),

    # ── stats ──
    (["stat"], "research_audit_stats", 0.8),
    (["distribution"], "research_audit_stats", 0.8),
    (["mean"], "research_audit_stats", 0.8),
    (["mean", "versus"], "research_audit_stats", 1.0),
    (["mean", "vs"], "research_audit_stats", 1.0),
    (["median"], "research_audit_stats", 0.7),
    (["histogram"], "research_audit_stats", 1.0),
    (["cross-tabulate"], "research_audit_stats", 1.0),
    (["cross tabulate"], "research_audit_stats", 1.0),
    (["crosstab"], "research_audit_stats", 1.0),
    (["which dimension"], "research_audit_stats", 0.9),
    (["causing"], "research_audit_stats", 0.7),
    (["groupby"], "research_audit_stats", 0.9),
    (["grouped by"], "research_audit_stats", 0.9),
    (["broken down by"], "research_audit_stats", 0.8),
    (["dimension"], "research_audit_stats", 0.5),
    (["percentile"], "research_audit_stats", 0.8),
    (["standard deviation"], "research_audit_stats", 0.8),

    # ── rescore ──
    (["rescore"], "research_audit_rescore", 1.0),
    (["re-score"], "research_audit_rescore", 1.0),
    (["what would happen if"], "research_audit_rescore", 0.9),
    (["what if"], "research_audit_rescore", 0.7),
    (["counterfactual"], "research_audit_rescore", 1.0),
    (["migration"], "research_audit_rescore", 0.7),
    (["verdict migration"], "research_audit_rescore", 0.9),
    (["changed thresholds"], "research_audit_rescore", 0.8),
    (["higher", "weight"], "research_audit_rescore", 0.6),
    (["raised", "threshold"], "research_audit_rescore", 0.7),
    (["lowered", "threshold"], "research_audit_rescore", 0.7),

    # ── sweep ──
    (["sweep"], "research_audit_sweep", 1.0),
    (["dose-response"], "research_audit_sweep", 1.0),
    (["dose response"], "research_audit_sweep", 1.0),
    (["optimal threshold"], "research_audit_sweep", 0.9),
    (["find the optimal"], "research_audit_sweep", 0.9),
    (["minimize false positive"], "research_audit_sweep", 0.8),
    (["from", "to", "step"], "research_audit_sweep", 0.7),
    (["sensitivity analysis"], "research_audit_sweep", 0.8),
    (["grid search"], "research_audit_sweep", 0.8),

    # ── timeline ──
    (["timeline"], "research_audit_timeline", 1.0),
    (["over time"], "research_audit_timeline", 0.9),
    (["trend"], "research_audit_timeline", 0.8),
    (["getting better"], "research_audit_timeline", 0.9),
    (["getting worse"], "research_audit_timeline", 0.9),
    (["improving"], "research_audit_timeline", 0.7),
    (["degrading"], "research_audit_timeline", 0.7),
    (["regime change"], "research_audit_timeline", 1.0),
    (["structural break"], "research_audit_timeline", 1.0),
    (["did something change"], "research_audit_timeline", 0.8),
    (["across sessions"], "research_audit_timeline", 0.7),

    # ── compare ──
    (["compare"], "research_audit_compare", 1.0),
    (["versus"], "research_audit_compare", 0.9),
    (["vs"], "research_audit_compare", 0.8),
    (["differ"], "research_audit_compare", 0.8),
    (["difference between"], "research_audit_compare", 0.9),
    (["side-by-side"], "research_audit_compare", 0.9),
    (["side by side"], "research_audit_compare", 0.9),
    (["before and after"], "research_audit_compare", 0.8),
    (["first half", "second half"], "research_audit_compare", 0.9),
    (["significant difference"], "research_audit_compare", 0.9),

    # ── validate ──
    (["validate"], "research_audit_validate", 1.0),
    (["tamper"], "research_audit_validate", 1.0),
    (["integrity"], "research_audit_validate", 0.9),
    (["hash chain"], "research_audit_validate", 1.0),
    (["signature"], "research_audit_validate", 0.9),
    (["reproducibility"], "research_audit_validate", 0.9),
    (["verify"], "research_audit_validate", 0.7),
    (["intact"], "research_audit_validate", 0.8),
    (["prove"], "research_audit_validate", 0.6),
    (["compliance"], "research_audit_validate", 0.5),
]


def _keyword_route(query: str) -> List[Tuple[str, float]]:
    """Route a query using keyword matching. Returns scored candidates.

    Each keyword rule contributes its priority_boost to the matching tool.
    When a rule has multiple keywords, ALL must be present (AND logic).
    Final score per tool is the maximum boost from any matching rule.

    Returns:
        List of (tool_name, score) sorted by score descending.
    """
    q = query.lower()
    tool_scores: Dict[str, float] = {}

    for keywords, tool_name, boost in _KEYWORD_RULES:
        # All keywords in the rule must be present
        if all(kw in q for kw in keywords):
            current = tool_scores.get(tool_name, 0.0)
            tool_scores[tool_name] = max(current, boost)

    # Sort by score descending
    ranked = sorted(tool_scores.items(), key=lambda x: -x[1])
    return ranked


# ═══════════════════════════════════════════════════════════════════════════
# Semantic routing (embedding-based)
# ═══════════════════════════════════════════════════════════════════════════

def _build_centroids(model, tool_defs: Dict) -> Dict[str, Any]:
    """Build per-tool centroids from tool_semantics exemplars.

    Same approach as test_semantic_routing.py: embed the semantic_description
    plus all legitimate_exemplars, then average and normalize.
    """
    centroids = {}
    for name, defn in tool_defs.items():
        if not name.startswith("research_audit_"):
            continue
        texts = [defn.semantic_description] + list(defn.legitimate_exemplars)
        embeddings = model.encode(texts, normalize_embeddings=True)
        centroid = np.mean(embeddings, axis=0)
        centroid = centroid / np.linalg.norm(centroid)
        centroids[name] = centroid
    return centroids


def _semantic_route(
    model, centroids: Dict, query: str
) -> List[Tuple[str, float]]:
    """Route query via cosine similarity to tool centroids.

    Returns:
        List of (tool_name, similarity_score) sorted by score descending.
    """
    query_emb = model.encode([query], normalize_embeddings=True)[0]
    scores = {}
    for name, centroid in centroids.items():
        scores[name] = float(np.dot(query_emb, centroid))
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return ranked


# ═══════════════════════════════════════════════════════════════════════════
# Parameter extraction
# ═══════════════════════════════════════════════════════════════════════════

def _extract_params(query: str, tool_name: str) -> Dict[str, Any]:
    """Extract parameters from a natural language query for a given tool.

    Uses regex and keyword patterns to pull out:
      - event_index: numbers after "index" or "event"
      - event_id: hex strings that look like event IDs
      - tool_a, tool_b: tool names after "compare" / "vs" / "versus"
      - threshold: numbers after "threshold"
      - session_id: session + hex pattern
      - window_size: numbers after "window"
      - dimension: recognized dimension names
      - verdict: recognized verdict names
      - groupby: field names after "by" or "grouped by"
      - start, stop, step: range parameters for sweep

    Returns:
        Dict of extracted kwargs. Empty dict if nothing found.
    """
    params: Dict[str, Any] = {}
    q = query.strip()
    ql = q.lower()

    short = SHORT_NAMES.get(tool_name, tool_name.replace("research_audit_", ""))

    # ── Event index extraction ──
    # "index 42", "event 42", "#42", "[42]"
    idx_match = re.search(
        r'(?:index|event|#)\s*(\d+)|'
        r'\[(\d+)\]',
        ql
    )
    if idx_match:
        val = idx_match.group(1) or idx_match.group(2)
        params["index"] = int(val)

    # ── Event ID extraction (hex-like strings with hyphens) ──
    # Looks for UUIDs or hex strings like "abc123", "audit-1772153040"
    eid_match = re.search(
        r'(?:event\s+(?:id\s+)?|id\s+)'
        r'([0-9a-f]{8,}(?:-[0-9a-f]{4,})*)',
        ql
    )
    if eid_match:
        params["event_id"] = eid_match.group(1)

    # ── Tool names for compare ──
    # "compare Bash to Read", "Bash vs Edit", "Bash versus Read"
    if short in ("compare", "stats"):
        # Pattern: "compare X to Y", "compare X and Y", "X vs Y", "X versus Y"
        cmp_match = re.search(
            r'compare\s+(\w+)\s+(?:to|and|with|versus|vs\.?)\s+(\w+)',
            ql
        )
        if not cmp_match:
            cmp_match = re.search(
                r'(\w+)\s+(?:versus|vs\.?)\s+(\w+)',
                ql
            )
        if cmp_match:
            a_raw = cmp_match.group(1)
            b_raw = cmp_match.group(2)
            # Check if these are known audit tool names (capitalize first letter)
            a_canon = _canonicalize_tool(a_raw)
            b_canon = _canonicalize_tool(b_raw)
            if a_canon and b_canon:
                params["tool_a"] = a_canon
                params["tool_b"] = b_canon

        # Session comparison: "compare session X to session Y"
        sess_cmp = re.search(
            r'(?:compare\s+)?session\s+(\S+)\s+(?:to|and|with|versus|vs\.?)\s+'
            r'(?:session\s+)?(\S+)',
            ql
        )
        if sess_cmp:
            params["session_a"] = sess_cmp.group(1)
            params["session_b"] = sess_cmp.group(2)

    # ── Before/after index for compare ──
    # "before and after event 800", "before index 500"
    if short == "compare":
        ba_match = re.search(
            r'(?:before\s+and\s+after|before/after|split\s+at)\s+'
            r'(?:event\s+|index\s+)?(\d+)',
            ql
        )
        if ba_match:
            params["before_index"] = int(ba_match.group(1))

        # "first half ... second half"
        if "first half" in ql and "second half" in ql:
            params["split_half"] = True

    # ── Threshold value extraction ──
    # "threshold to 0.55", "threshold 0.55", "threshold=0.55"
    thresh_match = re.search(
        r'(?:execute\s+)?threshold\s*(?:to|=|of)?\s*(0?\.\d+|\d+\.\d+)',
        ql
    )
    if thresh_match:
        params["threshold"] = float(thresh_match.group(1))

    # Specific threshold parameters: "st_execute", "st_clarify", etc.
    for param_name in ("st_execute", "st_clarify",
                        "boundary_violation"):
        pat = re.search(
            rf'{param_name}\s*(?:to|=)?\s*(0?\.\d+|\d+\.\d+)',
            ql
        )
        if pat:
            params[param_name] = float(pat.group(1))

    # ── Weight extraction ──
    # "purpose weight 0.45", "higher purpose weight", "weight_purpose=0.45"
    for dim in ("purpose", "scope", "tool", "chain", "boundary"):
        w_match = re.search(
            rf'(?:weight[_\s]?{dim}|{dim}\s+weight)\s*(?:to|=|of)?\s*'
            rf'(0?\.\d+|\d+\.\d+)',
            ql
        )
        if w_match:
            key = f"weight_{dim}"
            if dim == "boundary":
                key = "weight_boundary_penalty"
            params[key] = float(w_match.group(1))

    # ── Session ID extraction ──
    # "session abc123", "session_id cec0864e"
    sess_match = re.search(
        r'session[\s_](?:id\s+)?([0-9a-f]{6,})',
        ql
    )
    if sess_match:
        params["session_id"] = sess_match.group(1)

    # ── Window size extraction ──
    # "window 5", "window size 100", "radius 5"
    win_match = re.search(
        r'(?:window(?:\s+size)?|radius)\s*(?:of\s+)?(\d+)',
        ql
    )
    if win_match:
        params["window_size"] = int(win_match.group(1))

    # ── Dimension extraction ──
    for dim in DIMENSIONS:
        if dim in ql:
            params["dimension"] = dim
            break

    # ── Verdict extraction ──
    for verdict in VERDICTS:
        if verdict.lower() in ql:
            params["verdict"] = verdict
            break

    # ── Groupby extraction ──
    # "by verdict", "grouped by tool_call", "broken down by session"
    gb_match = re.search(
        r'(?:grouped?\s+by|broken\s+down\s+by|by)\s+'
        r'(verdict|tool_call|tool|session_id|session)',
        ql
    )
    if gb_match:
        raw_gb = gb_match.group(1)
        # Normalize
        if raw_gb == "tool":
            raw_gb = "tool_call"
        elif raw_gb == "session":
            raw_gb = "session_id"
        params["groupby"] = raw_gb

    # ── Sweep range extraction ──
    # "from 0.30 to 0.70", "from 0.30 to 0.70 step 0.05"
    if short == "sweep":
        range_match = re.search(
            r'from\s+(0?\.\d+|\d+\.?\d*)\s+to\s+(0?\.\d+|\d+\.?\d*)'
            r'(?:\s+(?:step|in)\s+(0?\.\d+|\d+\.?\d*))?',
            ql
        )
        if range_match:
            params["start"] = float(range_match.group(1))
            params["stop"] = float(range_match.group(2))
            if range_match.group(3):
                params["step"] = float(range_match.group(3))

        # Parameter name for sweep: "sweep the execute threshold",
        # "sweep st_execute", "sweep boundary_violation"
        sweep_param = re.search(
            r'sweep\s+(?:the\s+)?(?:over\s+)?'
            r'(st_execute|st_clarify|boundary_violation|'
            r'weight_purpose|weight_scope|weight_tool|weight_chain|'
            r'weight_boundary_penalty|execute\s+threshold|'
            r'clarify\s+threshold|boundary\s+threshold)',
            ql
        )
        if sweep_param:
            raw_param = sweep_param.group(1).strip()
            # Normalize human names to config param names
            param_map = {
                "execute threshold": "st_execute",
                "clarify threshold": "st_clarify",
                "boundary threshold": "boundary_violation",
            }
            params["param_name"] = param_map.get(raw_param, raw_param)

    # ── Sort order extraction ──
    if "ascending" in ql:
        params["ascending"] = True
    elif "descending" in ql or "worst" in ql or "lowest" in ql:
        params["ascending"] = False

    # ── Limit extraction ──
    limit_match = re.search(r'(?:top|first|limit|show)\s+(\d+)', ql)
    if limit_match:
        params["limit"] = int(limit_match.group(1))

    # ── Bins extraction for histogram ──
    bins_match = re.search(r'(\d+)\s+bins?', ql)
    if bins_match:
        params["bins"] = int(bins_match.group(1))

    # ── Lookback for regime change detection ──
    lb_match = re.search(r'lookback\s+(\d+)', ql)
    if lb_match:
        params["lookback"] = int(lb_match.group(1))

    # ── Z-score threshold for regime change ──
    z_match = re.search(
        r'(?:z-?score|threshold)\s*(?:of|=)?\s*(\d+\.?\d*)',
        ql
    )
    if z_match and short == "timeline":
        params["z_threshold"] = float(z_match.group(1))

    return params


def _canonicalize_tool(raw: str) -> Optional[str]:
    """Canonicalize a tool name from a query to the official form.

    Returns None if the name isn't recognized.
    """
    lower = raw.lower().strip()
    # Direct match in KNOWN_TOOLS
    for known in KNOWN_TOOLS:
        if lower == known:
            # Return with proper capitalization
            return raw.capitalize() if len(raw) > 1 else raw.upper()
    # Common aliases
    aliases = {
        "bash": "Bash",
        "read": "Read",
        "edit": "Edit",
        "write": "Write",
        "grep": "Grep",
        "glob": "Glob",
        "notebook": "NotebookEdit",
        "notebookedit": "NotebookEdit",
        "webfetch": "WebFetch",
        "websearch": "WebSearch",
        "toolsearch": "ToolSearch",
    }
    return aliases.get(lower)


# ═══════════════════════════════════════════════════════════════════════════
# Chain pattern detection
# ═══════════════════════════════════════════════════════════════════════════

def _detect_suspicious_patterns(chain: List[str]) -> List[str]:
    """Detect suspicious chain patterns.

    Returns a list of warning messages for detected patterns.
    """
    warnings = []
    if not chain:
        return warnings

    n = len(chain)
    shorts = [SHORT_NAMES.get(t, t.replace("research_audit_", "")) for t in chain]

    # Pattern: 3+ consecutive sweeps without stats/inspect
    consecutive_sweeps = 0
    for i, s in enumerate(shorts):
        if s == "sweep":
            consecutive_sweeps += 1
        elif s in ("stats", "inspect"):
            consecutive_sweeps = 0
        # Don't reset on other tools -- sweep,load,sweep still counts
        if consecutive_sweeps >= SWEEP_WARN_CONSECUTIVE:
            warnings.append(
                f"CLARIFY: {consecutive_sweeps} sweep calls without "
                f"stats/inspect. Parameter search without examining results "
                f"-- possible p-hacking. (chain position {i})"
            )
            consecutive_sweeps = 0  # Only warn once per streak

    # Pattern: 5+ rescore calls (cumulative, not just consecutive)
    rescore_count = sum(1 for s in shorts if s == "rescore")
    if rescore_count >= RESCORE_WARN_CONSECUTIVE:
        warnings.append(
            f"CLARIFY: {rescore_count} rescore calls in session. "
            f"Iterative refinement -- result-shopping risk."
        )

    # Pattern: many inspect calls filtering on session_id
    # (heuristic: 5+ inspect calls total could indicate profiling)
    inspect_count = sum(1 for s in shorts if s == "inspect")
    if inspect_count >= 5:
        warnings.append(
            f"CLARIFY: {inspect_count} inspect calls in session. "
            f"If filtering on session_id, verify this is governance "
            f"analysis, not user profiling."
        )

    # Pattern: 3+ exports to different paths
    export_count = sum(1 for s in shorts if s == "export")
    if export_count >= 3:
        warnings.append(
            f"ESCALATE: {export_count} export calls in session. "
            f"Possible data spraying."
        )

    # Pattern: any tool call with no prior load
    if n > 0 and shorts[0] != "load" and shorts[0] != "validate":
        # First call should typically be load or validate
        warnings.append(
            f"NOTE: First tool call was '{shorts[0]}', not 'load'. "
            f"Corpus should be loaded before analysis."
        )

    # Operational cap: 20+ calls without research question
    if n >= MAX_TOOL_CALLS_WITHOUT_QUESTION:
        warnings.append(
            f"CLARIFY: {n} tool calls without documented research "
            f"question. Open-ended fishing -- please document your "
            f"research objective."
        )

    return warnings


# ═══════════════════════════════════════════════════════════════════════════
# TeloscopeInterpreter
# ═══════════════════════════════════════════════════════════════════════════

class TeloscopeInterpreter:
    """TELOSCOPE natural language interpreter and tool dispatcher.

    Routes researcher queries to the correct research tool via semantic
    similarity (when sentence-transformers is available) or keyword
    matching (always available). Extracts parameters, dispatches tool
    calls, logs to TeloscopeAudit, and tracks chain continuity.

    Args:
        audit_dir: Path to the audit data directory (e.g., ~/.telos/posthoc_audit/).
        output_dir: Optional output directory for TeloscopeAudit logs.
            Defaults to ~/.telos/teloscope_audit/.
        telemetry_enabled: Whether to enable telemetry on the audit logger.

    Example:
        interp = TeloscopeInterpreter("~/.telos/posthoc_audit/")
        result = interp.execute("Show me the fidelity distribution grouped by verdict")
        print(result)
    """

    def __init__(
        self,
        audit_dir: str,
        output_dir: Optional[str] = None,
        telemetry_enabled: bool = False,
    ):
        self._audit_dir = audit_dir
        self._output_dir = output_dir or "~/.telos/teloscope_audit"
        self._telemetry_enabled = telemetry_enabled

        # Lazy state
        self._corpus: Optional[AuditCorpus] = None
        self._model = None          # SentenceTransformer (lazy)
        self._centroids = None      # Per-tool centroids (lazy)
        self._model_load_attempted = False

        # Audit logger
        self._audit = TeloscopeAudit(
            output_dir=self._output_dir,
            telemetry_enabled=telemetry_enabled,
        )

        # Session chain tracking
        self._chain: List[str] = []     # Tool names in call order
        self._call_count: int = 0
        self._warnings_issued: set = set()

    # ── Corpus management ─────────────────────────────────────────────

    def _ensure_corpus(self) -> AuditCorpus:
        """Lazily load the corpus on first access."""
        if self._corpus is None:
            self._corpus = load_corpus(self._audit_dir)
            logger.info(
                "Corpus loaded: %d events from %s",
                len(self._corpus), self._audit_dir,
            )
        return self._corpus

    # ── Embedding model management ────────────────────────────────────

    def _ensure_model(self) -> bool:
        """Lazily load the embedding model and build centroids.

        Returns True if embedding routing is available, False otherwise.
        """
        if self._model is not None:
            return True
        if self._model_load_attempted:
            return False

        self._model_load_attempted = True

        if not _HAS_EMBEDDINGS:
            logger.info("sentence-transformers not available. Using keyword routing.")
            return False

        if _TOOL_DEFINITIONS is None:
            logger.info("TOOL_DEFINITIONS not available. Using keyword routing.")
            return False

        try:
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._centroids = _build_centroids(self._model, _TOOL_DEFINITIONS)
            logger.info(
                "Embedding model loaded. %d research tool centroids built.",
                len(self._centroids),
            )
            return True
        except Exception as e:
            logger.warning("Failed to load embedding model: %s. Using keyword routing.", e)
            return False

    # ── Routing ───────────────────────────────────────────────────────

    def route_query(
        self, query: str
    ) -> Tuple[str, float, List[Tuple[str, float]]]:
        """Route a natural language query to the best-matching research tool.

        Uses semantic embedding similarity when available, falls back to
        keyword matching otherwise.

        Args:
            query: Natural language research question.

        Returns:
            Tuple of:
                - best_tool_name: Full tool name (e.g., "research_audit_stats")
                - confidence: Score of the best match (0.0 to 1.0)
                - top_3: List of (tool_name, score) for the top 3 candidates
        """
        # Try embedding-based routing
        if self._ensure_model() and self._centroids:
            ranked = _semantic_route(self._model, self._centroids, query)
            if ranked:
                best_name = ranked[0][0]
                best_score = ranked[0][1]
                top_3 = ranked[:3]
                return best_name, best_score, top_3

        # Keyword fallback
        ranked = _keyword_route(query)
        if ranked:
            best_name = ranked[0][0]
            best_score = ranked[0][1]
            top_3 = ranked[:3]
            return best_name, best_score, top_3

        # Last resort: no match found, default to stats (most general)
        return "research_audit_stats", 0.0, [("research_audit_stats", 0.0)]

    # ── Dispatch ──────────────────────────────────────────────────────

    def execute(self, query: str, **kwargs) -> str:
        """Route, extract parameters, dispatch, audit, and return result.

        End-to-end execution of a natural language research query:
        1. Route to the best tool
        2. Extract parameters from the query
        3. Call the tool function
        4. Log the call to TeloscopeAudit (Gate 2 observation)
        5. Track chain continuity (pattern detection)
        6. Return formatted result string

        Args:
            query: Natural language research question.
            **kwargs: Override parameters (take precedence over extracted).

        Returns:
            Formatted result string. Includes methodological warnings
            if any checks triggered.
        """
        # 1. Route
        tool_name, confidence, top_3 = self.route_query(query)
        short = SHORT_NAMES.get(tool_name, tool_name.replace("research_audit_", ""))

        # 2. Extract params
        extracted = _extract_params(query, tool_name)
        extracted.update(kwargs)  # Explicit kwargs override

        # 3. Dispatch
        result_text, checks = self._dispatch(tool_name, extracted, query)

        # 4. Audit
        self._audit.log_tool_call(
            tool_name=tool_name,
            tool_args=extracted,
            checks=checks,
        )

        # 5. Chain tracking
        self._chain.append(tool_name)
        self._call_count += 1
        chain_warnings = _detect_suspicious_patterns(self._chain)
        # Only issue NEW warnings (avoid repeating)
        new_warnings = [w for w in chain_warnings if w not in self._warnings_issued]
        for w in new_warnings:
            self._warnings_issued.add(w)
            logger.warning(w)

        # 6. Format output
        output_parts = []

        # Routing context
        output_parts.append(
            f"[TELOSCOPE] Routed to: {short} "
            f"(confidence={confidence:.2f}, "
            f"method={'semantic' if self._model else 'keyword'})"
        )

        # Methodological warnings
        warning_text = self._audit.format_warnings(checks)
        if warning_text:
            output_parts.append(warning_text)

        # Chain warnings
        if new_warnings:
            output_parts.append("")
            for w in new_warnings:
                output_parts.append(f"[CHAIN] {w}")

        # Result
        output_parts.append("")
        output_parts.append(result_text)

        return "\n".join(output_parts)

    def _dispatch(
        self,
        tool_name: str,
        params: Dict[str, Any],
        query: str,
    ) -> Tuple[str, List[MethodologicalCheck]]:
        """Dispatch a tool call and return (result_text, checks).

        Each tool has its own dispatch logic that maps extracted parameters
        to function arguments, runs methodological checks, and formats
        the output.
        """
        short = SHORT_NAMES.get(tool_name, tool_name.replace("research_audit_", ""))
        checks: List[MethodologicalCheck] = []

        try:
            if short == "load":
                return self._dispatch_load(params, checks)
            elif short == "inspect":
                return self._dispatch_inspect(params, checks)
            elif short == "stats":
                return self._dispatch_stats(params, checks)
            elif short == "rescore":
                return self._dispatch_rescore(params, checks)
            elif short == "sweep":
                return self._dispatch_sweep(params, checks)
            elif short == "timeline":
                return self._dispatch_timeline(params, checks)
            elif short == "compare":
                return self._dispatch_compare(params, checks)
            elif short == "validate":
                return self._dispatch_validate(params, checks)
            else:
                return f"Unknown tool: {tool_name}", checks
        except Exception as e:
            logger.error("Tool dispatch error (%s): %s", tool_name, e)
            return f"Error executing {short}: {e}", checks

    # ── Per-tool dispatch implementations ─────────────────────────────

    def _dispatch_load(
        self, params: Dict, checks: List[MethodologicalCheck]
    ) -> Tuple[str, List[MethodologicalCheck]]:
        """Load/reload the corpus and return summary."""
        # Force reload if called explicitly
        self._corpus = load_corpus(self._audit_dir)
        corpus = self._corpus

        # Corpus size check
        checks.append(check_corpus_size(len(corpus)))

        # Format
        return corpus.summary_table(), checks

    def _dispatch_inspect(
        self, params: Dict, checks: List[MethodologicalCheck]
    ) -> Tuple[str, List[MethodologicalCheck]]:
        """Inspect events."""
        if inspect_event is None:
            return "inspect module not available.", checks

        corpus = self._ensure_corpus()

        # Denominator disclosure
        checks.append(check_denominator(len(corpus), len(corpus)))

        # Determine mode: window vs event inspection
        if "window_size" in params and "index" in params:
            # Window mode
            radius = params.get("window_size", 5)
            center = params["index"]
            result = inspect_window(corpus, center=center, radius=radius)
            return result.format(), checks

        # Event inspection
        inspect_kwargs: Dict[str, Any] = {}
        if "index" in params:
            inspect_kwargs["index"] = params["index"]
        if "event_id" in params:
            inspect_kwargs["event_id"] = params["event_id"]
        if "verdict" in params:
            inspect_kwargs["verdict"] = params["verdict"]
        if "ascending" in params:
            inspect_kwargs["ascending"] = params["ascending"]
        if "limit" in params:
            inspect_kwargs["limit"] = params["limit"]
        if "dimension" in params:
            inspect_kwargs["sort_by"] = params["dimension"]

        # Check for "root cause" query
        ql = params.get("_query", "").lower()
        if not ql:
            # Build a simple query check from params
            pass
        # We don't have the original query here, but root_cause gets
        # triggered by keyword routing anyway

        if not inspect_kwargs:
            # No specific target -- show root cause summary
            if root_cause_summary is not None:
                rc = root_cause_summary(corpus)
                lines = ["Root Cause Summary", "=" * 30]
                for verdict, drivers in rc.items():
                    lines.append(f"\n  {verdict}:")
                    for driver, count in drivers.items():
                        lines.append(f"    {driver:<25} {count:>5}")
                return "\n".join(lines), checks

            # Fallback: inspect first event
            inspect_kwargs["index"] = 0

        details = inspect_event(corpus, **inspect_kwargs)
        if not details:
            return "No events matched the filter criteria.", checks

        # Sample size check for filtered results
        if len(details) < len(corpus):
            checks.append(
                check_denominator(
                    len(details), len(corpus),
                    filter_desc=str({k: v for k, v in inspect_kwargs.items()
                                     if k not in ("limit", "offset")}),
                )
            )

        output = "\n\n".join(d.format() for d in details)
        return output, checks

    def _dispatch_stats(
        self, params: Dict, checks: List[MethodologicalCheck]
    ) -> Tuple[str, List[MethodologicalCheck]]:
        """Compute and display statistics."""
        if corpus_stats is None:
            return "stats module not available.", checks

        corpus = self._ensure_corpus()

        # Sample size check
        checks.append(check_sample_size(len(corpus), claim_type="general"))

        # Denominator
        checks.append(check_denominator(len(corpus), len(corpus)))

        groupby = params.get("groupby")
        dimensions = None
        if "dimension" in params:
            dimensions = [params["dimension"]]

        # Dispatch to the right stats function
        ql_lower = str(params).lower()

        # Histogram
        if params.get("bins") or "histogram" in ql_lower:
            if histogram is None:
                return "histogram function not available.", checks
            dim = params.get("dimension", "composite")
            bins = params.get("bins", 20)
            hist = histogram(corpus, dimension=dim, bins=bins)
            lines = [f"Histogram: {dim} ({bins} bins)", "=" * 40]
            for start, end, count in hist:
                bar = "#" * min(count, 60)
                lines.append(f"  [{start:.3f}, {end:.3f}) {count:>5} {bar}")
            return "\n".join(lines), checks

        # Cross-tabulation
        if "cross" in ql_lower or "xtab" in ql_lower or "crosstab" in ql_lower:
            if cross_tabulate is None:
                return "cross_tabulate function not available.", checks
            xtab = cross_tabulate(corpus)
            if format_cross_tab is not None:
                return format_cross_tab(xtab), checks
            return str(xtab), checks

        # Dimension impact
        if "impact" in ql_lower or "culprit" in ql_lower or "causing" in ql_lower:
            if dimension_impact is None:
                return "dimension_impact function not available.", checks
            impact = dimension_impact(corpus)
            lines = ["Dimension Impact (non-EXECUTE events)", "=" * 40]
            for dim_name, freq, interp in impact:
                lines.append(f"  {dim_name:<12} {freq:>5.0%}  {interp}")
            return "\n".join(lines), checks

        # Standard stats
        result = corpus_stats(corpus, groupby=groupby, dimensions=dimensions)
        return result.format(), checks

    def _dispatch_rescore(
        self, params: Dict, checks: List[MethodologicalCheck]
    ) -> Tuple[str, List[MethodologicalCheck]]:
        """Run counterfactual re-scoring."""
        if rescore is None:
            return "rescore module not available.", checks

        corpus = self._ensure_corpus()

        # Sample size check
        checks.append(check_sample_size(len(corpus), claim_type="general"))

        # Build rescore kwargs
        rescore_kwargs: Dict[str, Any] = {}
        for key in ("st_execute", "st_clarify",
                     "boundary_violation", "weight_purpose", "weight_scope",
                     "weight_tool", "weight_chain", "weight_boundary_penalty"):
            if key in params:
                rescore_kwargs[key] = params[key]

        # If only a generic "threshold" was extracted and no specific param,
        # assume st_execute (most common use case)
        if "threshold" in params and "st_execute" not in rescore_kwargs:
            rescore_kwargs["st_execute"] = params["threshold"]

        result = rescore(corpus, **rescore_kwargs)
        return result.summary_table(), checks

    def _dispatch_sweep(
        self, params: Dict, checks: List[MethodologicalCheck]
    ) -> Tuple[str, List[MethodologicalCheck]]:
        """Run parameter sweep."""
        if sweep is None:
            return "sweep module not available.", checks

        corpus = self._ensure_corpus()

        # Determine sweep parameters
        param_name = params.get("param_name", "st_execute")
        start = params.get("start", 0.30)
        stop = params.get("stop", 0.70)
        step = params.get("step", 0.05)

        # Compute number of sweep points
        n_points = int((stop - start) / step) + 1

        # Sweep bounds check
        checks.append(check_sweep_bounds(n_points))

        # Sample size check
        checks.append(check_sample_size(len(corpus), claim_type="general"))

        if n_points > MAX_SWEEP_POINTS:
            return (
                f"Sweep would produce {n_points} points, exceeding the "
                f"maximum of {MAX_SWEEP_POINTS}. Reduce range or increase step."
            ), checks

        result = sweep(
            corpus,
            param_name=param_name,
            start=start,
            stop=stop,
            step=step,
        )

        output_parts = [result.to_table()]

        # Find optimal point
        optimal = result.optimal_point(metric="execute_rate")
        if optimal:
            output_parts.append(
                f"\nOptimal (max EXECUTE rate): "
                f"{param_name}={optimal.param_value:.3f} "
                f"(changed={optimal.result.n_changed}, "
                f"rate={optimal.result.change_rate:.1%})"
            )

        return "\n".join(output_parts), checks

    def _dispatch_timeline(
        self, params: Dict, checks: List[MethodologicalCheck]
    ) -> Tuple[str, List[MethodologicalCheck]]:
        """Run temporal analysis."""
        if timeline is None:
            return "timeline module not available.", checks

        corpus = self._ensure_corpus()

        # Sample size check for trend
        checks.append(check_sample_size(len(corpus), claim_type="trend"))

        metric = params.get("dimension", "composite")
        window_size = params.get("window_size", 50)

        ql_lower = str(params).lower()

        # Regime change detection
        if ("regime" in ql_lower or "structural" in ql_lower or
                "z_threshold" in params):
            if detect_regime_change is None:
                return "detect_regime_change function not available.", checks
            threshold = params.get("z_threshold", 2.0)
            lookback = params.get("lookback", 30)
            changes = detect_regime_change(
                corpus,
                dimension=metric,
                threshold=threshold,
                lookback=lookback,
            )
            if format_regime_changes is not None:
                return format_regime_changes(changes), checks
            if not changes:
                return "No regime changes detected.", checks
            lines = [f"Regime Changes ({metric}, n={len(changes)})"]
            for rc in changes:
                lines.append(
                    f"  [{rc.index}] z={rc.z_score:+.2f} "
                    f"value={rc.value:.3f} rolling_mean={rc.rolling_mean:.3f}"
                )
            return "\n".join(lines), checks

        # Session timeline
        if "session" in ql_lower or "across sessions" in ql_lower:
            if session_timeline is None:
                return "session_timeline function not available.", checks
            result = session_timeline(corpus)
            return result.format(), checks

        # Standard rolling window timeline
        step = max(window_size // 2, 1)
        result = timeline(
            corpus,
            window_size=window_size,
            step=step,
            metric=metric,
        )
        return result.format(), checks

    def _dispatch_compare(
        self, params: Dict, checks: List[MethodologicalCheck]
    ) -> Tuple[str, List[MethodologicalCheck]]:
        """Run structured comparison."""
        if compare is None:
            return "compare module not available.", checks

        corpus = self._ensure_corpus()

        # Tool comparison: "compare Bash to Read"
        if "tool_a" in params and "tool_b" in params:
            if compare_tools is None:
                return "compare_tools function not available.", checks

            a_corpus = corpus.filter(tool=params["tool_a"])
            b_corpus = corpus.filter(tool=params["tool_b"])

            # Balance check
            checks.append(check_comparison_balance(len(a_corpus), len(b_corpus)))

            result = compare_tools(corpus, params["tool_a"], params["tool_b"])
            return result.format(), checks

        # Session comparison: "compare session A to session B"
        if "session_a" in params and "session_b" in params:
            if compare_sessions is None:
                return "compare_sessions function not available.", checks

            a_corpus = corpus.filter(session=params["session_a"])
            b_corpus = corpus.filter(session=params["session_b"])
            checks.append(check_comparison_balance(len(a_corpus), len(b_corpus)))

            result = compare_sessions(
                corpus, params["session_a"], params["session_b"]
            )
            return result.format(), checks

        # Before/after split: "compare before and after event 800"
        if "before_index" in params:
            if compare_periods is None:
                return "compare_periods function not available.", checks

            idx = params["before_index"]
            checks.append(
                check_comparison_balance(idx, len(corpus) - idx)
            )

            result = compare_periods(corpus, before_index=idx)
            return result.format(), checks

        # Half split: "compare first half to second half"
        if params.get("split_half"):
            if compare_periods is None:
                return "compare_periods function not available.", checks

            mid = len(corpus) // 2
            checks.append(check_comparison_balance(mid, len(corpus) - mid))

            result = compare_periods(corpus, before_index=mid)
            return result.format(), checks

        # Fallback: need more info
        return (
            "Compare needs two groups. Try:\n"
            "  - 'compare Bash to Read' (tool comparison)\n"
            "  - 'compare session X to session Y' (session comparison)\n"
            "  - 'compare before and after event 800' (temporal split)\n"
            "  - 'compare first half to second half' (midpoint split)"
        ), checks

    def _dispatch_validate(
        self, params: Dict, checks: List[MethodologicalCheck]
    ) -> Tuple[str, List[MethodologicalCheck]]:
        """Run integrity validation."""
        if validate is None:
            return "validate module not available.", checks

        corpus = self._ensure_corpus()

        result = validate(corpus)
        return result.format(), checks

    # ── Session management ────────────────────────────────────────────

    def reset(self) -> None:
        """Clear corpus, reset chain, and start a fresh session."""
        self._corpus = None
        self._chain = []
        self._call_count = 0
        self._warnings_issued = set()
        logger.info("Interpreter session reset.")

    def status(self) -> Dict[str, Any]:
        """Return current session status.

        Returns:
            Dict with:
                - corpus_loaded: bool
                - n_events: int (0 if not loaded)
                - n_sessions: int (0 if not loaded)
                - chain_length: int (number of tool calls this session)
                - chain: list of short tool names called
                - embedding_available: bool
                - warnings_issued: list of warning strings
                - audit_dir: str
                - telemetry_enabled: bool
        """
        corpus_loaded = self._corpus is not None
        n_events = len(self._corpus) if corpus_loaded else 0
        n_sessions = self._corpus.n_sessions if corpus_loaded else 0

        short_chain = [
            SHORT_NAMES.get(t, t.replace("research_audit_", ""))
            for t in self._chain
        ]

        return {
            "corpus_loaded": corpus_loaded,
            "n_events": n_events,
            "n_sessions": n_sessions,
            "chain_length": self._call_count,
            "chain": short_chain,
            "embedding_available": self._model is not None,
            "warnings_issued": list(self._warnings_issued),
            "audit_dir": self._audit_dir,
            "telemetry_enabled": self._telemetry_enabled,
        }

    def __repr__(self) -> str:
        s = self.status()
        corpus_str = (
            f"{s['n_events']} events, {s['n_sessions']} sessions"
            if s["corpus_loaded"] else "not loaded"
        )
        routing = "semantic" if s["embedding_available"] else "keyword"
        return (
            f"TeloscopeInterpreter("
            f"corpus={corpus_str}, "
            f"chain={s['chain_length']} calls, "
            f"routing={routing})"
        )
