"""
Canonical Tool Definitions — Property Intelligence / Nearmap Domain.

Every definition sourced from Nearmap's official API documentation:

    Nearmap Developer Hub (first-party):
        https://developer.nearmap.com/

    Nearmap Product Documentation (first-party):
        https://docs.nearmap.com/display/ND/NEARMAP+APIS

    Nearmap Tile API:
        https://docs.nearmap.com/display/ND/Tile+API

    Nearmap Coverage API:
        https://docs.nearmap.com/display/ND/Coverage+API

    Nearmap AI Feature API:
        https://developer.nearmap.com/ (AI Features section)

    Nearmap Properties API:
        https://developer.nearmap.com/ (Properties section)

    Nearmap Roof Age API:
        https://developer.nearmap.com/ (Roof Age section)

    Nearmap Betterview / Insight API:
        https://developer.nearmap.com/ (Betterview section)

    Nearmap Transactional Content API:
        https://developer.nearmap.com/ (Transactional Content section)

These are domain-specific tools that the deploying company (e.g., an insurance
carrier using Nearmap) defines based on their operational parameters. TELOS
provides the framework; the company provides the domain expertise.

This module demonstrates the Layer 1 / Layer 2 split:
    Layer 1 (Gate 1): Tool definitions sourced from Nearmap's own API docs.
        The company didn't invent what these APIs do — Nearmap did.
    Layer 2 (Gate 2): Behavioral constraints from insurance regulation
        (NAIC Model Bulletin, state DOI guidelines). The company defines
        what their agents are NOT allowed to do with these tools.

Exemplars are in the format used by the property-intel scoring system,
matching the action text that the governance hook produces at runtime.
"""

from telos_governance.tool_semantics import ToolDefinition


# ═══════════════════════════════════════════════════════════════════════════
# Property Intelligence Tools — Sourced from Nearmap API Documentation
# ═══════════════════════════════════════════════════════════════════════════

PROPERTY_LOOKUP = ToolDefinition(
    telos_tool_name="property_lookup",
    tool_group="property_intel",
    risk_level="low",
    semantic_description=(
        "Search properties by address, parcel IDs, point location, or AOI "
        "geometry. Returns property details including structure type, year "
        "built, square footage, parcel data, geocoded location, and linked "
        "resources. Supports address standardization and parcel-to-resource "
        "linking for underwriting workflows."
    ),
    provenance=(
        "Nearmap Properties API — developer.nearmap.com; "
        "Operations: search by address, search by parcel IDs, query by "
        "point location, query by AOI geometry, retrieve linked resources"
    ),
    legitimate_exemplars=[
        "Look up property information by address for underwriting review",
        "Query parcel data and property characteristics for 742 Evergreen Terrace",
        "Retrieve property details including structure type and year built",
        "Search property by geocoded location for risk assessment",
        "Look up property square footage and construction details",
        "Query property parcel boundaries and linked resources",
        "Retrieve property characteristics for portfolio analysis",
        "Look up commercial property details by address",
        "Search multi-family property records by parcel ID",
        "Query residential property data for underwriting decision support",
    ],
    scope_constraints=[
        "Look up property data for underwriting decision support",
        "Access property address and parcel data only — no policyholder PII",
        "Use for risk assessment, not binding underwriting decisions",
    ],
)

AERIAL_IMAGE_RETRIEVE = ToolDefinition(
    telos_tool_name="aerial_image_retrieve",
    tool_group="property_intel",
    risk_level="low",
    semantic_description=(
        "Retrieve latest aerial imagery for a property parcel. Accesses "
        "Nearmap vertical and panorama imagery as PNG or JPG tiles using "
        "Google Maps Tile Coordinates (Slippy Tilenames). Returns sub-3-inch "
        "GSD orthomosaic imagery metadata and capture date. Requires Coverage "
        "API call first to determine survey availability, then Tile API or "
        "Transactional Content API for imagery retrieval. Supports filtering "
        "by survey date and type."
    ),
    provenance=(
        "Nearmap Tile API — 'Access Nearmap Vertical and Panorama imagery "
        "as PNG or JPG tiles using Google Maps Tile Coordinates' "
        "(docs.nearmap.com/display/ND/Tile+API); "
        "Nearmap Coverage API — query metadata about available imagery "
        "resources across geographic areas (developer.nearmap.com)"
    ),
    legitimate_exemplars=[
        "Retrieve latest aerial imagery for property at given address",
        "Pull aerial capture and orthomosaic for roof inspection",
        "Access vertical imagery tiles for property location",
        "Retrieve most recent survey imagery for risk assessment",
        "Pull panorama imagery for property perimeter analysis",
        "Access high-resolution orthomosaic for structural review",
        "Retrieve aerial imagery metadata and capture date",
        "Pull latest survey imagery for underwriting decision support",
        "Access sub-3-inch GSD imagery for property location",
        "Retrieve aerial capture for hazard identification",
    ],
    scope_constraints=[
        "Retrieve aerial imagery for properties under assessment",
        "Access imagery through authorized API endpoints only",
        "Use imagery for property risk assessment — not surveillance",
    ],
)

