#!/usr/bin/env python3
"""
TELOS Forensic Trace Demo — Standalone
Identical output to the forensic sections in nearmap_live_demo_v2/v3.
Runs on an existing trace file for separate video recording.

Usage:
  python3 demos/forensics_demo.py                                    # latest trace
  python3 demos/forensics_demo.py telos_governance_traces/session_telos-XXXX.jsonl
  DEMO_FAST=1 python3 demos/forensics_demo.py                       # skip pauses
"""

import hashlib
import json
import os
import sys
import time

_DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_DEMO_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _DEMO_DIR not in sys.path:
    sys.path.insert(0, _DEMO_DIR)

from _display_toolkit import (
    NO_COLOR, DEMO_FAST,
    _FG, _BG, _BOLD, _DIM, _RESET,
    _c, _bg, _pause, W, _kv,
    _header, _narrator,
)
from telos_core.trace_verifier import verify_trace_integrity
from telos_core.governance_trace import GovernanceTraceCollector
from telos_core.evidence_schema import PrivacyMode

try:
    from telos_observatory.services.report_generator import GovernanceReportGenerator
except ImportError:
    GovernanceReportGenerator = None

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as _serialization
    _HAS_ED25519 = True
except ImportError:
    _HAS_ED25519 = False


def _find_latest_trace():
    """Find the most recent trace file."""
    trace_dir = os.path.join(_PROJECT_ROOT, "telos_governance_traces")
    if not os.path.isdir(trace_dir):
        return None
    traces = sorted(
        [os.path.join(trace_dir, f) for f in os.listdir(trace_dir) if f.endswith(".jsonl")],
        key=os.path.getmtime,
        reverse=True,
    )
    return traces[0] if traces else None


