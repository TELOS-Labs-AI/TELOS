"""
Slide Export
============

Generates a branded, print-ready HTML document from demo slide data.
Includes both the conversational TELOS demo (14 slides) and the
agentic governance demo (10 slides) in a single downloadable file.

The HTML includes @media print CSS for clean PDF output from any browser.
"""

import streamlit as st
from datetime import date


def generate_slides_html(include_demo=True, include_agentic=True):
    """
    Generate a branded HTML document containing slide content.

    Args:
        include_demo: Include the 14-slide conversational TELOS demo
        include_agentic: Include the 10-slide agentic governance demo

    Returns:
        str: Complete HTML document ready for download/printing
    """
    sections = []

    if include_demo:
        from telos_observatory.demo_mode.telos_framework_demo import get_demo_slides
        demo_slides = get_demo_slides()
        sections.append(("TELOS Framework", "Conversational AI Governance", demo_slides))

    if include_agentic:
        from telos_observatory.agentic.agentic_demo_slides import get_agentic_demo_slides
        agentic_slides = get_agentic_demo_slides()
        sections.append(("Agentic Governance", "Action-Space AI Governance", agentic_slides))

    today = date.today().strftime("%B %d, %Y")
    slides_html = _build_sections(sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TELOS AI Governance - Demo Reference</title>
<style>
{_get_css()}
</style>
</head>
<body>

<div class="cover">
    <div class="cover-border">
        <h1>TELOS</h1>
        <p class="subtitle">Telically Entrained Linguistic Operational Substrate</p>
        <div class="divider"></div>
        <p class="doc-title">AI Governance Demo Reference</p>
        <p class="doc-date">{today}</p>
        <p class="doc-org">TELOS AI Labs Inc.</p>
        <p class="doc-contact">JB@telos-labs.ai</p>
    </div>
</div>

{slides_html}

<div class="footer-note">
    <p>TELOS AI Labs Inc. &middot; {today}</p>
    <p>github.com/TELOS-Labs-AI/telos</p>
</div>

</body>
</html>"""


def _build_sections(sections):
    """Build HTML for all slide sections."""
    parts = []

    for section_title, section_subtitle, slides in sections:
        parts.append(f"""
<div class="section-header">
    <h2>{section_title}</h2>
    <p class="section-subtitle">{section_subtitle}</p>
    <p class="slide-count">{len(slides)} slides</p>
</div>
""")
        for i, (question, answer) in enumerate(slides, 1):
            # Convert newlines to paragraphs
            answer_paragraphs = answer.split("\n\n")
            answer_html = "".join(f"<p>{_escape_html(p)}</p>" for p in answer_paragraphs)

            parts.append(f"""
<div class="slide">
    <div class="slide-number">{i}</div>
    <div class="question">
        <span class="q-label">Q:</span> {_escape_html(question)}
    </div>
    <div class="answer">
        {answer_html}
    </div>
</div>
""")

    return "\n".join(parts)


def _escape_html(text):
    """Escape HTML special characters while preserving intentional formatting."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    # Preserve bold markdown
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    return text


def _get_css():
    """Return the complete CSS for the export document."""
    return """
/* Base */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Georgia', 'Times New Roman', serif;
    color: #2c2c2c;
    line-height: 1.7;
    background: #ffffff;
}

/* Cover page */
.cover {
    page-break-after: always;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 60px 40px;
}

.cover-border {
    text-align: center;
    border: 3px solid #b8960c;
    border-radius: 4px;
    padding: 80px 60px;
    max-width: 600px;
    width: 100%;
}

.cover h1 {
    font-size: 56px;
    letter-spacing: 12px;
    color: #b8960c;
    margin-bottom: 8px;
    font-weight: 400;
}

.cover .subtitle {
    font-size: 13px;
    color: #666;
    letter-spacing: 1px;
    margin-bottom: 40px;
    font-style: italic;
}

.cover .divider {
    width: 80px;
    height: 2px;
    background: #b8960c;
    margin: 0 auto 40px auto;
}

.cover .doc-title {
    font-size: 22px;
    color: #333;
    margin-bottom: 30px;
}

.cover .doc-date {
    font-size: 14px;
    color: #888;
    margin-bottom: 8px;
}

.cover .doc-org {
    font-size: 16px;
    color: #555;
    margin-bottom: 4px;
}

.cover .doc-contact {
    font-size: 13px;
    color: #888;
}

/* Section headers */
.section-header {
    page-break-before: always;
    padding: 60px 40px 30px 40px;
    max-width: 740px;
    margin: 0 auto;
    border-bottom: 2px solid #b8960c;
    margin-bottom: 30px;
}

.section-header h2 {
    font-size: 32px;
    color: #b8960c;
    font-weight: 400;
    letter-spacing: 2px;
    margin-bottom: 6px;
}

.section-header .section-subtitle {
    font-size: 16px;
    color: #666;
    font-style: italic;
}

.section-header .slide-count {
    font-size: 13px;
    color: #999;
    margin-top: 10px;
}

/* Individual slides */
.slide {
    max-width: 740px;
    margin: 0 auto 40px auto;
    padding: 0 40px;
    page-break-inside: avoid;
    position: relative;
}

.slide-number {
    position: absolute;
    left: 0;
    top: 0;
    width: 28px;
    height: 28px;
    background: #b8960c;
    color: #fff;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-weight: 600;
}

.question {
    font-size: 17px;
    font-weight: 600;
    color: #333;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid #e0e0e0;
    font-family: 'Helvetica Neue', Arial, sans-serif;
}

.q-label {
    color: #b8960c;
    font-weight: 700;
    margin-right: 4px;
}

.answer {
    font-size: 15px;
    color: #444;
    line-height: 1.8;
}

.answer p {
    margin-bottom: 14px;
}

.answer p:last-child {
    margin-bottom: 0;
}

.answer strong {
    color: #333;
}

/* Footer */
.footer-note {
    text-align: center;
    padding: 40px;
    color: #999;
    font-size: 12px;
    border-top: 1px solid #e0e0e0;
    margin-top: 60px;
    max-width: 740px;
    margin-left: auto;
    margin-right: auto;
}

.footer-note p {
    margin: 4px 0;
}

/* Print styles */
@media print {
    body {
        font-size: 11pt;
    }

    .cover {
        min-height: auto;
        padding: 120px 40px;
    }

    .section-header {
        page-break-before: always;
        padding-top: 40px;
    }

    .slide {
        page-break-inside: avoid;
    }

    .footer-note {
        page-break-before: always;
    }

    @page {
        margin: 1in;
    }
}
"""


def render_download_button(key_prefix="slides"):
    """
    Render a Streamlit download button for the slides HTML document.

    Args:
        key_prefix: Unique prefix for the button key to avoid conflicts
    """
    html_content = generate_slides_html(include_demo=True, include_agentic=True)

    st.download_button(
        label="Download Slides (PDF-ready)",
        data=html_content,
        file_name="TELOS_AI_Governance_Demo.html",
        mime="text/html",
        key=f"{key_prefix}_download_slides",
        use_container_width=True
    )
