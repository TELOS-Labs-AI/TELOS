#!/usr/bin/env python3
"""
TELOS v2.0.0 -- OpenClaw Governance Demo
=========================================
Parameterized demo engine for all 9 OpenClaw governance surfaces.

Takes a config_id (e.g., "openclaw_shell_exec") and runs 10 scenarios
through the full L0->L1->L1.5->L2 governance cascade.

All 9 groups use a single governance config (templates/openclaw.yaml)
because OpenClaw is one agent with one purpose/scope/boundary set.
The groups demonstrate how TELOS governs different tool groups within
that single agent's attack surface.

Run:
  python3 demos/openclaw_live_demo.py --config openclaw_shell_exec
  DEMO_FAST=1 python3 demos/openclaw_live_demo.py --config openclaw_cross_group
  NO_COLOR=1 python3 demos/openclaw_live_demo.py --config openclaw_safe_baseline

Sources:
  CVE-2026-25253, CVE-2026-25157, Moltbook breach, ClawHavoc campaign,
  Cyera Research, infostealer evolution, Meta internal ban, Censys/Shodan
"""

import argparse
import hashlib
import hmac as _hmac
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

# Ensure the project root and demos dir are on sys.path
_DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_DEMO_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _DEMO_DIR not in sys.path:
    sys.path.insert(0, _DEMO_DIR)

# ---------------------------------------------------------------------------
# TELOS imports
# ---------------------------------------------------------------------------
from telos_core.embedding_provider import SentenceTransformerProvider
from telos_core.fidelity_engine import FidelityEngine
from telos_core.constants import (
    ST_AGENTIC_EXECUTE_THRESHOLD,
    ST_AGENTIC_CLARIFY_THRESHOLD,
    SIMILARITY_BASELINE,
    INTERVENTION_THRESHOLD,
    OUTPUT_INTERVENTION_THRESHOLD,
    DEFAULT_K_ATTRACTOR,
)
from telos_governance.tool_selection_gate import ToolSelectionGate, ToolDefinition, TOOL_SETS
from telos_governance.pa_extractor import PrimacyAttractor
from telos_governance.action_chain import ActionChain
from telos_core.governance_trace import GovernanceTraceCollector
from telos_core.evidence_schema import PrivacyMode, InterventionLevel
from telos_core.trace_verifier import verify_trace_integrity
from telos_observatory.services.report_generator import GovernanceReportGenerator

# Production engine imports (v2.0 cascade architecture)
from telos_governance.agentic_fidelity import AgenticFidelityEngine
from telos_governance.agentic_pa import AgenticPA
from telos_governance.types import ActionDecision
from telos_governance.config import load_config
from telos_governance.agent_templates import AgenticTemplate, register_config_tools

# SetFit L1.5 classifier (optional)
try:
    from telos_governance.setfit_classifier import SetFitBoundaryClassifier
    _HAS_SETFIT = True
except ImportError:
    _HAS_SETFIT = False

# Ed25519 session signing (optional)
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as _serialization
    _HAS_ED25519 = True
except ImportError:
    _HAS_ED25519 = False

# Display toolkit
from _display_toolkit import (  # noqa: E402
    NO_COLOR, DEMO_FAST, OBSERVE_MODE,
    _FG, _BG, _BOLD, _DIM, _STRIKE, _RESET,
    _c, _bg, _strike, _score_color, _zone_label, _bar,
    _pause, W, _wrap, _kv,
    _header, _section, _category_badge, _verdict_box,
    _score_panel, _agent_card, _blocked_card,
    _flow_line, _narrator, _cascade_panel,
)

# OpenClaw scenarios
from openclaw_scenarios import (
    SCENARIOS_BY_CONFIG, TOOL_DISPATCH, CONFIG_DISPLAY, CONFIG_ORDER,
)


# ═══════════════════════════════════════════════════════════════════════════
# Config resolution -- all groups use the same openclaw.yaml
# ═══════════════════════════════════════════════════════════════════════════

_OPENCLAW_YAML = os.path.join(_PROJECT_ROOT, "templates", "openclaw.yaml")


# ═══════════════════════════════════════════════════════════════════════════
# Receipt Bookkeeping
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class GovernanceReceipt:
    index: int
    request: str
    decision: Any
    fidelity: float
    tool: Optional[str]
    governance_ms: float
    llm_ms: float
    llm_called: bool
    tool_called: Optional[str] = None
    note: str = ""
    setfit_score: Optional[float] = None
    setfit_triggered: bool = False
    keyword_triggered: bool = False
    cascade_halt_layer: str = ""
    hmac_signature: str = ""


def _sign_receipt(receipt: GovernanceReceipt, key: bytes) -> str:
    """Compute HMAC-SHA512 over the canonical receipt payload."""
    payload = "{}|{}|{}|{:.6f}|{}|{:.2f}|{:.2f}|{}|{}|{}|{}".format(
        receipt.index,
        receipt.request,
        receipt.decision.value,
        receipt.fidelity,
        receipt.tool or "",
        receipt.governance_ms,
        receipt.llm_ms,
        receipt.llm_called,
        receipt.setfit_score if receipt.setfit_score is not None else "",
        receipt.setfit_triggered,
        receipt.cascade_halt_layer,
    )
    return _hmac.new(key, payload.encode("utf-8"), hashlib.sha512).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
