"""
TELOS Demo Display Toolkit
===========================
Shared display functions for all TELOS live demos (Nearmap, Healthcare, etc.)

Provides ANSI-colored terminal output with box-drawing characters,
score panels, cascade visualization, and verdict displays.

All functions respect NO_COLOR and DEMO_FAST environment variables.
"""

import os
import sys
import time

# Ensure the project root is on sys.path for telos_core/telos_governance imports
_TOOLKIT_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_PROJECT_ROOT = os.path.dirname(_TOOLKIT_DIR)
if _TOOLKIT_PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _TOOLKIT_PROJECT_ROOT)

from telos_core.constants import (
    FIDELITY_GREEN,
    FIDELITY_YELLOW,
    FIDELITY_ORANGE,
)
from telos_governance.agentic_fidelity import KEYWORD_EMBEDDING_FLOOR
from telos_governance.types import ActionDecision


# ═══════════════════════════════════════════════════════════════════════════
# Environment flags
# ═══════════════════════════════════════════════════════════════════════════

NO_COLOR = os.environ.get("NO_COLOR", "") != ""
DEMO_FAST = os.environ.get("DEMO_FAST", "") != ""
DEMO_PACE = float(os.environ.get("DEMO_PACE", "1.2"))
OBSERVE_MODE = os.getenv("DEMO_OBSERVE", "") == "1"


# ── ANSI code registry ──────────────────────────────────────────────────
_FG = {
    "green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m",
    "cyan": "\033[36m", "magenta": "\033[35m", "white": "\033[37m",
    "blue": "\033[34m", "dim": "\033[2m", "black": "\033[30m",
}
_BG = {
    "green": "\033[42m", "red": "\033[41m", "yellow": "\033[43m",
    "blue": "\033[44m", "magenta": "\033[45m", "cyan": "\033[46m",
}
_BOLD = "\033[1m"
_DIM = "\033[2m"
_STRIKE = "\033[9m"
_RESET = "\033[0m"


# ── Core text styling ───────────────────────────────────────────────────
def _c(text, fg=None, bold=False):
    """Colour text with foreground + optional bold. Respects NO_COLOR."""
    if NO_COLOR or fg is None:
        return text
    prefix = _FG.get(fg, "")
    if bold:
        prefix = _BOLD + prefix
    return "{}{}{}".format(prefix, text, _RESET)


def _bg(text, bg_color, fg_color="white", bold=True):
    """Text with background colour. Falls back to [BRACKETS] in NO_COLOR."""
    if NO_COLOR:
        return "[ {} ]".format(text)
    bg_code = _BG.get(bg_color, "")
    fg_code = _FG.get(fg_color, "")
    b = _BOLD if bold else ""
    return "{}{}{}{}{}".format(bg_code, fg_code, b, text, _RESET)


def _strike(text):
    """Strikethrough text. Falls back to ~text~ in NO_COLOR."""
    if NO_COLOR:
        return "~{}~".format(text)
    return "{}{}{}{}".format(_DIM, _STRIKE, text, _RESET)


# ── Score-aware colour ──────────────────────────────────────────────────
def _score_color(value):
    """Return fg colour name based on fidelity display zones (constants.py)."""
    if value >= FIDELITY_GREEN:
        return "green"
    elif value >= FIDELITY_YELLOW:
        return "yellow"
    elif value >= FIDELITY_ORANGE:
        return "yellow"
    else:
        return "red"


def _zone_label(fidelity):
    """Return display zone label for a fidelity score (constants.py)."""
    if fidelity >= FIDELITY_GREEN:
        return "GREEN"
    elif fidelity >= FIDELITY_YELLOW:
        return "YELLOW"
    elif fidelity >= FIDELITY_ORANGE:
        return "ORANGE"
    else:
        return "RED"


def _bar(score, width=14):
    """Score bar with per-value colour coding. Filled=coloured, empty=dim."""
    filled = max(0, int(score * width))
    empty = width - filled
    fill_str = "\u2588" * filled
    empty_str = "\u2591" * empty
    if NO_COLOR:
        return fill_str + empty_str
    fg = _FG.get(_score_color(score), "")
    return "{}{}{}{}{}{}".format(fg, fill_str, _RESET, _DIM, empty_str, _RESET)