def run_forensics(trace_file):
    start_wall = time.time()
    import hashlib as _hashlib

    # Load all events from trace
    _chain_events = []
    with open(trace_file, "r") as _cf:
        for _cl in _cf:
            _cl = _cl.strip()
            if _cl:
                _chain_events.append(json.loads(_cl))

    # Extract session_id from first event
    session_id = _chain_events[0].get("session_id", "unknown") if _chain_events else "unknown"

    # ══════════════════════════════════════════════════════════════════
    # Header
    # ══════════════════════════════════════════════════════════════════

    print()
    _header(
        "TELOS Forensic Trace Analysis\n"
        "\n"
        "Session:  {}\n"
        "Trace:    {}\n"
        "Independent verification of governance audit trail".format(
            session_id, os.path.basename(trace_file))
    )
    _pause(2.0)

    # ══════════════════════════════════════════════════════════════════
    # Section 1: Governance Session Proof
    # ══════════════════════════════════════════════════════════════════

    # Reconstruct receipt-like data from trace events for session proof
    # Build per-turn verdicts from trace
    turn_data = {}  # turn_number -> {input, fidelity, intervened, ...}
    for e in _chain_events:
        et = e.get("event_type", "")
        tn = e.get("turn_number", 0)
        if tn not in turn_data:
            turn_data[tn] = {"input": "", "fidelity": 0.0, "intervened": False, "intervention_level": ""}
        if et in ("turn_start", "turn_started"):
            turn_data[tn]["input"] = e.get("user_input", "")
        elif et == "fidelity_calculated":
            turn_data[tn]["fidelity"] = e.get("normalized_fidelity", 0.0)
        elif et == "intervention_triggered":
            turn_data[tn]["intervened"] = True
            turn_data[tn]["intervention_level"] = e.get("intervention_level", "")
            turn_data[tn]["trigger_reason"] = e.get("trigger_reason", "")

    # Compute a session digest from event hashes (analogous to receipt chain)
    event_hashes = [e.get("event_hash", "") for e in _chain_events if e.get("event_hash")]
    session_digest_input = "|".join(event_hashes)
    session_digest = hashlib.sha256(session_digest_input.encode("utf-8")).hexdigest()

    # Ed25519 session signature (ephemeral — proves the mechanism works)
    ed_session_sig = None
    ed_pub_hex = None
    if _HAS_ED25519:
        ed_private = Ed25519PrivateKey.generate()
        ed_public = ed_private.public_key()
        ed_pub_bytes = ed_public.public_bytes(
            encoding=_serialization.Encoding.Raw,
            format=_serialization.PublicFormat.Raw,
        )
        ed_pub_hex = ed_pub_bytes.hex()
        ed_session_sig = ed_private.sign(session_digest.encode("utf-8")).hex()
        ed_public.verify(
            bytes.fromhex(ed_session_sig),
            session_digest.encode("utf-8"),
        )

    _pause(1.0)
    _header("Governance Session Proof")
    print()
    _kv("Session", session_id)
    _kv("Events", "{} (SHA-256 hash chain)".format(len(_chain_events)))
    _kv("Audit trail", "SHA-256 hash chain (tamper-evident)")
    _kv("Trace file", trace_file)
    _pause(1.5)

    # Per-turn verdict table (analogous to receipt signatures)
    sorted_turns = sorted(t for t in turn_data if t > 0)
    if sorted_turns:
        print()
        print(_c("  Per-turn governance verdicts:", "white", bold=True))
        print()
        for tn in sorted_turns:
            td = turn_data[tn]
            if td["intervened"]:
                dc = "red"
                verdict = "ESCALATE"
            elif td["fidelity"] >= 0.70:
                dc = "green"
                verdict = "EXECUTE"
            elif td["fidelity"] >= 0.50:
                dc = "yellow"
                verdict = "CLARIFY"
            else:
                dc = "red"
                verdict = "ESCALATE"
            # Use event hash as the "signature" for this turn
            turn_hashes = [e.get("event_hash", "") for e in _chain_events
                           if e.get("turn_number") == tn and e.get("event_hash")]
            sig = turn_hashes[-1][:16] + "..." + turn_hashes[-1][-8:] if turn_hashes else "n/a"
            print("    #{:<3d} {}  {}".format(
                tn, _c(verdict, dc), _c(sig, "cyan")))
        _pause(1.5)

    # Session digest
    print()
    print(_c("  Session digest (SHA-256 of event chain):", "white", bold=True))
    print("    {}".format(_c(session_digest, "cyan")))
    _pause(1.0)

    # Ed25519 session signature
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

    # Blocked requests audit trail
    blocked_turns = [tn for tn in sorted_turns if turn_data[tn]["intervened"]]
    if blocked_turns:
        print()
        print(_c("  Blocked requests (audit trail):", "dim"))
        for tn in blocked_turns:
            td = turn_data[tn]
            note = td.get("trigger_reason", "outside agent scope")
            short_req = td["input"][:70] + "..." if len(td["input"]) > 70 else td["input"]
            print("    #{:<3d} {}  \"{}\" \u2014 {}".format(
                tn, _c("ESCALATE", "red"), short_req, _c(note, "dim")))
        _pause(2.0)

    # ══════════════════════════════════════════════════════════════════
    # Section 2: Forensic Trace Verification (exact copy from v2)
    # ══════════════════════════════════════════════════════════════════

    _pause(1.0)
    _header("Forensic Trace Verification")
    _pause(0.5)

    print()
    print(_c("  Verifying cryptographic hash chain ...", "dim"))
    _pause(1.0)

    report = verify_trace_integrity(trace_file)

    # ── Chain walk visualization with semantic narration ──
    _GENESIS = "0" * 64

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

        print("  {} {:>3d}  {:<28s}  {}  {}".format(
            _mark, _ci + 1, _etype, _c(_short, "cyan"), _arrow))

        # Semantic narration
        _narr = _chain_narration(_ce)
        if _narr:
            print("       {}".format(_c(_narr, "dim")))

        _expected = _ehash
        _pause(0.12)

    print()
    print("  {}  {} = hash verified   {}  {} = chain link".format(
        _c("\u2713", "green"), _c("abc123...", "cyan"),
        _c("\u2190", "dim"), _c("prev_hash", "dim")))
    _pause(1.5)

    # ── Verification result ──
    if report.is_valid:
        print()
        print("  {}".format(_bg(" CHAIN INTEGRITY VERIFIED ", "green", "black")))
    else:
        print()
        print("  {}".format(_bg(" CHAIN INTEGRITY FAILED ", "red", "white")))
        if report.broken_at_index is not None:
            print("  Broken at event #{} ({})".format(
                report.broken_at_index, report.broken_at_event_type))
    _pause(1.5)

    print()
    _kv("Trace file", trace_file)
    _kv("File size", "{:,} bytes".format(report.file_size_bytes))
    _kv("Total events", str(report.total_events))
    _kv("Hash algorithm", "SHA-256")
    _kv("Chain status", _c("VALID", "green") if report.is_valid else _c("BROKEN", "red"))
    _kv("Verified in", "{:.1f}ms".format(report.verification_duration_ms))
    _pause(1.0)

    # SAAI compliance
    print()
    print(_c("  SAAI Framework Compliance:", "white", bold=True))
    _kv("Baseline established", "Yes" if report.baseline_established else "No (< {} turns)".format(
        __import__("telos_core.constants", fromlist=["BASELINE_TURN_COUNT"]).BASELINE_TURN_COUNT))
    _kv("Mandatory reviews", str(report.mandatory_reviews_triggered))
    _kv("Final drift level", report.final_drift_level or "normal")
    # Extract privacy mode from session_start event
    privacy_mode = "full"
    for e in _chain_events:
        if e.get("event_type") == "session_start":
            privacy_mode = e.get("privacy_mode", "full")
            break
    _kv("Privacy mode", privacy_mode)
    _pause(1.0)

    # Event breakdown
    print()
    print(_c("  Event breakdown:", "dim"))
    for evt_type, count in sorted(report.saai_events.items()):
        print("    {:<30s} {}".format(evt_type, count))
    _pause(1.5)

    print()
    print("  {}".format(_c(
        "To re-verify this trace at any time:",
        "dim")))
    print("  {}".format(_c(
        "  telos verify {} --chain".format(trace_file),
        "cyan")))
    _pause(1.0)

    # ══════════════════════════════════════════════════════════════════
    # Section 3: Forensic Trace Interpreter (exact copy from v2)
    # ══════════════════════════════════════════════════════════════════

    _pause(0.5)
    _header("Forensic Trace Interpreter")
    _pause(0.5)

    print()
    print(_c("  Reading forensic trace ...", "dim"))
    _pause(0.8)

    # Extract per-turn fidelity trajectory
    fid_trajectory = []
    for e in _chain_events:
        if e.get("event_type") == "fidelity_calculated":
            fid_trajectory.append({
                "turn": e.get("turn_number", 0),
                "fidelity": e.get("normalized_fidelity", 0.0),
                "raw": e.get("raw_similarity", 0.0),
                "blocked": e.get("layer1_hard_block", False) or e.get("layer2_outside_basin", False),
            })

    # Extract user inputs per turn
    trace_inputs = {}
    for e in _chain_events:
        if e.get("event_type") in ("turn_start", "turn_started"):
            trace_inputs[e.get("turn_number", 0)] = e.get("user_input", "")

    # Extract interventions
    trace_interventions = []
    for e in _chain_events:
        if e.get("event_type") == "intervention_triggered":
            trace_interventions.append({
                "turn": e.get("turn_number", 0),
                "level": e.get("intervention_level", ""),
                "trigger": e.get("trigger_reason", ""),
                "fidelity": e.get("fidelity_at_trigger", 0.0),
                "action": e.get("action_taken", ""),
            })

    # ── Fidelity sparkline ──
    fidelities = [t["fidelity"] for t in fid_trajectory]
    if fidelities:
        # Build sparkline with per-value coloring
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

    # ── Per-turn scoring table ──
    if fid_trajectory:
        intervention_turn_set = {i["turn"] for i in trace_interventions}

        print()
        print(_c("  Per-turn scoring:", "white", bold=True))
        print()
        print("  {:<6s} {:<10s} {:<7s} {:<16s} {:<9s} {}".format(
            "Turn", "Fidelity", "Zone", "", "Status", "Request"))
        print("  {}".format(_c("\u2500" * (W - 4), "dim")))

        for t in fid_trajectory:
            turn = t["turn"]
            fid = t["fidelity"]

            # Zone label (matches TELOS display zones from constants.py)
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

            # Bar
            bar_w = 14
            filled = max(0, int(fid * bar_w))
            empty = bar_w - filled
            if NO_COLOR:
                bar_str = "\u2588" * filled + "\u2591" * empty
            else:
                fg_code = _FG.get(zone_fg, "")
                bar_str = "{}{}\033[0m\033[2m{}\033[0m".format(
                    fg_code, "\u2588" * filled, "\u2591" * empty)

            # Status
            if turn in intervention_turn_set:
                status = _c("BLOCKED", "red")
            else:
                status = _c("ALLOWED", "green")

            # Truncated request
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

    # ── Intervention log ──
    if trace_interventions:
        _pause(0.5)
        print()
        print(_c("  Intervention log ({})".format(len(trace_interventions)), "white", bold=True))
        print()
        print("  {:<6s} {:<14s} {:<22s} {:<10s} {}".format(
            "Turn", "Level", "Trigger", "Fidelity", "Action"))
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
    print("  {}".format(_c(
        "To run forensics interactively:",
        "dim")))
    print("  {}".format(_c(
        "  telos interpret {} --events".format(trace_file),
        "cyan")))
    _pause(1.0)

    # ══════════════════════════════════════════════════════════════════
    # Section 4: HTML Governance Report
    # ══════════════════════════════════════════════════════════════════

    if GovernanceReportGenerator is not None:
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
            # Reconstruct session data from trace events
            tc = GovernanceTraceCollector.__new__(GovernanceTraceCollector)
            tc.trace_file = __import__("pathlib").Path(trace_file)
            tc._events = _chain_events
            tc.session_id = session_id
            session_data = tc.export_to_dict()
            html_path = generator.generate_report(session_data)
            print()
            print("  {}".format(_bg(" HTML REPORT GENERATED ", "green", "black")))
            print()
            _kv("Report", str(html_path))
            _kv("Format", "Self-contained HTML (Plotly charts, dark theme)")
            _kv("Viewer", "Any browser \u2014 no server required")
            print()
            print("  {}".format(_c(
                "To open the report:", "dim")))
            print("  {}".format(_c(
                "  open {}".format(html_path), "cyan")))
        except Exception as exc:
            print()
            print("  {}".format(_c(
                "[HTML report skipped: {}]".format(exc), "yellow")))
        _pause(1.0)

    # ── Done ──────────────────────────────────────────────────────────
    print()
    elapsed = time.time() - start_wall
    print(_c("  Forensic analysis completed in {:.1f}s".format(elapsed), "dim"))
    print(_c("\u2550" * W, "cyan", bold=True))
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        trace_path = sys.argv[1]
        if not os.path.isabs(trace_path):
            trace_path = os.path.join(_PROJECT_ROOT, trace_path)
    else:
        trace_path = _find_latest_trace()

    if not trace_path or not os.path.isfile(trace_path):
        print("Error: No trace file found. Provide a path or run a demo first.")
        sys.exit(1)

    run_forensics(trace_path)
