#!/usr/bin/env python3
"""
TELOSCOPE Demo Analysis
========================

Runs the full TELOSCOPE analysis pipeline over governance demo audit data
and produces formatted console output and optional HTML reports.

Usage:
    python3 demo_teloscope_analysis.py /path/to/demo_audit.jsonl
    python3 demo_teloscope_analysis.py --generate
    python3 demo_teloscope_analysis.py /path/to/demo_audit.jsonl --html report.html
"""
import argparse
import math
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Import strategy: the telemetry directory contains an ``inspect.py`` that
# shadows the stdlib ``inspect`` module. We must ensure the stdlib inspect
# is loaded first before the telemetry directory appears on sys.path.
# Same pattern as test_telemetry_wiring.py.
# ---------------------------------------------------------------------------

_TELEMETRY_DIR = os.path.dirname(os.path.abspath(__file__))

if "inspect" not in sys.modules:
    _saved_path = sys.path[:]
    sys.path = [
        p for p in sys.path
        if os.path.abspath(p) != _TELEMETRY_DIR and p != ""
    ]
    import inspect  # noqa: E402 — stdlib only, no shadow
    assert hasattr(inspect, "signature"), "Got local inspect.py instead of stdlib!"
    sys.path = _saved_path

if _TELEMETRY_DIR not in sys.path:
    sys.path.insert(0, _TELEMETRY_DIR)

# -- TELOSCOPE imports (telos_governance.* first, fallback to direct) --------

try:
    from telos_governance.corpus import load_corpus, AuditCorpus
except (ImportError, AttributeError):
    from corpus import load_corpus, AuditCorpus

try:
    from telos_governance.stats import corpus_stats, StatsResult, DIMENSIONS
except (ImportError, AttributeError):
    from stats import corpus_stats, StatsResult, DIMENSIONS

try:
    from telos_governance.validate import validate, ValidationResult
except (ImportError, AttributeError):
    from validate import validate, ValidationResult

try:
    from telos_governance.compare import compare, CompareResult
except (ImportError, AttributeError):
    from compare import compare, CompareResult

try:
    from telos_governance.report import executive_report, ExecReport
except (ImportError, AttributeError):
    from report import executive_report, ExecReport

try:
    from telos_governance.demo_audit_bridge import generate_sample_demo_corpus
except (ImportError, AttributeError):
    from demo_audit_bridge import generate_sample_demo_corpus


# ---------------------------------------------------------------------------
# ANSI color codes
# ---------------------------------------------------------------------------