# ── Pacing ──────────────────────────────────────────────────────────────
def _pause(seconds):
    """Pause for screen recording pacing. Skipped when DEMO_FAST is set."""
    if DEMO_FAST:
        return
    sys.stdout.flush()
    time.sleep(seconds * DEMO_PACE)


# ── Layout primitives ──────────────────────────────────────────────────
W = 70  # Full width for 80-col terminal with margin


def _wrap(text, width):
    """Word-wrap text to width."""
    words = text.split()
    lines = []
    current = ""
    for w in words:
        if current and len(current) + 1 + len(w) > width:
            lines.append(current)
            current = w
        else:
            current = "{} {}".format(current, w) if current else w
    if current:
        lines.append(current)
    return lines or [""]


def _kv(key, value, indent=2):
    """Key-value line."""
    pad = " " * indent
    print("{}{:<20s} {}".format(pad, _c(key + ":", "dim"), value))


# ── Box components ──────────────────────────────────────────────────────
def _header(text):
    """Page-level header with double-line border."""
    print()
    print(_c("\u2550" * W, "cyan", bold=True))
    for line in text.strip().split("\n"):
        print(_c("  {}".format(line.strip()), "cyan", bold=True))
    print(_c("\u2550" * W, "cyan", bold=True))


def _section(text):
    """Scenario section header with single-line border."""
    print()
    print()
    print(_c("\u2500" * W, "dim"))
    for line in text.strip().split("\n"):
        print(_c("  {}".format(line.strip()), "white", bold=True))
    print(_c("\u2500" * W, "dim"))


def _category_badge(category):
    """Background-coloured badge for scenario category."""
    badge_map = {
        "IN-SCOPE": ("green", "black"),
        "BOUNDARY": ("red", "white"),
        "OUT-OF-SCOPE": ("yellow", "black"),
        "ADVERSARIAL": ("magenta", "white"),
        "MULTI-STEP": ("blue", "white"),
        "EDGE-CASE": ("cyan", "black"),
        "NEGATION-BLIND": ("magenta", "white"),
        "CHAIN-DRIFT": ("blue", "white"),
    }
    bg_col, fg_col = badge_map.get(category, ("blue", "white"))
    padded = " {} ".format(category)
    return _bg(padded, bg_col, fg_col)


def _verdict_box(decision, detail=""):
    """Double-line verdict box with background colour. The key visual beat.

    Accepts any decision enum (ActionDecision or GovernanceDecision) — uses
    string value comparison for compatibility across engine types.
    """
    inner_w = W - 6  # account for "  ║" on each side

    dec_val = decision.value if hasattr(decision, 'value') else str(decision).lower()

    if dec_val == "execute":
        glyph = "\u2713"
        label = "EXECUTE"
        desc = "Request approved \u2014 proceeding to agent"
        border_fg = "green"
        bg_col = "green"
    elif dec_val == "clarify":
        glyph = "\u26A0"
        label = "CLARIFY"
        desc = "Verifying intent before proceeding"
        border_fg = "yellow"
        bg_col = "yellow"
    elif dec_val == "escalate":
        glyph = "\u2717"
        label = "ESCALATE"
        desc = detail or "Blocked at governance layer"
        border_fg = "red"
        bg_col = "red"
    else:
        glyph = "\u2717"
        label = "INERT"
        desc = "Blocked \u2014 outside agent scope"
        border_fg = "red"
        bg_col = "red"

    content = "  {}  {}  \u2014  {}".format(glyph, label, desc)

    if NO_COLOR:
        print()
        print("  +{}+".format("=" * (W - 4)))
        print("  | {} |".format(content.ljust(W - 6)))
        print("  +{}+".format("=" * (W - 4)))
    else:
        border = _FG.get(border_fg, "") + _BOLD
        fg_for_bg = "black" if bg_col in ("green", "yellow", "cyan") else "white"
        print()
        print("  {}\u2554{}\u2557{}".format(border, "\u2550" * (W - 4), _RESET))
        padded = content.ljust(inner_w)
        print("  {}\u2551{}{}{}{}\u2551{}".format(
            border, _RESET,
            _bg(padded, bg_col, fg_for_bg),
            border, "", _RESET
        ))
        print("  {}\u255A{}\u255D{}".format(border, "\u2550" * (W - 4), _RESET))


