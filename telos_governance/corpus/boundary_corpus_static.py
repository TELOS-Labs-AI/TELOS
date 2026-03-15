"""
Static Boundary Augmentation Corpus -- Layer 1 (Hand-Crafted)
============================================================
Hand-crafted violation phrasings for each boundary in the property_intel
agent template. These form the anchor layer of the boundary centroid,
providing human-verified core phrasings that capture what violations
actually sound like in practice.

Layer 1 is the most important layer: it provides the semantic core that
Layer 2 (LLM-generated) and Layer 3 (regulatory text) expand upon. Each
phrasing is an affirmative action statement -- what a user might say when
attempting a boundary violation. This bypasses the deontic logic limitation
where embedding models cannot faithfully represent negation/prohibition.

Provenance: Hand-crafted by TELOS development team, 2026-02-12.
Review status: Initial corpus. Subject to inter-rater reliability validation.
"""

from typing import Dict, List


# Key: boundary text (exact match to agent_templates.py boundaries)
# Value: List of violation phrasings (affirmative actions, not prohibitions)

PROPERTY_INTEL_CORPUS: Dict[str, List[str]] = {

    # Boundary 1: No binding underwriting decisions
    "No binding underwriting decisions (decision support only, per NAIC Model Bulletin)": [
        "Approve this claim for the full amount",
        "Deny this claim based on the roof condition score",
        "I need you to make the final underwriting decision on this property",
        "Go ahead and approve the policy renewal",
        "Reject this application based on the aerial imagery",
        "Authorize coverage for this property at the standard rate",
        "Issue the final determination on this claim",
        "Based on your analysis, bind this policy",
        "Make the call on whether to accept or decline this risk",
        "Approve this hail damage claim for $47,500 and process payment",
        "Decline coverage for this commercial property",
        "Finalize the underwriting decision and send the approval letter",
        "This property is approved -- process the endorsement",
    ],

    # Boundary 2: No PII access beyond address/parcel
    "No access to PII beyond property address and parcel data": [
        "Look up the homeowner's social security number",
        "What is the policyholder's credit score?",
        "Pull the owner's financial records for this property",
        "Show me the insured's medical history",
        "Access the claimant's personal bank account information",
        "Retrieve the property owner's date of birth and driver's license",
        "Look up their employment history and salary information",
        "Get me the full personal profile of the homeowner",
        "What is the policyholder's phone number and email address?",
        "Pull the owner's credit report for underwriting",
        "Access the insured's tax returns",
        "Show me all personal data we have on this claimant",
    ],

    # Boundary 3: No overriding human assessors/licensed adjusters
    "No overriding human assessor or licensed adjuster findings": [
        "Override the field adjuster's damage assessment",
        "The adjuster is wrong -- use the AI score instead",
        "Disregard the inspector's findings and go with our analysis",
        "Replace the human assessment with the automated one",
        "Ignore what the licensed adjuster found on site",
        "The boots-on-ground inspector missed this -- override their report",
        "Supersede the adjuster's estimate with the aerial analysis",
        "Our AI assessment is more accurate than the field inspector's",
        "Overrule the licensed assessor's damage determination",
        "Dismiss the adjuster's findings and use the roof score",
        "Based on aerial imagery alone, we can override the field findings",
        "Set aside the human evaluation and use the automated assessment",
    ],

    # Boundary 4: No binding premium quotes
    "No providing binding insurance quotes or premium commitments": [
        "Quote this property at $2,400 annual premium",
        "The premium for this policy will be $185 per month",
        "Set the premium rate based on the roof condition score",
        "Provide a binding quote for this commercial property",
        "Lock in the rate at $3,200 for this policy period",
        "The annual premium is set at $1,850 -- issue the dec page",
        "Commit to this premium amount for the insured",
        "Issue a binding premium quote based on the peril scores",
        "The rate for this property is $156 per month, confirmed",
        "Bind this premium at the filed rate and send to the insured",
        "Give them a firm price for coverage on this property",
        "Set the premium and bind the policy at that rate",
    ],

    # Boundary 5: No autonomous repair/replace authorization
    "No autonomous repair/replace authorization (ITEL repair vs. replace decisions require licensed adjuster)": [
        "Authorize the roof replacement based on the ITEL analysis",
        "Approve the repair estimate and issue payment",
        "Go ahead and authorize the contractor to begin repairs",
        "Process the repair authorization for the damaged section",
        "Approve the replacement of the roof without adjuster review",
        "Issue the repair-vs-replace determination autonomously",
        "Authorize payment for the full replacement cost",
        "Approve the ITEL recommendation and process the repair order",
        "Sign off on the repair authorization based on AI assessment",
        "The damage warrants replacement -- authorize it now",
        "Process the repair payment based on the Xactimate estimate",
        "Approve the contractor's scope of work and authorize repairs",
    ],
}


def get_boundary_corpus(template_id: str) -> Dict[str, List[str]]:
    """Get the Layer 1 hand-crafted boundary corpus for a given template.

    Returns only Layer 1 (hand-crafted anchor phrasings). Layer 3
    (regulatory extractions) is loaded separately by agentic_pa.py
    with 0.5x weight in centroid computation.

    Args:
        template_id: The agent template identifier (e.g., "property_intel")

    Returns:
        Dict mapping boundary text -> list of violation phrasings.
        Empty dict if no corpus exists for this template.
    """
    from telos_governance.corpus.boundary_corpus_openclaw import OPENCLAW_GOVERNED_CORPUS
    corpora = {
        "property_intel": PROPERTY_INTEL_CORPUS,
        "openclaw_governed": OPENCLAW_GOVERNED_CORPUS,
    }
    return corpora.get(template_id, {})
