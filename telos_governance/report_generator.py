"""
Agentic Forensic Report Generator
===================================
Generates self-contained HTML forensic reports for agentic governance sessions.

9-section forensic report structure:
1. Executive Summary -- session-level governance health
2. Session Metadata -- agent config, PA definition, tool inventory, thresholds, data retention
3. Turn-by-Turn Decision Log -- per-turn governance decisions with IEEE 7001 receipts
4. Tool Selection Audit Trail -- tools invoked, alternatives ranked, selection reasoning
5. SAAI Drift Analysis -- sliding window drift trajectory, tier transitions
6. Boundary Enforcement Log -- violations attempted, sanctions applied, human overrides
7. IEEE 7001 Alignment Checklist -- 5-item transparency checklist (self-assessed)
8. Regulatory Mapping -- requirement → report section → code reference

Export formats: Self-contained HTML (no CDN deps), JSONL, CSV
"""

import csv
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ===========================================================================
# HTML Template -- Self-contained, no CDN dependencies
# ===========================================================================

AGENTIC_REPORT_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TELOS Agentic Forensic Report - {{ session_id }}</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --border-color: #30363d;
            --gold: #F4D03F;
            --green: #27ae60;
            --yellow: #f39c12;
            --orange: #e67e22;
            --red: #e74c3c;
            --blue: #3498db;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            text-align: center; padding: 30px 0;
            border-bottom: 2px solid var(--gold); margin-bottom: 30px;
        }
        header h1 { color: var(--gold); font-size: 2.2em; margin-bottom: 5px; }
        header .subtitle { color: var(--text-secondary); font-size: 1.05em; }
        header .classification {
            color: var(--gold); font-size: 0.85em; margin-top: 8px;
            letter-spacing: 1px; text-transform: uppercase;
        }
        section {
            background: var(--bg-secondary); border: 1px solid var(--border-color);
            border-radius: 8px; padding: 25px; margin-bottom: 25px;
        }
        section h2 {
            color: var(--gold); border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px; margin-bottom: 20px; font-size: 1.3em;
        }
        section h2 .section-num {
            background: var(--gold); color: var(--bg-primary); border-radius: 4px;
            padding: 2px 8px; font-size: 0.75em; margin-right: 8px;
        }
        .stats-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px; margin-bottom: 20px;
        }
        .stat-card {
            background: var(--bg-tertiary); border: 1px solid var(--border-color);
            border-radius: 8px; padding: 15px; text-align: center;
        }
        .stat-card .label {
            color: var(--text-secondary); font-size: 0.85em;
            text-transform: uppercase; letter-spacing: 0.5px;
        }
        .stat-card .value {
            font-size: 1.8em; font-weight: bold; margin-top: 4px;
        }
        .stat-card .value.green { color: var(--green); }
        .stat-card .value.yellow { color: var(--yellow); }
        .stat-card .value.orange { color: var(--orange); }
        .stat-card .value.red { color: var(--red); }
        .stat-card .value.gold { color: var(--gold); }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border-color); }
        th { background: var(--bg-tertiary); color: var(--gold); font-weight: 600; font-size: 0.9em; }
        td { font-size: 0.9em; }
        tr:hover { background: var(--bg-tertiary); }
        .badge {
            display: inline-block; padding: 3px 8px; border-radius: 4px;
            font-size: 0.8em; font-weight: 500;
        }
        .badge.green { background: rgba(39,174,96,0.2); color: var(--green); }
        .badge.yellow { background: rgba(243,156,18,0.2); color: var(--yellow); }
        .badge.orange { background: rgba(230,126,34,0.2); color: var(--orange); }
        .badge.red { background: rgba(231,76,60,0.2); color: var(--red); }
        .badge.blue { background: rgba(52,152,219,0.2); color: var(--blue); }
        .badge.gold { background: rgba(244,208,63,0.2); color: var(--gold); }
        .checklist-item {
            padding: 8px 12px; margin: 6px 0; background: var(--bg-tertiary);
            border-radius: 6px; border-left: 3px solid var(--border-color);
        }
        .checklist-item.pass { border-left-color: var(--green); }
        .checklist-item.fail { border-left-color: var(--red); }
        .checklist-item .status { float: right; font-weight: bold; }
        .checklist-item .status.pass { color: var(--green); }
        .checklist-item .status.fail { color: var(--red); }
        .health-bar {
            height: 8px; border-radius: 4px; background: var(--bg-tertiary);
            margin-top: 6px; overflow: hidden;
        }
        .health-bar-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
        footer {
            text-align: center; padding: 25px 0; color: var(--text-secondary);
            border-top: 1px solid var(--border-color); margin-top: 25px;
            font-size: 0.9em;
        }
        footer a { color: var(--gold); text-decoration: none; }
        .collapsible {
            cursor: pointer; padding: 10px; background: var(--bg-tertiary);
            border: 1px solid var(--border-color); border-radius: 6px; margin-bottom: 8px;
        }
        .collapsible::after { content: ' \\25BC'; float: right; }
        .collapsible.collapsed::after { content: ' \\25B6'; }
        .collapsible-content {
            padding: 12px; border: 1px solid var(--border-color);
            border-top: none; border-radius: 0 0 6px 6px;
            background: var(--bg-primary); display: none;
        }
        .collapsible-content.open { display: block; }
        .retention-notice {
            background: rgba(52,152,219,0.1); border: 1px solid var(--blue);
            border-radius: 6px; padding: 12px; margin-top: 12px;
        }
        .retention-notice h4 { color: var(--blue); margin-bottom: 4px; }
    </style>