def _score_panel(rows):
    """Rounded-corner panel for the scoring breakdown.
    rows: list of (label, value_str, bar_str, tag_str)
    """
    inner_w = W - 6
    if NO_COLOR:
        border_l, border_r, top_l, top_r, bot_l, bot_r, hrule = "|", "|", "+", "+", "+", "+", "-"
    else:
        border_l = _DIM + "\u2502" + _RESET
        border_r = _DIM + "\u2502" + _RESET
        top_l = _DIM + "\u256D" + _RESET
        top_r = _DIM + "\u256E" + _RESET
        bot_l = _DIM + "\u2570" + _RESET
        bot_r = _DIM + "\u256F" + _RESET
        hrule = _DIM + "\u2500" + _RESET

    # Top
    if NO_COLOR:
        print("  {}{}{}".format(top_l, hrule * (W - 4), top_r))
    else:
        print("  {}{}\u2500{}{}{}\u256E{}".format(
            _DIM, "\u256D", _RESET,
            _DIM, "\u2500" * (W - 6), _RESET
        ))

    for row in rows:
        if row is None:
            # Separator
            if NO_COLOR:
                print("  {}{}{}".format("|", "-" * (W - 4), "|"))
            else:
                print("  {}  {}{}".format(border_l, _DIM + "\u2500" * (W - 8) + _RESET, border_r))
            continue
        label, val_str, bar_str, tag_str = row
        line = "  {:10s} {:>6s}  {}  {}".format(label, val_str, bar_str, tag_str)
        print("  {} {}{}".format(border_l, line, border_r))

    # Bottom
    if NO_COLOR:
        print("  {}{}{}".format(bot_l, hrule * (W - 4), bot_r))
    else:
        print("  {}{}\u2500{}{}{}\u256F{}".format(
            _DIM, "\u2570", _RESET,
            _DIM, "\u2500" * (W - 6), _RESET
        ))


def _agent_card(tool_called, response, width=None):
    """Blue-bordered card for agent responses."""
    w = (width or W) - 4
    inner = w - 2

    if NO_COLOR:
        hdr = "-- Agent Response "
        print()
        print("  +{}+".format("-" * w))
        if tool_called:
            print("  | Tool: {}{} |".format(tool_called, " " * max(0, inner - 7 - len(tool_called))))
        for ln in _wrap(response, inner - 2):
            print("  |  {}{} |".format(ln, " " * max(0, inner - 2 - len(ln))))
        print("  +{}+".format("-" * w))
        return

    blue = _FG.get("blue", "")
    hdr_text = " Agent Response "
    hdr_rule_len = max(0, w - len(hdr_text) - 3)
    print()
    print("  {}\u250C\u2500{}{}{}{}\u2500{}{}\u2510{}".format(
        blue, _RESET, _c(hdr_text, "blue", bold=True),
        blue, "", "\u2500" * hdr_rule_len, "", _RESET
    ))

    if tool_called:
        tool_line = "  Tool: {}".format(_c(tool_called, "cyan", bold=True))
        print("  {}\u2502{} {}{}{}".format(blue, _RESET, tool_line,
              " " * max(0, w - 10 - len(tool_called)), blue + "\u2502" + _RESET))
        print("  {}\u2502{}{}{}\u2502{}".format(blue, _RESET, " " * w, blue, _RESET))

    for ln in _wrap(response, inner - 2):
        padding = max(0, w - len(ln) - 2)
        print("  {}\u2502{}  {}{}{}{}{}".format(
            blue, _RESET, ln, " " * padding, "", blue, "\u2502" + _RESET
        ))

    print("  {}\u2514{}\u2518{}".format(blue, "\u2500" * w, _RESET))


