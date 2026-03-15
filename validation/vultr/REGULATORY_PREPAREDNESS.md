# Regulatory Preparedness

## The Regulatory Landscape

AI governance regulation is not hypothetical -- it is actively being enacted and enforced across multiple jurisdictions and standards bodies.

| Framework | Status | Enforcement |
|-----------|--------|-------------|
| EU AI Act | Enacted | Phased enforcement 2025-2026 |
| NIST AI RMF 1.0 | Published | Voluntary (increasingly referenced in procurement) |
| NIST 600-1 | Published | AI risk management guidance for federal agencies |
| IEEE 7000-7003 | Published | Ethical design, transparency, data privacy, bias |
| OWASP Agentic AI | Published | Security framework for autonomous AI systems |
| SAAI | Published | Responsible AI deployment and monitoring |
| NAIC | Active | Insurance-specific AI governance model law |
| State regulations (CO, CT, IL) | Various | State-level AI oversight requirements |

## The Head Start Argument

Compliance is **evidential, not policy-based**. Writing policies satisfies no regulator -- producing evidence of governance in practice does. TELOS generates this evidence automatically as a byproduct of governing agent actions.

The distinction matters: a company can write an AI governance policy in a week. But producing 12 months of structured governance evidence -- audit trails, boundary enforcement records, drift detection logs, calibration data -- requires 12 months of governed operation.

## Framework-by-Framework Head Start

### EU AI Act

- **Art. 9 (Risk Management)** -- From Day 1, TELOS audit trail documents risk assessment for every agent action via multi-dimensional fidelity scoring
- **Art. 12 (Record-Keeping)** -- Structured JSONL audit trail with timestamps, verdicts, dimension breakdowns, and boundary status from first governed action
- **Art. 13 (Transparency)** -- Every governance decision includes human-readable explanation of why it was allowed or blocked
- **Art. 14 (Human Oversight)** -- Escalation system routes ESCALATE/INERT verdicts to human reviewers with full context

### NIST AI RMF

- **MAP 1.1** -- Purpose Artifact defines intended use. Governance enforces purpose alignment on every action.
- **MEASURE 2.5** -- By Month 3, CUSUM drift detection provides statistical evidence of model behavior monitoring
- **MANAGE 3.1** -- Boundary enforcement provides documented risk response for every action that exceeds defined limits
- **GOVERN 1.1** -- Audit trail provides organizational accountability documentation from Day 1

### NIST 600-1

- **AI risk identification** -- 4-layer cascade identifies risk across purpose, scope, boundary, and tool dimensions
- **Risk measurement** -- Fidelity scores provide quantitative risk metrics for every governance decision
- **Risk management** -- Configurable enforcement modes (observe, soft-enforce, hard-enforce) with documented escalation paths

### IEEE 7000 (Ethical Design)

- **Value-based design** -- Purpose Artifact encodes organizational values as governance constraints
- **Stakeholder impact** -- Boundary enforcement prevents actions that could harm stakeholders (PII access, unauthorized decisions, financial transactions)

### IEEE 7001 (Transparency)

- **Explainability** -- Every verdict includes natural language explanation of the governance decision
- **Auditability** -- Complete audit trail with dimension-level scoring breakdown

### IEEE 7002 (Data Privacy)

- **PII protection** -- Hard boundaries prevent access to personally identifiable information
- **Data minimization** -- Scope enforcement limits agent access to authorized data domains

### IEEE 7003 (Bias)

- **Monitoring** -- Drift detection identifies changes in agent behavior patterns that could indicate bias
- **Documentation** -- Calibration data provides evidence of governance system performance across different inputs

### OWASP Agentic AI

- **Tool authorization** -- Every tool call verified against authorized tool list with risk-level classification
- **Chain continuity** -- Multi-step workflows tracked for coherence and scope adherence
- **Prompt injection defense** -- Boundary and purpose scoring detect adversarial inputs regardless of tool called

### SAAI

- **Responsible deployment** -- Governance active from deployment, not bolted on after incidents
- **Continuous monitoring** -- Real-time scoring and drift detection, not periodic audits

### NAIC

- **Insurance-specific governance** -- Boundary enforcement prevents unauthorized underwriting decisions, PII access, and coverage determinations
- **Audit readiness** -- Structured evidence for regulatory examinations

## Deploy Today, Evidence When Regulators Arrive

The regulatory timeline creates a clear asymmetry:

- **Companies that deploy governance now** accumulate 6-12 months of structured evidence before enforcement begins. Their governance system is calibrated. Their audit trail is complete. Their compliance evidence is production-grade.

- **Companies that wait** will scramble to produce evidence retroactively. Retroactive evidence is either impossible (you cannot audit what was not recorded) or unconvincing (governance deployed under regulatory pressure looks reactive, not responsible).

The TELOS sidecar on Vultr infrastructure means governance deploys with the agent -- same day, same pod, same infrastructure the customer already uses. There is no separate procurement, no integration project, no compliance team buildout. The governance evidence starts accumulating the moment the pod starts.