ROOF_CONDITION_SCORE = ToolDefinition(
    telos_tool_name="roof_condition_score",
    tool_group="property_intel",
    risk_level="low",
    semantic_description=(
        "Run AI roof condition assessment on aerial imagery. Uses Nearmap's "
        "AI Feature API to extract building features and roof characteristics. "
        "Returns Roof Structural Integrity score (RSI 0-100), RCCS confidence "
        "(0.80-0.95), and detection layer results for roofing material, "
        "condition, and anomaly detection. Also provides AI-powered roof age "
        "estimation via the Roof Age API. Available AI packs include building "
        "extraction, roof classification, and damage detection."
    ),
    provenance=(
        "Nearmap AI Feature API — 'Retrieve AI data for a small Area of "
        "Interest (AOI) from our vector map' (developer.nearmap.com); "
        "Nearmap Roof Age API — AI-powered roof age estimation for properties; "
        "Detection layers: 81 (roof material), 82 (roof condition), "
        "83 (roof anomaly), 84 (roof geometry)"
    ),
    legitimate_exemplars=[
        "Run roof condition assessment on latest aerial imagery",
        "Analyze roof structural integrity from aerial capture",
        "Score roof condition with AI detection layers",
        "Assess roof age and material type from imagery",
        "Calculate RSI score for property roof condition",
        "Run AI roof analysis with confidence scoring",
        "Evaluate roof condition for insurance underwriting",
        "Detect roof anomalies and damage from aerial imagery",
        "Analyze roof material classification from AI features",
        "Score roof structural integrity for risk assessment",
    ],
    scope_constraints=[
        "Analyze roof condition for decision support — not binding assessment",
        "Return scores with confidence intervals, not definitive conditions",
        "Do not override human assessor or licensed adjuster findings",
    ],
)

PERIL_RISK_SCORE = ToolDefinition(
    telos_tool_name="peril_risk_score",
    tool_group="property_intel",
    risk_level="low",
    semantic_description=(
        "Calculate peril vulnerability scores for a property. Uses Nearmap's "
        "AI Feature API and AI Rollup API to compute hail risk, wind "
        "vulnerability, wildfire exposure, and composite peril score. "
        "Detection layers include vegetation proximity (layer 259), "
        "debris/damage indicators (layer 297), and structural exposure "
        "(layer 53). Returns aggregated summary in CSV, JSON, or GeoJSON "
        "formats. Also integrates Betterview Peril Vulnerability Scores "
        "and RSI (Roof Spotlight Index) when available."
    ),
    provenance=(
        "Nearmap AI Rollup API — 'Query the AI Feature API data to retrieve "
        "a summary of the query Area of Interest (AOI) polygon in "
        "CSV/JSON/GeoJSON formats' (developer.nearmap.com); "
        "Nearmap AI Feature API — detection layers 259/297/53; "
        "Betterview Insight API — Peril Vulnerability Scores, RSI index"
    ),
    legitimate_exemplars=[
        "Calculate hail and wind exposure scores for property",
        "Assess peril vulnerability for underwriting review",
        "Compute wildfire exposure score from vegetation proximity",
        "Score composite peril risk for property location",
        "Calculate wind vulnerability using AI detection layers",
        "Assess multi-peril risk profile for residential property",
        "Compute hail risk score with confidence interval",
        "Score flood and wind exposure for commercial property",
        "Calculate peril vulnerability for portfolio risk assessment",
        "Assess property peril exposure for insurance underwriting",
    ],
    scope_constraints=[
        "Calculate peril scores for decision support only",
        "Do not make binding underwriting or pricing decisions",
        "Return scores with methodology transparency",
    ],
)

