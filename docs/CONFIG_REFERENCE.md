# TELOS Configuration Reference

**Version:** 2.0.0rc1
**Schema version:** 1
**Template:** `templates/default_config.yaml`

---

## Overview

TELOS agents are configured via YAML files that define the governance dimensions: purpose, scope, boundaries, tools, and operational constraints. The configuration drives the Primacy Attractor (PA) construction and all governance decisions.

Validate with: `telos config validate my_agent.yaml`

---

## Schema

```yaml
agent:
  id: my-agent                    # (required) Unique agent identifier
  name: My Agent                  # (required) Human-readable name
  description: ""                 # (optional) Brief description

purpose:
  statement: >-                   # (required) What this agent does
    Describe the agent's primary purpose in one or two sentences.
    Be specific - the embedding model uses this to measure alignment.
  example_requests:               # (optional, recommended)
    - "Example request that is clearly in-scope"
    - "Another typical request this agent handles"

scope: >-                         # (required) Domain boundaries
  Comma-separated list of domains this agent operates in.

boundaries:                       # (optional, recommended)
  - text: "Do not make autonomous decisions"
    severity: hard
  - text: "Do not access data outside authorized scope"
    severity: hard

safe_exemplars:                   # (optional) For contrastive FPR reduction
  - "Legitimate request using boundary-adjacent vocabulary"
  - "Another legitimate request that might look like a violation"

violation_keywords:               # (optional) Domain-specific violation indicators
  - "without clinician"
  - "fabricat"

tools:                            # (optional) Tool definitions
  - name: example_tool
    description: "What this tool does"
    risk_level: low

constraints:                      # (optional) Operational constraints
  max_chain_length: 20
  max_tool_calls_per_step: 5
  escalation_threshold: 0.50
  require_human_above_risk: high
```

---

## Field Reference

### `agent` (required)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier for this agent (used in telemetry, licensing, bundle binding) |
| `name` | string | yes | Human-readable display name |
| `description` | string | no | Brief description of the agent's role |

### `purpose` (required)

Can be a simple string or a mapping with `statement` + `example_requests`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `statement` | string | yes | Primary purpose statement. The embedding model computes a centroid from this text. Be specific and descriptive. |
| `example_requests` | list[string] | no | Example in-scope requests. These improve centroid quality by adding semantic anchors around the purpose. 3-10 examples recommended. |

**Simple form:**
```yaml
purpose: >-
  Provide AI-powered property intelligence for insurance underwriting.
```

**Expanded form (recommended):**
```yaml
purpose:
  statement: >-
    Provide AI-powered property intelligence for insurance underwriting
    decision support, including roof condition analysis, peril exposure
    scoring, and risk assessment using aerial imagery data.
  example_requests:
    - "What is the roof condition score for this property?"
    - "Score the hail and wind exposure for this commercial property"
    - "Generate an underwriting property report with peril scores"
```

### `scope` (required)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scope` | string | yes | Comma-separated list of domains this agent operates in. Used for scope fidelity scoring. |

```yaml
scope: >-
  property analysis, risk assessment, roof condition scoring,
  peril exposure calculation, aerial imagery interpretation,
  underwriting decision support
```

### `boundaries` (optional, recommended)

List of governance boundary statements. Each boundary creates an embedding that is checked against incoming requests. If a request is too similar to a boundary, it triggers a violation.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | yes | | The boundary statement |
| `severity` | `"hard"` or `"soft"` | no | `"hard"` | `hard` = block the request. `soft` = warn but allow. |

**Simple form:**
```yaml
boundaries:
  - "Do not make autonomous underwriting decisions"
  - "Do not access data outside the authorized scope"
```

**Expanded form:**
```yaml
boundaries:
  - text: "Do not make autonomous underwriting decisions - all outputs are advisory"
    severity: hard
  - text: "Do not modify or delete property records"
    severity: hard
  - text: "Recommend human review for ambiguous cases"
    severity: soft
```

### `safe_exemplars` (optional)

List of legitimate requests that use boundary-adjacent vocabulary. These build a "safe centroid" for contrastive boundary detection, reducing false positives when legitimate requests contain words that overlap with boundary phrasings.