def _blocked_card(request, reason):
    """Red double-line box for blocked requests. Striking visual."""
    inner = W - 6
    header_text = "  \u2717  BLOCKED \u2014 LLM never called"

    if NO_COLOR:
        print()
        print("  +{}+".format("=" * (W - 4)))
        print("  | {} |".format(header_text.ljust(inner)))
        print("  | {} |".format(" " * inner))
        for ln in _wrap(request, inner - 4):
            struck = "~ {} ~".format(ln)
            print("  |  {} |".format(struck.ljust(inner - 2)))
        print("  | {} |".format(" " * inner))
        reason_line = "  Reason: {}".format(reason)
        print("  | {} |".format(reason_line.ljust(inner)))
        print("  +{}+".format("=" * (W - 4)))
        return

    red_b = _FG["red"] + _BOLD

    print()
    print("  {}\u2554{}\u2557{}".format(red_b, "\u2550" * (W - 4), _RESET))

    # Header line with red background
    padded_hdr = header_text.ljust(inner)
    print("  {}\u2551{}{}{}\u2551{}".format(
        red_b, _RESET, _bg(padded_hdr, "red", "white"), red_b, _RESET
    ))

    # Blank
    print("  {}\u2551{}{}{}{}".format(red_b, _RESET, " " * inner, red_b, "\u2551" + _RESET))

    # Struck-through request
    for ln in _wrap(request, inner - 4):
        struck = _strike(ln)
        # Pad accounting for ANSI codes in struck
        visible_len = len(ln) + 2  # ~~ adds 2 in NO_COLOR, but in ANSI just the text
        pad = max(0, inner - 4 - len(ln))
        print("  {}\u2551{}  {}{}{}{}{}".format(
            red_b, _RESET, "  ", struck, " " * pad, red_b, "\u2551" + _RESET
        ))

    # Blank
    print("  {}\u2551{}{}{}{}".format(red_b, _RESET, " " * inner, red_b, "\u2551" + _RESET))

    # Reason
    reason_line = "  Reason: {}".format(reason)
    pad = max(0, inner - len(reason_line))
    print("  {}\u2551{}{}{}{} {}{}".format(
        red_b, _RESET, _c(reason_line, "red"), " " * pad, "", red_b, "\u2551" + _RESET
    ))

    print("  {}\u255A{}\u255D{}".format(red_b, "\u2550" * (W - 4), _RESET))


def _flow_line(allowed):
    """Visual flow: Request -> TELOS Gate -> result."""
    if allowed:
        result = _c(" \u2713 ALLOWED \u2500\u25B6 AI AGENT ", "green")
    else:
        result = _c(" \u2717 BLOCKED   (LLM never called) ", "red")

    print()
    parts = [
        _c(" REQUEST ", "white", bold=True),
        _c(" \u2500\u2500\u25B6 ", "dim"),
        _c(" TELOS GATE ", "cyan", bold=True),
        _c(" \u2500\u2500\u25B6 ", "dim"),
        result,
    ]
    print("  {}".format("".join(parts)))


def _narrator(text):
    """Cyan narrator cue between scenarios."""
    print()
    for ln in _wrap(text, W - 8):
        print("  {} {}".format(_c("\u25B8", "cyan"), _c(ln, "cyan")))


