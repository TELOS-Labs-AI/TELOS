#!/usr/bin/env python3
"""
Vultr local review app.

Partnership review surface for Vultr:
- auto-start governance simulation on page load
- stream events with decision panel showing cascade detail
- narrative flow: problem -> proof -> partnership
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = PROJECT_ROOT / ".demo_runtime" / "vultr"
AUDIT_PATH = RUNTIME_ROOT / "audit" / "telos_audit.jsonl"
ESCALATION_DIR = RUNTIME_ROOT / "escalations"
LOG_DIR = RUNTIME_ROOT / "logs"
CONFIG_PATH = PROJECT_ROOT / "demos" / "vultr_governed_cloud.yaml"

_lock = threading.Lock()
_proc_state: Dict[str, Dict[str, Any]] = {
    "feed": {
        "process": None,
        "log_handle": None,
        "log_path": LOG_DIR / "feed.log",
        "returncode": None,
    },
}


def _ensure_runtime_dirs() -> None:
    for path in (RUNTIME_ROOT, AUDIT_PATH.parent, ESCALATION_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _base_env() -> Dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["VULTR_RUNTIME_DIR"] = str(RUNTIME_ROOT)
    env["VULTR_AUDIT_PATH"] = str(AUDIT_PATH)
    env["VULTR_ESCALATION_DIR"] = str(ESCALATION_DIR)
    env["VULTR_CONFIG"] = str(CONFIG_PATH)
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    return env


def _cleanup_finished(name: str) -> None:
    state = _proc_state[name]
    proc = state["process"]
    if proc is not None and proc.poll() is not None:
        handle = state["log_handle"]
        if handle is not None:
            handle.close()
        state["returncode"] = proc.returncode
        state["process"] = None
        state["log_handle"] = None


def _start_process(name: str, args: List[str], extra_env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    _ensure_runtime_dirs()
    with _lock:
        _cleanup_finished(name)
        state = _proc_state[name]
        if state["process"] is not None:
            raise HTTPException(status_code=409, detail=f"{name} already running")

        log_path = state["log_path"]
        log_handle = open(log_path, "ab")
        env = _base_env()
        if extra_env:
            env.update(extra_env)

        proc = subprocess.Popen(
            args,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        state["process"] = proc
        state["log_handle"] = log_handle
        state["started_at"] = time.time()
        state["returncode"] = None
        return {"pid": proc.pid, "log_path": str(log_path)}


def _tail_log(log_path: Path, lines: int = 40) -> List[str]:
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return text[-lines:]


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _load_escalations() -> List[Dict[str, Any]]:
    if not ESCALATION_DIR.exists():
        return []
    items = []
    for path in sorted(ESCALATION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_file"] = path.name
            items.append(data)
        except Exception:
            continue
    return items


def _decision_summary(events: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"EXECUTE": 0, "CLARIFY": 0, "ESCALATE": 0, "INERT": 0}
    for event in events:
        if event.get("event") != "tool_call_scored":
            continue
        decision = str(event.get("data", {}).get("decision", "")).upper()
        if decision in counts:
            counts[decision] += 1
    return counts


def _recent_scored_events(events: List[Dict[str, Any]], limit: int = 30) -> List[Dict[str, Any]]:
    scored = []
    for event in events:
        if event.get("event") != "tool_call_scored":
            continue
        data = event.get("data", {})
        scored.append(
            {
                "timestamp": event.get("timestamp"),
                "decision": str(data.get("decision", "")).upper(),
                "tool_name": data.get("tool_name"),
                "risk_tier": data.get("risk_tier"),
                "fidelity": data.get("fidelity"),
                "action_text": data.get("action_text"),
                "boundary_triggered": data.get("boundary_triggered"),
                "explanation": data.get("explanation"),
                "purpose_fidelity": data.get("purpose_fidelity"),
                "scope_fidelity": data.get("scope_fidelity"),
                "boundary_violation": data.get("boundary_violation"),
                "tool_fidelity": data.get("tool_fidelity"),
                "chain_continuity": data.get("chain_continuity"),
                "cascade_layers": data.get("cascade_layers"),
            }
        )
    return scored[-limit:][::-1]


def _status_payload() -> Dict[str, Any]:
    _ensure_runtime_dirs()
    _cleanup_finished("feed")

    audit_events = _read_jsonl(AUDIT_PATH)
    escalations = _load_escalations()

    proc = _proc_state["feed"]["process"]
    process_status = {
        "feed": {
            "running": proc is not None,
            "pid": proc.pid if proc is not None else None,
            "returncode": _proc_state["feed"].get("returncode"),
            "log_path": str(_proc_state["feed"]["log_path"]),
            "tail": _tail_log(_proc_state["feed"]["log_path"]),
        },
    }

    return {
        "runtime_root": str(RUNTIME_ROOT),
        "config_path": str(CONFIG_PATH),
        "audit_path": str(AUDIT_PATH),
        "escalation_dir": str(ESCALATION_DIR),
        "counts": _decision_summary(audit_events),
        "audit_event_count": len(audit_events),
        "recent_events": _recent_scored_events(audit_events),
        "escalations": escalations[:10],
        "processes": process_status,
    }


HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>TELOS Governance Engine -- Vultr Cloud</title>
  <style>
    :root {
      --bg: #0d1117;
      --panel: #161b22;
      --muted: #8b949e;
      --text: #e6edf3;
      --accent: #007bff;
      --green: #4ade80;
      --yellow: #facc15;
      --red: #f87171;
      --cyan: #67e8f9;
      --gray: #94a3b8;
      --border: #30363d;
    }
    * { box-sizing: border-box; }
    body { background: var(--bg); color: var(--text); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; margin: 0; font-size: 13px; }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 24px; }

    /* Sticky summary bar */
    .sticky-bar { position: fixed; top: 0; left: 0; right: 0; background: #0d1117ee; border-bottom: 1px solid var(--border); padding: 8px 24px; z-index: 100; display: none; backdrop-filter: blur(8px); }
    .sticky-bar.visible { display: flex; align-items: center; justify-content: center; gap: 24px; }
    .sticky-bar .sb-item { font-size: 12px; }
    .sticky-bar .sb-val { font-weight: 700; }

    /* Header */
    .header { margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid var(--border); }
    .header h1 { margin: 0 0 16px; color: var(--accent); font-size: 22px; letter-spacing: -0.5px; }
    .header .problem { color: var(--text); font-size: 14px; line-height: 1.6; margin: 0 0 12px; max-width: 800px; }
    .header .solution { color: var(--cyan); font-size: 13px; margin: 0 0 8px; line-height: 1.5; }
    .header .key-point { color: var(--green); font-size: 13px; margin: 0 0 12px; }
    .header .cta { color: var(--muted); font-size: 12px; margin: 0; }

    /* Observation mode callout */
    .obs-callout { background: #0c2d48; border: 1px solid #1e4d7b; padding: 16px; margin-bottom: 32px; }
    .obs-callout .obs-title { color: var(--cyan); font-weight: 700; font-size: 14px; margin-bottom: 8px; }
    .obs-callout .obs-body { color: var(--text); font-size: 12px; line-height: 1.6; }
    .obs-callout .obs-body strong { color: var(--cyan); }

    /* Cascade explainer */
    .cascade-bar { display: flex; align-items: center; gap: 0; margin: 0 0 32px; overflow-x: auto; }
    .cascade-step { background: var(--panel); border: 1px solid var(--border); padding: 10px 14px; flex: 1; min-width: 130px; }
    .cascade-step .cs-label { color: var(--accent); font-size: 11px; font-weight: 700; text-transform: uppercase; }
    .cascade-step .cs-desc { color: var(--muted); font-size: 11px; margin-top: 4px; }
    .cascade-step .cs-time { color: var(--green); font-size: 10px; margin-top: 2px; }
    .cascade-arrow { color: var(--muted); padding: 0 4px; font-size: 16px; flex-shrink: 0; }

    /* Simulation section */
    .sim-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
    .sim-header h2 { margin: 0; font-size: 16px; color: var(--accent); }
    .sim-controls { display: flex; gap: 8px; align-items: center; }
    button { background: var(--panel); color: var(--text); border: 1px solid var(--accent); padding: 8px 14px; cursor: pointer; font-family: inherit; font-size: 12px; }
    button:hover { background: #1f2630; }
    .sim-status { color: var(--muted); font-size: 12px; }

    /* Observation counters -- reframed */
    .counters { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px; }
    .counter { background: var(--panel); border: 1px solid var(--border); padding: 12px; text-align: center; transition: border-color 0.3s; }
    .counter.pulse { animation: pulse-border 0.6s ease-out; }
    .counter .c-label { font-size: 11px; color: var(--muted); text-transform: uppercase; font-weight: 600; }
    .counter .c-value { font-size: 32px; font-weight: 700; margin-top: 4px; }
    .counter .c-desc { font-size: 10px; color: var(--muted); margin-top: 2px; }
    .c-observed { color: var(--cyan); }
    .c-nominal { color: var(--green); }
    .c-flagged { color: var(--yellow); }
    .c-boundary { color: var(--red); }
    @keyframes pulse-border { 0% { border-color: var(--accent); } 100% { border-color: var(--border); } }

    /* Main simulation layout */
    .sim-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 32px; }

    /* Event stream */
    .panel { background: var(--panel); border: 1px solid var(--border); padding: 14px; }
    .panel h3 { margin: 0 0 10px; font-size: 12px; color: var(--muted); font-weight: 600; text-transform: uppercase; }
    .event-stream { max-height: 420px; overflow-y: auto; }
    .ev-row { padding: 8px 0; border-bottom: 1px solid var(--border); border-left: 3px solid transparent; padding-left: 10px; transition: background 0.3s; }
    .ev-row.new { animation: flash-in 0.5s ease-out; }
    .ev-row.selected { background: #1c2333; }
    .ev-row:hover { background: #1c2333; cursor: pointer; }
    .ev-verdict { font-weight: 700; font-size: 11px; display: inline-block; width: 80px; }
    .ev-tool { color: var(--muted); font-size: 11px; }
    .ev-action { color: var(--text); font-size: 12px; margin-top: 3px; line-height: 1.4; }
    .ev-obs-note { font-size: 10px; margin-top: 2px; font-style: italic; }
    .ev-row.v-EXECUTE { border-left-color: var(--green); }
    .ev-row.v-CLARIFY { border-left-color: var(--yellow); }
    .ev-row.v-ESCALATE { border-left-color: var(--red); }
    .ev-row.v-INERT { border-left-color: var(--gray); }
    .v-EXECUTE .ev-verdict { color: var(--green); }
    .v-CLARIFY .ev-verdict { color: var(--yellow); }
    .v-ESCALATE .ev-verdict { color: var(--red); }
    .v-INERT .ev-verdict { color: var(--gray); }
    @keyframes flash-in { 0% { background: #1c2333; } 100% { background: transparent; } }

    /* Decision panel */
    .decision-panel { position: sticky; top: 60px; }
    .dp-verdict { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
    .dp-obs-label { font-size: 11px; margin-bottom: 12px; padding: 3px 8px; display: inline-block; border-radius: 3px; }
    .dp-section { margin-bottom: 14px; }
    .dp-section-title { font-size: 11px; color: var(--muted); text-transform: uppercase; font-weight: 600; margin-bottom: 6px; }
    .dp-action { color: var(--text); font-size: 12px; line-height: 1.5; margin-bottom: 4px; }
    .dp-tool { color: var(--muted); font-size: 11px; }
    .dp-explanation { color: var(--text); font-size: 12px; line-height: 1.5; background: #0d1117; padding: 10px; border-left: 3px solid var(--accent); }
    .dp-dims { width: 100%; }
    .dp-dims td { padding: 4px 8px; font-size: 12px; border-bottom: 1px solid #21262d; }
    .dp-dims .dim-name { color: var(--muted); }
    .dp-dims .dim-val { font-weight: 600; text-align: right; }
    .dp-bar { height: 4px; background: #21262d; margin-top: 2px; }
    .dp-bar-fill { height: 100%; transition: width 0.3s; }
    .dp-empty { color: var(--muted); font-size: 13px; text-align: center; padding: 40px 0; line-height: 1.6; }

    /* Architecture section */
    h2.section-title { font-size: 16px; color: var(--accent); margin: 32px 0 16px; padding-top: 16px; border-top: 1px solid var(--border); }
    .arch-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 32px; }
    .pod-diagram { font-size: 11px; line-height: 1.7; color: var(--green); }
    .arch-facts .af-row { padding: 6px 0; border-bottom: 1px solid #21262d; display: flex; justify-content: space-between; }
    .af-label { color: var(--muted); }
    .af-value { color: var(--text); font-weight: 600; }

    /* Economics section */
    .econ-layout { margin-bottom: 32px; }
    .timeline-step { padding: 12px 0; border-bottom: 1px solid #21262d; }
    .ts-phase { color: var(--accent); font-weight: 700; font-size: 12px; }
    .ts-desc { color: var(--text); font-size: 12px; margin-top: 4px; }

    /* Compliance badges */
    .compliance-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
    .badge { padding: 4px 10px; font-size: 11px; border-radius: 3px; background: #0d4429; color: var(--green); }

    .small { color: var(--muted); font-size: 12px; }
    @media (max-width: 900px) {
      .sim-layout, .arch-layout, .econ-layout, .counters { grid-template-columns: 1fr; }
      .cascade-bar { flex-wrap: wrap; }
    }
  </style>
</head>
<body>

  <!-- Sticky summary bar -->
  <div class="sticky-bar" id="sticky-bar">
    <span class="sb-item"><span class="sb-val" style="color:var(--cyan)" id="sb-total">0</span> observed</span>
    <span class="sb-item"><span class="sb-val" style="color:var(--red)" id="sb-findings">0</span> findings</span>
    <span class="sb-item"><span class="sb-val" style="color:var(--green)">8-17ms</span> latency (measured)</span>
    <span class="sb-item" style="color:var(--cyan)">OBSERVATION MODE -- agent uninterrupted</span>
  </div>

  <div class="wrap">

    <!-- 1. Header -->
    <div class="header">
      <h1>TELOS GOVERNANCE ENGINE</h1>
      <p class="problem">
        Enterprise AI agents execute thousands of autonomous decisions per hour on
        your infrastructure. Right now, no one knows what those agents are actually
        doing. There is no semantic understanding of agent behavior, no post-hoc
        forensic trail, and no evidence to hand regulators when they ask.
      </p>
      <p class="solution">
        TELOS deploys as a silent observation layer -- a Kubernetes sidecar that
        semantically scores every agent action in 8-17ms (measured on production workloads). The agent is never
        interrupted. Nothing changes for the customer's workload.
      </p>
      <p class="key-point">
        What changes: every action is now understood, scored, and recorded.
        When you need to know what an agent did and why -- the evidence is already there.
      </p>
      <p class="cta" id="cta-text">Deploying observation layer...</p>
    </div>

    <!-- Observation Mode Callout -->
    <div class="obs-callout">
      <div class="obs-title">Observation Mode -- How TELOS Enters Production</div>
      <div class="obs-body">
        TELOS starts in <strong>observation mode</strong>. Every agent action is scored through
        the full 4-layer cascade, but nothing is blocked. The agent runs exactly as it would
        without governance. The telemetry accumulates silently -- building a semantic model of
        what "normal" looks like for this specific workload.<br><br>
        Over time, the system <strong>entrains</strong>: it learns the agent's patterns, calibrates
        its thresholds from real production data, and refines its false positive rate.
        When a customer chooses to enable enforcement boundaries, the governance model
        has been building context from real workload data -- not starting cold.<br><br>
        This is not keyword matching. This is <strong>semantic governance</strong> -- TELOS understands
        what the agent is doing, not just what words it used. No other production system provides this layer.
      </div>
    </div>

    <!-- 2. Cascade Explainer -->
    <div class="cascade-bar">
      <div class="cascade-step">
        <div class="cs-label">Action</div>
        <div class="cs-desc">Agent requests tool call</div>
      </div>
      <div class="cascade-arrow">&#x2192;</div>
      <div class="cascade-step">
        <div class="cs-label">L1: Keywords</div>
        <div class="cs-desc">Violation term scan</div>
        <div class="cs-time">~1ms</div>
      </div>
      <div class="cascade-arrow">&#x2192;</div>
      <div class="cascade-step">
        <div class="cs-label">L2: Semantic</div>
        <div class="cs-desc">ONNX embedding similarity</div>
        <div class="cs-time">~5ms</div>
      </div>
      <div class="cascade-arrow">&#x2192;</div>
      <div class="cascade-step">
        <div class="cs-label">L3: Classifier</div>
        <div class="cs-desc">SetFit categorization</div>
        <div class="cs-time">~10ms</div>
      </div>
      <div class="cascade-arrow">&#x2192;</div>
      <div class="cascade-step">
        <div class="cs-label">L4: Composite</div>
        <div class="cs-desc">5-dimension score</div>
        <div class="cs-time">~1ms</div>
      </div>
      <div class="cascade-arrow">&#x2192;</div>
      <div class="cascade-step">
        <div class="cs-label">Recorded</div>
        <div class="cs-desc">Scored, logged, never blocked</div>
        <div class="cs-time">8-17ms (measured)</div>
      </div>
    </div>

    <!-- 3. Live Simulation -->
    <div class="sim-header">
      <h2>Observation Layer -- Live Simulation</h2>
      <div class="sim-controls">
        <span class="sim-status" id="sim-status"></span>
        <button onclick="runSim()" id="btn-run">Run Simulation</button>
        <button onclick="resetSim()">Reset</button>
      </div>
    </div>

    <div class="counters">
      <div class="counter" id="card-total"><div class="c-label">Observed</div><div class="c-value c-observed" id="cnt-total">0</div><div class="c-desc">Actions silently scored</div></div>
      <div class="counter" id="card-nominal"><div class="c-label">Nominal</div><div class="c-value c-nominal" id="cnt-nominal">0</div><div class="c-desc">Within expected behavior</div></div>
      <div class="counter" id="card-review"><div class="c-label">Review</div><div class="c-value c-flagged" id="cnt-review">0</div><div class="c-desc">Worth post-hoc examination</div></div>
      <div class="counter" id="card-finding"><div class="c-label">Findings</div><div class="c-value c-boundary" id="cnt-finding">0</div><div class="c-desc">Boundary proximity detected</div></div>
    </div>

    <div class="sim-layout">
      <!-- Event stream -->
      <div class="panel">
        <h3>Observation Stream</h3>
        <div class="event-stream" id="event-stream">
          <div class="dp-empty" id="stream-empty">
            Waiting for simulation to start...
          </div>
        </div>
      </div>

      <!-- Decision panel -->
      <div class="panel decision-panel" id="decision-panel">
        <h3>Observation Detail</h3>
        <div id="dp-content">
          <div class="dp-empty">
            Click any event to see the full scoring cascade.<br><br>
            In observation mode, every action is scored but none are blocked.
            The telemetry shows what the agent did and how close it came to
            defined boundaries -- forensic evidence that does not exist today.
          </div>
        </div>
      </div>
    </div>

    <!-- 4. Deployment Architecture -->
    <h2 class="section-title">How It Deploys</h2>
    <p class="small" style="margin-bottom:16px;">The events above were scored by the observation sidecar shown here. The agent was never interrupted. Same engine, same cascade, same audit trail as production.</p>
    <div class="arch-layout">
      <div class="panel">
        <pre class="pod-diagram">
  ┌──────────── Vultr Kubernetes Pod ────────────┐
  │                                              │
  │  ┌──────────────┐   ┌───────────────────┐   │
  │  │  AI Agent     │──▸│  TELOS Sidecar    │   │
  │  │  Container    │   │  (observation)    │   │
  │  │               │◂──│                   │   │
  │  │  LLM calls    │   │  scores silently  │   │
  │  │  Tool exec    │   │  never blocks     │   │
  │  │  Business     │   │  8-17ms measured  │   │
  │  │  logic        │   │                   │   │
  │  └──────────────┘   └───────────────────┘   │
  │                             │                │
  │                    ┌────────▾────────┐       │
  │                    │  Audit Volume   │       │
  │                    │  (Block PVC)    │       │
  │                    │  immutable      │       │
  │                    │  append-only    │       │
  │                    │  forensic-grade │       │
  │                    └─────────────────┘       │
  └──────────────────────────────────────────────┘</pre>
      </div>
      <div class="panel">
        <h3>What We Know (Measured)</h3>
        <div class="arch-facts">
          <div class="af-row"><span class="af-label">Agent impact</span><span class="af-value">None -- observation only</span></div>
          <div class="af-row"><span class="af-label">Integration</span><span class="af-value">Hook-based -- no agent code changes</span></div>
          <div class="af-row"><span class="af-label">Scoring latency</span><span class="af-value">8-17ms per action (measured)</span></div>
          <div class="af-row"><span class="af-label">Embedding model</span><span class="af-value">~24MB ONNX (MiniLM-L6-v2)</span></div>
          <div class="af-row"><span class="af-label">Scoring</span><span class="af-value">CPU-only -- no GPU required</span></div>
          <div class="af-row"><span class="af-label">Audit trail</span><span class="af-value">Append-only JSONL, hash-chained</span></div>
          <div class="af-row"><span class="af-label">Entrainment</span><span class="af-value">Self-calibrates from production telemetry</span></div>
        </div>
        <div class="small" style="margin-top:10px;color:#94a3b8;">
          Latency measured on production TELOS daemon scoring live agent tool calls. Resource footprint (RAM, CPU) varies by deployment -- sidecar sizing TBD with Vultr engineering.
        </div>
      </div>
    </div>

    <!-- 5. Telemetry Timeline -->
    <h2 class="section-title">Expected Telemetry Progression</h2>
    <div class="econ-layout">
      <div class="panel">
        <div class="small" style="margin-bottom:14px;color:#94a3b8;">Expected timelines based on system architecture. Actual progression depends on workload volume and complexity.</div>
        <div class="timeline-step">
          <div class="ts-phase">Day 1 (expected)</div>
          <div class="ts-desc">Observation layer active. Full audit trail. Every action semantically scored and recorded. Compliance evidence begins accumulating.</div>
        </div>
        <div class="timeline-step">
          <div class="ts-phase">~Month 3 (expected)</div>
          <div class="ts-desc">Entrainment model expected to calibrate from accumulated telemetry. CUSUM drift detection tuning. False positive rate refinement. The system begins learning what "normal" looks like for this workload.</div>
        </div>
        <div class="timeline-step">
          <div class="ts-phase">~Month 12 (expected)</div>
          <div class="ts-desc">Custom SetFit classifier trainable on domain data. Governance model expected to have calibrated from thousands of real decisions. If enforcement is enabled, it starts with accumulated workload context -- not from scratch.</div>
        </div>
      </div>
    </div>

    <!-- 6. Compliance (compact badges) -->
    <h2 class="section-title">Compliance Coverage -- 11 Frameworks</h2>
    <div class="panel" style="margin-bottom:32px;">
      <div class="compliance-row">
        <span class="badge">EU AI Act</span>
        <span class="badge">NIST AI RMF</span>
        <span class="badge">NIST 600-1</span>
        <span class="badge">IEEE 7000</span>
        <span class="badge">IEEE 7001</span>
        <span class="badge">IEEE 7002</span>
        <span class="badge">IEEE 7003</span>
        <span class="badge">SAAI</span>
        <span class="badge">Berkeley CLTC</span>
        <span class="badge">OWASP Agentic</span>
        <span class="badge">NAIC</span>
      </div>
      <div class="small">
        Observation mode generates the same compliance evidence as enforcement mode.
        Every scored action maps to specific framework requirements. When regulators
        ask for evidence of AI governance, the audit trail is already there -- months
        of it, accumulated silently, without ever interrupting the agent.
      </div>
    </div>

  </div>

  <script>
    let knownEvents = 0;
    let selectedIdx = -1;
    let allEvents = [];
    let prevCounts = { EXECUTE: 0, CLARIFY: 0, ESCALATE: 0, INERT: 0 };
    let autoStarted = false;

    function esc(text) {
      return (text || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    }

    function dimColor(val) {
      if (val >= 0.7) return 'var(--green)';
      if (val >= 0.4) return 'var(--yellow)';
      return 'var(--red)';
    }

    // Map internal verdicts to observation-mode language
    function obsLabel(decision) {
      if (decision === 'EXECUTE') return 'NOMINAL';
      if (decision === 'CLARIFY') return 'REVIEW';
      if (decision === 'ESCALATE') return 'FINDING';
      if (decision === 'INERT') return 'FINDING';
      return decision;
    }

    function obsNote(decision, boundary) {
      if (decision === 'EXECUTE') return '';
      if (decision === 'CLARIFY') return 'Flagged for post-hoc review -- agent was not interrupted';
      if (decision === 'ESCALATE' || decision === 'INERT') {
        return boundary ? 'Boundary proximity detected -- would be caught if enforcement enabled' : 'Anomalous action recorded -- agent was not interrupted';
      }
      return '';
    }

    function obsColor(decision) {
      if (decision === 'EXECUTE') return 'var(--green)';
      if (decision === 'CLARIFY') return 'var(--yellow)';
      return 'var(--red)';
    }

    function obsBgLabel(decision) {
      if (decision === 'EXECUTE') return { bg: '#0d4429', color: 'var(--green)', text: 'Observed -- nominal' };
      if (decision === 'CLARIFY') return { bg: '#3d2e00', color: 'var(--yellow)', text: 'Observed -- flagged for review' };
      return { bg: '#4c1d1d', color: 'var(--red)', text: 'Observed -- finding (would trigger enforcement)' };
    }

    function showDecision(event) {
      if (!event) return;
      const fid = event.fidelity != null ? event.fidelity.toFixed(4) : '--';
      const dims = [
        ['Purpose Fidelity', event.purpose_fidelity],
        ['Scope Fidelity', event.scope_fidelity],
        ['Boundary Violation', event.boundary_violation],
        ['Tool Fidelity', event.tool_fidelity],
        ['Chain Continuity', event.chain_continuity],
      ];

      let cascadeHtml = '';
      if (event.cascade_layers && event.cascade_layers.length) {
        cascadeHtml = '<div class="dp-section"><div class="dp-section-title">Cascade Layers Hit</div>' +
          event.cascade_layers.map(l => '<div class="small">' + esc(l) + '</div>').join('') +
          '</div>';
      }

      const label = obsBgLabel(event.decision);
      const note = obsNote(event.decision, event.boundary_triggered);
      const boundaryHtml = event.boundary_triggered
        ? '<div style="color:var(--red);font-size:12px;margin-top:8px;">Boundary proximity: this action came close to or crossed a defined boundary. In enforcement mode, this would require human authorization.</div>'
        : '';

      document.getElementById('dp-content').innerHTML = `
        <div class="dp-verdict" style="color:${obsColor(event.decision)}">${obsLabel(event.decision)}</div>
        <div class="dp-obs-label" style="background:${label.bg};color:${label.color}">${label.text}</div>
        <div class="dp-section">
          <div class="dp-section-title">Agent Action</div>
          <div class="dp-action">${esc(event.action_text)}</div>
          <div class="dp-tool">Tool: ${esc(event.tool_name)} | Risk tier: ${esc(event.risk_tier)} | Fidelity: ${fid}</div>
          ${boundaryHtml}
        </div>
        <div class="dp-section">
          <div class="dp-section-title">Semantic Analysis</div>
          <div class="dp-explanation">${esc(event.explanation)}</div>
        </div>
        ${cascadeHtml}
        <div class="dp-section">
          <div class="dp-section-title">Dimension Scores</div>
          <table class="dp-dims">
            ${dims.map(([name, val]) => {
              const v = val != null ? val.toFixed(4) : '--';
              const pct = val != null ? Math.round(val * 100) : 0;
              const col = val != null ? dimColor(val) : 'var(--muted)';
              return `<tr>
                <td class="dim-name">${name}</td>
                <td class="dim-val" style="color:${col}">${v}</td>
                <td style="width:40%"><div class="dp-bar"><div class="dp-bar-fill" style="width:${pct}%;background:${col}"></div></div></td>
              </tr>`;
            }).join('')}
          </table>
        </div>
        ${note ? '<div class="small" style="margin-top:12px;font-style:italic;">' + esc(note) + '</div>' : ''}`;
    }

    function pulseCard(id) {
      const el = document.getElementById(id);
      if (!el) return;
      el.classList.remove('pulse');
      void el.offsetWidth;
      el.classList.add('pulse');
    }

    async function runSim() {
      const res = await fetch('/api/run-simulation', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) alert(data.detail || 'Failed to start');
      document.getElementById('btn-run').disabled = true;
      document.getElementById('sim-status').textContent = 'Observing...';
    }

    async function resetSim() {
      const res = await fetch('/api/reset', { method: 'POST' });
      if (res.ok) {
        knownEvents = 0;
        selectedIdx = -1;
        allEvents = [];
        prevCounts = { EXECUTE: 0, CLARIFY: 0, ESCALATE: 0, INERT: 0 };
        document.getElementById('event-stream').innerHTML = '<div class="dp-empty" id="stream-empty">Waiting for simulation to start...</div>';
        document.getElementById('dp-content').innerHTML = '<div class="dp-empty">Click any event to see the full scoring cascade.</div>';
        ['cnt-total','cnt-nominal','cnt-review','cnt-finding'].forEach(id => document.getElementById(id).textContent = '0');
        document.getElementById('btn-run').disabled = false;
        document.getElementById('btn-run').textContent = 'Run Simulation';
        document.getElementById('sim-status').textContent = '';
        document.getElementById('sb-total').textContent = '0';
        document.getElementById('sb-findings').textContent = '0';
      }
    }

    async function refresh() {
      const res = await fetch('/api/status');
      const data = await res.json();
      const counts = data.counts;

      // Compute observation-mode counters
      const total = counts.EXECUTE + counts.CLARIFY + counts.ESCALATE + counts.INERT;
      const nominal = counts.EXECUTE;
      const review = counts.CLARIFY;
      const findings = counts.ESCALATE + counts.INERT;

      // Update counters with pulse
      const prev_total = prevCounts.EXECUTE + prevCounts.CLARIFY + prevCounts.ESCALATE + prevCounts.INERT;
      if (total !== prev_total) { document.getElementById('cnt-total').textContent = total; pulseCard('card-total'); }
      const prev_nom = prevCounts.EXECUTE;
      if (nominal !== prev_nom) { document.getElementById('cnt-nominal').textContent = nominal; pulseCard('card-nominal'); }
      const prev_rev = prevCounts.CLARIFY;
      if (review !== prev_rev) { document.getElementById('cnt-review').textContent = review; pulseCard('card-review'); }
      const prev_find = prevCounts.ESCALATE + prevCounts.INERT;
      if (findings !== prev_find) { document.getElementById('cnt-finding').textContent = findings; pulseCard('card-finding'); }
      prevCounts = { ...counts };

      // Sticky bar
      document.getElementById('sb-total').textContent = total;
      document.getElementById('sb-findings').textContent = findings;

      // Process status
      const running = data.processes.feed.running;
      const statusEl = document.getElementById('sim-status');
      const btnEl = document.getElementById('btn-run');
      if (running) {
        statusEl.textContent = 'Observing agent actions...';
        btnEl.disabled = true;
      } else if (total > 0) {
        statusEl.textContent = total + ' actions observed';
        btnEl.disabled = false;
        btnEl.textContent = 'Run Again';
      }

      // Stream events
      const events = data.recent_events;
      allEvents = events;

      if (events.length > 0) {
        const streamEl = document.getElementById('event-stream');
        const emptyEl = document.getElementById('stream-empty');
        if (emptyEl) emptyEl.remove();

        let html = '';
        events.forEach((ev, i) => {
          const isNew = i < (events.length - knownEvents);
          const isSelected = i === selectedIdx;
          const note = obsNote(ev.decision, ev.boundary_triggered);
          html += `<div class="ev-row v-${ev.decision} ${isNew ? 'new' : ''} ${isSelected ? 'selected' : ''}" onclick="selectEvent(${i})">
            <span class="ev-verdict">${obsLabel(ev.decision)}</span>
            <span class="ev-tool">${esc(ev.tool_name)}</span>
            <div class="ev-action">${esc(ev.action_text)}</div>
            ${note ? '<div class="ev-obs-note" style="color:' + obsColor(ev.decision) + '">' + esc(note) + '</div>' : ''}
          </div>`;
        });
        streamEl.innerHTML = html;
        knownEvents = events.length;

        // Auto-show first finding, or newest event
        if (selectedIdx === -1) {
          const findIdx = events.findIndex(e => e.decision === 'ESCALATE' || e.decision === 'INERT');
          showDecision(events[findIdx >= 0 ? findIdx : 0]);
        }
      }

      // CTA text
      const ctaEl = document.getElementById('cta-text');
      if (total > 0 && findings > 0) {
        ctaEl.innerHTML = total + ' actions observed silently. <span style="color:var(--red)">' + findings + ' finding' + (findings > 1 ? 's' : '') + '</span> recorded -- the agent was never interrupted. Click any event to see the scoring detail.';
        ctaEl.style.color = 'var(--cyan)';
      } else if (total > 0) {
        ctaEl.textContent = total + ' actions observed. All within expected behavior. Agent was never interrupted.';
        ctaEl.style.color = 'var(--cyan)';
      } else if (running) {
        ctaEl.textContent = 'Deploying observation layer...';
      }
    }

    function selectEvent(idx) {
      selectedIdx = idx;
      showDecision(allEvents[idx]);
      document.querySelectorAll('.ev-row').forEach((el, i) => {
        el.classList.toggle('selected', i === idx);
      });
    }

    // Sticky bar on scroll
    window.addEventListener('scroll', () => {
      const bar = document.getElementById('sticky-bar');
      const counters = document.querySelector('.counters');
      if (counters) {
        const rect = counters.getBoundingClientRect();
        bar.classList.toggle('visible', rect.bottom < 0 && allEvents.length > 0);
      }
    });

    // Auto-start
    setTimeout(async () => {
      if (!autoStarted) {
        autoStarted = true;
        try {
          const check = await fetch('/api/status');
          const d = await check.json();
          const total = d.counts.EXECUTE + d.counts.CLARIFY + d.counts.ESCALATE + d.counts.INERT;
          if (total === 0 && !d.processes.feed.running) {
            await runSim();
          }
        } catch(e) {}
      }
    }, 1500);

    refresh();
    setInterval(refresh, 1500);
  </script>
</body>
</html>
"""


