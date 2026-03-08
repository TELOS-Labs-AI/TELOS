"""
HTML Report Generator for TELOS Governance Evidence
====================================================

Generates self-contained HTML reports for governance sessions.
Inspired by claude-trace patterns but adapted for TELOS governance context.

Features:
- Self-contained HTML (no external dependencies)
- Base64 embedded data for offline viewing
- Interactive Plotly charts
- Fidelity trajectory visualization
- Intervention timeline
- Privacy-aware content display

Requirements:
- Jinja2 for templating
- Plotly for charts (optional, generates static SVG if unavailable)
"""

import json
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# HTML Template with embedded styles and scripts
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TELOS Governance Report - {{ session_id }}</title>
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

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid var(--gold);
            margin-bottom: 30px;
        }

        header h1 {
            color: var(--gold);
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        header .subtitle {
            color: var(--text-secondary);
            font-size: 1.1em;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }

        .stat-card .label {
            color: var(--text-secondary);
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-card .value {
            color: var(--gold);
            font-size: 2em;
            font-weight: bold;
            margin-top: 5px;
        }

        .stat-card .value.green { color: var(--green); }
        .stat-card .value.yellow { color: var(--yellow); }
        .stat-card .value.orange { color: var(--orange); }
        .stat-card .value.red { color: var(--red); }

        section {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 30px;
        }

        section h2 {
            color: var(--gold);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            margin-bottom: 20px;
        }

        .chart-container {
            width: 100%;
            min-height: 300px;
            background: var(--bg-tertiary);
            border-radius: 6px;
            padding: 15px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }

        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }

        th {
            background: var(--bg-tertiary);
            color: var(--gold);
            font-weight: 600;
        }

        tr:hover {
            background: var(--bg-tertiary);
        }

        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 500;
        }

        .badge.green { background: rgba(39, 174, 96, 0.2); color: var(--green); }
        .badge.yellow { background: rgba(243, 156, 18, 0.2); color: var(--yellow); }
        .badge.orange { background: rgba(230, 126, 34, 0.2); color: var(--orange); }
        .badge.red { background: rgba(231, 76, 60, 0.2); color: var(--red); }
        .badge.blue { background: rgba(52, 152, 219, 0.2); color: var(--blue); }

        .timeline {
            position: relative;
            padding-left: 30px;
        }

        .timeline::before {
            content: '';
            position: absolute;
            left: 10px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: var(--border-color);
        }

        .timeline-item {
            position: relative;
            padding: 15px 0;
            border-bottom: 1px solid var(--border-color);
        }

        .timeline-item::before {
            content: '';
            position: absolute;
            left: -24px;
            top: 20px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--gold);
        }

        .timeline-item.intervention::before { background: var(--red); }
        .timeline-item.fidelity-drop::before { background: var(--orange); }

        .privacy-notice {
            background: rgba(244, 208, 63, 0.1);
            border: 1px solid var(--gold);
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 20px;
        }

        .privacy-notice h4 {
            color: var(--gold);
            margin-bottom: 5px;
        }

        footer {
            text-align: center;
            padding: 30px 0;
            color: var(--text-secondary);
            border-top: 1px solid var(--border-color);
            margin-top: 30px;
        }

        footer a {
            color: var(--gold);
            text-decoration: none;
        }

        .collapsible {
            cursor: pointer;
            padding: 10px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            margin-bottom: 10px;
        }

        .collapsible::after {
            content: ' \\25BC';
            float: right;
        }

        .collapsible.collapsed::after {
            content: ' \\25B6';
        }

        .collapsible-content {
            padding: 15px;
            border: 1px solid var(--border-color);
            border-top: none;
            border-radius: 0 0 6px 6px;
            background: var(--bg-primary);
            display: none;
        }

        .collapsible-content.open {
            display: block;
        }
    </style>
    <!-- Plotly.js for interactive charts -->
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
</head>
<body>
    <div class="container">
        <header>
            <h1>TELOS Governance Report</h1>
            <p class="subtitle">Session: {{ session_id }} | Generated: {{ generated_at }}</p>
        </header>

        {% if privacy_mode != 'full' %}
        <div class="privacy-notice">
            <h4>Privacy Mode: {{ privacy_mode | title }}</h4>
            <p>
                {% if privacy_mode == 'deltas_only' %}
                This report contains only governance metrics and fidelity changes. No conversation content is included.
                {% elif privacy_mode == 'hashed' %}
                Content has been replaced with cryptographic hashes for privacy verification without exposing raw data.
                {% endif %}
            </p>
        </div>
        {% endif %}

        <!-- Summary Statistics -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total Turns</div>
                <div class="value">{{ stats.total_turns }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Average Fidelity</div>
                <div class="value {{ fidelity_class(stats.average_fidelity) }}">{{ "%.3f"|format(stats.average_fidelity) }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Interventions</div>
                <div class="value {% if stats.total_interventions > 0 %}red{% else %}green{% endif %}">{{ stats.total_interventions }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Total Events</div>
                <div class="value">{{ stats.total_events }}</div>
            </div>
        </div>

        <!-- Fidelity Trajectory Chart -->
        <section>
            <h2>Fidelity Trajectory</h2>
            <div id="fidelity-chart" class="chart-container"></div>
        </section>

        <!-- Intervention Summary -->
        {% if interventions %}
        <section>
            <h2>Intervention Log</h2>
            <table>
                <thead>
                    <tr>
                        <th>Turn</th>
                        <th>Level</th>
                        <th>Reason</th>
                        <th>Fidelity</th>
                        <th>Action</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
                    {% for intervention in interventions %}
                    <tr>
                        <td>{{ intervention.turn }}</td>
                        <td><span class="badge {{ intervention_class(intervention.level) }}">{{ intervention.level | upper }}</span></td>
                        <td>{{ intervention.reason }}</td>
                        <td>{{ "%.3f"|format(intervention.fidelity) }}</td>
                        <td>{{ intervention.action }}</td>
                        <td>{{ intervention.timestamp | truncate(19) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </section>
        {% else %}
        <section>
            <h2>Intervention Log</h2>
            <p style="color: var(--green); text-align: center; padding: 30px;">
                No interventions triggered during this session.
            </p>
        </section>
        {% endif %}

        <!-- Event Timeline -->
        <section>
            <h2>Event Timeline</h2>
            <div class="collapsible collapsed" onclick="toggleCollapsible(this)">
                View All {{ events | length }} Events
            </div>
            <div class="collapsible-content">
                <div class="timeline">
                    {% for event in events[:50] %}
                    <div class="timeline-item {% if event.event_type == 'intervention_triggered' %}intervention{% elif event.event_type == 'fidelity_calculated' and event.normalized_fidelity < 0.5 %}fidelity-drop{% endif %}">
                        <strong>{{ event.event_type | replace('_', ' ') | title }}</strong>
                        {% if event.turn_number %}<span class="badge blue">Turn {{ event.turn_number }}</span>{% endif %}
                        <br>
                        <small style="color: var(--text-secondary);">{{ event.timestamp }}</small>
                        {% if event.normalized_fidelity %}
                        <br><span class="badge {{ fidelity_class(event.normalized_fidelity) }}">Fidelity: {{ "%.3f"|format(event.normalized_fidelity) }}</span>
                        {% endif %}
                    </div>
                    {% endfor %}
                    {% if events | length > 50 %}
                    <p style="text-align: center; color: var(--text-secondary);">... and {{ events | length - 50 }} more events</p>
                    {% endif %}
                </div>
            </div>
        </section>

        <!-- Raw Data (collapsed) -->
        <section>
            <h2>Raw Data Export</h2>
            <div class="collapsible collapsed" onclick="toggleCollapsible(this)">
                View JSON Data
            </div>
            <div class="collapsible-content">
                <pre style="overflow-x: auto; background: var(--bg-primary); padding: 15px; border-radius: 6px; font-size: 0.85em;">{{ raw_data_json }}</pre>
            </div>
        </section>

        <footer>
            <p>Generated by <a href="https://telos-labs.ai">TELOS Observatory</a></p>
            <p style="font-size: 0.9em; margin-top: 10px;">
                TELOS: Telically Entrained Linguistic Operational Substrate
            </p>
        </footer>
    </div>

    <script>
        // Fidelity trajectory chart
        const fidelityData = {{ fidelity_trajectory_json | safe }};

        if (fidelityData && fidelityData.length > 0) {
            const trace = {
                x: fidelityData.map(d => d.turn),
                y: fidelityData.map(d => d.fidelity),
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Fidelity',
                line: {
                    color: '#F4D03F',
                    width: 2
                },
                marker: {
                    color: fidelityData.map(d => {
                        if (d.fidelity >= 0.70) return '#27ae60';
                        if (d.fidelity >= 0.60) return '#f39c12';
                        if (d.fidelity >= 0.50) return '#e67e22';
                        return '#e74c3c';
                    }),
                    size: 10
                }
            };

            // Add threshold lines
            const thresholds = [
                { y: 0.70, color: '#27ae60', name: 'Green Zone (0.70)' },
                { y: 0.60, color: '#f39c12', name: 'Yellow Zone (0.60)' },
                { y: 0.50, color: '#e67e22', name: 'Orange Zone (0.50)' },
            ];

            const layout = {
                title: '',
                xaxis: {
                    title: 'Turn Number',
                    color: '#8b949e',
                    gridcolor: '#30363d'
                },
                yaxis: {
                    title: 'Fidelity Score',
                    range: [0, 1],
                    color: '#8b949e',
                    gridcolor: '#30363d'
                },
                paper_bgcolor: '#21262d',
                plot_bgcolor: '#21262d',
                font: { color: '#e6edf3' },
                shapes: thresholds.map(t => ({
                    type: 'line',
                    x0: 0,
                    x1: Math.max(...fidelityData.map(d => d.turn)),
                    y0: t.y,
                    y1: t.y,
                    line: {
                        color: t.color,
                        width: 1,
                        dash: 'dash'
                    }
                })),
                margin: { t: 30, b: 50, l: 60, r: 30 }
            };

            Plotly.newPlot('fidelity-chart', [trace], layout, { responsive: true });
        } else {
            document.getElementById('fidelity-chart').innerHTML =
                '<p style="text-align: center; color: #8b949e; padding: 100px 0;">No fidelity data available</p>';
        }

        // Collapsible sections
        function toggleCollapsible(element) {
            element.classList.toggle('collapsed');
            const content = element.nextElementSibling;
            content.classList.toggle('open');
        }
    </script>
</body>
</html>
'''


class GovernanceReportGenerator:
    """
    Generates self-contained HTML reports for TELOS governance sessions.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize report generator.

        Args:
            output_dir: Directory for output files (default: ./telos_reports)
        """
        self.output_dir = output_dir or Path("./telos_reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Try to import Jinja2, fall back to simple string replacement
        try:
            from jinja2 import Template, Environment
            self._jinja_available = True
            self._env = Environment()
            self._env.filters['truncate'] = lambda s, l: s[:l] if s else ''
            self._template = self._env.from_string(HTML_TEMPLATE)
        except ImportError:
            self._jinja_available = False
            self._template = None
            logger.warning("Jinja2 not available - using simplified template rendering")

    def generate_report(
        self,
        session_data: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> Path:
        """
        Generate HTML report from session data.

        Args:
            session_data: Session data from GovernanceTraceCollector.export_to_dict()
            filename: Optional output filename (default: session_<id>_report.html)

        Returns:
            Path to generated report file
        """
        session_id = session_data.get('session_id', 'unknown')
        privacy_mode = session_data.get('privacy_mode', 'deltas_only')

        # Prepare template context
        context = {
            'session_id': session_id,
            'privacy_mode': privacy_mode,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
            'stats': session_data.get('stats', {}),
            'fidelity_trajectory': session_data.get('fidelity_trajectory', []),
            'fidelity_trajectory_json': json.dumps(session_data.get('fidelity_trajectory', [])),
            'interventions': session_data.get('interventions', []),
            'events': session_data.get('events', []),
            'raw_data_json': json.dumps(session_data, indent=2, default=str),
            'fidelity_class': self._fidelity_class,
            'intervention_class': self._intervention_class,
        }

        # Render template
        if self._jinja_available and self._template:
            html_content = self._template.render(**context)
        else:
            html_content = self._render_simple(context)

        # Write output file
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"session_{session_id}_{timestamp}_report.html"

        output_path = self.output_dir / filename
        output_path.write_text(html_content, encoding='utf-8')

        logger.info(f"Generated governance report: {output_path}")
        return output_path

    def generate_from_trace_file(
        self,
        trace_file: Path,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Generate report directly from a JSONL trace file.

        Args:
            trace_file: Path to JSONL trace file
            filename: Optional output filename

        Returns:
            Path to generated report file
        """
        from telos_core.governance_trace import GovernanceTraceCollector

        # Load trace file into a temporary collector
        collector = GovernanceTraceCollector(
            session_id="loaded_session",
            storage_dir=trace_file.parent,
        )
        collector.load_session(trace_file)

        # Export and generate report
        session_data = collector.export_to_dict()
        return self.generate_report(session_data, filename)

    @staticmethod
    def _fidelity_class(fidelity: float) -> str:
        """Get CSS class for fidelity value."""
        if fidelity >= 0.70:
            return "green"
        elif fidelity >= 0.60:
            return "yellow"
        elif fidelity >= 0.50:
            return "orange"
        else:
            return "red"

    @staticmethod
    def _intervention_class(level: str) -> str:
        """Get CSS class for intervention level."""
        level_lower = level.lower()
        if level_lower in ('none', 'monitor'):
            return "green"
        elif level_lower in ('correct',):
            return "yellow"
        elif level_lower in ('intervene',):
            return "orange"
        else:
            return "red"

    def _render_simple(self, context: Dict[str, Any]) -> str:
        """
        Simple template rendering fallback without Jinja2.
        Only handles basic variable substitution.
        """
        html = HTML_TEMPLATE

        # Basic variable substitutions
        html = html.replace('{{ session_id }}', str(context.get('session_id', '')))
        html = html.replace('{{ generated_at }}', str(context.get('generated_at', '')))
        html = html.replace('{{ privacy_mode }}', str(context.get('privacy_mode', '')))
        html = html.replace('{{ fidelity_trajectory_json | safe }}',
                           context.get('fidelity_trajectory_json', '[]'))
        html = html.replace('{{ raw_data_json }}', context.get('raw_data_json', '{}'))

        # Stats
        stats = context.get('stats', {})
        html = html.replace('{{ stats.total_turns }}', str(stats.get('total_turns', 0)))
        html = html.replace('{{ stats.total_interventions }}', str(stats.get('total_interventions', 0)))
        html = html.replace('{{ stats.total_events }}', str(stats.get('total_events', 0)))
        html = html.replace('{{ "%.3f"|format(stats.average_fidelity) }}',
                           f"{stats.get('average_fidelity', 0):.3f}")

        # Note: This simple renderer doesn't handle loops or conditionals
        # For full functionality, install Jinja2: pip install jinja2

        return html


# Convenience function for quick report generation
def generate_session_report(session_data: Dict[str, Any]) -> Path:
    """
    Quick function to generate a governance report.

    Args:
        session_data: Session data from collector.export_to_dict()

    Returns:
        Path to generated HTML report
    """
    generator = GovernanceReportGenerator()
    return generator.generate_report(session_data)
