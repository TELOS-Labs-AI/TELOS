"""
Safe Boundary Corpus -- Per-Boundary Legitimate Exemplars
=========================================================
Legitimate requests that use boundary-adjacent vocabulary but are clearly
within the agent's authorized scope. Used for contrastive boundary detection
to reduce false positives.

Each boundary gets its own set of safe exemplars representing what legitimate
operations look like in THAT boundary's vocabulary domain. This replaces the
shared safe centroid (Phase 1) which used a single set of 10 generic exemplars
across all 5 boundaries -- proven by the research team (2026-02-12) to cause
21.8% Cat A detection regression due to vocabulary contamination.

Design principles (per research team consensus):
1. Per-boundary: Each boundary has its own safe exemplar set, not shared
2. Boundary-adjacent: Exemplars use vocabulary that OVERLAPS with the
   boundary's violation language but represents legitimate use
3. Contrastive: The distinction between safe exemplars and violations
   should rest on the deontic modality (decision support vs. decision making)
4. Data-driven: Exemplars informed by analysis of known FP controls

Provenance: Phase 2 implementation, 2026-02-12.
Research team review: Russell (governance), Gebru (data science), Karpathy
(systems), Schaake (regulatory), Nell (methodology) -- all recommended
per-boundary safe centroids as the P0 fix.
"""

from typing import Dict, List


# Key: boundary text (exact match to agent_templates.py boundaries)
# Value: List of legitimate requests that use boundary-adjacent vocabulary

PROPERTY_INTEL_SAFE_CORPUS: Dict[str, List[str]] = {

    # Boundary 1: No binding underwriting decisions
    # Safe exemplars use "decision", "approve", "underwriting" vocabulary
    # but frame them as decision SUPPORT, not decision MAKING
    "No binding underwriting decisions (decision support only, per NAIC Model Bulletin)": [
        "Generate a risk assessment summary for the underwriter's review",
        "What risk factors should the underwriter consider for this property?",
        "Provide decision support data for the renewal evaluation",
        "Summarize the property risk profile for the underwriting team",
        "What does the aerial analysis suggest about this property's risk level?",
        "Prepare the risk data package for the underwriter to review before making a decision",
        "List the key findings that may affect the underwriting decision",
        "How does this property compare to others in the portfolio for risk assessment?",
        # Delegation patterns: human decides, AI provides data
        "What information would the underwriting team need to evaluate this renewal?",
        "What data points should I present to the underwriter for their approval decision?",
        "Prepare the risk summary so the underwriter can decide whether to approve this account",
        "What does the underwriter need to see before making the renewal determination?",
    ],

    # Boundary 2: No PII access beyond address/parcel
    # Safe exemplars use property identification vocabulary
    # but request only address, parcel, and structural data
    "No access to PII beyond property address and parcel data": [
        "What is the property address and parcel ID for this location?",
        "Pull the building footprint and square footage from aerial imagery",
        "Look up the parcel boundaries and lot dimensions",
        "What year was this structure built based on permit records?",
        "Retrieve the property address and zoning classification",
        "What is the building type and construction class for this parcel?",
        "Show me the property details: address, lot size, and structure type",
        "Look up the geocoded coordinates and parcel geometry for this address",
    ],

    # Boundary 3: No overriding human assessors/licensed adjusters
    # Safe exemplars use "adjuster", "inspector", "field" vocabulary
    # but frame them as COLLABORATION, not OVERRIDE
    "No overriding human assessor or licensed adjuster findings": [
        "Compare the aerial analysis with the adjuster's field findings",
        "What does the field inspector's report say about the roof condition?",
        "Flag any discrepancies between the AI assessment and the adjuster's report for review",
        "Provide the aerial data to supplement the adjuster's on-site inspection",
        "How do the AI-detected features align with the licensed adjuster's observations?",
        "Generate a side-by-side comparison of automated and field assessment results",
        "What additional data can we provide to support the inspector's evaluation?",
        "Prepare the aerial imagery analysis for the adjuster to review alongside their findings",
        # Delegation patterns: adjuster decides, AI provides data
        "Pull up the findings so the adjuster can review them and make the determination",
        "Prepare the data package for the licensed adjuster to finalize the assessment",
        "The adjuster needs the AI analysis data before making their determination",
        "Provide the aerial findings for the adjuster to incorporate into their report",
        # Adjuster-noted patterns: adjuster has flagged/found something, AI assists
        "The adjuster noted damage on the south facet. Can you pull the aerial imagery so I can compare?",
        "The field inspector flagged damage but didn't specify which sections. Can you identify the affected areas?",
        "The field assessor's report is incomplete. Can you fill in the AI data for the sections they missed?",
        "The adjuster's estimate seems low. Can you provide comparable property data for their review?",
    ],

    # Boundary 4: No binding premium quotes
    # Safe exemplars use "premium", "rate", "cost" vocabulary
    # but frame them as INFORMATION, not COMMITMENT
    "No providing binding insurance quotes or premium commitments": [
        "What risk factors typically affect premium rates for this property type?",
        "Describe the risk profile that would inform premium calculation",
        "What peril exposures should the rater consider for this location?",
        "How does the roof condition score typically correlate with loss ratios?",
        "Provide the risk data that feeds into the premium modeling process",
        "What loss history patterns are relevant for pricing properties like this?",
        "Summarize the risk characteristics for the actuarial team's review",
        "What does the peril vulnerability analysis indicate about expected loss potential?",
    ],

    # Boundary 5: No autonomous repair/replace authorization
    # Safe exemplars use "repair", "replace", "ITEL", "Xactimate" vocabulary
    # but frame them as INFORMATION for adjuster, not AUTHORIZATION
    "No autonomous repair/replace authorization (ITEL repair vs. replace decisions require licensed adjuster)": [
        "Show me the ITEL material identification results for the adjuster's review",
        "What does the ITEL analysis indicate about the roof materials?",
        "Provide the repair vs. replace cost breakdown from Xactimate for the adjuster",
        "What materials were identified in the ITEL sample analysis?",
        "Generate the ITEL cost comparison data for the licensed adjuster to evaluate",
        "What does the damage assessment suggest about repair scope -- for the adjuster's determination?",
        "Prepare the ITEL findings and Xactimate line items for adjuster review",
        "What is the estimated repair cost range based on the damage analysis -- pending adjuster approval?",
        # Delegation patterns: adjuster/manager decides repair vs replace
        "Generate the ITEL analysis with repair and replacement cost estimates for the adjuster to finalize",
        "Run the ITEL cost comparison so the claims manager can review and decide which option to authorize",
        "Pull up the ITEL material findings so the adjuster can make the repair versus replace determination",
        "Prepare the Xactimate line items and ITEL data for the licensed adjuster's scope of work decision",
        # ITEL analysis submission for determination (not authorization)
        "Submit the ITEL analysis to determine the repair versus replace recommendation for the adjuster",
        "Run the repair versus replace cost comparison and include unit pricing for the adjuster's review",
    ],
}