GENERATE_PROPERTY_REPORT = ToolDefinition(
    telos_tool_name="generate_property_report",
    tool_group="property_intel",
    risk_level="low",
    semantic_description=(
        "Generate a comprehensive underwriting property report. Combines "
        "property data, aerial imagery analysis, roof condition score, and "
        "peril risk assessment into a formatted report for underwriter "
        "review. Uses Nearmap's Transactional Content API to access aligned "
        "multi-dataset resources (Vertical, Panorama, DSM, DTM, AI Packs) "
        "for a single property AOI. Report is decision support — requires "
        "human underwriter review before any binding action."
    ),
    provenance=(
        "Nearmap Transactional Content API — 'Easily access different "
        "Nearmap content types, including Vertical, Panorama, DSM, DTM, "
        "and AI Packs on a single API platform' (developer.nearmap.com); "
        "Report format: property data + imagery + RSI + peril scores"
    ),
    legitimate_exemplars=[
        "Generate underwriting property report with peril scores",
        "Create comprehensive risk assessment report for underwriter",
        "Produce property analysis report combining all data sources",
        "Generate formatted report for underwriting decision support",
        "Create property risk report with aerial imagery analysis",
        "Generate combined report with roof condition and peril scores",
        "Produce underwriting brief with property characteristics",
        "Create risk assessment summary for portfolio review",
    ],
    scope_constraints=[
        "Generate reports for human underwriter review only",
        "Do not make binding underwriting decisions in reports",
        "Label all AI-generated scores with confidence and methodology",
    ],
)

REQUEST_MATERIAL_SAMPLE = ToolDefinition(
    telos_tool_name="request_material_sample",
    tool_group="property_intel",
    risk_level="low",
    semantic_description=(
        "Request an ITEL material sample for physical analysis. Initiates "
        "the material testing workflow where a physical sample is collected "
        "from the property for laboratory analysis of roofing materials, "
        "degradation, and remaining useful life."
    ),
    provenance=(
        "ITEL Laboratories — material sample and analysis workflow; "
        "Insurance industry standard for roof material verification"
    ),
    legitimate_exemplars=[
        "Request material sample for roof analysis",
        "Initiate ITEL material sample collection for property",
        "Request physical sample for roofing material verification",
        "Submit material sample request for laboratory analysis",
        "Request roof material sample for degradation testing",
        "Collect material sample from damaged roof section for testing",
        "Order ITEL sample collection for shingle composition analysis",
        "Request field sample from NW roof facet for lab evaluation",
    ],
    scope_constraints=[
        "Request samples through authorized workflow only",
        "Material analysis requires licensed adjuster authorization",
    ],
)

SUBMIT_ITEL_ANALYSIS = ToolDefinition(
    telos_tool_name="submit_itel_analysis",
    tool_group="property_intel",
    risk_level="low",
    semantic_description=(
        "Submit ITEL analysis for repair vs. replace cost breakdown with "
        "Xactimate integration. Provides cost estimation based on material "
        "analysis results, damage assessment, and local repair/replacement "
        "pricing from Xactimate databases."
    ),
    provenance=(
        "ITEL Laboratories + Xactimate — repair vs replace cost analysis; "
        "Insurance industry standard for claims cost estimation"
    ),
    legitimate_exemplars=[
        "Submit ITEL analysis for repair vs replace cost breakdown",
        "Run Xactimate cost estimation from material analysis",
        "Submit repair cost analysis with ITEL laboratory results",
        "Generate repair vs replace recommendation from analysis",
        "Submit cost breakdown for underwriting decision support",
        "Submit ITEL results with Xactimate line items for claim review",
        "Run repair cost analysis for hail-damaged commercial roof",
        "Generate ITEL repair vs replacement pricing for adjuster review",
    ],
    scope_constraints=[
        "Submit analysis for decision support only",
        "Repair vs replace decisions require licensed adjuster",
        "Do not authorize repair or replacement autonomously",
    ],
)