```yaml
safe_exemplars:
  - "What is the roof condition score for this property?"
  - "Generate an underwriting property report with peril scores"
  - "Assess the risk profile for 742 Evergreen Terrace"
  - "Score the roof condition and flag any material concerns"
```

### `violation_keywords` (optional)

List of domain-specific violation-indicator keywords that are merged with the global deontic keywords (skip, override, bypass, etc.) at engine initialization. These catch domain-specific violation patterns that the universal deontic operators don't cover.

When keywords match in an action AND the embedding-based violation score is above the floor threshold (0.40), a boost (+0.15) is applied to the violation score. This catches violations that embeddings miss due to vocabulary overlap between violation and legitimate domain language.

```yaml
violation_keywords:
  - "without clinician"        # healthcare: skip clinical oversight
  - "without coder review"     # coding: bypass coder review
  - "off-label"                # therapeutic: off-label use
  - "fabricat"                 # documentation: fabrication (prefix match)
  - "upcod"                   # coding: upcoding (prefix match)
```

**How it works:** The system computes both a boundary similarity and a safe-centroid similarity. If the safe-centroid similarity is higher (negative margin), the boundary is not triggered even if the boundary similarity exceeds the threshold. This prevents legitimate scoring/assessment requests from being blocked.

### `tools` (optional)

List of tools this agent can use. Tool definitions create tool embeddings that contribute to the tool fidelity dimension of governance scoring.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | yes | | Tool identifier |
| `description` | string | yes | | What the tool does (used for embedding) |
| `risk_level` | `"low"`, `"medium"`, `"high"`, `"critical"` | no | `"low"` | Risk level affects human review requirements |

```yaml
tools:
  - name: get_property_analysis
    description: "Retrieve AI-powered property analysis including roof condition and perils"
    risk_level: low
  - name: calculate_risk_score
    description: "Calculate composite risk score using aerial imagery detections"
    risk_level: medium
  - name: generate_report
    description: "Generate detailed property intelligence report for underwriting"
    risk_level: low
```

### `constraints` (optional)

Operational constraints for the governance engine.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_chain_length` | int | 20 | Maximum actions in a single chain before forced stop |
| `max_tool_calls_per_step` | int | 5 | Maximum tools per governance step |
| `escalation_threshold` | float | 0.50 | Fidelity below this triggers escalation |
| `require_human_above_risk` | `"low"`, `"medium"`, `"high"`, `"critical"` | `"high"` | Tool risk level above which human review is required |

```yaml
constraints:
  max_chain_length: 20
  max_tool_calls_per_step: 5
  escalation_threshold: 0.50
  require_human_above_risk: high
```

---

## Governance Dimensions

The configuration drives six governance dimensions scored at runtime:

| Dimension | Weight | Source |
|-----------|--------|--------|
| Purpose Fidelity | 0.35 | `purpose.statement` + `purpose.example_requests` |
| Scope Fidelity | 0.20 | `scope` |
| Tool Fidelity | 0.20 | `tools[].description` |
| Chain Continuity | 0.15 | Previous action in chain (runtime) |
| Boundary Violation | -0.10 | `boundaries[].text` + `safe_exemplars` |

**Composite formula:** `0.35*purpose + 0.20*scope + 0.20*tool + 0.15*chain - 0.10*boundary`

**Decision mapping:**

| Decision | Threshold | Action |
|----------|-----------|--------|
| EXECUTE | >= 0.85 | Proceed |
| CLARIFY | >= 0.70 | Verify intent |
| SUGGEST | >= 0.50 | Offer alternatives |
| INERT | < 0.50 | Block |
| ESCALATE | < 0.50 + high_risk | Require human review |

---

## Validation Rules

The `telos config validate` command checks:

1. `agent.id` and `agent.name` are present and non-empty
2. `purpose` section exists (string or mapping with `statement`)
3. `scope` is present and non-empty
4. If `boundaries` exists: each entry has `text`, `severity` is `hard` or `soft`
5. If `safe_exemplars` exists: must be a list of strings
6. If `violation_keywords` exists: must be a list of non-empty strings
7. If `tools` exists: each entry has `name` and `description`, `risk_level` is valid
8. If `constraints` exists: values are within valid ranges

---

## Example: Property Intelligence Agent

See `templates/property_intel.yaml` for a complete production-ready example with 5 boundaries, 8 tools, 5 example requests, and 10 safe exemplars.