def _cascade_panel(result, gov_ms, setfit_loaded=False):
    """Render the L0->L1->L1.5->L2 cascade as a boxed panel.

    Args:
        result: AgenticFidelityResult from the production engine
        gov_ms: Total governance latency in milliseconds
        setfit_loaded: Whether the SetFit model was loaded
    """
    inner = W - 6
    print()
    # Top border
    if NO_COLOR:
        print("  +-- CASCADE {}+".format("-" * (inner - 13)))
    else:
        print("  {}{}\u2500 {} {}{}\u256E{}".format(
            _DIM, "\u256D", _RESET + _c("CASCADE", "white", bold=True),
            _DIM, "\u2500" * (inner - 13), _RESET))

    def _layer_line(name, status, color, detail):
        label = "  {:<15s}".format(name)
        st = "{:<12s}".format(status)
        if NO_COLOR:
            print("  | {}{}  {} |".format(label, st, detail))
        else:
            border = _DIM + "\u2502" + _RESET
            colored_st = _c(st, color) if color != "dim" else _c(st, "dim")
            print("  {} {}{}  {} {}".format(border, label, colored_st, detail, border))

    # L0: Keywords
    if result.keyword_triggered:
        kw_list = ", ".join(result.keyword_matches[:3])
        _layer_line("L0:keywords", "TRIGGERED", "red",
                    "[{}]".format(kw_list))
    else:
        _layer_line("L0:keywords", "PASS", "green", "")

    # L1: Cosine similarity (boundary violation score)
    bv = result.boundary_violation
    if result.boundary_triggered and not result.setfit_triggered:
        # L1 caught the violation
        detail_parts = ["{:.2f}".format(bv)]
        if result.dimension_explanations.get("boundary"):
            detail_parts.append(result.dimension_explanations["boundary"][:30])
        _layer_line("L1:cosine", "VIOLATION", "red", "  ".join(detail_parts))
    else:
        threshold_note = ""
        if bv >= KEYWORD_EMBEDDING_FLOOR:
            threshold_note = "(in SetFit zone)"
        elif bv > 0.0:
            threshold_note = "(below floor {:.2f})".format(KEYWORD_EMBEDDING_FLOOR)
        _layer_line("L1:cosine", "PASS  {:.2f}".format(bv), "green", threshold_note)

    # L1.5: SetFit classifier
    if not setfit_loaded:
        _layer_line("L1.5:SetFit", "\u2500\u2500 n/a \u2500\u2500", "dim", "(not loaded)")
    elif result.setfit_score is not None:
        if result.setfit_triggered:
            _layer_line("L1.5:SetFit", "ESCALATED", "red",
                        "P(violation) = {:.2f}".format(result.setfit_score))
        else:
            _layer_line("L1.5:SetFit", "PASS", "green",
                        "P(violation) = {:.2f}".format(result.setfit_score))
    elif result.boundary_triggered:
        _layer_line("L1.5:SetFit", "\u2500\u2500 skip \u2500\u2500", "dim", "(L1 already triggered)")
    else:
        _layer_line("L1.5:SetFit", "\u2500\u2500 skip \u2500\u2500", "dim", "(cosine below floor)")

    # L2: LLM review
    _layer_line("L2:LLM", "\u2500\u2500 skip \u2500\u2500", "dim", "(not needed)")

    # Total line
    dec_val = result.decision.value if hasattr(result.decision, 'value') else str(result.decision).lower()
    dec_color = "green" if dec_val in ("execute", "clarify") else "red"
    total_line = "  Total: {:.1f}ms  Decision: {}".format(
        gov_ms, _c(dec_val.upper(), dec_color, bold=True))
    if NO_COLOR:
        print("  | {} |".format(total_line.ljust(inner)))
    else:
        border = _DIM + "\u2502" + _RESET
        print("  {} {} {}".format(border, total_line + " " * max(0, inner - 40), border))

    # Bottom border
    if NO_COLOR:
        print("  +{}+".format("-" * (inner + 2)))
    else:
        print("  {}{}\u2500{}{}{}\u256F{}".format(
            _DIM, "\u2570", _RESET,
            _DIM, "\u2500" * (inner - 1), _RESET))