class C:
    """ANSI color codes for terminal output."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    GREEN   = "\033[38;2;34;197;94m"     # #22c55e
    YELLOW  = "\033[38;2;234;179;8m"     # #eab308
    RED     = "\033[38;2;239;68;68m"     # #ef4444
    CYAN    = "\033[38;2;56;189;248m"    # #38bdf8
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"
    BLUE    = "\033[38;2;96;165;250m"    # #60a5fa
    MAGENTA = "\033[38;2;192;132;252m"   # #c084fc


def _color_verdict(verdict: str) -> str:
    """Color-code a verdict string."""
    colors = {
        "EXECUTE": C.GREEN, "CLARIFY": C.YELLOW,
        "INERT": C.RED, "ESCALATE": C.RED,
    }
    return f"{colors.get(verdict, C.WHITE)}{verdict}{C.RESET}"


def _color_traffic(light: str) -> str:
    """Color-code a traffic light status."""
    colors = {"GREEN": C.GREEN, "YELLOW": C.YELLOW, "RED": C.RED,
              "PASS": C.GREEN, "PARTIAL": C.YELLOW, "FAIL": C.RED,
              "NOT_PRESENT": C.GRAY, "NOT_AVAILABLE": C.GRAY,
              "NO_SIGNATURES": C.GRAY}
    color = colors.get(light.upper().replace(" ", "_"), C.WHITE)
    return f"{color}{C.BOLD}{light}{C.RESET}"


def _traffic_symbol(status: str) -> str:
    """Return a colored circle for traffic light status."""
    s = status.upper().replace(" ", "_")
    if s in ("PASS", "GREEN"):
        return f"{C.GREEN}●{C.RESET}"
    elif s in ("PARTIAL", "YELLOW"):
        return f"{C.YELLOW}●{C.RESET}"
    elif s in ("FAIL", "RED"):
        return f"{C.RED}●{C.RESET}"
    return f"{C.GRAY}○{C.RESET}"


# ---------------------------------------------------------------------------
# Box-drawing table helpers
# ---------------------------------------------------------------------------

def _box_top(widths: List[int]) -> str:
    return "┌" + "┬".join("─" * w for w in widths) + "┐"

def _box_mid(widths: List[int]) -> str:
    return "├" + "┼".join("─" * w for w in widths) + "┤"

def _box_bot(widths: List[int]) -> str:
    return "└" + "┴".join("─" * w for w in widths) + "┘"

def _box_row(cells: List[str], widths: List[int], aligns: Optional[List[str]] = None) -> str:
    """Format a row with padding. aligns: 'l', 'r', 'c'."""
    if aligns is None:
        aligns = ["l"] * len(cells)
    parts = []
    for cell, w, a in zip(cells, widths, aligns):
        # Strip ANSI for width calculation
        visible = _strip_ansi(cell)
        pad = w - len(visible)
        if pad < 0:
            pad = 0
        if a == "r":
            parts.append(" " * pad + cell)
        elif a == "c":
            lp = pad // 2
            rp = pad - lp
            parts.append(" " * lp + cell + " " * rp)
        else:
            parts.append(cell + " " * pad)
    return "│" + "│".join(parts) + "│"


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape codes for width calculation."""
    import re
    return re.sub(r"\033\[[0-9;]*m", "", s)


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def _stdev(values: List[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _median(values: List[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    if n % 2 == 0:
        return (s[n // 2 - 1] + s[n // 2]) / 2
    return s[n // 2]


def _dim_values(corpus: AuditCorpus, dim: str) -> List[float]:
    return [getattr(e, dim) for e in corpus]


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_header():
    w = 72
    print()
    print(f"{C.CYAN}{C.BOLD}{'─' * w}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}  TELOSCOPE Independent Governance Audit{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}  TELOS AI Labs{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'─' * w}{C.RESET}")
    print()


def print_corpus_summary(corpus: AuditCorpus):
    n = len(corpus)
    sessions = corpus.n_sessions
    timestamps = [e.timestamp for e in corpus if e.timestamp]
    date_min = min(timestamps)[:19] if timestamps else "N/A"
    date_max = max(timestamps)[:19] if timestamps else "N/A"

    print(f"  {C.BOLD}Corpus{C.RESET}")
    print(f"  {'Events:':<16} {C.WHITE}{n}{C.RESET}")
    print(f"  {'Sessions:':<16} {C.WHITE}{sessions}{C.RESET}")
    print(f"  {'Date range:':<16} {C.DIM}{date_min} to {date_max}{C.RESET}")
    print(f"  {'Source:':<16} {C.DIM}{corpus.source_path}{C.RESET}")
    print()


def print_verdict_table(corpus: AuditCorpus):
    n = len(corpus)
    verdict_order = ["EXECUTE", "CLARIFY", "INERT", "ESCALATE"]
    dist: Dict[str, int] = {}
    for e in corpus:
        dist[e.verdict] = dist.get(e.verdict, 0) + 1

    print(f"  {C.BOLD}Verdict Distribution{C.RESET}")
    widths = [14, 8, 10, 24]
    aligns = ["l", "r", "r", "l"]
    print(f"  {_box_top(widths)}")
    print(f"  {_box_row([' Verdict', ' Count', ' Rate', ' Bar'], widths, aligns)}")
    print(f"  {_box_mid(widths)}")

    for v in verdict_order:
        count = dist.get(v, 0)
        if count == 0 and v not in dist:
            continue
        rate = count / n if n > 0 else 0.0
        bar_len = int(rate * 20)
        bar_char = "█" * bar_len + "░" * (20 - bar_len)
        label = _color_verdict(v)
        pct_str = f"{rate:.1%} ({count}/{n})"
        print(f"  {_box_row([' ' + label, f'{count} ', f' {pct_str}', ' ' + bar_char], widths, aligns)}")

    print(f"  {_box_bot(widths)}")
    print()


def print_dimension_table(corpus: AuditCorpus):
    dims = ["composite", "purpose", "scope", "boundary", "tool", "chain"]
    print(f"  {C.BOLD}Fidelity Dimensional Analysis{C.RESET}")

    widths = [14, 8, 8, 8, 8, 8]
    aligns = ["l", "r", "r", "r", "r", "r"]
    print(f"  {_box_top(widths)}")
    print(f"  {_box_row([' Dimension', ' Mean', ' Median', ' Stdev', ' Min', ' Max'], widths, aligns)}")
    print(f"  {_box_mid(widths)}")

    for dim in dims:
        vals = _dim_values(corpus, dim)
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        med = _median(vals)
        sd = _stdev(vals, mean)
        mn = min(vals)
        mx = max(vals)

        # Color: green if mean > 0.7, yellow 0.4-0.7, red < 0.4
        if mean >= 0.7:
            color = C.GREEN
        elif mean >= 0.4:
            color = C.YELLOW
        else:
            color = C.RED

        name = f" {dim}"
        print(f"  {_box_row([name, f'{color}{mean:.3f}{C.RESET} ', f'{med:.3f} ', f'{sd:.3f} ', f'{mn:.3f} ', f'{mx:.3f} '], widths, aligns)}")

    print(f"  {_box_bot(widths)}")
    print()


def print_comparison(corpus: AuditCorpus, cmp: CompareResult):
    print(f"  {C.BOLD}Allowed vs Blocked Comparison{C.RESET}")
    print(f"  {C.DIM}Group A (Allowed):  {cmp.n_a} events   "
          f"Group B (Blocked):  {cmp.n_b} events{C.RESET}")
    print()

    # Dimension comparison
    widths = [14, 10, 10, 10, 10, 10]
    aligns = ["l", "r", "r", "r", "r", "r"]
    print(f"  {_box_top(widths)}")
    print(f"  {_box_row([' Dimension', ' Allowed', ' Blocked', ' Delta', ' Cohen d', ' Effect'], widths, aligns)}")
    print(f"  {_box_mid(widths)}")

    for dc in cmp.dimension_comparison:
        delta_str = f"{dc.delta:+.3f}"
        d_str = f"{dc.cohens_d:+.2f}"
        # Effect label
        ad = abs(dc.cohens_d)
        if ad < 0.2:
            eff = f"{C.GRAY}neg{C.RESET}"
        elif ad < 0.5:
            eff = f"{C.YELLOW}small{C.RESET}"
        elif ad < 0.8:
            eff = f"{C.YELLOW}med{C.RESET}"
        else:
            eff = f"{C.GREEN}large{C.RESET}" if dc.cohens_d > 0 else f"{C.RED}large{C.RESET}"

        print(f"  {_box_row([f' {dc.dimension}', f'{dc.mean_a:.3f} ', f'{dc.mean_b:.3f} ', f'{delta_str} ', f'{d_str} ', f' {eff}'], widths, aligns)}")

    print(f"  {_box_bot(widths)}")
    print()


def print_validation(val: ValidationResult):
    print(f"  {C.BOLD}Integrity Verification{C.RESET}")
    checks = [
        ("Hash Chain", val.chain.status),
        ("Signatures", val.signatures.status),
        ("Reproducibility", val.reproducibility.status),
    ]
    for name, status in checks:
        sym = _traffic_symbol(status)
        label = status.upper().replace("_", " ")
        color_label = _color_traffic(label)
        print(f"    {sym}  {name:<20} {color_label}")

    overall = val.overall_status.upper()
    sym = _traffic_symbol(overall)
    print()
    print(f"    {sym}  {C.BOLD}Overall: {_color_traffic(overall)}{C.RESET}")
    print()


def print_executive(exec_rpt: ExecReport):
    print(f"  {C.BOLD}Executive Summary{C.RESET}")
    tl = exec_rpt.traffic_light
    sym = _traffic_symbol(tl)
    print(f"    Governance Health: {sym} {_color_traffic(tl)}")
    print(f"    EXECUTE rate:     {exec_rpt.execute_rate:.1%} "
          f"({exec_rpt.verdict_distribution.get('EXECUTE', 0)}/{exec_rpt.n_events})")
    if exec_rpt.integrity_status:
        isym = _traffic_symbol(exec_rpt.integrity_status)
        print(f"    Integrity:        {isym} {_color_traffic(exec_rpt.integrity_status)}")
    print()
    if exec_rpt.top_findings:
        print(f"    {C.BOLD}Top Findings:{C.RESET}")
        for i, finding in enumerate(exec_rpt.top_findings[:5], 1):
            print(f"      {i}. {finding}")
        print()


def print_timing(timings: Dict[str, float]):
    print(f"  {C.BOLD}Pipeline Timing{C.RESET}")
    total = sum(timings.values())
    widths = [18, 10, 10]
    aligns = ["l", "r", "r"]
    print(f"  {_box_top(widths)}")
    print(f"  {_box_row([' Stage', ' Time (ms)', ' % Total'], widths, aligns)}")
    print(f"  {_box_mid(widths)}")

    for stage, ms in timings.items():
        pct = (ms / total * 100) if total > 0 else 0.0
        print(f"  {_box_row([f' {stage}', f'{ms:.1f} ', f'{pct:.0f}% '], widths, aligns)}")

    print(f"  {_box_mid(widths)}")
    print(f"  {_box_row([f' {C.BOLD}Total{C.RESET}', f'{C.BOLD}{total:.1f}{C.RESET} ', '100% '], widths, aligns)}")
    print(f"  {_box_bot(widths)}")
    print()


def print_caveats(n: int):
    if n < 30:
        print(f"  {C.YELLOW}{C.BOLD}Small-Sample Caveats (n={n}){C.RESET}")
        print(f"  {C.YELLOW}  - Effect sizes and p-values are unreliable with n < 30{C.RESET}")
        print(f"  {C.YELLOW}  - Percentile estimates have wide confidence intervals{C.RESET}")
        print(f"  {C.YELLOW}  - Chi-squared tests may not satisfy minimum cell count assumptions{C.RESET}")
        print(f"  {C.YELLOW}  - Results should be interpreted as directional, not definitive{C.RESET}")
        print()


def print_footer():
    w = 72
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"  {C.DIM}Generated {now}{C.RESET}")
    print(f"  {C.DIM}TELOSCOPE v1.0 -- TELOS AI Labs{C.RESET}")
    print(f"{C.CYAN}{'─' * w}{C.RESET}")
    print()


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def generate_html(
    corpus: AuditCorpus,
    stats_full: StatsResult,
    stats_verdict: StatsResult,
    val: ValidationResult,
    cmp: CompareResult,
    exec_rpt: ExecReport,
    timings: Dict[str, float],
) -> str:
    """Generate a self-contained dark-theme HTML report."""
    n = len(corpus)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    timestamps = [e.timestamp for e in corpus if e.timestamp]
    date_min = min(timestamps)[:19] if timestamps else "N/A"
    date_max = max(timestamps)[:19] if timestamps else "N/A"

    # Traffic light color mapping
    def tl_color(status: str) -> str:
        s = status.upper().replace("_", " ").replace(" ", "_")
        if s in ("PASS", "GREEN"):
            return "#22c55e"
        elif s in ("PARTIAL", "YELLOW"):
            return "#eab308"
        elif s in ("FAIL", "RED"):
            return "#ef4444"
        return "#6b7280"

    # Verdict distribution
    dist: Dict[str, int] = {}
    for e in corpus:
        dist[e.verdict] = dist.get(e.verdict, 0) + 1
    verdict_order = ["EXECUTE", "CLARIFY", "INERT", "ESCALATE"]
    verdict_colors = {
        "EXECUTE": "#22c55e", "CLARIFY": "#eab308",
        "INERT": "#ef4444", "ESCALATE": "#ef4444",
    }

    verdict_rows = ""
    for v in verdict_order:
        count = dist.get(v, 0)
        if count == 0 and v not in dist:
            continue
        rate = count / n if n > 0 else 0.0
        bar_pct = rate * 100
        vc = verdict_colors.get(v, "#6b7280")
        verdict_rows += f"""
        <tr>
            <td style="color:{vc};font-weight:bold">{v}</td>
            <td class="num">{count}</td>
            <td class="num">{rate:.1%} ({count}/{n})</td>
            <td>
                <div style="background:#1e293b;border-radius:4px;height:18px;width:200px;position:relative">
                    <div style="background:{vc};border-radius:4px;height:18px;width:{bar_pct:.0f}%"></div>
                </div>
            </td>
        </tr>"""

    # Dimension analysis
    dims = ["composite", "purpose", "scope", "boundary", "tool", "chain"]
    dim_rows = ""
    for dim in dims:
        vals = _dim_values(corpus, dim)
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        med = _median(vals)
        sd = _stdev(vals, mean)
        mn = min(vals)
        mx = max(vals)
        if mean >= 0.7:
            dc = "#22c55e"
        elif mean >= 0.4:
            dc = "#eab308"
        else:
            dc = "#ef4444"
        dim_rows += f"""
        <tr>
            <td>{dim}</td>
            <td class="num" style="color:{dc}">{mean:.3f}</td>
            <td class="num">{med:.3f}</td>
            <td class="num">{sd:.3f}</td>
            <td class="num">{mn:.3f}</td>
            <td class="num">{mx:.3f}</td>
        </tr>"""

    # Validation
    checks = [
        ("Hash Chain", val.chain.status),
        ("Signatures", val.signatures.status),
        ("Reproducibility", val.reproducibility.status),
    ]
    val_rows = ""
    for name, status in checks:
        label = status.upper().replace("_", " ")
        sc = tl_color(status)
        val_rows += f"""
        <tr>
            <td>{name}</td>
            <td style="color:{sc};font-weight:bold">&#9679; {label}</td>
        </tr>"""
    overall_label = val.overall_status.upper()
    overall_color = tl_color(val.overall_status)
    val_rows += f"""
        <tr style="border-top:2px solid #334155">
            <td style="font-weight:bold">Overall</td>
            <td style="color:{overall_color};font-weight:bold">&#9679; {overall_label}</td>
        </tr>"""

    # Comparison
    cmp_rows = ""
    for dc_item in cmp.dimension_comparison:
        delta_str = f"{dc_item.delta:+.3f}"
        d_str = f"{dc_item.cohens_d:+.2f}"
        ad = abs(dc_item.cohens_d)
        if ad < 0.2:
            eff_label, eff_color = "negligible", "#6b7280"
        elif ad < 0.5:
            eff_label, eff_color = "small", "#eab308"
        elif ad < 0.8:
            eff_label, eff_color = "medium", "#eab308"
        else:
            eff_label = "large"
            eff_color = "#22c55e" if dc_item.cohens_d > 0 else "#ef4444"
        cmp_rows += f"""
        <tr>
            <td>{dc_item.dimension}</td>
            <td class="num">{dc_item.mean_a:.3f}</td>
            <td class="num">{dc_item.mean_b:.3f}</td>
            <td class="num">{delta_str}</td>
            <td class="num">{d_str}</td>
            <td style="color:{eff_color}">{eff_label}</td>
        </tr>"""

    # Timing
    total_time = sum(timings.values())
    timing_rows = ""
    for stage, ms in timings.items():
        pct = (ms / total_time * 100) if total_time > 0 else 0.0
        timing_rows += f"""
        <tr>
            <td>{stage}</td>
            <td class="num">{ms:.1f}</td>
            <td class="num">{pct:.0f}%</td>
        </tr>"""
    timing_rows += f"""
        <tr style="border-top:2px solid #334155;font-weight:bold">
            <td>Total</td>
            <td class="num">{total_time:.1f}</td>
            <td class="num">100%</td>
        </tr>"""

    # Executive summary
    tl = exec_rpt.traffic_light
    tl_c = tl_color(tl)
    findings_html = ""
    for i, f in enumerate(exec_rpt.top_findings[:5], 1):
        findings_html += f"<li>{f}</li>\n"

    # Small-sample caveat
    caveat_html = ""
    if n < 30:
        caveat_html = f"""
    <div style="background:#422006;border:1px solid #92400e;border-radius:8px;padding:16px;margin:24px 0">
        <h3 style="color:#fbbf24;margin-top:0">Small-Sample Caveat (n={n})</h3>
        <ul style="color:#fde68a;margin-bottom:0">
            <li>Effect sizes and p-values are unreliable with n &lt; 30</li>
            <li>Percentile estimates have wide confidence intervals</li>
            <li>Chi-squared tests may not satisfy minimum cell count assumptions</li>
            <li>Results should be interpreted as directional, not definitive</li>
        </ul>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TELOSCOPE Governance Audit Report</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
        background: #0f172a;
        color: #e2e8f0;
        line-height: 1.6;
        padding: 40px 20px;
    }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    h1 {{
        color: #38bdf8;
        font-size: 24px;
        border-bottom: 2px solid #38bdf8;
        padding-bottom: 12px;
        margin-bottom: 8px;
    }}
    h2 {{
        color: #38bdf8;
        font-size: 18px;
        margin-top: 32px;
        margin-bottom: 12px;
        border-bottom: 1px solid #1e293b;
        padding-bottom: 8px;
    }}
    .subtitle {{
        color: #64748b;
        font-size: 14px;
        margin-bottom: 32px;
    }}
    .summary-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 16px;
        margin: 16px 0;
    }}
    .summary-card {{
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
    }}
    .summary-card .label {{ color: #94a3b8; font-size: 12px; }}
    .summary-card .value {{ color: #f1f5f9; font-size: 22px; font-weight: bold; }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 12px 0;
        font-size: 13px;
    }}
    th {{
        background: #1e293b;
        color: #94a3b8;
        text-align: left;
        padding: 8px 12px;
        border-bottom: 2px solid #334155;
        font-weight: normal;
        text-transform: uppercase;
        font-size: 11px;
        letter-spacing: 0.05em;
    }}
    td {{
        padding: 8px 12px;
        border-bottom: 1px solid #1e293b;
    }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .traffic-large {{
        display: inline-block;
        font-size: 32px;
        font-weight: bold;
        padding: 8px 24px;
        border-radius: 8px;
        margin: 8px 0;
    }}
    footer {{
        margin-top: 48px;
        padding-top: 16px;
        border-top: 1px solid #334155;
        color: #64748b;
        font-size: 12px;
        text-align: center;
    }}
</style>
</head>
<body>
<div class="container">
    <h1>TELOSCOPE Governance Audit Report</h1>
    <div class="subtitle">TELOS AI Labs &mdash; Generated {now}</div>

    <h2>Summary</h2>
    <div class="summary-grid">
        <div class="summary-card">
            <div class="label">Events</div>
            <div class="value">{n}</div>
        </div>
        <div class="summary-card">
            <div class="label">Sessions</div>
            <div class="value">{corpus.n_sessions}</div>
        </div>
        <div class="summary-card">
            <div class="label">Date Range</div>
            <div class="value" style="font-size:14px">{date_min[:10]}<br>to {date_max[:10]}</div>
        </div>
        <div class="summary-card">
            <div class="label">Governance Health</div>
            <div class="value" style="color:{tl_c}">&#9679; {tl}</div>
        </div>
    </div>

    <h2>Verdict Distribution</h2>
    <table>
        <thead>
            <tr><th>Verdict</th><th class="num">Count</th><th class="num">Rate</th><th>Distribution</th></tr>
        </thead>
        <tbody>{verdict_rows}
        </tbody>
    </table>

    <h2>Dimensional Analysis</h2>
    <table>
        <thead>
            <tr><th>Dimension</th><th class="num">Mean</th><th class="num">Median</th><th class="num">Stdev</th><th class="num">Min</th><th class="num">Max</th></tr>
        </thead>
        <tbody>{dim_rows}
        </tbody>
    </table>

    <h2>Integrity Verification</h2>
    <table>
        <thead>
            <tr><th>Check</th><th>Status</th></tr>
        </thead>
        <tbody>{val_rows}
        </tbody>
    </table>

    <h2>Allowed vs Blocked Comparison</h2>
    <p style="color:#94a3b8;margin-bottom:8px">Allowed (EXECUTE/CLARIFY): {cmp.n_a} events &mdash; Blocked (INERT/ESCALATE): {cmp.n_b} events</p>
    <table>
        <thead>
            <tr><th>Dimension</th><th class="num">Allowed</th><th class="num">Blocked</th><th class="num">Delta</th><th class="num">Cohen's d</th><th>Effect</th></tr>
        </thead>
        <tbody>{cmp_rows}
        </tbody>
    </table>

    <h2>Executive Summary</h2>
    <div style="margin:16px 0">
        <div class="traffic-large" style="background:#1e293b;border:2px solid {tl_c};color:{tl_c}">&#9679; {tl}</div>
    </div>
    <p>EXECUTE rate: {exec_rpt.execute_rate:.1%} ({exec_rpt.verdict_distribution.get('EXECUTE', 0)}/{n})</p>
    {"<h3 style='color:#e2e8f0;margin-top:16px'>Top Findings</h3><ol style='margin:8px 0 0 20px'>" + findings_html + "</ol>" if findings_html else ""}

    {caveat_html}

    <h2>Pipeline Timing</h2>
    <table>
        <thead>
            <tr><th>Stage</th><th class="num">Time (ms)</th><th class="num">% Total</th></tr>
        </thead>
        <tbody>{timing_rows}
        </tbody>
    </table>

    <footer>
        Generated by TELOSCOPE v1.0 &mdash; TELOS AI Labs
    </footer>
</div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_analysis(jsonl_path: str, html_path: Optional[str] = None):
    """Run the full TELOSCOPE analysis pipeline over demo audit data."""
    timings: Dict[str, float] = {}

    # 1. Load corpus
    t0 = time.perf_counter()
    corpus = load_corpus(jsonl_path)
    timings["Load"] = (time.perf_counter() - t0) * 1000

    n = len(corpus)
    if n == 0:
        print(f"  {C.RED}Error: No audit events found in {jsonl_path}{C.RESET}")
        sys.exit(1)

    # 2. Stats
    t0 = time.perf_counter()
    stats_full = corpus_stats(corpus)
    stats_verdict = corpus_stats(corpus, groupby="verdict")
    try:
        stats_tool = corpus_stats(corpus, groupby="tool_call")
    except Exception:
        stats_tool = None
    timings["Stats"] = (time.perf_counter() - t0) * 1000

    # 3. Validate
    t0 = time.perf_counter()
    val = validate(corpus)
    timings["Validate"] = (time.perf_counter() - t0) * 1000

    # 4. Compare: allowed vs blocked
    t0 = time.perf_counter()
    allowed = corpus.filter(predicate=lambda e: e.verdict in ("EXECUTE", "CLARIFY"))
    blocked = corpus.filter(predicate=lambda e: e.verdict in ("INERT", "ESCALATE"))
    cmp = compare(allowed, blocked, label_a="Allowed", label_b="Blocked")
    timings["Compare"] = (time.perf_counter() - t0) * 1000

    # 5. Executive report
    t0 = time.perf_counter()
    exec_rpt = executive_report(corpus, validation_result=val)
    timings["Report"] = (time.perf_counter() - t0) * 1000

    # -- Console output --
    print_header()
    print_corpus_summary(corpus)
    print_verdict_table(corpus)
    print_dimension_table(corpus)
    print_comparison(corpus, cmp)
    print_validation(val)
    print_executive(exec_rpt)
    print_caveats(n)
    print_timing(timings)
    print_footer()

    # -- Optional HTML --
    if html_path:
        html = generate_html(corpus, stats_full, stats_verdict, val, cmp, exec_rpt, timings)
        with open(html_path, "w") as f:
            f.write(html)
        print(f"  {C.GREEN}HTML report written to: {html_path}{C.RESET}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="TELOSCOPE Independent Governance Audit Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s /path/to/demo_audit.jsonl
  %(prog)s --generate
  %(prog)s /path/to/demo_audit.jsonl --html report.html
""",
    )
    parser.add_argument("jsonl_path", nargs="?", help="Path to audit JSONL file")
    parser.add_argument("--generate", action="store_true",
                        help="Generate sample demo corpus and analyze it")
    parser.add_argument("--html", metavar="PATH",
                        help="Write HTML report to this path")
    args = parser.parse_args()

    if not args.jsonl_path and not args.generate:
        parser.print_help()
        sys.exit(1)

    if args.generate:
        out = args.jsonl_path or "/tmp/demo_audit.jsonl"
        print(f"  Generating sample demo corpus -> {out}")
        generate_sample_demo_corpus(out)
        run_analysis(out, html_path=args.html)
    else:
        if not os.path.exists(args.jsonl_path):
            print(f"  {C.RED}File not found: {args.jsonl_path}{C.RESET}")
            sys.exit(1)
        run_analysis(args.jsonl_path, html_path=args.html)


if __name__ == "__main__":
    main()