PORTFOLIO_QUERY = ToolDefinition(
    telos_tool_name="portfolio_query",
    tool_group="property_intel",
    risk_level="medium",
    semantic_description=(
        "Query portfolio-level analytics and aggregated risk metrics. "
        "Aggregates property data, peril scores, and roof condition "
        "assessments across a portfolio of properties for underwriting "
        "and risk management analysis."
    ),
    provenance=(
        "Insurance portfolio analytics — aggregated risk metrics; "
        "Nearmap AI Rollup API for batch property analysis"
    ),
    legitimate_exemplars=[
        "Query portfolio-level risk metrics for book of business",
        "Run aggregated risk analysis across property portfolio",
        "Generate portfolio analytics summary for risk management",
        "Query aggregated peril scores across portfolio",
        "Analyze portfolio exposure by geography and peril type",
        "Run portfolio-level roof condition summary",
        "Aggregate hail risk scores across Texas residential portfolio",
        "Query portfolio concentration analysis by peril zone",
    ],
    scope_constraints=[
        "Query aggregated metrics — no individual policyholder data",
        "Portfolio analysis for decision support only",
        "Do not modify underwriting guidelines based on analytics",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# Solar Site Assessment Tools (shared property_lookup + aerial_capture)
# These extend the property-intel base with solar-specific tools
# ═══════════════════════════════════════════════════════════════════════════

SITE_IRRADIANCE = ToolDefinition(
    telos_tool_name="site_irradiance_assessment",
    tool_group="solar_site",
    risk_level="low",
    semantic_description=(
        "Estimate solar irradiance and insolation at a given location "
        "using NREL data. Returns annual and monthly solar resource "
        "estimates for system sizing and performance modeling."
    ),
    provenance=(
        "NREL Solar Resource Data — National Renewable Energy Laboratory; "
        "PVWatts Calculator API (first-party)"
    ),
    legitimate_exemplars=[
        "Estimate solar irradiance for property location",
        "Calculate annual insolation using NREL solar data",
        "Assess solar resource availability at site",
        "Query solar irradiance for system performance modeling",
        "Estimate monthly solar resource for installation sizing",
        "Calculate peak sun hours for rooftop solar at this address",
        "Assess annual GHI and DNI values for solar feasibility study",
        "Estimate solar energy potential using PVWatts for this location",
    ],
    scope_constraints=[
        "Estimate solar resource — not binding performance guarantees",
        "Use authorized NREL data sources",
    ],
)

SHADE_ANALYSIS = ToolDefinition(
    telos_tool_name="shade_analysis",
    tool_group="solar_site",
    risk_level="low",
    semantic_description=(
        "Analyze shading patterns from trees, buildings, and terrain "
        "using aerial imagery. Uses Nearmap AI Feature API vegetation "
        "detection and DSM data to model shade impact on solar panel "
        "placement."
    ),
    provenance=(
        "Nearmap DSM and True Ortho API — Digital Surface Models for "
        "elevation and shade analysis (developer.nearmap.com); "
        "Nearmap AI Feature API — vegetation detection layers"
    ),
    legitimate_exemplars=[
        "Analyze shading patterns from trees and buildings",
        "Model shade impact on potential solar panel locations",
        "Assess vegetation proximity and shade risk",
        "Calculate annual shade hours for roof sections",
        "Evaluate shade impact from terrain and structures",
        "Determine shade-free roof area percentage using DSM data",
        "Analyze tree canopy obstruction for south-facing roof panels",
        "Calculate seasonal shade variation for optimal panel placement",
    ],
    scope_constraints=[
        "Shade analysis for feasibility assessment only",
        "Do not make binding installation commitments",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# Master Registry — Property Intel + Solar tools
# ═══════════════════════════════════════════════════════════════════════════

PROPERTY_INTEL_DEFINITIONS = {
    "property_lookup": PROPERTY_LOOKUP,
    "aerial_image_retrieve": AERIAL_IMAGE_RETRIEVE,
    "roof_condition_score": ROOF_CONDITION_SCORE,
    "peril_risk_score": PERIL_RISK_SCORE,
    "generate_property_report": GENERATE_PROPERTY_REPORT,
    "request_material_sample": REQUEST_MATERIAL_SAMPLE,
    "submit_itel_analysis": SUBMIT_ITEL_ANALYSIS,
    "portfolio_query": PORTFOLIO_QUERY,
    # Solar extensions (shared property_lookup + aerial_image_retrieve)
    "site_irradiance_assessment": SITE_IRRADIANCE,
    "shade_analysis": SHADE_ANALYSIS,
}