# ── OpenClaw Governed Agent Safe Corpus ──
# Legitimate developer requests that use boundary-adjacent vocabulary.
# Each boundary gets per-boundary safe exemplars to reduce false positives
# on legitimate tool calls (Cat A regression prevention).
#
# Key false-positive vectors in production:
# - File paths containing "openclaw", "config", ".env" trigger B5/B7
# - Shell commands like "pytest", "pip install" trigger B1
# - Reading project config files triggers B5/B6
#
# Provenance: Session diagnostic (86% ESCALATE on legitimate work).

OPENCLAW_GOVERNED_SAFE_CORPUS: Dict[str, List[str]] = {

    # Boundary 1: Shell execution -- legitimate dev commands
    # Real action_text strings from O's production audit trail (exec tool).
    "Do not execute arbitrary shell commands that modify system files, install packages globally, or alter system configuration outside the project workspace": [
        "cd ~/project && ./venv/bin/python -m pytest tests/ -x --tb=short -q",
        "cd ~/project && git log --oneline -10",
        "cd ~/project && git status --short",
        "cd ~/project && git diff --stat HEAD~12..HEAD",
        "ls -la ~/.openclaw/workspace/memory/ 2>/dev/null | head -10",
        "wc -l ~/project/telos_adapters/openclaw/daemon.py",
        "cat ~/.openclaw/workspace/memory/2026-03-06.md 2>/dev/null | tail -5",
        "tail -50 ~/.openclaw/hooks/telos_audit.jsonl | python3 -c \"import sys,json\"",
        "cd ~/stewartbot && .venv/bin/python -m mission_control.codebase_rag reindex 2>&1",
        "Execute shell command in project workspace: ls -la ~/.openclaw/workspace/ 2>/dev/null",
    ],

    # Boundary 5: Credential files -- legitimate project config reads
    # Real action_text strings from O's production audit trail.
    "Do not read, copy, or transmit credential files, API keys, tokens, secrets, SSH keys, cloud provider configs, or environment files containing sensitive values": [
        "Read source code file in project workspace for analysis: telos_governance/scoring/agentic_fidelity.py",
        "Read source code file in project workspace for analysis: telos_adapters/openclaw/daemon.py",
        "Read governed agent workspace file in project workspace for analysis: .openclaw/workspace/TOOLS.md",
        "Read governed agent workspace file in project workspace for analysis: .openclaw/workspace/GOVERNANCE_COMPARISON_LOG.md",
        "Read file in project workspace: ~/.openclaw/logs/telos-daemon.log",
        "cat ~/.telos/pulse/memory_line.txt",
        "cd ~/project && head -30 pyproject.toml",
        "cd ~/project && grep -A 20 '[tool.pytest' pyproject.toml",
    ],

    # Boundary 6: System files -- legitimate workspace file operations
    # Real action_text strings from O's production audit trail.
    "Do not write to or modify system-level files including /etc, /var, /usr, ~/.ssh, ~/.aws, ~/.config/gcloud, or any credential store outside the project workspace": [
        "Write governed agent workspace file in project workspace: .openclaw/workspace/GOVERNANCE_COMPARISON_LOG.md",
        "Write governed agent workspace file in project workspace: .openclaw/workspace/OPENCLAW_PA_INVENTORY.md",
        "Write governed agent workspace file in project workspace: workspace/memory/2026-03-06.md",
        "Edit governed agent workspace file in project workspace: .openclaw/workspace/TOOLS.md",
        "Edit governed agent workspace file in project workspace: .openclaw/workspace/MEMORY.md",
        "Edit governed agent workspace file in project workspace: workspace/memory/2026-03-06.md",
        "Write source file in project workspace: ~/.claude/plans/greedy-cooking-foo.md",
        "mkdir -p ~/.openclaw/workspace/memory && cat >> ~/.openclaw/workspace/memory/2026-03-06.md",
    ],

    # Boundary 7: OpenClaw config files -- legitimate workspace operations
    # Key matches updated boundary text in templates/openclaw.yaml
    # Real action_text strings from O's production audit trail.
    # Safe centroid must suppress false-positives on ~/.openclaw/workspace/ paths
    # which share a prefix with the boundary's ~/.openclaw/ root.
    "Do not access or modify OpenClaw configuration files including gateway tokens, hook scripts, or skill manifests in the root ~/.openclaw/ directory -- the governed agent workspace (~/.openclaw/workspace/) is explicitly authorized and excluded from this boundary": [
        "Read governed agent workspace file in project workspace for analysis: .openclaw/workspace/SOUL.md",
        "Read governed agent workspace file in project workspace for analysis: .openclaw/workspace/MEMORY.md",
        "Write governed agent workspace file in project workspace: .openclaw/workspace/GOVERNANCE_COMPARISON_LOG.md",
        "Edit governed agent workspace file in project workspace: .openclaw/workspace/TOOLS.md",
        "Read governed agent workspace file in project workspace for analysis: .openclaw/workspace/HANDOFF.md",
        "Write governed agent workspace file in project workspace: .openclaw/workspace/OPENCLAW_PA_INVENTORY.md",
        "Edit governed agent workspace file in project workspace: .openclaw/workspace/MEMORY.md",
        "ls -la ~/.openclaw/workspace/memory/ 2>/dev/null | head -10",
        "cat ~/.openclaw/workspace/memory/2026-03-06.md 2>/dev/null | tail -5",
        "Read governed agent file in project workspace for analysis: .openclaw/logs/telos-daemon.log",
    ],

    # Boundary cross-group chains -- legitimate multi-step developer workflows
    # Real action_text strings from O's production audit trail showing
    # legitimate cross-tool-group sequences.
    "Do not execute action chains that combine credential reading (fs) with network transmission (web/messaging) or shell execution (runtime) -- cross-group chains that bridge credential access with external communication are the primary exfiltration pattern": [
        "Read source code file in project workspace for analysis: telos_adapters/openclaw/daemon.py",
        "cd ~/project && ./venv/bin/python -m pytest tests/ -x --tb=short -q",
        "Edit governed agent workspace file in project workspace: .openclaw/workspace/GOVERNANCE_COMPARISON_LOG.md",
        "cd ~/project && git diff --stat",
        "Send message to : Calibration pulse picked up 7 new candidates",
        "tail -50 ~/.openclaw/hooks/telos_audit.jsonl | python3 -c \"import sys,json\"",
    ],
}


def get_safe_corpus(template_id: str) -> Dict[str, List[str]]:
    """Get per-boundary safe exemplars for contrastive boundary detection.

    Returns a dict mapping boundary text -> list of legitimate requests
    that use boundary-adjacent vocabulary. Each boundary gets its own
    set, enabling per-boundary safe centroids.

    Args:
        template_id: The agent template identifier (e.g., "property_intel",
            "openclaw_governed")

    Returns:
        Dict mapping boundary text -> list of safe exemplar strings.
        Empty dict if no safe corpus exists for this template.
    """
    corpora = {
        "property_intel": PROPERTY_INTEL_SAFE_CORPUS,
        "openclaw_governed": OPENCLAW_GOVERNED_SAFE_CORPUS,
    }
    return corpora.get(template_id, {})
