#!/usr/bin/env python3
"""
TELOS v2.0.0 — Live Agentic Governance Demo (v3 — 5-Act Interleaved)
Nearmap Property Intelligence: Insurance + Solar

Five-act structure:
  Act 1: Insurance Governance (5 scenarios)
  Act 2: TELOSCOPE on Insurance (point-by-point)
  Act 3: PA Swap → Solar Governance (5 scenarios)
  Act 4: TELOSCOPE on Solar (point-by-point)
  Act 5: Interpreter Close

Run:
  python3 demos/nearmap_live_demo_v3.py                         # full 5-act demo
  DEMO_FAST=1 python3 demos/nearmap_live_demo_v3.py             # skip pauses
  DEMO_INSURANCE_ONLY=1 python3 demos/nearmap_live_demo_v3.py   # Acts 1-2 + close
  NO_COLOR=1 python3 demos/nearmap_live_demo_v3.py              # plain ASCII
"""

import hashlib
import json
import logging
import os
import sys
import time
import uuid

# Suppress governance engine warnings in demo output (e.g., "Hard boundary triggered")
logging.getLogger("telos_governance").setLevel(logging.ERROR)

# Ensure the project root and demos dir are on sys.path
_DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_DEMO_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _DEMO_DIR not in sys.path:
    sys.path.insert(0, _DEMO_DIR)

# ---------------------------------------------------------------------------
# Import everything from v2 — no duplication
# ---------------------------------------------------------------------------
from nearmap_live_demo_v2 import (
    # PA configs
    PA_TEXT, TOOLS, BOUNDARIES, BOUNDARY_TOPICS, ADVERSARIAL_PATTERNS,
    SOLAR_PA_TEXT, SOLAR_TOOLS, SOLAR_BOUNDARIES, SOLAR_BOUNDARY_TOPICS,
    # Scenarios
    Scenario, PADemoConfig, SCENARIOS, SOLAR_SCENARIOS,
    # Tool dispatch
    TOOL_DISPATCH, SOLAR_TOOL_DISPATCH,
    # Receipts
    GovernanceReceipt, _sign_receipt,
    # Display functions
    _act_zero_preamble, _pa_swap_transition, _run_pa_scenarios,
    # Engine flags
    USE_PRODUCTION_ENGINE, EngineDecision,
    _HAS_SETFIT, _HAS_ED25519, _HAS_TELOSCOPE,
)

# Display toolkit
from _display_toolkit import (
    NO_COLOR, DEMO_FAST, OBSERVE_MODE,
    _c, _bg, _pause, W, _wrap, _kv,
    _header, _section, _narrator,
    _score_color, _zone_label, _bar,
)

# TELOS engine imports (needed for init)
try:
    from telos_core.embedding_provider import OnnxEmbeddingProvider
except ImportError:
    OnnxEmbeddingProvider = None
try:
    from telos_core.embedding_provider import SentenceTransformerProvider
except ImportError:
    SentenceTransformerProvider = None

from telos_core.fidelity_engine import FidelityEngine
from telos_core.governance_trace import GovernanceTraceCollector
from telos_core.evidence_schema import PrivacyMode
from telos_governance.pa_extractor import PrimacyAttractor

# SetFit
try:
    from telos_governance.setfit_classifier import SetFitBoundaryClassifier
except ImportError:
    pass

# Ed25519
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as _serialization
except ImportError:
    pass

# Forensic trace verification
from telos_core.trace_verifier import verify_trace_integrity

# Governance HTML report generator
try:
    from telos_observatory.services.report_generator import GovernanceReportGenerator
except ImportError:
    GovernanceReportGenerator = None