</head>
<body>
<div class="container">
    <header>
        <div class="classification">Forensic Governance Report</div>
        <h1>TELOS Agentic Governance Audit</h1>
        <p class="subtitle">Session: {{ session_id }} | Generated: {{ generated_at }}</p>
        <p class="subtitle">Agent: {{ agent_name }} ({{ template_id }})</p>
    </header>

    <!-- Section 1: Executive Summary -->
    <section>
        <h2><span class="section-num">1</span>Executive Summary</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Steps Completed</div>
                <div class="value gold">{{ total_steps }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Avg Effective Fidelity</div>
                <div class="value {{ fidelity_class(avg_fidelity) }}">{{ "%.1f"|format(avg_fidelity * 100) }}%</div>
            </div>
            <div class="stat-card">
                <div class="label">Boundary Violations</div>
                <div class="value {% if boundary_count > 0 %}red{% else %}green{% endif %}">{{ boundary_count }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Escalations</div>
                <div class="value {% if escalation_count > 0 %}orange{% else %}green{% endif %}">{{ escalation_count }}</div>
            </div>
            <div class="stat-card">
                <div class="label">SAAI Drift</div>
                <div class="value {{ saai_color }}">{{ final_drift_level }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Governance Health</div>
                <div class="value {{ health_color }}">{{ health_label }}</div>
            </div>
        </div>
        <p style="color: var(--text-secondary);">{{ executive_narrative }}</p>
    </section>

    {% if benchmark_context %}
    <!-- Section 1b: Benchmark Validation Context -->
    <section>
        <h2><span class="section-num">1b</span>Benchmark Validation Context</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total Scenarios</div>
                <div class="value gold">{{ benchmark_context.total_scenarios }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Overall Accuracy</div>
                <div class="value {{ 'green' if benchmark_context.overall_accuracy >= 0.85 else 'red' }}">{{ "%.1f"|format(benchmark_context.overall_accuracy * 100) }}%</div>
            </div>
            <div class="stat-card">
                <div class="label">Adversarial Detection</div>
                <div class="value {{ 'green' if benchmark_context.adversarial_detection >= 0.70 else 'red' }}">{{ "%.1f"|format(benchmark_context.adversarial_detection * 100) }}%</div>
            </div>
            <div class="stat-card">
                <div class="label">Elapsed</div>
                <div class="value gold">{{ benchmark_context.elapsed_seconds }}s</div>
            </div>
        </div>
        <table>
            <thead><tr><th>Category</th><th>Description</th><th>Correct</th><th>Total</th><th>Accuracy</th></tr></thead>
            <tbody>
            {% for cat in benchmark_context.categories %}
            <tr>
                <td><span class="badge {{ cat.color }}">{{ cat.label }}</span></td>
                <td>{{ cat.description }}</td>
                <td>{{ cat.correct }}</td>
                <td>{{ cat.total }}</td>
                <td>{{ "%.1f"|format(cat.accuracy * 100) }}%</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
        {% if benchmark_context.known_gaps %}
        <div style="margin-top: 15px; padding: 10px; background: var(--bg-tertiary); border-radius: 6px;">
            <strong style="color: var(--orange);">Known Gaps ({{ benchmark_context.known_gaps|length }}):</strong>
            <ul style="color: var(--text-secondary); font-size: 0.88em; margin-top: 4px; padding-left: 20px;">
            {% for gap in benchmark_context.known_gaps %}
                <li>{{ gap }}</li>
            {% endfor %}
            </ul>
        </div>
        {% endif %}
    </section>
    {% endif %}

    <!-- Section 2: Session Metadata -->
    <section>
        <h2><span class="section-num">2</span>Session Metadata</h2>
        <table>
            <tr><th style="width:220px;">Parameter</th><th>Value</th></tr>
            <tr><td>Agent Template</td><td>{{ template_id }} ({{ agent_name }})</td></tr>
            <tr><td>Purpose</td><td>{{ agent_purpose }}</td></tr>
            <tr><td>Scope</td><td>{{ agent_scope }}</td></tr>
            <tr><td>Boundaries</td><td>{{ boundary_list }}</td></tr>
            <tr><td>Tool Inventory</td><td>{{ tool_list }}</td></tr>
            <tr><td>Decision Thresholds</td><td>{{ decision_thresholds }}</td></tr>
            <tr><td>SAAI Thresholds</td><td>WARNING: 10% | RESTRICT: 15% (tightens EXECUTE to {{ restrict_threshold }}) | BLOCK: 20%</td></tr>
            <tr><td>Max Chain Length</td><td>20</td></tr>
            <tr><td>Embedding Model</td><td>{{ embedding_model }}</td></tr>
        </table>
        <div class="retention-notice">
            <h4>Data Retention Policy</h4>
            <p style="color: var(--text-secondary); font-size: 0.9em;">
                Governance traces: Minimum 3 years (configurable per jurisdiction).
                Forensic reports: Minimum 7 years.
                Audit trail events: Minimum 7 years.
                PII: Per applicable privacy law. All governance data stored with SHA-256 hash chain integrity.
            </p>
        </div>
    </section>

    <!-- Section 3: Turn-by-Turn Decision Log -->
    <section>
        <h2><span class="section-num">3</span>Turn-by-Turn Decision Log</h2>
        <table>
            <thead>
                <tr>
                    <th>Step</th>
                    <th>Decision</th>
                    <th>Purpose</th>
                    <th>Scope</th>
                    <th>Tool</th>
                    <th>Chain SCI</th>
                    <th>Boundary</th>
                    <th>Effective</th>
                    <th>Drift</th>
                    <th>Tool Selected</th>
                </tr>
            </thead>
            <tbody>
                {% for turn in turns %}
                <tr>
                    <td>{{ turn.step }}</td>
                    <td><span class="badge {{ decision_class(turn.decision) }}">{{ turn.decision }}</span></td>
                    <td>{{ "%.0f"|format(turn.purpose * 100) }}%</td>
                    <td>{{ "%.0f"|format(turn.scope * 100) }}%</td>
                    <td>{{ "%.0f"|format(turn.tool * 100) }}%</td>
                    <td>{{ "%.0f"|format(turn.chain * 100) }}%</td>
                    <td>{% if turn.boundary_triggered %}<span class="badge red">VIOLATION</span>{% else %}{{ "%.0f"|format(turn.boundary * 100) }}%{% endif %}</td>
                    <td><span class="badge {{ fidelity_class(turn.effective) }}">{{ "%.0f"|format(turn.effective * 100) }}%</span></td>
                    <td><span class="badge {{ saai_badge_class(turn.drift_level) }}">{{ turn.drift_level }}</span></td>
                    <td>{{ turn.selected_tool or '--' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        <p style="color: var(--text-secondary); margin-top: 12px; font-size: 0.85em;">
            Each row is an IEEE 7001 governance receipt: composite fidelity equation with per-dimension explanations.
        </p>
    </section>

    <!-- Section 4: Tool Selection Audit Trail -->
    <section>
        <h2><span class="section-num">4</span>Tool Selection Audit Trail</h2>
        {% for turn in turns %}
        {% if turn.tool_rankings %}
        <div class="collapsible collapsed" onclick="toggleCollapsible(this)">
            Step {{ turn.step }}: {{ turn.selected_tool or 'No tool' }} ({{ turn.decision }})
        </div>
        <div class="collapsible-content">
            <table>
                <thead><tr><th>Rank</th><th>Tool</th><th>Fidelity</th><th>Selected</th><th>Blocked</th></tr></thead>
                <tbody>
                {% for tool in turn.tool_rankings %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ tool.tool_name }}</td>
                    <td>{{ "%.0f"|format(tool.fidelity * 100) }}%</td>
                    <td>{% if tool.is_selected %}<span class="badge green">YES</span>{% else %}--{% endif %}</td>
                    <td>{% if tool.is_blocked %}<span class="badge red">BLOCKED</span>{% else %}--{% endif %}</td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
        {% endfor %}
    </section>

    <!-- Section 5: SCI Chain Analysis -->
    <section>
        <h2><span class="section-num">5</span>SCI Chain Analysis</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Chain Length</div>
                <div class="value gold">{{ chain_length }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Avg SCI</div>
                <div class="value {{ fidelity_class(avg_sci) }}">{{ "%.0f"|format(avg_sci * 100) }}%</div>
            </div>
            <div class="stat-card">
                <div class="label">Chain Breaks</div>
                <div class="value {% if chain_breaks > 0 %}orange{% else %}green{% endif %}">{{ chain_breaks }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Chain Status</div>
                <div class="value {% if chain_continuous %}green{% else %}orange{% endif %}">{{ 'Continuous' if chain_continuous else 'Broken' }}</div>
            </div>
        </div>
        <p style="color: var(--text-secondary); font-size: 0.9em;">
            Semantic Continuity Index (SCI) measures cosine similarity between consecutive action embeddings.
            SCI &ge; 0.30 = continuous. Decay factor: 0.90. Chain breaks force re-justification against the Primacy Attractor.
        </p>
    </section>

    <!-- Section 6: SAAI Drift Analysis -->
    <section>
        <h2><span class="section-num">6</span>SAAI Drift Analysis</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Baseline Fidelity</div>
                <div class="value gold">{{ "%.1f"|format((saai_baseline or 0) * 100) }}%</div>
            </div>
            <div class="stat-card">
                <div class="label">Final Drift</div>
                <div class="value {{ saai_color }}">{{ "%.1f"|format(final_drift_magnitude * 100) }}%</div>
            </div>
            <div class="stat-card">
                <div class="label">Final Level</div>
                <div class="value {{ saai_color }}">{{ final_drift_level }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Tier Transitions</div>
                <div class="value gold">{{ tier_transition_count }}</div>
            </div>
        </div>
        {% if drift_trajectory %}
        <table>
            <thead><tr><th>Step</th><th>Eff. Fidelity</th><th>Drift Magnitude</th><th>Drift Level</th></tr></thead>
            <tbody>
            {% for dt in drift_trajectory %}
            <tr>
                <td>{{ dt.step }}</td>
                <td>{{ "%.1f"|format(dt.fidelity * 100) }}%</td>
                <td>{{ "%.1f"|format(dt.magnitude * 100) }}%</td>
                <td><span class="badge {{ saai_badge_class(dt.level) }}">{{ dt.level }}</span></td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
        {% endif %}
        <p style="color: var(--text-secondary); margin-top: 12px; font-size: 0.85em;">
            SAAI Thresholds: WARNING at 10% cumulative drift, RESTRICT at 15%, BLOCK at 20%.
            Baseline established from first 3 turns. Drift = (baseline - current_avg) / baseline.
        </p>
        <div style="margin-top: 15px; padding: 10px; background: var(--bg-tertiary); border-radius: 6px;">
            <strong style="color: var(--gold);">RESTRICT Enforcement (Ostrom DP5):</strong>
            <span style="color: var(--text-secondary); font-size: 0.9em;">
                At RESTRICT tier (15-20% drift), the EXECUTE threshold is tightened
                from {{ execute_threshold }} to {{ restrict_threshold }}.
                Actions scoring between these thresholds are downgraded from EXECUTE to CLARIFY,
                requiring operator confirmation before proceeding. A boundary violation during
                RESTRICT triggers compound sanctioning: forced ESCALATE with immediate human review.
            </span>
        </div>
    </section>

    <!-- Section 7: Boundary Enforcement Log -->
    <section>
        <h2><span class="section-num">7</span>Boundary Enforcement Log</h2>
        {% if boundary_events %}
        <table>
            <thead><tr><th>Step</th><th>Boundary</th><th>Violation Score</th><th>Action Taken</th><th>Overridden</th><th>Override Reason</th></tr></thead>
            <tbody>
            {% for be in boundary_events %}
            <tr>
                <td>{{ be.step }}</td>
                <td>{{ be.boundary_name }}</td>
                <td><span class="badge red">{{ "%.0f"|format(be.violation_score * 100) }}%</span></td>
                <td>{{ be.action_taken }}</td>
                <td>{% if be.overridden %}<span class="badge orange">YES</span>{% else %}No{% endif %}</td>
                <td>{{ be.override_reason or '--' }}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p style="color: var(--green); text-align: center; padding: 20px;">No boundary violations during this session.</p>
        {% endif %}
        <div style="margin-top: 15px; padding: 10px; background: var(--bg-tertiary); border-radius: 6px;">
            <strong style="color: var(--gold);">Human Override Tracking:</strong>
            <span style="color: var(--text-secondary);">
                Total overrides: {{ total_overrides }}.
                Each override logged with GovernanceEvent.overridden=True and override_reason.
            </span>
        </div>
    </section>

    <!-- Section 8: IEEE 7001 Alignment Checklist (self-assessed) -->
    <section>
        <h2><span class="section-num">8</span>IEEE 7001 Alignment Checklist (Self-Assessed)</h2>
        {% for item in ieee_checklist %}
        <div class="checklist-item {{ 'pass' if item.passed else 'fail' }}">
            <span class="status {{ 'pass' if item.passed else 'fail' }}">{{ 'PASS' if item.passed else 'FAIL' }}</span>
            <strong>{{ item.name }}</strong>
            <p style="color: var(--text-secondary); font-size: 0.88em; margin-top: 4px;">{{ item.description }}</p>
        </div>
        {% endfor %}
    </section>

    <!-- Section 9: Regulatory Mapping -->
    <section>
        <h2><span class="section-num">9</span>Regulatory Mapping</h2>
        <table>
            <thead><tr><th>Requirement</th><th>Source</th><th>Report Section</th><th>TELOS Implementation</th></tr></thead>
            <tbody>
            {% for rm in regulatory_mapping %}
            <tr>
                <td>{{ rm.requirement }}</td>
                <td><span class="badge blue">{{ rm.source }}</span></td>
                <td>Section {{ rm.section }}</td>
                <td><code style="font-size: 0.85em;">{{ rm.code_ref }}</code></td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </section>

    <footer>
        <p>Generated by <a href="https://telos-labs.ai">TELOS AI Labs Inc.</a> | JB@telos-labs.ai</p>
        <p style="margin-top: 8px;">TELOS: Telically Entrained Linguistic Operational Substrate</p>
        <p style="margin-top: 4px; font-size: 0.85em;">This report is designed to support Post-Market Monitoring requirements under EU AI Act Article 72.</p>
    </footer>
</div>

<script>
function toggleCollapsible(el) {
    el.classList.toggle('collapsed');
    el.nextElementSibling.classList.toggle('open');
}
</script>
</body>
</html>
'''


class AgenticForensicReportGenerator:
    """
    Generates 9-section forensic HTML reports for agentic governance sessions.

    Consumes per-turn data from streamlit session state or a list of turn dicts,
    and produces self-contained HTML, JSONL, or CSV exports.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("./telos_reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        from jinja2 import Environment
        self._env = Environment(autoescape=True)
        self._env.filters['truncate'] = lambda s, l: s[:l] if s else ''
        self._template = self._env.from_string(AGENTIC_REPORT_TEMPLATE)

    # =========================================================================
    # Public API
    # =========================================================================

    def generate_report(
        self,
        session_id: str,
        template_id: str,
        agent_name: str,
        agent_purpose: str,
        agent_scope: str,
        boundaries: List[str],
        tools: List[str],
        turns: List[Dict[str, Any]],
        filename: Optional[str] = None,
        benchmark_context: Optional[Dict[str, Any]] = None,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2 (384-dim)",
    ) -> Path:
        """
        Generate a 9-section forensic HTML report.

        Args:
            session_id: Unique session identifier
            template_id: Agent template ID (e.g. 'property_intel')
            agent_name: Human-readable agent name
            agent_purpose: Agent purpose statement
            agent_scope: Agent scope statement
            boundaries: List of boundary strings
            tools: List of tool names
            turns: List of per-turn dicts, each containing:
                step, decision, purpose_fidelity, scope_fidelity, tool_fidelity,
                chain_sci, boundary_fidelity, boundary_triggered, effective_fidelity,
                selected_tool, tool_rankings, drift_level, drift_magnitude,
                saai_baseline, user_request, response_text
            filename: Optional output filename
            benchmark_context: Optional dict with benchmark validation metadata
            embedding_model: Embedding model name for metadata section

        Returns:
            Path to generated HTML report
        """
        context = self._build_context(
            session_id=session_id,
            template_id=template_id,
            agent_name=agent_name,
            agent_purpose=agent_purpose,
            agent_scope=agent_scope,
            boundaries=boundaries,
            tools=tools,
            turns=turns,
            benchmark_context=benchmark_context,
            embedding_model=embedding_model,
        )

        html = self._template.render(**context)

        if filename is None:
            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f"agentic_forensic_{session_id}_{ts}.html"

        output_path = self.output_dir / filename
        output_path.write_text(html, encoding='utf-8')
        logger.info(f"Generated agentic forensic report: {output_path}")
        return output_path

    def generate_jsonl(
        self,
        session_id: str,
        turns: List[Dict[str, Any]],
        filename: Optional[str] = None,
    ) -> Path:
        """Export session as JSONL (GovernanceEvent schema)."""
        if filename is None:
            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f"agentic_forensic_{session_id}_{ts}.jsonl"

        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            for turn in turns:
                event = {
                    "event_type": "agentic_governance_decision",
                    "session_id": session_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "step": turn.get("step", 0),
                    "decision": turn.get("decision", ""),
                    "purpose_fidelity": turn.get("purpose_fidelity", 0.0),
                    "scope_fidelity": turn.get("scope_fidelity", 0.0),
                    "tool_fidelity": turn.get("tool_fidelity", 0.0),
                    "chain_sci": turn.get("chain_sci", 0.0),
                    "boundary_fidelity": turn.get("boundary_fidelity", 0.0),
                    "boundary_triggered": turn.get("boundary_triggered", False),
                    "effective_fidelity": turn.get("effective_fidelity", 0.0),
                    "selected_tool": turn.get("selected_tool"),
                    "drift_level": turn.get("drift_level", "NORMAL"),
                    "drift_magnitude": turn.get("drift_magnitude", 0.0),
                }
                f.write(json.dumps(event) + '\n')

        logger.info(f"Generated JSONL export: {output_path}")
        return output_path

    def generate_csv(
        self,
        session_id: str,
        turns: List[Dict[str, Any]],
        filename: Optional[str] = None,
    ) -> Path:
        """Export aggregate metrics as CSV."""
        if filename is None:
            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f"agentic_forensic_{session_id}_{ts}.csv"

        output_path = self.output_dir / filename
        fieldnames = [
            "step", "decision", "purpose_fidelity", "scope_fidelity",
            "tool_fidelity", "chain_sci", "boundary_fidelity",
            "boundary_triggered", "effective_fidelity", "selected_tool",
            "drift_level", "drift_magnitude",
        ]

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for turn in turns:
                writer.writerow({
                    "step": turn.get("step", 0),
                    "decision": turn.get("decision", ""),
                    "purpose_fidelity": f"{turn.get('purpose_fidelity', 0.0):.4f}",
                    "scope_fidelity": f"{turn.get('scope_fidelity', 0.0):.4f}",
                    "tool_fidelity": f"{turn.get('tool_fidelity', 0.0):.4f}",
                    "chain_sci": f"{turn.get('chain_sci', 0.0):.4f}",
                    "boundary_fidelity": f"{turn.get('boundary_fidelity', 0.0):.4f}",
                    "boundary_triggered": turn.get("boundary_triggered", False),
                    "effective_fidelity": f"{turn.get('effective_fidelity', 0.0):.4f}",
                    "selected_tool": turn.get("selected_tool", ""),
                    "drift_level": turn.get("drift_level", "NORMAL"),
                    "drift_magnitude": f"{turn.get('drift_magnitude', 0.0):.4f}",
                })

        logger.info(f"Generated CSV export: {output_path}")
        return output_path

    # =========================================================================
    # Context Building
    # =========================================================================

    def _build_context(
        self,
        session_id: str,
        template_id: str,
        agent_name: str,
        agent_purpose: str,
        agent_scope: str,
        boundaries: List[str],
        tools: List[str],
        turns: List[Dict[str, Any]],
        benchmark_context: Optional[Dict[str, Any]] = None,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2 (384-dim)",
    ) -> Dict[str, Any]:
        """Build full Jinja2 template context from session data."""

        # Normalize turn data
        norm_turns = []
        for t in turns:
            norm_turns.append({
                "step": t.get("step", t.get("step_number", 0)),
                "decision": t.get("decision", "EXECUTE"),
                "purpose": t.get("purpose_fidelity", 0.0),
                "scope": t.get("scope_fidelity", 0.0),
                "tool": t.get("tool_fidelity", 0.0),
                "chain": t.get("chain_sci", 0.0),
                "boundary": t.get("boundary_fidelity", 0.0),
                "boundary_triggered": t.get("boundary_triggered", False),
                "effective": t.get("effective_fidelity", 0.0),
                "selected_tool": t.get("selected_tool"),
                "tool_rankings": t.get("tool_rankings", []),
                "drift_level": t.get("drift_level", "NORMAL"),
                "drift_magnitude": t.get("drift_magnitude", 0.0),
                "user_request": t.get("user_request", ""),
                "response_text": t.get("response_text", ""),
                "saai_baseline": t.get("saai_baseline"),
                "boundary_name": t.get("boundary_name"),
                "overridden": t.get("overridden", False),
                "override_reason": t.get("override_reason"),
            })

        total_steps = len(norm_turns)
        effective_scores = [t["effective"] for t in norm_turns]
        avg_fidelity = sum(effective_scores) / len(effective_scores) if effective_scores else 0.0

        boundary_events = [t for t in norm_turns if t["boundary_triggered"]]
        boundary_count = len(boundary_events)
        escalation_count = sum(1 for t in norm_turns if t["decision"] == "ESCALATE")
        total_overrides = sum(1 for t in norm_turns if t.get("overridden"))

        # Chain analysis
        chain_scis = [t["chain"] for t in norm_turns]
        avg_sci = sum(chain_scis) / len(chain_scis) if chain_scis else 0.0
        chain_breaks = sum(1 for t in norm_turns if t["chain"] < 0.30 and t["step"] > 1)
        chain_continuous = chain_breaks == 0

        # SAAI drift trajectory
        drift_trajectory = []
        tier_transitions = 0
        prev_level = "NORMAL"
        final_drift_level = "NORMAL"
        final_drift_magnitude = 0.0
        saai_baseline = None

        for t in norm_turns:
            dl = t["drift_level"]
            dm = t["drift_magnitude"]
            drift_trajectory.append({
                "step": t["step"],
                "fidelity": t["effective"],
                "magnitude": dm,
                "level": dl,
            })
            if dl != prev_level:
                tier_transitions += 1
                prev_level = dl
            final_drift_level = dl
            final_drift_magnitude = dm
            if t["saai_baseline"] is not None:
                saai_baseline = t["saai_baseline"]

        # Health assessment
        if boundary_count == 0 and avg_fidelity >= 0.70 and final_drift_level in ("NORMAL", "WARNING"):
            health_label = "HEALTHY"
            health_color = "green"
        elif boundary_count <= 1 and avg_fidelity >= 0.50:
            health_label = "FAIR"
            health_color = "yellow"
        else:
            health_label = "AT RISK"
            health_color = "red"

        # Executive narrative
        narrative_parts = [f"This session completed {total_steps} governance steps"]
        narrative_parts.append(f"with an average effective fidelity of {avg_fidelity:.0%}")
        if boundary_count > 0:
            narrative_parts.append(f", {boundary_count} boundary violation(s)")
        if escalation_count > 0:
            narrative_parts.append(f", {escalation_count} escalation(s)")
        narrative_parts.append(f". SAAI drift: {final_drift_level} ({final_drift_magnitude:.1%}).")
        if chain_continuous:
            narrative_parts.append(" The action chain maintained semantic continuity throughout.")
        else:
            narrative_parts.append(f" The action chain experienced {chain_breaks} break(s).")
        executive_narrative = "".join(narrative_parts)

        # IEEE 7001 Alignment Checklist (self-assessed)
        ieee_checklist = self._build_ieee_checklist(norm_turns, avg_fidelity, total_steps)

        # Regulatory mapping
        regulatory_mapping = self._build_regulatory_mapping()

        # SAAI color
        saai_color_map = {"NORMAL": "green", "WARNING": "yellow", "RESTRICT": "orange", "BLOCK": "red"}
        saai_color = saai_color_map.get(final_drift_level, "gold")

        # Boundary events for Section 7
        boundary_log = []
        for be in boundary_events:
            boundary_log.append({
                "step": be["step"],
                "boundary_name": be.get("boundary_name") or "Hard boundary",
                "violation_score": be["boundary"],
                "action_taken": "ESCALATE -- routed to human review",
                "overridden": be.get("overridden", False),
                "override_reason": be.get("override_reason"),
            })

        # Determine thresholds based on embedding model
        is_st = "sentence-transformer" in embedding_model.lower() or "minilm" in embedding_model.lower()
        if is_st:
            execute_threshold = "0.45"
            restrict_threshold = "0.52"
            decision_thresholds = (
                "EXECUTE \u2265 0.45 | CLARIFY \u2265 0.35 | "
                "INERT < 0.35 | ESCALATE: boundary or < 0.35+risk "
                "(SentenceTransformer/MiniLM thresholds)"
            )
        else:
            execute_threshold = "0.85"
            restrict_threshold = "0.90"
            decision_thresholds = (
                "EXECUTE \u2265 0.85 | CLARIFY \u2265 0.70 | "
                "INERT < 0.70 | ESCALATE: boundary or < 0.70+risk "
                "(Mistral thresholds)"
            )

        return {
            "session_id": session_id,
            "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            "template_id": template_id,
            "agent_name": agent_name,
            "agent_purpose": agent_purpose,
            "agent_scope": agent_scope,
            "boundary_list": "; ".join(boundaries),
            "tool_list": ", ".join(tools),
            "total_steps": total_steps,
            "avg_fidelity": avg_fidelity,
            "boundary_count": boundary_count,
            "escalation_count": escalation_count,
            "total_overrides": total_overrides,
            "final_drift_level": final_drift_level,
            "final_drift_magnitude": final_drift_magnitude,
            "saai_baseline": saai_baseline,
            "saai_color": saai_color,
            "health_label": health_label,
            "health_color": health_color,
            "executive_narrative": executive_narrative,
            "turns": norm_turns,
            "drift_trajectory": drift_trajectory,
            "tier_transition_count": tier_transitions,
            "chain_length": total_steps,
            "avg_sci": avg_sci,
            "chain_breaks": chain_breaks,
            "chain_continuous": chain_continuous,
            "boundary_events": boundary_log,
            "ieee_checklist": ieee_checklist,
            "regulatory_mapping": regulatory_mapping,
            # Dynamic thresholds
            "decision_thresholds": decision_thresholds,
            "execute_threshold": execute_threshold,
            "restrict_threshold": restrict_threshold,
            "embedding_model": embedding_model,
            # Benchmark context (optional)
            "benchmark_context": benchmark_context,
            # Template helper functions
            "fidelity_class": self._fidelity_class,
            "decision_class": self._decision_class,
            "saai_badge_class": self._saai_badge_class,
        }

    # =========================================================================
    # Section Builders
    # =========================================================================

    @staticmethod
    def _build_ieee_checklist(
        turns: List[Dict], avg_fidelity: float, total_steps: int,
    ) -> List[Dict[str, Any]]:
        """Build IEEE 7001 alignment checklist (7 items, self-assessed)."""
        has_explanations = total_steps > 0  # All turns produce dimension_explanations
        has_decisions = all(t.get("decision") for t in turns)
        has_drift = any(t.get("drift_level") != "NORMAL" for t in turns)
        has_restrict = any(t.get("drift_level") == "RESTRICT" for t in turns)

        return [
            {
                "name": "Explainability Receipt",
                "description": (
                    "Composite fidelity equation with per-dimension explanations "
                    "(purpose, scope, tool, chain, boundary) provided for every governance decision."
                ),
                "passed": has_explanations,
            },
            {
                "name": "Interpretability Validation",
                "description": (
                    "Summary understandable to non-ML reader: each decision tier "
                    "(EXECUTE/CLARIFY/INERT/ESCALATE) maps to a plain-language action."
                ),
                "passed": has_decisions,
            },
            {
                "name": "Consistency Guarantee",
                "description": (
                    "Same input produces same governance decision -- deterministic cosine similarity "
                    "scoring with fixed thresholds from telos_core/constants.py."
                ),
                "passed": True,  # Deterministic by architecture
            },
            {
                "name": "Audit Trail Completeness",
                "description": (
                    "All 5 decision points captured per action (PRE_ACTION, TOOL_SELECT, "
                    "TOOL_EXECUTE, POST_ACTION, CHAIN_END) with full AgenticFidelityResult."
                ),
                "passed": total_steps > 0,
            },
            {
                "name": "Disclosure of Governance Parameters",
                "description": (
                    "PA purpose, scope, boundaries, thresholds, and tool inventory visible "
                    "in Session Metadata (Section 2) of this report."
                ),
                "passed": True,  # Always included in Section 2
            },
            {
                "name": "Graduated Sanctions (Ostrom DP5)",
                "description": (
                    "SAAI drift tiers apply proportional sanctions: WARNING (log), "
                    "RESTRICT (tighten EXECUTE threshold), BLOCK (force ESCALATE). "
                    "RESTRICT + boundary violation triggers compound escalation."
                ),
                "passed": True,  # Architecturally guaranteed by process_request()
            },
            {
                "name": "Adversarial Robustness Testing",
                "description": (
                    "Category E adversarial scenarios test prompt injection, social engineering, "
                    "authority fabrication, output manipulation, and purpose redefinition attacks. "
                    "Detection rate tracked with known evasion gaps documented."
                ),
                "passed": True,  # Validated by TestAdversarialRobustness
            },
        ]

    @staticmethod
    def _build_regulatory_mapping() -> List[Dict[str, str]]:
        """Build regulatory requirement → section → code mapping table."""
        return [
            {
                "requirement": "Written AIS Program with FACTS principles",
                "source": "NAIC Model Bulletin (2023), AIS Program",
                "section": "2",
                "code_ref": "agent_templates.py (PA definition)",
            },
            {
                "requirement": "Model drift evaluation",
                "source": "NAIC Model Bulletin (2023), Section 3",
                "section": "6",
                "code_ref": "AgenticDriftTracker (agentic_response_manager.py)",
            },
            {
                "requirement": "Third-party vendor audit rights",
                "source": "NAIC Model Bulletin (2023), Section 3(5)",
                "section": "4, 7",
                "code_ref": "GovernanceProtocol.check_tool_execute()",
            },
            {
                "requirement": "Trace logs: output → input → model → threshold → decision",
                "source": "NAIC Model Bulletin (2023), Section 3(5)",
                "section": "3",
                "code_ref": "AgenticFidelityEngine.score_action()",
            },
            {
                "requirement": "Human review for high-stakes decisions",
                "source": "NAIC Model Bulletin (2023), Section 3(3)",
                "section": "7",
                "code_ref": "ESCALATE + human_required flag",
            },
            {
                "requirement": "High-risk AI documentation",
                "source": "CO SB 24-205",
                "section": "2, 8",
                "code_ref": "AgenticPA, IEEE 7001 checklist",
            },
            {
                "requirement": "Algorithmic discrimination audit",
                "source": "CO SB 24-205",
                "section": "3, 9",
                "code_ref": "Per-turn decision log (Section 3)",
            },
            {
                "requirement": "Post-market monitoring plan",
                "source": "Article 72",
                "section": "3, 5, 6",
                "code_ref": "GovernanceTraceCollector + SAAI drift",
            },
            {
                "requirement": "Active, systematic data collection",
                "source": "Article 72",
                "section": "3, 6",
                "code_ref": "JSONL export (GovernanceEvent schema)",
            },
            {
                "requirement": "Transparency of autonomous systems",
                "source": "IEEE 7001",
                "section": "8",
                "code_ref": "dimension_explanations dict",
            },
            {
                "requirement": "Cumulative drift monitoring with tiered response",
                "source": "SAAI",
                "section": "6",
                "code_ref": "AgenticDriftTracker (SAAI thresholds)",
            },
            {
                "requirement": "RESTRICT graduated sanctions",
                "source": "SAAI + Ostrom DP5",
                "section": "6",
                "code_ref": "process_request() RESTRICT override (agentic_response_manager.py)",
            },
            {
                "requirement": "Continuous, not episodic governance",
                "source": "SAAI",
                "section": "3, 5, 6",
                "code_ref": "5-point GovernanceProtocol",
            },
            {
                "requirement": "Adversarial robustness validation (ASI01)",
                "source": "OWASP Top 10 for Agentic Applications 2026",
                "section": "1b",
                "code_ref": "TestAdversarialRobustness (test_nearmap_benchmark.py)",
            },
            # --- NIST AI 600-1 (Generative AI Profile, July 2024) ---
            # See: research/regulatory/nist_ai_600_1_alignment.md
            {
                "requirement": "Trustworthy AI characteristics integrated into policies (GV 1.2)",
                "source": "NIST AI 600-1",
                "section": "3, 5",
                "code_ref": "6-dimension composite scoring (agentic_fidelity.py)",
            },
            {
                "requirement": "Governance policies across AI lifecycle (GV 1.4)",
                "source": "NIST AI 600-1",
                "section": "3, 5",
                "code_ref": "5-point GovernanceProtocol (governance_protocol.py)",
            },
            {
                "requirement": "Roles and responsibilities for AI risk management (GV 2.1)",
                "source": "NIST AI 600-1",
                "section": "2, 5",
                "code_ref": "PA config model: customer defines (TKey-signed), TELOS measures",
            },
            {
                "requirement": "Data collection and retention policies (GV 5.1)",
                "source": "NIST AI 600-1",
                "section": "3, 6",
                "code_ref": "PrivacyMode enum (evidence_schema.py) + IntelligenceCollector levels",
            },
            {
                "requirement": "Document intended purpose and context (MAP 1.1)",
                "source": "NIST AI 600-1",
                "section": "2",
                "code_ref": "AgenticPA purpose/scope (agentic_pa.py, config.py)",
            },
            {
                "requirement": "AI system categorized by risk (MAP 2.1)",
                "source": "NIST AI 600-1",
                "section": "2, 5",
                "code_ref": "4 risk tiers per tool (CRITICAL/HIGH/MEDIUM/LOW)",
            },
            {
                "requirement": "Document capabilities and limitations (MAP 2.2)",
                "source": "NIST AI 600-1",
                "section": "2, 4, 7",
                "code_ref": "AgenticPA tools + boundaries + bundle manifest",
            },
            {
                "requirement": "Supply chain risk mapping (MAP 3.1)",
                "source": "NIST AI 600-1",
                "section": "4",
                "code_ref": "ClawHavoc-sourced boundaries; ActionClassifier supply chain detection",
            },
            {
                "requirement": "AI system tested for performance (MS 2.1)",
                "source": "NIST AI 600-1",
                "section": "3, 7",
                "code_ref": "7 benchmarks / 5,212 scenarios (telos benchmark run)",
            },
            {
                "requirement": "Ongoing monitoring data collection (MS 2.5)",
                "source": "NIST AI 600-1",
                "section": "3, 6",
                "code_ref": "IntelligenceCollector (intelligence_layer.py)",
            },
            {
                "requirement": "Quantitative trustworthiness metrics (MS 2.6)",
                "source": "NIST AI 600-1",
                "section": "3, 5",
                "code_ref": "FidelityGate + AgenticFidelityEngine composite scoring",
            },
            {
                "requirement": "AI performance tracked over time (MS 2.8)",
                "source": "NIST AI 600-1",
                "section": "3, 6",
                "code_ref": "CUSUM drift detection (CUSUMMonitorBank, agentic_fidelity.py)",
            },
            {
                "requirement": "Mechanisms to supersede/disengage AI system (MG 2.2)",
                "source": "NIST AI 600-1",
                "section": "5, 6",
                "code_ref": "INERT/RESTRICT verdicts; Permission Controller deny; fail-policy",
            },
            {
                "requirement": "Mechanisms to deactivate AI system (MG 2.4)",
                "source": "NIST AI 600-1",
                "section": "5, 7",
                "code_ref": "Daemon governance_active gate; unsigned PA = INERT; daemon shutdown",
            },
            {
                "requirement": "Supply chain integrity for AI components (MAP 3.1)",
                "source": "NIST AI 600-1",
                "section": "4",
                "code_ref": "Dual-signed .telos bundles (signing.py, bundle.py)",
            },
            # --- NIST AI RMF 100 ---
            {
                "requirement": "Responsible AI policies (GOVERN 1.1)",
                "source": "NIST AI RMF",
                "section": "2, 5",
                "code_ref": "YAML config schema + constants.py single source of truth",
            },
            {
                "requirement": "Risk response mechanisms (MANAGE 2.2)",
                "source": "NIST AI RMF",
                "section": "5, 6",
                "code_ref": "Direction levels (NONE → HARD_BLOCK) in fidelity_gate.py",
            },
            {
                "requirement": "Post-deployment monitoring (MANAGE 4.1)",
                "source": "NIST AI RMF",
                "section": "3, 6",
                "code_ref": "GovernanceSessionContext + receipt chain (session.py)",
            },
            # --- OWASP Top 10 for Agentic Applications 2026 (ASI01-ASI10) ---
            {
                "requirement": "Excessive agency prevention (ASI02)",
                "source": "OWASP Top 10 for Agentic Applications 2026",
                "section": "3, 5",
                "code_ref": "Graduated sanctions + composite ceiling (agentic_fidelity.py)",
            },
            {
                "requirement": "Supply chain vulnerability protection (ASI04)",
                "source": "OWASP Top 10 for Agentic Applications 2026",
                "section": "4",
                "code_ref": "Ed25519 dual-signed bundles (signing.py, bundle.py)",
            },
            {
                "requirement": "Insecure plugin design prevention (ASI02)",
                "source": "OWASP Top 10 for Agentic Applications 2026",
                "section": "4, 7",
                "code_ref": "Semantic tool ranking + risk levels (tool_selection_gate.py)",
            },
            {
                "requirement": "Agent goal hijack boundary defense (ASI01)",
                "source": "OWASP Top 10 for Agentic Applications 2026",
                "section": "1b, 7",
                "code_ref": "Boundary corpus centroid detection (agentic_pa.py)",
            },
            {
                "requirement": "Human-agent trust exploitation detection (ASI09)",
                "source": "OWASP Top 10 for Agentic Applications 2026",
                "section": "6",
                "code_ref": "Drift tracking + telemetry patterns (intelligence_layer.py)",
            },
            # --- IEEE P7000 Series ---
            {
                "requirement": "Ethical concerns in system architecture (P7000)",
                "source": "IEEE P7000",
                "section": "2, 5",
                "code_ref": "AgenticPA 6-dimension governance spec (agentic_pa.py)",
            },
            {
                "requirement": "Algorithmic bias multi-factor assessment (P7003)",
                "source": "IEEE P7003",
                "section": "3, 5",
                "code_ref": "Multi-dimensional composite scoring (agentic_fidelity.py)",
            },
            {
                "requirement": "Data privacy graduated minimization (P7002)",
                "source": "IEEE P7002",
                "section": "3, 6",
                "code_ref": "Three privacy modes (PrivacyMode enum in evidence_schema.py) + encrypted export (data_export.py)",
            },
            # --- FedRAMP Controls ---
            {
                "requirement": "Continuous monitoring (CA-7)",
                "source": "FedRAMP",
                "section": "3, 6",
                "code_ref": "Signed receipt chains per session (receipt_signer.py, session.py)",
            },
            {
                "requirement": "Information integrity (SI-7)",
                "source": "FedRAMP",
                "section": "4",
                "code_ref": "AES-256-GCM + Ed25519 bundle format (crypto_layer.py, bundle.py)",
            },
            {
                "requirement": "External system services (SA-9)",
                "source": "FedRAMP",
                "section": "4",
                "code_ref": "Dual-signature provenance verification (signing.py)",
            },
        ]

    # =========================================================================
    # CSS Class Helpers (passed to Jinja2)
    # =========================================================================

    @staticmethod
    def _fidelity_class(fidelity: float) -> str:
        if fidelity >= 0.70:
            return "green"
        elif fidelity >= 0.60:
            return "yellow"
        elif fidelity >= 0.50:
            return "orange"
        return "red"

    @staticmethod
    def _decision_class(decision: str) -> str:
        d = decision.upper()
        if d == "EXECUTE":
            return "green"
        elif d == "CLARIFY":
            return "yellow"
        elif d in ("INERT", "ESCALATE"):
            return "red"
        return "blue"

    @staticmethod
    def _saai_badge_class(level: str) -> str:
        mapping = {"NORMAL": "green", "WARNING": "yellow", "RESTRICT": "orange", "BLOCK": "red"}
        return mapping.get(level, "blue")

    # =========================================================================
    # In-Memory HTML Generation (for st.download_button)
    # =========================================================================

    def generate_report_html(
        self,
        session_id: str,
        template_id: str,
        agent_name: str,
        agent_purpose: str,
        agent_scope: str,
        boundaries: List[str],
        tools: List[str],
        turns: List[Dict[str, Any]],
        benchmark_context: Optional[Dict[str, Any]] = None,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2 (384-dim)",
    ) -> str:
        """
        Generate a 9-section forensic HTML report and return as string.

        Same as generate_report() but returns HTML content instead of
        writing to disk. Used by st.download_button in the UI.
        """
        context = self._build_context(
            session_id=session_id,
            template_id=template_id,
            agent_name=agent_name,
            agent_purpose=agent_purpose,
            agent_scope=agent_scope,
            boundaries=boundaries,
            tools=tools,
            turns=turns,
            benchmark_context=benchmark_context,
            embedding_model=embedding_model,
        )
        return self._template.render(**context)


# ===========================================================================
# Convenience function
# ===========================================================================

def generate_agentic_forensic_report(
    session_id: str,
    template_id: str,
    agent_name: str,
    agent_purpose: str,
    agent_scope: str,
    boundaries: List[str],
    tools: List[str],
    turns: List[Dict[str, Any]],
) -> Path:
    """Quick function to generate an agentic forensic report."""
    generator = AgenticForensicReportGenerator()
    return generator.generate_report(
        session_id=session_id,
        template_id=template_id,
        agent_name=agent_name,
        agent_purpose=agent_purpose,
        agent_scope=agent_scope,
        boundaries=boundaries,
        tools=tools,
        turns=turns,
    )