app = FastAPI(title="Vultr Local Review")


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML


@app.get("/api/status")
async def status() -> JSONResponse:
    return JSONResponse(_status_payload())


@app.post("/api/run-simulation")
async def run_simulation() -> JSONResponse:
    extra_env = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "DEMO_FAST": "1",
    }
    result = _start_process(
        "feed",
        [sys.executable, str(PROJECT_ROOT / "demos" / "vultr_demo_feed.py")],
        extra_env=extra_env,
    )
    return JSONResponse({"started": True, **result})


@app.post("/api/reset")
async def reset_runtime() -> JSONResponse:
    with _lock:
        _cleanup_finished("feed")
        if _proc_state["feed"]["process"] is not None:
            raise HTTPException(status_code=409, detail="feed still running")
        _proc_state["feed"]["returncode"] = None
    if RUNTIME_ROOT.exists():
        for path in sorted(RUNTIME_ROOT.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
    _ensure_runtime_dirs()
    return JSONResponse({"reset": True})


@app.get("/artifacts/{name}")
async def artifact(name: str) -> FileResponse:
    artifact_dir = RUNTIME_ROOT / "artifacts"
    path = artifact_dir / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "demos.vultr_local_review_app:app",
        host=os.environ.get("TELOS_REVIEW_HOST", "127.0.0.1"),
        port=int(os.environ.get("TELOS_REVIEW_PORT", "8615")),
        reload=False,
    )