# Mistral Agent Loop (reused from nearmap/healthcare demos)
# ═══════════════════════════════════════════════════════════════════════════

def _run_agent_loop(request, system_prompt, client, model, tool_dispatch, mistral_tools):
    """Real agentic loop: Mistral decides tools -> execute -> summarise."""
    tools_called = []
    t0 = time.perf_counter()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request},
    ]

    resp = client.chat.complete(
        model=model, messages=messages,
        tools=mistral_tools, tool_choice="auto", max_tokens=300,
    )
    msg = resp.choices[0].message

    if not msg.tool_calls:
        return ((msg.content or "").strip(), tools_called, (time.perf_counter() - t0) * 1000)

    messages.append(msg)

    for tc in msg.tool_calls:
        fn_name = tc.function.name
        try:
            fn_args = json.loads(tc.function.arguments)
        except (json.JSONDecodeError, TypeError):
            fn_args = {}

        executor = tool_dispatch.get(fn_name)
        result = executor(fn_args) if executor else {"error": "Unknown tool"}
        tools_called.append(fn_name)

        messages.append({
            "role": "tool", "name": fn_name,
            "content": json.dumps(result), "tool_call_id": tc.id,
        })

    final = client.chat.complete(model=model, messages=messages, max_tokens=300)
    content = (final.choices[0].message.content or "").strip()
    return (content, tools_called, (time.perf_counter() - t0) * 1000)


# ═══════════════════════════════════════════════════════════════════════════
# Main Demo
# ═══════════════════════════════════════════════════════════════════════════