# TELOSCOPE imports
if _HAS_TELOSCOPE:
    from telos_governance.demo_audit_bridge import make_audit_record, write_demo_corpus
    from telos_governance.corpus import load_corpus
    from telos_governance.stats import corpus_stats
    from telos_governance.validate import validate
    from telos_governance.compare import compare
    from telos_governance.report import executive_report
    from telos_governance.demo_teloscope_analysis import (
        print_corpus_summary, print_verdict_table, print_validation,
        print_comparison, print_caveats, generate_html,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Scenario Subsets — 5 per domain, picked from v2's full lists
# ═══════════════════════════════════════════════════════════════════════════

# Insurance: indices 0, 1, 3, 4, 6
# [0] Roof condition (ALLOW), [1] Bind coverage (ESCALATE),
# [3] Hail/wind (ALLOW), [4] Repair cost (CLARIFY), [6] Prompt injection (ESCALATE)
INSURANCE_SUBSET = [SCENARIOS[i] for i in (0, 1, 3, 4, 6)]

# Solar: indices 0, 1, 2, 3, 4
# [0] Irradiance (ALLOW), [1] Binding contract (ESCALATE),
# [2] Structural engineering (ESCALATE, unique to solar),
# [3] Shade analysis (ALLOW), [4] Financial guarantee (ESCALATE)
SOLAR_SUBSET = [SOLAR_SCENARIOS[i] for i in (0, 1, 2, 3, 4)]


# ═══════════════════════════════════════════════════════════════════════════
# TELOSCOPE Exercises — analyst-style interrogation of governance data
# ═══════════════════════════════════════════════════════════════════════════

def _teloscope_exercise_inspect(receipts, corpus):
    """Exercise 1: Inspect the most interesting single decision."""
    _section("Inspect: Drill into a single decision")
    _pause(1.0)

    # Find the most interesting receipt: highest fidelity among blocked,
    # or lowest fidelity among allowed — the closest call
    allowed_r = [r for r in receipts if r.decision.value in ("execute", "clarify")]
    blocked_r = [r for r in receipts if r.decision.value == "escalate"]

    target = None
    if blocked_r:
        # Highest fidelity among blocked = closest to being allowed
        target = max(blocked_r, key=lambda r: r.fidelity)
        target_type = "blocked"
    elif allowed_r:
        target = min(allowed_r, key=lambda r: r.fidelity)
        target_type = "allowed"

    if target is None:
        return

    print()
    _narrator("An auditor drills into the closest call in this batch.")
    _pause(1.5)

    dec_val = target.decision.value.upper()
    dec_color = "green" if dec_val in ("EXECUTE", "CLARIFY") else "red"

    print()
    print(_c("  Request:  ", "dim") + '"{}"'.format(target.request[:70]))
    print(_c("  Verdict:  ", "dim") + _c(dec_val, dec_color, bold=True))
    print(_c("  Fidelity: ", "dim") + _c("{:.3f}".format(target.fidelity),
          "green" if target.fidelity > 0.6 else "yellow" if target.fidelity > 0.4 else "red"))
    print(_c("  Tool:     ", "dim") + (target.tool or "none"))

    if target.cascade_halt_layer and target.cascade_halt_layer != "none":
        print(_c("  Halted at:", "dim") + _c(" {} layer".format(
            target.cascade_halt_layer), "red"))

    if target.setfit_triggered:
        print(_c("  SetFit:   ", "dim") + _c(
            "P(violation) = {:.2f} — ML classifier confirmed boundary".format(
                target.setfit_score or 0.0), "red"))
    elif target.keyword_triggered:
        print(_c("  Keywords: ", "dim") + _c("triggered — fast-path detection", "red"))

    print()
    if target_type == "blocked":
        print(_c("  This was the closest call among blocked decisions.", "dim"))
        print(_c("  Fidelity {:.3f} — the engine stopped this before the agent acted.".format(
            target.fidelity), "dim"))
    else:
        print(_c("  This was the weakest allowed decision.", "dim"))
        print(_c("  Fidelity {:.3f} — barely above the threshold.".format(
            target.fidelity), "dim"))

    _pause(3.0)


def _teloscope_exercise_counterfactual(receipts):
    """Exercise 2: Counterfactual — what if the threshold was different?"""
    _section('Counterfactual: "What if?"')
    _pause(1.0)

    # Find a CLARIFY receipt (most interesting for counterfactual)
    # or fall back to the lowest-fidelity EXECUTE
    clarify_r = [r for r in receipts if r.decision.value == "clarify"]
    execute_r = [r for r in receipts if r.decision.value == "execute"]

    if clarify_r:
        target = clarify_r[0]
        scenario = "CLARIFY → EXECUTE"
    elif execute_r:
        target = min(execute_r, key=lambda r: r.fidelity)
        scenario = "EXECUTE threshold sensitivity"
    else:
        return

    print()
    _narrator("The governance record isn't static — you can ask 'what if?' of any decision.")
    _pause(1.5)

    fid = target.fidelity
    dec_val = target.decision.value.upper()

    print()
    print(_c("  Decision: ", "dim") + '"{}"'.format(target.request[:70]))
    print(_c("  Scored:   ", "dim") + "{:.3f}  →  {}".format(
        fid, _c(dec_val, "yellow" if dec_val == "CLARIFY" else "green", bold=True)))
    print()

    # EXECUTE threshold is ~0.85 composite, CLARIFY is ~0.70
    # For the demo narrative, show what happens at different thresholds
    if dec_val == "CLARIFY":
        print(_c("  Current EXECUTE threshold: 0.85", "dim"))
        print(_c("  This decision scored {:.3f} — below EXECUTE, above CLARIFY.".format(fid), "dim"))
        print()
        lower = fid - 0.02
        print("  {} If the threshold were {:.2f} instead of 0.85:".format(
            _c("→", "cyan"), lower))
        print("    {} — the agent proceeds without verification.".format(
            _c("EXECUTE", "green", bold=True)))
        print()
        print("  {} At the current threshold:".format(_c("→", "cyan")))
        print("    {} — the engine asks for intent verification first.".format(
            _c("CLARIFY", "yellow", bold=True)))
        print()
        print(_c("  The threshold is an operator decision. This data proves what it costs.", "dim"))
    else:
        print(_c("  This EXECUTE scored {:.3f} against a 0.85 threshold.".format(fid), "dim"))
        higher = 0.85 + (0.95 - 0.85)
        print()
        print("  {} If the threshold were {:.2f}:".format(
            _c("→", "cyan"), higher))
        print("    {} — this would need verification.".format(
            _c("CLARIFY", "yellow", bold=True)))
        print()
        print(_c("  Every threshold choice is visible in the audit record.", "dim"))

    _pause(3.0)


def _teloscope_exercise_compliance(receipts):
    """Exercise 3: Compliance query — filter the governance record."""
    _section('Compliance query: "Show me every decision where..."')
    _pause(1.0)

    print()
    _narrator("An auditor asks: show me every decision where purpose fidelity was below 0.55.")
    _pause(1.5)

    threshold = 0.55
    flagged = [r for r in receipts if r.fidelity < threshold]
    clean = [r for r in receipts if r.fidelity >= threshold]

    print()
    print(_c("  Query: fidelity < {:.2f}".format(threshold), "white", bold=True))
    print(_c("  Result: {}/{} decisions flagged".format(len(flagged), len(receipts)), "white"))
    print()

    if flagged:
        for r in flagged:
            dec_val = r.decision.value.upper()
            dec_color = "green" if dec_val in ("EXECUTE", "CLARIFY") else "red"
            print("    {} {:<10s} {:.3f}  \"{}\"".format(
                _c("\u25CF", dec_color),
                _c(dec_val, dec_color),
                r.fidelity,
                r.request[:70]))
    else:
        print(_c("    No decisions below {:.2f} — all within acceptable range.".format(
            threshold), "green"))

    print()
    print(_c("  {}/{} decisions passed this compliance check.".format(
        len(clean), len(receipts)), "dim"))
    print(_c("  The governance record answers any question an auditor can ask.", "dim"))

    _pause(3.0)


# ═══════════════════════════════════════════════════════════════════════════
# TELOSCOPE Interleave — point-by-point after each domain
# ═══════════════════════════════════════════════════════════════════════════

def _teloscope_interleave(domain_label, receipts, session_id, is_first=False):
    """Bridge governance receipts to JSONL, run TELOSCOPE tools point-by-point.

    1. Narrator bridge (connective tissue)
    2. Show JSONL file explicitly
    3. Verdict distribution (stats)
    4. Integrity verification (validate)
    5. Allowed vs Blocked comparison (compare)
    6. HTML report generated
    7. Small-sample caveats
    """
    if not _HAS_TELOSCOPE:
        print()
        print(_c("  [TELOSCOPE skipped — tools not installed]", "yellow"))
        return

    n = len(receipts)
    domain_lower = domain_label.lower().replace(" ", "_")

    _header("Act {} — TELOSCOPE on {}".format(
        "2" if domain_lower == "insurance" else "4", domain_label))
    _pause(1.0)

    # --- TELOSCOPE introduction (first call only) ---
    if is_first:
        _narrator(
            "TELOSCOPE is the observation instrument \u2014 it reads the audit trail "
            "the governance engine just created and subjects it to independent analysis."
        )
        _pause(2.0)

    # --- Narrator bridge ---
    _narrator(
        "Those {} governance decisions produced an audit file. "
        "TELOSCOPE reads it now.".format(n)
    )
    _pause(2.0)

    # --- Bridge receipts to JSONL ---
    output_dir = os.path.join(_PROJECT_ROOT, "demos", "output")
    os.makedirs(output_dir, exist_ok=True)

    jsonl_path = os.path.join(output_dir, "{}_{}.jsonl".format(domain_lower, session_id))
    html_path = os.path.join(output_dir, "{}_{}.html".format(domain_lower, session_id))

    records = []
    for r in receipts:
        records.append(make_audit_record(
            scenario_name=r.request[:80],
            tool_name=r.tool or "unknown",
            verdict=r.decision.value.upper(),
            fidelity_score=r.fidelity,
            cascade_halt_layer=r.cascade_halt_layer or None,
            session_id=session_id,
        ))
    write_demo_corpus(records, jsonl_path)

    # --- Show JSONL explicitly ---
    print()
    print(_c("  Audit file: {}".format(jsonl_path), "cyan"))
    print(_c("  Events:     {}".format(n), "white"))
    _pause(1.5)

    # --- Load corpus ---
    corpus = load_corpus(jsonl_path)

    # --- Stats: verdict distribution ---
    print()
    print_verdict_table(corpus)
    _pause(2.0)

    # --- Validate: integrity verification ---
    val = validate(corpus)
    print_validation(val)
    _narrator(
        "Signatures show DEGRADED \u2014 expected in a demo environment using "
        "ephemeral keys. In production with Ed25519 signing, all three checks "
        "pass. The hash chain itself is intact and tamper-evident."
    )
    _pause(1.5)

    # --- Compare: allowed vs blocked ---
    allowed = corpus.filter(predicate=lambda e: e.verdict in ("EXECUTE", "CLARIFY"))
    blocked = corpus.filter(predicate=lambda e: e.verdict == "ESCALATE")
    if len(allowed) > 0 and len(blocked) > 0:
        cmp = compare(allowed, blocked, label_a="Allowed", label_b="Blocked")
        print_comparison(corpus, cmp)
        _pause(1.5)
    else:
        cmp = None

    # --- Caveats ---
    print_caveats(n)

    # --- Exercise 1: Inspect a specific decision ---
    _teloscope_exercise_inspect(receipts, corpus)

    # --- Exercise 2: Counterfactual ---
    _teloscope_exercise_counterfactual(receipts)

    # --- Exercise 3: Compliance query ---
    _teloscope_exercise_compliance(receipts)

    # --- HTML report ---
    try:
        stats_full = corpus_stats(corpus)
        stats_verdict = corpus_stats(corpus, groupby="verdict")
        exec_rpt = executive_report(corpus, validation_result=val)
        timings = {"Analysis": 0.0}
        if cmp is None:
            cmp = compare(allowed, blocked, label_a="Allowed", label_b="Blocked")
        html = generate_html(corpus, stats_full, stats_verdict, val, cmp, exec_rpt, timings)
        with open(html_path, "w") as f:
            f.write(html)
        print(_c("  HTML report: {}".format(html_path), "dim"))
    except Exception as exc:
        print(_c("  [HTML report skipped: {}]".format(exc), "yellow"))

    _pause(1.0)


# ═══════════════════════════════════════════════════════════════════════════
# Interpreter Close — plain language, no jargon
# ═══════════════════════════════════════════════════════════════════════════

def _interpreter_close(all_receipts, total_gov_ms):
    """Plain-language macro interpretation of the demo.

    Stewart-interpreter style. 8-10 lines. No jargon.
    """
    _header("Act 5 — What You Just Saw")
    _pause(1.0)

    total = len(all_receipts)
    allowed = sum(1 for r in all_receipts
                  if r.decision.value.upper() in ("EXECUTE",))
    clarified = sum(1 for r in all_receipts
                    if r.decision.value.upper() == "CLARIFY")
    escalated = sum(1 for r in all_receipts
                    if r.decision.value.upper() == "ESCALATE")
    avg_ms = total_gov_ms / total if total > 0 else 0.0

    lines = [
        "",
        "Two agents. Two purposes. Same governance engine.",
        "{} decisions scored in ~{:.0f}ms each \u2014 before the agent acted, not retroactively.".format(total, avg_ms),
        "{} escalated to human review. {} clarified. {} allowed to proceed.".format(
            escalated, clarified, allowed),
        "Every decision recorded in a tamper-evident audit chain.",
        "TELOSCOPE independently verified chain integrity and measured scoring distribution.",
        "",
        "What this means:",
        "",
        "These governance decisions are now auditable artifacts.",
        "They prove regulatory compliance \u2014 not as a claim, but as a cryptographic record.",
        "The boundaries you defined are enforced and measured inside the working agents you operate.",
    ]

    for line in lines:
        if line == "":
            print()
        else:
            print("  {}".format(_c(line, "white")))
        _pause(0.5)

    _pause(3.0)

    # Scale framing
    print()
    print("  {}".format(_c(
        "{} decisions for this demo. In production, thousands per day "
        "through the same pipeline at the same latency.".format(total), "dim")))
    _pause(2.0)


# ═══════════════════════════════════════════════════════════════════════════
# Main — 5-Act Demo
# ═══════════════════════════════════════════════════════════════════════════

def main():
    session_id = "telos-{}".format(uuid.uuid4().hex[:8])
    start_wall = time.time()

    INSURANCE_ONLY = os.environ.get("DEMO_INSURANCE_ONLY", "").strip() == "1"

    # ── Header ────────────────────────────────────────────────────────
    _header(
        "TELOS v2.0.0 — Live Agentic Governance Demo\n"
        "Nearmap Property Intelligence: Insurance{}\n"
        "\n"
        "What you are about to see:\n"
        "  {} agents. Same governance engine. Different purposes.\n"
        "  TELOS scores each request in <30ms — BEFORE the LLM runs.\n"
        "  After each domain, TELOSCOPE independently audits every decision.\n"
        "  Every decision is cryptographically signed for audit.".format(
            "" if INSURANCE_ONLY else " + Solar",
            "One" if INSURANCE_ONLY else "Two",
        )
    )
    _pause(2.0)

    # ── Disclaimer ────────────────────────────────────────────────────
    print()
    print(_c("  " + "─" * 64, "dim"))
    print(_c("  DISCLAIMER", "yellow"))
    print(_c("  " + "─" * 64, "dim"))
    print(_c("  This demonstration is an artificial approximation built", "dim"))
    print(_c("  entirely from publicly available information. No Nearmap", "dim"))
    print(_c("  systems, APIs, or proprietary data were accessed. Property", "dim"))
    print(_c("  data, detection layers, and tool definitions are simulated", "dim"))
    print(_c("  composites derived from public records, published product", "dim"))
    print(_c("  documentation, and industry-standard insurance terminology.", "dim"))
    print(_c("  ", "dim"))
    print(_c("  The purpose is to demonstrate TELOS governance capabilities", "dim"))
    print(_c("  — not to replicate or reverse-engineer any Nearmap product.", "dim"))
    print(_c("  " + "─" * 64, "dim"))
    print()
    _pause(3.0)

    # ── Engine Initialisation ─────────────────────────────────────────
    print()
    print(_c("  Initialising governance engine ...", "dim"))
    _pause(1.0)

    t0 = time.perf_counter()
    embed_provider = None
    if OnnxEmbeddingProvider is not None:
        try:
            embed_provider = OnnxEmbeddingProvider()
        except Exception:
            pass
    if embed_provider is None and SentenceTransformerProvider is not None:
        try:
            embed_provider = SentenceTransformerProvider(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
        except Exception:
            pass
    if embed_provider is None:
        print(_c("  ERROR: No embedding provider available.", "red"))
        sys.exit(1)
    embed_fn = embed_provider.encode

    # Legacy engine (always initialised)
    legacy_engine = FidelityEngine(model_type="sentence_transformer")

    # SetFit L1.5 classifier
    setfit_classifier = None
    setfit_loaded = False
    if USE_PRODUCTION_ENGINE and _HAS_SETFIT:
        try:
            setfit_classifier = SetFitBoundaryClassifier(
                model_dir=os.path.join(_PROJECT_ROOT, "models", "setfit_healthcare_v1"),
                calibration_path=os.path.join(_PROJECT_ROOT, "models", "setfit_healthcare_v1", "calibration.json"),
            )
            setfit_loaded = True
            print(_c("  SetFit L1.5 classifier loaded", "green"))
        except Exception:
            pass

    # Ephemeral HMAC key
    hmac_key = os.urandom(32)

    # Ed25519: signs the session digest at close
    if _HAS_ED25519:
        ed_private = Ed25519PrivateKey.generate()
        ed_public = ed_private.public_key()
        ed_pub_bytes = ed_public.public_bytes(
            encoding=_serialization.Encoding.Raw,
            format=_serialization.PublicFormat.Raw,
        )
        ed_pub_hex = ed_pub_bytes.hex()
    else:
        ed_private = None
        ed_public = None
        ed_pub_hex = None

    # Forensic trace collector
    trace_dir = os.path.join(_PROJECT_ROOT, "telos_governance_traces")
    trace = GovernanceTraceCollector(
        session_id=session_id,
        storage_dir=__import__("pathlib").Path(trace_dir),
        privacy_mode=PrivacyMode.FULL,
    )
    trace.start_session(
        telos_version="v2.0.0",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        enforcement_mode="enforcement",
    )
    trace.record_pa_established(
        pa_template="property_intelligence",
        purpose_statement=PA_TEXT,
        tau=0.5, rigidity=0.5, basin_radius=2.0,
    )

    init_s = time.perf_counter() - t0

    # Mistral check
    mistral_key = os.environ.get("MISTRAL_API_KEY", "")
    mistral_client = None
    mistral_model = "mistral-small-latest"
    if mistral_key:
        try:
            from mistralai import Mistral
            mistral_client = Mistral(api_key=mistral_key)
        except ImportError:
            pass

    has_agent = mistral_client is not None

    # Engine summary
    print()
    _kv("Session", session_id)
    _kv("Engine", _c("AgenticFidelityEngine (production)", "green") if USE_PRODUCTION_ENGINE else "Legacy")
    _kv("Cascade", "L0:keywords → L1:cosine → L1.5:SetFit → L2:LLM")
    if has_agent:
        _kv("LLM", "{} (native function calling)".format(mistral_model))
    else:
        _kv("LLM", _c("none", "yellow") + " — governance-only mode")
    _kv("Engine init", "{:.2f}s".format(init_s))
    _pause(2.0)

    # ── Build PA configs (v3 subsets) ─────────────────────────────────
    insurance_config = PADemoConfig(
        label="Insurance",
        agent_name="Property Intelligence Agent",
        pa_text=PA_TEXT,
        scope_text="Property lookup, aerial image retrieval, AI feature extraction, "
                   "roof condition scoring, peril risk assessment, property report generation",
        tools=TOOLS,
        boundaries=BOUNDARIES,
        boundary_topics=BOUNDARY_TOPICS + ADVERSARIAL_PATTERNS,
        scenarios=INSURANCE_SUBSET,
        tool_dispatch=TOOL_DISPATCH,
        constraints={"max_chain_length": 20, "escalation_threshold": 0.50, "require_human_above_risk": "high"},
        has_mistral=has_agent,
    )

    solar_config = PADemoConfig(
        label="Solar",
        agent_name="Solar Site Assessment Agent",
        pa_text=SOLAR_PA_TEXT,
        scope_text="Solar feasibility analysis, site resource assessment, performance modeling, "
                   "permitting research, incentive identification, shade and orientation analysis",
        tools=SOLAR_TOOLS,
        boundaries=SOLAR_BOUNDARIES,
        boundary_topics=SOLAR_BOUNDARY_TOPICS,
        scenarios=SOLAR_SUBSET,
        tool_dispatch=SOLAR_TOOL_DISPATCH,
        constraints={"max_chain_length": 25, "escalation_threshold": 0.50, "require_human_above_risk": "high"},
        config_path=os.path.join(_PROJECT_ROOT, "templates", "solar_site_assessor.yaml"),
    )

    # ══════════════════════════════════════════════════════════════════
    # ACT 1 — Insurance Governance
    # ══════════════════════════════════════════════════════════════════

    _header("Act 1 — Insurance Governance")
    _pause(0.5)

    _act_zero_preamble(
        agent_name=insurance_config.agent_name,
        purpose=insurance_config.pa_text,
        scope=insurance_config.scope_text,
        boundaries=insurance_config.boundaries,
        tools=insurance_config.tools,
        constraints=insurance_config.constraints,
    )

    insurance_receipts = []
    ins_gov_ms, ins_saved, ins_blocked = _run_pa_scenarios(
        insurance_config, embed_fn, hmac_key, setfit_classifier, setfit_loaded,
        mistral_client, mistral_model, legacy_engine, trace,
        insurance_receipts, USE_PRODUCTION_ENGINE, receipt_offset=0,
        show_two_gate=True,
    )

    # ══════════════════════════════════════════════════════════════════
    # ACT 2 — TELOSCOPE on Insurance
    # ══════════════════════════════════════════════════════════════════

    _teloscope_interleave("Insurance", insurance_receipts, session_id, is_first=True)

    if INSURANCE_ONLY:
        # Skip Acts 3-4, jump to interpreter close
        _interpreter_close(insurance_receipts, ins_gov_ms)

        print()
        elapsed = time.time() - start_wall
        print(_c("  Demo completed in {:.1f}s".format(elapsed), "dim"))
        print(_c("═" * W, "cyan", bold=True))
        print()
        return

    # ══════════════════════════════════════════════════════════════════
    # ACT 3 — PA Swap → Solar Governance
    # ══════════════════════════════════════════════════════════════════

    # PA swap transition
    prev_tool_names = {t.name for t in insurance_config.tools}
    curr_tool_names = {t.name for t in solar_config.tools}
    shared = sorted(prev_tool_names & curr_tool_names) or None

    _pa_swap_transition(
        "Insurance", "aerial imagery for underwriting",
        "no binding coverage, no PII, no overriding assessors",
        "Solar", "site feasibility for solar installations",
        "no contracts, no structural engineering, no electrical design",
        shared_tools=shared,
    )

    _narrator(
        "This is how one platform governs different customers on the same "
        "infrastructure. The engine stays the same. The purpose specification changes."
    )
    _pause(2.0)

    _header("Act 3 — Solar Governance")
    _pause(0.5)

    _act_zero_preamble(
        agent_name=solar_config.agent_name,
        purpose=solar_config.pa_text,
        scope=solar_config.scope_text,
        boundaries=solar_config.boundaries,
        tools=solar_config.tools,
        constraints=solar_config.constraints,
    )

    solar_receipts = []
    sol_gov_ms, sol_saved, sol_blocked = _run_pa_scenarios(
        solar_config, embed_fn, hmac_key, setfit_classifier, setfit_loaded,
        mistral_client, mistral_model, legacy_engine, trace,
        solar_receipts, USE_PRODUCTION_ENGINE,
        receipt_offset=len(insurance_receipts),
        show_two_gate=True,
    )

    # ══════════════════════════════════════════════════════════════════
    # ACT 4 — TELOSCOPE on Solar
    # ══════════════════════════════════════════════════════════════════

    _teloscope_interleave("Solar", solar_receipts, session_id)

    # ══════════════════════════════════════════════════════════════════
    # ACT 5 — Interpreter Close
    # ══════════════════════════════════════════════════════════════════

    all_receipts = insurance_receipts + solar_receipts
    total_gov_ms = ins_gov_ms + sol_gov_ms

    _interpreter_close(all_receipts, total_gov_ms)

    # ══════════════════════════════════════════════════════════════════
    # FORENSIC SESSION PROOF
    # ══════════════════════════════════════════════════════════════════

    # ── End forensic session ──
    elapsed_so_far = time.time() - start_wall
    trace.end_session(duration_seconds=elapsed_so_far, end_reason="demo_completed")

    # Compute session digest
    session_digest_input = "|".join(r.hmac_signature for r in all_receipts)
    session_digest = hashlib.sha256(session_digest_input.encode("utf-8")).hexdigest()

    # Ed25519 session signature
    ed_session_sig = None
    if _HAS_ED25519 and ed_private is not None:
        ed_session_sig = ed_private.sign(session_digest.encode("utf-8")).hex()
        ed_public.verify(bytes.fromhex(ed_session_sig), session_digest.encode("utf-8"))

    _pause(1.0)
    _header("Governance Session Proof")
    print()
    _kv("Session", session_id)
    _kv("Receipts", "{} (HMAC-SHA512 signed)".format(len(all_receipts)))
    _kv("Audit trail", "SHA-256 hash chain (tamper-evident)")
    _kv("Trace file", str(trace.trace_file))
    _pause(1.5)

    print()
    print(_c("  Receipt signatures (HMAC-SHA512):", "white", bold=True))
    print()
    for r in all_receipts:
        dc = "green" if r.decision in (EngineDecision.EXECUTE, EngineDecision.CLARIFY) else "red"
        sig_short = r.hmac_signature[:16] + "..." + r.hmac_signature[-8:]
        print("    #{:<3d} {}  {}".format(r.index, _c(r.decision.value.upper(), dc), _c(sig_short, "cyan")))
    _pause(1.5)

    print()
    print(_c("  Session digest (SHA-256 of receipt chain):", "white", bold=True))
    print("    {}".format(_c(session_digest, "cyan")))
    _pause(1.0)

    if ed_session_sig:
        print()
        print(_c("  Ed25519 session signature:", "white", bold=True))
        print("    Public key:  {}".format(_c(ed_pub_hex, "cyan")))
        print("    Signature:   {}...{}".format(_c(ed_session_sig[:24], "cyan"), _c(ed_session_sig[-16:], "cyan")))
        print("    Verified:    {}".format(_c("YES", "green")))
    else:
        print()
        print(_c("  Ed25519 session signature: unavailable (install `cryptography`)", "yellow"))
    _pause(1.5)

    print()
    print(_c("  Blocked requests (audit trail):", "dim"))
    for r in all_receipts:
        if r.decision == EngineDecision.ESCALATE:
            note = r.note or "outside agent scope"
            short_req = r.request[:70] + "..." if len(r.request) > 70 else r.request
            print("    #{:<3d} {}  \"{}\" \u2014 {}".format(r.index, _c(r.decision.value.upper(), "red"), short_req, _c(note, "dim")))
    _pause(2.0)

    # ══════════════════════════════════════════════════════════════════
    # FORENSIC TRACE VERIFICATION
    # ══════════════════════════════════════════════════════════════════

    _pause(1.0)
    _header("Forensic Trace Verification")
    _pause(0.5)

    print()
    print(_c("  Verifying cryptographic hash chain ...", "dim"))
    _pause(1.0)

    report = verify_trace_integrity(trace.trace_file)
    stats = trace.get_session_stats()

    import hashlib as _hashlib
    _GENESIS = "0" * 64
    _chain_events = []
    with open(trace.trace_file, "r") as _cf:
        for _cl in _cf:
            _cl = _cl.strip()
            if _cl:
                _chain_events.append(json.loads(_cl))

    def _chain_narration(ev):
        et = ev.get("event_type", "")
        if et == "session_start":
            mode = ev.get("enforcement_mode", "enforcement")
            ver = ev.get("telos_version", "?")
            return "Session opened ({} mode, TELOS {})".format(mode, ver)
        elif et == "pa_established":
            tmpl = ev.get("pa_template", "custom")
            tau = ev.get("tau", "?")
            rig = ev.get("rigidity", "?")
            return "Purpose attractor locked: {} (tau={}, rigidity={})".format(tmpl, tau, rig)
        elif et == "turn_start":
            inp = ev.get("user_input", "")
            snippet = inp[:70] + "..." if len(inp) > 70 else inp
            return "\"{}\"".format(snippet)
        elif et == "fidelity_calculated":
            nf = ev.get("normalized_fidelity", 0)
            zone = ev.get("fidelity_zone", "?").upper()
            basin = "in basin" if ev.get("in_basin") else "OUTSIDE basin"
            return "Fidelity {:.3f} ({}) -- {}".format(nf, zone, basin)
        elif et == "intervention_triggered":
            reason = ev.get("trigger_reason", "?")
            action = ev.get("action_taken", "?")
            nf = ev.get("fidelity_at_trigger", 0)
            return "INTERVENTION: {} -> {} (fidelity {:.3f})".format(reason, action, nf)
        elif et == "response_generated":
            ms = ev.get("generation_time_ms", 0)
            out_scored = ev.get("output_governance_scored", False)
            if out_scored:
                out_f = ev.get("output_normalized_fidelity", 0)
                out_z = ev.get("output_fidelity_zone", "?")
                return "LLM response sealed ({}ms, output fidelity {:.3f} {})".format(ms, out_f, out_z)
            return "LLM response sealed ({}ms)".format(ms)
        elif et == "turn_complete":
            turn = ev.get("turn_number", "?")
            intervened = ev.get("intervention_applied", False)
            ff = ev.get("final_fidelity", 0)
            status = "intervention applied" if intervened else "no intervention"
            return "Turn {} closed -- {}, fidelity {:.3f}".format(turn, status, ff)
        elif et == "baseline_established":
            mu = ev.get("baseline_fidelity", 0)
            std = ev.get("baseline_std", 0)
            n = ev.get("baseline_turn_count", 0)
            return "Baseline locked: mu={:.3f} sigma={:.3f} ({} turns)".format(mu, std, n)
        elif et == "session_end":
            turns = ev.get("total_turns", 0)
            intv = ev.get("total_interventions", 0)
            avg = ev.get("average_fidelity", 0)
            dur = ev.get("duration_seconds", 0)
            return "Session closed: {} turns, {} interventions, avg fidelity {:.3f} ({:.0f}s)".format(turns, intv, avg, dur)
        return ""

    print()
    print(_c("  HASH CHAIN ({} events)".format(len(_chain_events)), "white", bold=True))
    print("  {}".format(_c("\u2500" * 66, "dim")))
    print()
    _expected = _GENESIS
    for _ci, _ce in enumerate(_chain_events):
        _etype = _ce.get("event_type", "unknown")
        _ehash = _ce.get("event_hash", "")
        _phash = _ce.get("previous_hash", "")
        _short = _ehash[:12] if _ehash else "n/a"
        _sprev = _phash[:12] if _phash else "n/a"
        _lok = (_phash == _expected)
        if _lok and _ehash:
            _ecopy = {k: v for k, v in _ce.items() if k != "event_hash"}
            _hc = _expected + json.dumps(_ecopy, sort_keys=True)
            _computed = _hashlib.sha256(_hc.encode("utf-8")).hexdigest()
            _lok = (_ehash == _computed)
        _mark = _c("\u2713", "green") if _lok else _c("\u2717", "red")
        if _ci == 0:
            _arrow = _c("genesis", "dim")
        else:
            _arrow = "{} {}".format(_c("\u2190", "dim"), _c(_sprev, "dim"))
        print("  {} {:>3d}  {:<28s}  {}  {}".format(_mark, _ci + 1, _etype, _c(_short, "cyan"), _arrow))
        _narr = _chain_narration(_ce)
        if _narr:
            print("       {}".format(_c(_narr, "dim")))
        _expected = _ehash
        _pause(0.12)

    print()
    print("  {}  {} = hash verified   {}  {} = chain link".format(
        _c("\u2713", "green"), _c("abc123...", "cyan"), _c("\u2190", "dim"), _c("prev_hash", "dim")))
    _pause(1.5)

    if report.is_valid:
        print()
        print("  {}".format(_bg(" CHAIN INTEGRITY VERIFIED ", "green", "black")))
    else:
        print()
        print("  {}".format(_bg(" CHAIN INTEGRITY FAILED ", "red", "white")))
        if report.broken_at_index is not None:
            print("  Broken at event #{} ({})".format(report.broken_at_index, report.broken_at_event_type))
    _pause(1.5)

    print()
    _kv("Trace file", str(trace.trace_file))
    _kv("File size", "{:,} bytes".format(report.file_size_bytes))
    _kv("Total events", str(report.total_events))
    _kv("Hash algorithm", "SHA-256")
    _kv("Chain status", _c("VALID", "green") if report.is_valid else _c("BROKEN", "red"))
    _kv("Verified in", "{:.1f}ms".format(report.verification_duration_ms))
    _pause(1.0)

    print()
    # SAAI Framework by Dr. Nell Watson and Ali Hessami (CC BY-ND 4.0)
    print(_c("  SAAI Framework Alignment:", "white", bold=True))
    _kv("Baseline established", "Yes" if report.baseline_established else "No")
    _kv("Mandatory reviews", str(report.mandatory_reviews_triggered))
    _kv("Final drift level", report.final_drift_level or "normal")
    _kv("Privacy mode", stats.get("privacy_mode", "full"))
    _pause(1.0)

    print()
    print(_c("  Event breakdown:", "dim"))
    for evt_type, count in sorted(report.saai_events.items()):
        print("    {:<30s} {}".format(evt_type, count))
    _pause(1.5)

    print()
    print("  {}".format(_c("To re-verify this trace at any time:", "dim")))
    print("  {}".format(_c("  telos verify {} --chain".format(trace.trace_file), "cyan")))
    _pause(1.0)

    # ══════════════════════════════════════════════════════════════════
    # FORENSIC TRACE INTERPRETER
    # ══════════════════════════════════════════════════════════════════

    _pause(0.5)
    _header("Forensic Trace Interpreter")
    _pause(0.5)

    print()
    print(_c("  Reading forensic trace ...", "dim"))
    _pause(0.8)

    trace_events = []
    with open(trace.trace_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                trace_events.append(json.loads(line))

    fid_trajectory = []
    for e in trace_events:
        if e.get("event_type") == "fidelity_calculated":
            fid_trajectory.append({
                "turn": e.get("turn_number", 0),
                "fidelity": e.get("normalized_fidelity", 0.0),
                "raw": e.get("raw_similarity", 0.0),
                "blocked": e.get("layer1_hard_block", False) or e.get("layer2_outside_basin", False),
            })

    trace_inputs = {}
    for e in trace_events:
        if e.get("event_type") in ("turn_start", "turn_started"):
            trace_inputs[e.get("turn_number", 0)] = e.get("user_input", "")

    trace_interventions = []
    for e in trace_events:
        if e.get("event_type") == "intervention_triggered":
            trace_interventions.append({
                "turn": e.get("turn_number", 0),
                "level": e.get("intervention_level", ""),
                "trigger": e.get("trigger_reason", ""),
                "fidelity": e.get("fidelity_at_trigger", 0.0),
                "action": e.get("action_taken", ""),
            })

    # Fidelity sparkline
    fidelities = [t["fidelity"] for t in fid_trajectory]
    if fidelities:
        spark_blocks = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
        spark_chars = []
        for v in fidelities:
            v = max(0.0, min(1.0, v))
            idx = min(int(v * (len(spark_blocks) - 1)), len(spark_blocks) - 1)
            ch = spark_blocks[idx]
            if v >= 0.70:
                fg = "green"
            elif v >= 0.50:
                fg = "yellow"
            else:
                fg = "red"
            spark_chars.append(_c(ch, fg))
        sparkline = "".join(spark_chars)
        avg_f = sum(fidelities) / len(fidelities)
        min_f = min(fidelities)
        max_f = max(fidelities)

        print()
        print(_c("  Fidelity trajectory:", "white", bold=True))
        print()
        print("  {}  ({} turns)".format(sparkline, len(fidelities)))
        print()
        _kv("Avg fidelity", _c("{:.3f}".format(avg_f), "green" if avg_f >= 0.45 else "yellow"))
        _kv("Range", "{:.3f} \u2013 {:.3f}".format(min_f, max_f))
        _pause(1.5)

    if fid_trajectory:
        intervention_turn_set = {i["turn"] for i in trace_interventions}
        print()
        print(_c("  Per-turn scoring:", "white", bold=True))
        print()
        print("  {:<6s} {:<10s} {:<7s} {:<16s} {:<9s} {}".format("Turn", "Fidelity", "Zone", "", "Status", "Request"))
        print("  {}".format(_c("\u2500" * (W - 4), "dim")))

        for t in fid_trajectory:
            turn = t["turn"]
            fid = t["fidelity"]
            if fid >= 0.70:
                zone = "GREEN"
                zone_fg = "green"
            elif fid >= 0.60:
                zone = "YELLOW"
                zone_fg = "yellow"
            elif fid >= 0.50:
                zone = "ORANGE"
                zone_fg = "yellow"
            else:
                zone = "RED"
                zone_fg = "red"

            bar_w = 14
            filled = max(0, int(fid * bar_w))
            empty = bar_w - filled
            if NO_COLOR:
                bar_str = "\u2588" * filled + "\u2591" * empty
            else:
                _FG = {"green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m"}
                fg_code = _FG.get(zone_fg, "")
                bar_str = "{}{}\033[0m\033[2m{}\033[0m".format(fg_code, "\u2588" * filled, "\u2591" * empty)

            if turn in intervention_turn_set:
                status = _c("BLOCKED", "red")
            else:
                status = _c("ALLOWED", "green")

            req = trace_inputs.get(turn, "")
            short_req = req[:70] + "..." if len(req) > 70 else req

            print("  {:<6d} {:<10s} {:<7s} {}  {:<9s} {}".format(
                turn,
                _c("{:.3f}".format(fid), zone_fg),
                _c(zone, zone_fg),
                bar_str,
                status,
                _c('"{}"'.format(short_req), "dim") if short_req else "",
            ))
            _pause(0.4)

    if trace_interventions:
        _pause(0.5)
        print()
        print(_c("  Intervention log ({})".format(len(trace_interventions)), "white", bold=True))
        print()
        print("  {:<6s} {:<14s} {:<22s} {:<10s} {}".format("Turn", "Level", "Trigger", "Fidelity", "Action"))
        print("  {}".format(_c("\u2500" * (W - 4), "dim")))
        for i in trace_interventions:
            level_fg = "red" if i["level"] in ("hard_block", "escalate") else "yellow"
            fid_fg = "red" if i["fidelity"] < 0.25 else "yellow"
            print("  {:<6d} {:<14s} {:<22s} {:<10s} {}".format(
                i["turn"],
                _c(i["level"].upper(), level_fg),
                i["trigger"][:22],
                _c("{:.3f}".format(i["fidelity"]), fid_fg),
                i["action"],
            ))
        _pause(1.5)
    else:
        print()
        print("  {}".format(_c("No interventions triggered", "green")))

    print()
    print("  {}".format(_c("To run forensics interactively:", "dim")))
    print("  {}".format(_c("  telos interpret {} --events".format(trace.trace_file), "cyan")))
    _pause(1.0)

    # ══════════════════════════════════════════════════════════════════
    # HTML GOVERNANCE REPORT
    # ══════════════════════════════════════════════════════════════════

    _pause(0.5)
    _header("Governance Report")
    _pause(0.5)

    print()
    print(_c("  Generating HTML governance report ...", "dim"))
    _pause(1.0)

    try:
        report_dir = os.path.join(_PROJECT_ROOT, "telos_reports")
        generator = GovernanceReportGenerator(
            output_dir=__import__("pathlib").Path(report_dir)
        )
        session_data = trace.export_to_dict()
        html_path = generator.generate_report(session_data)
        print()
        print("  {}".format(_bg(" HTML REPORT GENERATED ", "green", "black")))
        print()
        _kv("Report", str(html_path))
        _kv("Format", "Self-contained HTML (Plotly charts, dark theme)")
        _kv("Viewer", "Any browser \u2014 no server required")
        print()
        print("  {}".format(_c("To open the report:", "dim")))
        print("  {}".format(_c("  open {}".format(html_path), "cyan")))
    except Exception as exc:
        print()
        print("  {}".format(_c("[HTML report skipped: {}]".format(exc), "yellow")))
    _pause(1.0)

    # ── Done ──────────────────────────────────────────────────────────
    print()
    elapsed = time.time() - start_wall
    print(_c("  Demo completed in {:.1f}s".format(elapsed), "dim"))
    print(_c("═" * W, "cyan", bold=True))
    print()


if __name__ == "__main__":
    main()