def _two_gate_panel(prod_result, gov_ms):
    """Render the two-gate governance display.

    Gate 1 — Tool Selection: "Is this the right tool?"
    Gate 2 — Behavioral Fidelity: "Is this within your boundaries?"

    Derives gate outcomes from the engine's actual scoring data.
    """
    inner = W - 6
    decision = prod_result.decision
    dec_val = decision.value if hasattr(decision, 'value') else str(decision).lower()
    tool_f = prod_result.tool_fidelity
    tool_name = prod_result.selected_tool or "none"
    purpose_f = prod_result.purpose_fidelity
    boundary_triggered = prod_result.boundary_triggered
    boundary_score = prod_result.boundary_violation
    boundary_name = prod_result.dimension_explanations.get("boundary", "")

    # --- Gate 1: Tool Selection ---
    if tool_f >= 0.70:
        g1_sym = _c("\u2713", "green", bold=True)
        g1_status = _c("PASS", "green", bold=True)
        g1_detail = "{} ({:.2f})".format(tool_name, tool_f)
    elif tool_f >= 0.40:
        g1_sym = _c("\u26A0", "yellow", bold=True)
        g1_status = _c("UNCERTAIN", "yellow", bold=True)
        g1_detail = "best match: {} ({:.2f})".format(tool_name, tool_f)
    else:
        g1_sym = _c("\u2717", "red", bold=True)
        g1_status = _c("FAIL", "red", bold=True)
        g1_detail = "no confident tool match ({:.2f})".format(tool_f)

    # --- Gate 2: Behavioral Fidelity ---
    contrastive_suppressed = getattr(prod_result, "contrastive_suppressed", False)
    chain_broken = getattr(prod_result, "chain_broken", False)
    if boundary_triggered:
        g2_sym = _c("\u2717", "red", bold=True)
        g2_status = _c("FAIL", "red", bold=True)
        # Extract boundary label from engine explanation: "... against 'label' ..."
        b_name = "boundary triggered"
        if boundary_name and "'" in boundary_name:
            parts = boundary_name.split("'")
            if len(parts) >= 2:
                b_name = parts[1][:50]
        elif boundary_name:
            b_name = boundary_name[:50].rsplit(" ", 1)[0] if len(boundary_name) > 50 else boundary_name
        g2_detail = "{} ({:.2f})".format(b_name, boundary_score)
    elif contrastive_suppressed and boundary_score >= 0.40:
        g2_sym = _c("\u26A0", "yellow", bold=True)
        g2_status = _c("CAUTION", "yellow", bold=True)
        g2_detail = "boundary signal detected ({:.2f}) \u2014 decision capped".format(boundary_score)
    elif chain_broken and dec_val in ("clarify",):
        g2_sym = _c("\u26A0", "yellow", bold=True)
        g2_status = _c("VERIFY", "yellow", bold=True)
        g2_detail = "chain discontinuity \u2014 verifying intent"
    elif purpose_f < 0.58:
        g2_sym = _c("\u26A0", "yellow", bold=True)
        g2_status = _c("MARGINAL", "yellow", bold=True)
        g2_detail = "purpose alignment {:.2f}".format(purpose_f)
    else:
        g2_sym = _c("\u2713", "green", bold=True)
        g2_status = _c("PASS", "green", bold=True)
        g2_detail = "no boundaries triggered"

    # --- Render ---
    print()
    if NO_COLOR:
        print("  +-- GOVERNANCE GATES {}+".format("-" * (inner - 22)))
    else:
        print("  {}{}\u2500 {} {}{}\u256E{}".format(
            _DIM, "\u256D", _RESET + _c("GOVERNANCE GATES", "white", bold=True),
            _DIM, "\u2500" * (inner - 22), _RESET))

    def _gate_line(text):
        if NO_COLOR:
            print("  | {} |".format(text.ljust(inner)))
        else:
            border = _DIM + "\u2502" + _RESET
            print("  {} {} {}".format(border, text, border))

    _gate_line("")
    _gate_line("  {}  Gate 1 \u2014 Tool Selection".format(
        _c("\u2500" * 2, "cyan")))
    _gate_line("  {}".format(_c('"Is this the right tool?"', "dim")))
    _gate_line("  {} {}    {}".format(g1_sym, g1_status, g1_detail))
    _gate_line("")
    _gate_line("  {}  Gate 2 \u2014 Behavioral Fidelity".format(
        _c("\u2500" * 2, "cyan")))
    _gate_line("  {}".format(_c('"Is this within your boundaries?"', "dim")))
    _gate_line("  {} {}    {}".format(g2_sym, g2_status, g2_detail))
    _gate_line("")

    # Timing
    dec_color = "green" if dec_val in ("execute", "clarify") else "red"
    _gate_line("  \u23F1 {:.0f}ms    Verdict: {}".format(
        gov_ms, _c(dec_val.upper(), dec_color, bold=True)))

    if NO_COLOR:
        print("  +{}+".format("-" * (inner + 2)))
    else:
        print("  {}{}\u2500{}{}{}\u256F{}".format(
            _DIM, "\u2570", _RESET,
            _DIM, "\u2500" * (inner - 1), _RESET))