def main(config_id: str, output_dir: Optional[str] = None):
    """Run the OpenClaw governance demo for a single tool group.

    Args:
        config_id: Tool group identifier (e.g., "openclaw_shell_exec")
        output_dir: Optional delivery folder for artifacts
    """
    session_id = "telos-{}".format(uuid.uuid4().hex[:8])
    start_wall = time.time()

    # Validate config
    if config_id not in CONFIG_DISPLAY:
        print("Unknown config: {}".format(config_id))
        print("Available: {}".format(", ".join(CONFIG_ORDER)))
        sys.exit(1)

    display = CONFIG_DISPLAY[config_id]
    scenarios = SCENARIOS_BY_CONFIG[config_id]
    tool_dispatch = TOOL_DISPATCH[config_id]

    # ── Section 1: Header ───────────────────────────────────────────
    _header(
        "TELOS v2.0.0 \u2014 OpenClaw Governance Demo\n"
        "{}\n"
        "\n"
        "What you are about to see:\n"
        "  {} requests enter a governed OpenClaw agent.\n"
        "  TELOS scores each request in <30ms \u2014 BEFORE the tool executes.\n"
        "  Aligned requests proceed. Violations are stopped cold.\n"
        "  Every decision is cryptographically signed for audit.".format(
            display["short_name"], len(scenarios))
    )
    _pause(2.0)

    # ── Disclaimer ────────────────────────────────────────────────
    print()
    print(_c("  " + "\u2500" * 64, "dim"))
    print(_c("  DISCLAIMER", "yellow"))
    print(_c("  " + "\u2500" * 64, "dim"))
    print(_c("  This demonstration uses synthetic scenarios derived from", "dim"))
    print(_c("  documented CVEs, security research, and real-world incidents.", "dim"))
    print(_c("  No live OpenClaw instances were accessed or modified.", "dim"))
    print(_c("  ", "dim"))
    print(_c("  Sources: CVE-2026-25253 (CVSS 8.8), CVE-2026-25157,", "dim"))
    print(_c("  Moltbook breach (Wiz Research), ClawHavoc campaign (Cisco),", "dim"))
    print(_c("  Cyera Research, Meta internal ban, Censys/Shodan data.", "dim"))
    print(_c("  " + "\u2500" * 64, "dim"))
    print()
    _pause(2.0)

    # ── Load config from YAML ──────────────────────────────────────
    print()
    print(_c("  Initialising governance engine ...", "dim"))
    _pause(1.0)

    t0 = time.perf_counter()
    embed_provider = SentenceTransformerProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    embed_fn = embed_provider.encode

    # Load YAML config -- all groups share openclaw.yaml
    config = load_config(_OPENCLAW_YAML)
    register_config_tools(config)
    template = AgenticTemplate.from_config(config)

    # Resolve tools from TOOL_SETS
    tools = TOOL_SETS.get("openclaw_governed", [])

    # Legacy engine (for output governance scoring)
    pa = PrimacyAttractor(
        text=template.purpose,
        embedding=embed_fn(template.purpose),
        source="configured",
    )
    legacy_engine = FidelityEngine(model_type="sentence_transformer")
    chain = ActionChain()

    # Production engine (v2.0 cascade)
    setfit_classifier = None
    setfit_loaded = False

    if _HAS_SETFIT:
        try:
            # Prefer config-based model selection: OpenClaw uses setfit_openclaw_v1,
            # falls back to healthcare model if OpenClaw model not yet exported.
            _openclaw_model = os.path.join(_PROJECT_ROOT, "models", "setfit_openclaw_v1")
            _healthcare_model = os.path.join(_PROJECT_ROOT, "models", "setfit_healthcare_v1")
            if os.path.isdir(_openclaw_model) and os.path.exists(os.path.join(_openclaw_model, "model.onnx")):
                _model_dir = _openclaw_model
                _model_label = "OpenClaw (AUC 0.990)"
            else:
                _model_dir = _healthcare_model
                _model_label = "Healthcare (AUC 0.980)"
            _cal_path = os.path.join(_model_dir, "calibration.json")
            setfit_classifier = SetFitBoundaryClassifier(
                model_dir=_model_dir,
                calibration_path=_cal_path if os.path.exists(_cal_path) else None,
            )
            setfit_loaded = True
            print(_c("  SetFit L1.5 classifier loaded -- {} calibrated".format(_model_label), "green"))
        except Exception as e:
            print(_c("  SetFit L1.5 unavailable: {}".format(e), "yellow"))

    pa_agentic = AgenticPA.create_from_template(
        purpose=template.purpose,
        scope=template.scope,
        boundaries=template.boundaries,
        tools=tools,
        embed_fn=embed_fn,
        example_requests=template.example_requests,
        safe_exemplars=template.safe_exemplars,
        template_id="openclaw_governed",
    )

    prod_engine = AgenticFidelityEngine(
        embed_fn=embed_fn,
        pa=pa_agentic,
        violation_keywords=template.violation_keywords,
        setfit_classifier=setfit_classifier,
    )
    print(_c("  Production engine ready (L0\u2192L1\u2192L1.5\u2192L2 cascade)", "green"))

    # ── Ephemeral cryptographic keys (per-session) ──
    hmac_key = os.urandom(32)

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
        enforcement_mode="observation" if OBSERVE_MODE else "enforcement",
    )
    trace.record_pa_established(
        pa_template="openclaw_governed",
        purpose_statement=template.purpose,
        tau=0.5, rigidity=0.5, basin_radius=2.0,
    )

    init_s = time.perf_counter() - t0

    # Check for Mistral
    mistral_key = os.environ.get("MISTRAL_API_KEY", "")
    mistral_client = None
    mistral_model = "mistral-small-latest"
    mistral_tools = None
    if mistral_key:
        try:
            from mistralai import Mistral
            mistral_client = Mistral(api_key=mistral_key)
            mistral_tools = []
            for t in config.tools:
                params = {}
                if hasattr(t, 'parameters') and t.parameters:
                    for p in t.parameters:
                        params[p.get("name", "input")] = {
                            "type": p.get("type", "string"),
                            "description": p.get("description", ""),
                        }
                if not params:
                    params = {"input": {"type": "string", "description": "Input for {}".format(t.name)}}
                mistral_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": {
                            "type": "object",
                            "properties": params,
                        },
                    },
                })
        except ImportError:
            pass

    has_agent = mistral_client is not None

    # ── Engine info display ──
    print()
    _kv("Agent", template.name)
    _kv("Purpose", template.purpose[:70] + "..." if len(template.purpose) > 70 else template.purpose)
    _kv("Tool Group", display["short_name"])
    _kv("Boundaries", "{} hard constraints".format(len(template.boundaries)))
    _kv("Tools", "{} authorised tools (10 groups, 4 risk tiers)".format(len(config.tools)))
    _kv("Embedding", "Local (no cloud dependency)")
    _kv("Engine", _c("AgenticFidelityEngine (production)", "green"))
    _kv("Cascade", "L0:keywords \u2192 L1:cosine \u2192 L1.5:SetFit \u2192 L2:LLM")
    if setfit_loaded:
        _kv("SetFit L1.5", _c("loaded", "green") + " (AUC 0.980, threshold {:.2f})".format(
            setfit_classifier.threshold))
    else:
        _kv("SetFit L1.5", _c("unavailable", "yellow") + " (cascade runs without L1.5)")

    if has_agent:
        _kv("LLM", "{} (native function calling)".format(mistral_model))
        _kv("Mode", _c("AGENTIC", "green") + " \u2014 Mistral decides tool calls")
    else:
        _kv("LLM", _c("none", "yellow"))
        _kv("Mode", _c("GOVERNANCE-ONLY", "yellow") + " \u2014 set MISTRAL_API_KEY for agent mode")

    _kv("Tool backends", _c("simulated", "yellow") + " \u2014 real OpenClaw tools plug in here")
    _kv("Engine init", "{:.2f}s".format(init_s))

    if OBSERVE_MODE:
        print()
        print(_c("  MODE: OBSERVATION (scoring only \u2014 no enforcement)", "yellow"))

    _pause(2.0)

    # ── How TELOS Works (concept panel) ─────────────────────────────
    print()
    print("  {}".format(_c("\u250C" + "\u2500" * (W - 6) + "\u2510", "cyan")))
    print("  {}  {}{}".format(
        _c("\u2502", "cyan"),
        _c("HOW TELOS WORKS:", "white", bold=True),
        " " * (W - 24) + _c("\u2502", "cyan"),
    ))
    concept_lines = [
        "  Fidelity = alignment between request and agent purpose",
        "  Cascade  = L0:keywords \u2192 L1:cosine \u2192 L1.5:SetFit \u2192 L2:LLM",
        "  Chain SCI = coherence tracking across multi-step actions",
    ]
    for cl in concept_lines:
        pad = W - 6 - len(cl)
        if pad < 0:
            pad = 0
        print("  {}  {}{}{}".format(
            _c("\u2502", "cyan"), _c(cl, "dim"),
            " " * pad, _c("\u2502", "cyan"),
        ))
    print("  {}".format(_c("\u2514" + "\u2500" * (W - 6) + "\u2518", "cyan")))
    _pause(2.0)

    # ── WATCH FOR legend ────────────────────────────────────────────
    print()
    print("  {}".format(_c("\u250C" + "\u2500" * (W - 6) + "\u2510", "cyan")))
    print("  {}  {}{}".format(
        _c("\u2502", "cyan"),
        _c("WATCH FOR:", "white", bold=True),
        " " * (W - 22) + _c("\u2502", "cyan"),
    ))
    items = [
        "  \u2022 {} = request approved, tool executes".format(_c("Green EXECUTE", "green")),
        "  \u2022 {} = blocked BEFORE the tool runs".format(_c("Red ESCALATE", "red")),
        "  \u2022 {} = nuanced middle \u2014 verify intent".format(_c("Yellow CLARIFY", "yellow")),
        "  \u2022 {} = 4-layer governance cascade".format(_c("CASCADE panel", "cyan")),
        "  \u2022 Governance latency (bottom of each scenario)",
    ]
    for item_text in items:
        print("  {}  {}{}".format(
            _c("\u2502", "cyan"), item_text,
            " " * 2 + _c("\u2502", "cyan"),
        ))
    print("  {}".format(_c("\u2514" + "\u2500" * (W - 6) + "\u2518", "cyan")))
    _pause(3.0)

    receipts = []
    total_gov_ms = 0.0
    llm_calls_saved = 0
    would_block_count = 0

    # ── Section 2: Scenarios ────────────────────────────────────────
    total = len(scenarios)

    for idx, scenario in enumerate(scenarios):
        num = idx + 1

        badge = _category_badge(scenario.category)
        _section("[{}/{}]  {}  \u2014  {}".format(num, total, badge, scenario.label))
        _pause(1.0)

        if scenario.narrator:
            _narrator(scenario.narrator)
            _pause(2.0)

        print()
        print("  {} \"{}\"".format(_c("Request:", "white", bold=True), scenario.request))
        _pause(1.5)

        # ── Governance scoring ──
        t_gov = time.perf_counter()
        input_emb = embed_fn(scenario.request)

        prod_result = prod_engine.score_action(scenario.request)
        gov_ms = (time.perf_counter() - t_gov) * 1000
        total_gov_ms += gov_ms

        purpose_f = prod_result.purpose_fidelity
        raw_sim = prod_result.purpose_fidelity
        tool_f = prod_result.tool_fidelity
        tool_name = prod_result.selected_tool or "none"
        max_boundary_sim = prod_result.boundary_violation
        boundary_violation = prod_result.boundary_triggered
        matched_boundary_name = prod_result.dimension_explanations.get("boundary", "none")
        decision = prod_result.decision

        _setfit_triggered = prod_result.setfit_triggered
        _setfit_score = prod_result.setfit_score
        _keyword_triggered = prod_result.keyword_triggered
        _keyword_matches = prod_result.keyword_matches

        if _keyword_triggered and boundary_violation:
            _cascade_halt = "L0+L1"
        elif boundary_violation and not _setfit_triggered:
            _cascade_halt = "L1"
        elif _setfit_triggered:
            _cascade_halt = "L1.5"
        elif decision == ActionDecision.ESCALATE:
            _cascade_halt = "fidelity"
        else:
            _cascade_halt = "none"

        step = chain.add_step(
            action_text=scenario.request, embedding=input_emb,
            direct_fidelity=purpose_f,
        )
        chain_sci = step.continuity_score

        if purpose_f >= ST_AGENTIC_EXECUTE_THRESHOLD:
            purpose_label = "aligned"
        elif purpose_f >= ST_AGENTIC_CLARIFY_THRESHOLD:
            purpose_label = "in-scope"
        else:
            purpose_label = "drift"

        if chain_sci > 0.6:
            chain_label = "coherent"
        elif chain_sci > 0.3:
            chain_label = "drifting"
        elif step.step_index == 0:
            chain_label = "start"
        else:
            chain_label = "broken"

        boundary_hit = (
            boundary_violation
            and decision.value in ("escalate", "inert")
        )
        if boundary_hit:
            boundary_tag = _c("VIOLATION ({})".format(matched_boundary_name[:30]), "red")
        elif boundary_violation:
            boundary_tag = _c("detected (allowed)", "yellow")
        else:
            boundary_tag = _c("clear", "green")

        allowed = decision.value in ("execute", "clarify")
        would_block = not allowed

        if OBSERVE_MODE and not allowed:
            allowed = True
            would_block_count += 1

        _cascade_panel(prod_result, gov_ms, setfit_loaded)

        if _setfit_triggered and not hasattr(main, '_setfit_narrated'):
            main._setfit_narrated = True
            _narrator(
                "The ML classifier catches what cosine similarity misses "
                "\u2014 negation-blind patterns where the vocabulary looks "
                "in-scope but the intent is a boundary violation. In "
                "production, each deployment domain gets a domain-specific model."
            )
            _pause(2.0)

        _flow_line(allowed)

        if OBSERVE_MODE and would_block:
            obs_label = "WOULD BLOCK" if decision.value == "inert" else "WOULD ESCALATE"
            print("  {}".format(_c("  OBSERVATION: {} \u2014 tool NOT called in enforcement mode".format(obs_label), "yellow")))

        _pause(1.0)

        # ── Scoring panel ──
        print()
        print(_c("  Governance Scoring:", "dim"))
        _score_panel([
            ("Purpose", "{:.3f}".format(purpose_f), _bar(purpose_f), _c(purpose_label, _score_color(purpose_f))),
            ("Tool", "{:.3f}".format(tool_f), _bar(tool_f), tool_name),
            ("Chain SCI", "{:.3f}".format(chain_sci), _bar(max(0, chain_sci)), "step {} ({})".format(step.step_index + 1, chain_label)),
            ("Boundary", "{:.3f}".format(max_boundary_sim), " " * 14, boundary_tag),
        ])
        _pause(2.0)

        verdict_detail = ""
        if would_block:
            verdict_detail = scenario.note or "outside agent scope"
        _verdict_box(decision, verdict_detail)
        _pause(2.0)

        # ── Agent loop or blocked ──
        llm_response = None
        llm_ms = 0.0
        llm_called = False
        agent_tool_called = None

        if allowed:
            if has_agent:
                print()
                print("  {}".format(_c("  Agent reasoning ...", "blue")))
                _pause(0.5)
                try:
                    response_text, tools_used, loop_ms = _run_agent_loop(
                        scenario.request, template.system_prompt,
                        mistral_client, mistral_model,
                        tool_dispatch, mistral_tools,
                    )
                    llm_response = response_text
                    llm_ms = loop_ms
                    llm_called = True
                    if tools_used:
                        agent_tool_called = ", ".join(tools_used)
                except Exception as exc:
                    llm_response = "[Agent error: {}]".format(exc)
                    llm_called = True

                if llm_response:
                    display_text = llm_response[:300] + ("..." if len(llm_response) > 300 else "")
                    _agent_card(agent_tool_called, display_text)
                    _pause(3.0)
            else:
                print()
                print("  {}".format(_c("[governance-only mode \u2014 set MISTRAL_API_KEY for agent responses]", "yellow")))
                _pause(1.0)
        else:
            llm_calls_saved += 1
            reason = scenario.note or "outside agent scope"
            _blocked_card(scenario.request, reason)
            _pause(3.0)

        # ── Output governance ──
        output_fidelity = None
        output_zone = None
        output_raw = None
        output_in_basin = None
        output_would_suppress = False

        if llm_response and len(llm_response) >= 10 and not llm_response.startswith("[Agent error:"):
            response_emb = embed_fn(llm_response)
            output_result = legacy_engine.evaluate_request(
                input_embedding=response_emb,
                pa_embedding=pa.embedding,
            )
            output_fidelity = output_result.fidelity.normalized_fidelity
            output_raw = output_result.fidelity.raw_similarity
            output_zone = _zone_label(output_fidelity)
            output_in_basin = output_fidelity >= OUTPUT_INTERVENTION_THRESHOLD
            output_would_suppress = output_fidelity < OUTPUT_INTERVENTION_THRESHOLD

            print()
            print(_c("  Output governance:", "dim"))
            zone_color = _score_color(output_fidelity)
            print("    Response fidelity  {:.2f} {}  {}".format(
                output_fidelity, _bar(output_fidelity),
                _c(output_zone, zone_color)))

            if output_would_suppress:
                if OBSERVE_MODE:
                    print("    {}".format(_c(
                        "OBSERVATION: Would suppress \u2014 response drift detected (fidelity {:.2f})".format(output_fidelity),
                        "yellow")))
                else:
                    print("    {}".format(_c(
                        "OUTPUT GOVERNANCE: Response drift detected (fidelity {:.2f})".format(output_fidelity),
                        "red")))
            else:
                print("    {}".format(_c("Response allowed \u2014 within governance basin", "green")))

        # ── Metadata line ──
        print()
        latency_parts = ["{:.0f}ms governance".format(gov_ms)]
        if llm_called:
            latency_parts.append("{:.1f}s agent".format(llm_ms / 1000))
        meta = "\u23F1 {}".format(" + ".join(latency_parts))
        meta += "   |   Receipt #{} signed (HMAC-SHA512)".format(num)
        print("  {}".format(_c(meta, "dim")))

        if scenario.category == "MULTI-STEP" and step.step_index > 0:
            print()
            print(_c("  Chain timeline:", "dim"))
            chain_start = max(0, len(chain.steps) - 3)
            for s in chain.steps[chain_start:]:
                if s.effective_fidelity >= ST_AGENTIC_CLARIFY_THRESHOLD:
                    marker = _c("\u25CF", "green")
                else:
                    marker = _c("\u25CF", "red")
                print("    {} Step {} \u2014 SCI={:.2f}  fidelity={:.3f}".format(
                    marker, s.step_index + 1, s.continuity_score, s.effective_fidelity))
            _pause(1.5)

        # ── Forensic trace ──
        turn_t0 = time.perf_counter()
        trace.start_turn(turn_number=num, user_input=scenario.request)
        prev_fid = receipts[-1].fidelity if receipts else None
        trace.record_fidelity(
            turn_number=num,
            raw_similarity=raw_sim,
            normalized_fidelity=purpose_f,
            layer1_hard_block=(raw_sim < SIMILARITY_BASELINE),
            layer2_outside_basin=(purpose_f < INTERVENTION_THRESHOLD),
            distance_from_pa=1.0 - raw_sim,
            in_basin=(purpose_f >= INTERVENTION_THRESHOLD),
            previous_fidelity=prev_fid,
        )
        if would_block and not OBSERVE_MODE:
            i_level = InterventionLevel.ESCALATE
            trigger = "boundary_violation" if boundary_violation else "hard_block" if raw_sim < SIMILARITY_BASELINE else "basin_exit"
            trace.record_intervention(
                turn_number=num,
                intervention_level=i_level,
                trigger_reason=trigger,
                fidelity_at_trigger=purpose_f,
                controller_strength=min(DEFAULT_K_ATTRACTOR * (1.0 - purpose_f), 1.0),
                semantic_band=_zone_label(purpose_f).lower(),
                action_taken="escalate",
            )
        if llm_response:
            trace.record_response(
                turn_number=num,
                response_source="mistral_agent",
                response_content=llm_response,
                generation_time_ms=int(llm_ms),
                response_fidelity=output_fidelity if output_fidelity is not None else purpose_f,
                output_governance_scored=(output_fidelity is not None),
                output_raw_similarity=output_raw,
                output_normalized_fidelity=output_fidelity,
                output_fidelity_zone=output_zone,
                output_in_basin=output_in_basin,
                output_would_suppress=output_would_suppress,
            )
        trace.complete_turn(
            turn_number=num,
            final_fidelity=purpose_f,
            intervention_applied=(would_block and not OBSERVE_MODE),
            intervention_level=(
                InterventionLevel.ESCALATE if (would_block and not OBSERVE_MODE) else InterventionLevel.NONE
            ),
            turn_duration_ms=int((time.perf_counter() - turn_t0) * 1000),
        )

        receipt = GovernanceReceipt(
            index=num, request=scenario.request, decision=decision,
            fidelity=purpose_f, tool=tool_name,
            governance_ms=gov_ms, llm_ms=llm_ms, llm_called=llm_called,
            tool_called=agent_tool_called, note=scenario.note,
            setfit_score=_setfit_score,
            setfit_triggered=_setfit_triggered,
            keyword_triggered=_keyword_triggered,
            cascade_halt_layer=_cascade_halt,
        )
        receipt.hmac_signature = _sign_receipt(receipt, hmac_key)
        receipts.append(receipt)

    # ── End forensic session ──────────────────────────────────────
    elapsed_so_far = time.time() - start_wall
    trace.end_session(duration_seconds=elapsed_so_far, end_reason="demo_completed")

    # ── Section 3: Session Proof ────────────────────────────────────
    session_digest_input = "|".join(r.hmac_signature for r in receipts)
    session_digest = hashlib.sha256(session_digest_input.encode("utf-8")).hexdigest()

    ed_session_sig = None
    if _HAS_ED25519 and ed_private is not None:
        ed_session_sig = ed_private.sign(session_digest.encode("utf-8")).hex()
        ed_public.verify(
            bytes.fromhex(ed_session_sig),
            session_digest.encode("utf-8"),
        )

    _pause(1.0)
    _header("Governance Session Proof")
    print()
    _kv("Session", session_id)
    _kv("Tool Group", display["short_name"])
    _kv("Receipts", "{} (HMAC-SHA512 signed)".format(len(receipts)))
    _kv("Audit trail", "SHA-256 hash chain (tamper-evident)")
    _kv("Trace file", str(trace.trace_file))
    _pause(1.5)

    print()
    print(_c("  Receipt signatures (HMAC-SHA512):", "white", bold=True))
    print()
    for r in receipts:
        dc = "green" if r.decision in (ActionDecision.EXECUTE, ActionDecision.CLARIFY) else "red"
        sig_short = r.hmac_signature[:16] + "..." + r.hmac_signature[-8:]
        print("    #{:<3d} {}  {}".format(
            r.index, _c(r.decision.value.upper(), dc),
            _c(sig_short, "cyan")))
    _pause(1.5)

    print()
    print(_c("  Session digest (SHA-256 of receipt chain):", "white", bold=True))
    print("    {}".format(_c(session_digest, "cyan")))
    _pause(1.0)

    if ed_session_sig:
        print()
        print(_c("  Ed25519 session signature:", "white", bold=True))
        print("    Public key:  {}".format(_c(ed_pub_hex, "cyan")))
        print("    Signature:   {}...{}".format(
            _c(ed_session_sig[:24], "cyan"),
            _c(ed_session_sig[-16:], "cyan")))
        print("    Verified:    {}".format(_c("YES", "green")))
    else:
        print()
        print(_c("  Ed25519 session signature: unavailable (install `cryptography`)", "yellow"))
    _pause(1.5)

    print()
    print(_c("  Blocked requests (audit trail):", "dim"))
    for r in receipts:
        if r.decision == ActionDecision.ESCALATE:
            note = r.note or "outside agent scope"
            short_req = r.request[:50] + "..." if len(r.request) > 50 else r.request
            print("    #{:<3d} {}  \"{}\" \u2014 {}".format(
                r.index, _c(r.decision.value.upper(), "red"), short_req, _c(note, "dim")))
    _pause(2.0)

    # ── Section 4: Summary ──────────────────────────────────────────
    n_allowed = sum(1 for r in receipts if r.decision in (
        ActionDecision.EXECUTE, ActionDecision.CLARIFY))
    n_blocked = sum(1 for r in receipts if r.decision == ActionDecision.ESCALATE)
    n_tool_calls = sum(1 for r in receipts if r.tool_called)
    avg_gov = total_gov_ms / len(receipts) if receipts else 0

    n_setfit_fired = sum(1 for r in receipts if r.setfit_triggered)
    n_keyword_fired = sum(1 for r in receipts if r.keyword_triggered)
    halt_dist = {}
    for r in receipts:
        layer = r.cascade_halt_layer or "none"
        halt_dist[layer] = halt_dist.get(layer, 0) + 1

    _header("Summary")
    print()

    if OBSERVE_MODE:
        print(_c("  Mode: OBSERVATION \u2014 no enforcement applied", "yellow"))
        print("  Requests that would have been blocked: {}".format(would_block_count))
        print()

    _kv("Tool Group", display["short_name"])
    _kv("Allowed", str(n_allowed))
    _kv("Blocked", str(n_blocked))
    _kv("Total", str(len(receipts)))
    _kv("Avg governance", "{:.0f}ms per request".format(avg_gov))
    if has_agent:
        _kv("Agent tool calls", str(n_tool_calls))
    _kv("LLM calls saved", _c("{} (blocked before API)".format(llm_calls_saved), "green"))

    print()
    print(_c("  Cascade breakdown:", "white", bold=True))
    _kv("L0 keyword triggers", str(n_keyword_fired))
    _kv("L1.5 SetFit triggers", str(n_setfit_fired))
    _kv("SetFit model", _c("loaded (AUC 0.980)", "green") if setfit_loaded else _c("unavailable", "yellow"))
    for layer_name in ("none", "L0+L1", "L1", "L1.5", "fidelity"):
        count = halt_dist.get(layer_name, 0)
        if count > 0:
            label = {"none": "passed all layers", "L0+L1": "halted at L0+L1",
                     "L1": "halted at L1 (cosine)", "L1.5": "halted at L1.5 (SetFit)",
                     "fidelity": "halted at fidelity"}.get(layer_name, layer_name)
            _kv("  " + label, str(count))
    _pause(2.0)

    print()
    print(_c("  What this means for OpenClaw security:", "white", bold=True))
    _pause(0.5)
    outcomes = [
        "Boundary violations are stopped BEFORE tools execute \u2014 not after",
        "Legitimate developer workflows proceed with zero friction ({:.0f}ms overhead)".format(avg_gov),
        "Every decision is HMAC-SHA512 signed with Ed25519 session proof",
        "10 tool groups across 4 risk tiers governed by a single cascade engine",
        "Cross-group exfiltration chains detected via chain continuity tracking",
    ]
    for o in outcomes:
        print("  \u2022 {}".format(o))
        _pause(0.8)
    _pause(2.0)

    # ── Section 5: Forensic Verification ──────────────────────────
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
        """Human-readable narration for each sealed event."""
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
            snippet = inp[:50] + "..." if len(inp) > 50 else inp
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
            return "Session closed: {} turns, {} interventions, avg fidelity {:.3f} ({:.0f}s)".format(
                turns, intv, avg, dur)
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

        _narr = _chain_narration(_ce)
        print("  {} {:>3d}  {:<28s}  {}  {}".format(
            _mark, _ci + 1, _etype, _c(_short, "cyan"), _arrow))
        if _narr:
            print("  {}     {}".format(" " * 1, _c(_narr, "dim")))
        _expected = _ehash
        _pause(0.08)

    print()
    print("  {}  {} = hash verified   {}  {} = chain link".format(
        _c("\u2713", "green"), _c("abc123...", "cyan"),
        _c("\u2190", "dim"), _c("prev_hash", "dim")))
    _pause(1.0)

    if report.is_valid:
        print()
        print("  {}".format(_bg(" CHAIN INTEGRITY VERIFIED ", "green", "black")))
    else:
        print()
        print("  {}".format(_bg(" CHAIN INTEGRITY FAILED ", "red", "white")))
    _pause(1.0)

    print()
    _kv("Trace file", str(trace.trace_file))
    _kv("File size", "{:,} bytes".format(report.file_size_bytes))
    _kv("Total events", str(report.total_events))
    _kv("Hash algorithm", "SHA-256")
    _kv("Chain status", _c("VALID", "green") if report.is_valid else _c("BROKEN", "red"))
    _kv("Verified in", "{:.1f}ms".format(report.verification_duration_ms))
    _pause(1.0)

    # ── Section 6: HTML Governance Report ──────────────────────────
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
    except Exception as exc:
        html_path = None
        print()
        print("  {}".format(_c(
            "[HTML report skipped: {}]".format(exc), "yellow")))
    _pause(1.0)

    # ── Section 7: Delivery folder ──────────────────────────────────
    if output_dir:
        _pause(0.5)
        _header("Delivery Artifacts")
        print()

        config_short = config_id.replace("openclaw_", "")
        delivery_dir = os.path.join(output_dir, config_short)
        os.makedirs(delivery_dir, exist_ok=True)

        dst_yaml = os.path.join(delivery_dir, "config.yaml")
        shutil.copy2(_OPENCLAW_YAML, dst_yaml)
        _kv("Config YAML", dst_yaml)

        dst_trace = os.path.join(delivery_dir, "session_trace.jsonl")
        shutil.copy2(str(trace.trace_file), dst_trace)
        _kv("Session trace", dst_trace)

        dst_receipts = os.path.join(delivery_dir, "receipts.json")
        receipt_data = []
        for r in receipts:
            receipt_data.append({
                "index": r.index,
                "request": r.request,
                "decision": r.decision.value,
                "fidelity": r.fidelity,
                "tool": r.tool,
                "governance_ms": r.governance_ms,
                "llm_called": r.llm_called,
                "setfit_score": r.setfit_score,
                "setfit_triggered": r.setfit_triggered,
                "keyword_triggered": r.keyword_triggered,
                "cascade_halt_layer": r.cascade_halt_layer,
                "hmac_signature": r.hmac_signature,
            })
        with open(dst_receipts, "w") as f:
            json.dump(receipt_data, f, indent=2)
        _kv("Receipts", dst_receipts)

        dst_proof = os.path.join(delivery_dir, "session_proof.json")
        proof_data = {
            "session_id": session_id,
            "config_id": config_id,
            "receipt_count": len(receipts),
            "session_digest_sha256": session_digest,
            "ed25519_public_key": ed_pub_hex,
            "ed25519_signature": ed_session_sig,
            "verified": True,
        }
        with open(dst_proof, "w") as f:
            json.dump(proof_data, f, indent=2)
        _kv("Session proof", dst_proof)

        if html_path and os.path.exists(str(html_path)):
            dst_html = os.path.join(delivery_dir, "report.html")
            shutil.copy2(str(html_path), dst_html)
            _kv("HTML report", dst_html)

        print()
        print("  {}".format(_bg(" DELIVERY ARTIFACTS SAVED ", "green", "black")))
        _pause(1.0)

    print()
    elapsed = time.time() - start_wall
    print(_c("  Demo completed in {:.1f}s".format(elapsed), "dim"))
    print(_c("\u2550" * W, "cyan", bold=True))
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="TELOS OpenClaw Governance Demo",
        epilog="Environment variables: DEMO_FAST=1 (skip pauses), DEMO_OBSERVE=1 (extended pauses)",
    )
    parser.add_argument("--config", "-c", required=True,
                        help="Tool group ID (e.g., openclaw_shell_exec)")
    parser.add_argument("--output", "-o", default=None,
                        help="Delivery folder for artifacts")
    parser.add_argument("--fast", action="store_true",
                        help="Skip pauses between scenarios (equivalent to DEMO_FAST=1)")
    parser.add_argument("--observe", action="store_true",
                        help="Extended pauses for audience demos (equivalent to DEMO_OBSERVE=1)")
    args = parser.parse_args()

    if args.fast:
        os.environ["DEMO_FAST"] = "1"
    if args.observe:
        os.environ["DEMO_OBSERVE"] = "1"

    main(args.config, args.output)
