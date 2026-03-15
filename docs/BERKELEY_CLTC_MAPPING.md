# TELOS Mapping to UC Berkeley CLTC Agentic AI Risk-Management Standards Profile

**Date:** 2026-02-22
**For:** Jeffrey Brunner, Founder, TELOS AI Labs Inc.
**Source Document:** Madkour, Newman, Raman, Jackson, Murphy, Yuan. "Agentic AI Risk-Management Standards Profile." Version 1.0, February 2026. UC Berkeley Center for Long-Term Cybersecurity, AI Security Initiative.
**URL:** https://cltc.berkeley.edu/publication/agentic-ai-risk-management-standards-profile

> **Generative AI Disclosure:** This document was developed with assistance from an LLM-based agent (Claude, Anthropic). The mapping draws on the full text of the Berkeley CLTC Agentic AI Profile (54 pages) and the TELOS Framework Whitepaper v3.0, CLAUDE.md development guide, and existing validation artifacts. All TELOS implementation claims reference specific files, components, or test results in the TELOS repository. This is not independent third-party validation.

> **Conflict of Interest Disclosure:** This analysis was developed for TELOS AI Labs Inc. by an AI agent operating within the TELOS development environment. TELOS AI Labs has a commercial interest in demonstrating alignment with governance standards.

---

## Executive Summary

The UC Berkeley CLTC Agentic AI Risk-Management Standards Profile is a specialized extension of the NIST AI Risk Management Framework (AI RMF) for agentic AI systems. Published February 2026 by Berkeley's AI Security Initiative, it provides targeted practices and controls organized around the four NIST AI RMF core functions: **Govern, Map, Measure, and Manage**.

The Profile identifies **12 high-priority subcategories** requiring attention for agentic AI governance. TELOS provides implementation-level coverage for the majority of these subcategories, with particularly strong alignment in areas involving runtime governance, graduated intervention, emergency shutdown mechanisms, risk tiering, dimensional assessment, and continuous monitoring.

### Coverage Summary

| Coverage Level | Count | Subcategories |
|---|---|---|
| **Strong** (direct implementation) | 8 | Govern 1.4, Govern 1.7, Govern 2.1, Map 1.5, Map 5.1, Manage 1.1, Manage 2.4, Manage 4.1 |
| **Partial** (architectural support, not full scope) | 3 | Measure 1.1, Measure 3.2, Manage 2.3 |
| **Organizational** (requires deployer practices, not tooling) | 4 | Govern 4.2, Govern 5.1, Govern 6.1, Map 1.1 |
| **Out of Scope** (evaluation/red-teaming focus) | 2 | Measure 2.7, Map 3.5 |

**Key finding:** The Berkeley Profile reads like a requirements specification for a system TELOS has already built. The alignment is structural, not retrofitted -- TELOS's Govern/Map/Measure/Manage whitepaper organization (Section 1.3) predates this Profile. The convergence reflects independent derivation from the same NIST AI RMF foundation.

---

## Part 1: High-Priority Subcategory Mapping

### Govern 1.4 -- AI-Interpretable Governance Frameworks

**Profile Requirement (p. 17):**
> "Consider translating key governance documents into structured, AI-interpretable frameworks. This procedure allows agentic systems not only to operate under human-directed rules but also to access and act in accordance with organizational safety and risk priorities in real time."

> "When implementing this translation, a critical distinction must be made between a framework that is AI-interpretable and one that is AI-writable. While making the framework AI-interpretable is a recommended control for enabling safer autonomy, allowing an AI to *modify* its own framework is a high-risk activity."

**TELOS Implementation:** STRONG

| Profile Requirement | TELOS Component | Implementation |
|---|---|---|
| Translate governance to AI-interpretable frameworks | Primacy Attractor (PA) YAML configs | Purpose, scope, boundaries, authorized tools, and risk tolerances encoded as structured YAML that the governance engine reads at runtime |
| Framework must be AI-interpretable (read-only) | PA configs are read-only to the agent | The agent cannot modify its own PA. Only the human governor can update the PA specification |
| AI-writable frameworks are high-risk | PA immutability by design | No API or mechanism exists for the governed agent to write to its own PA. The governance engine reads the PA; the agent is scored against it |
| Frameworks must be measurable and verifiable | 6-dimensional scoring + cosine fidelity | Every governance decision is measured against the PA and produces a signed receipt with dimensional scores |
| Agent-specific policies for tool access, decision authority, sub-goals | PA YAML schema | `authorized_tools`, `boundaries`, `scope`, `purpose` fields in every PA config. See `templates/` directory for 9 production configs |

**Evidence:**
- `templates/default_config.yaml` -- annotated PA config template
- `templates/property_intel.yaml` -- Nearmap domain-specific PA
- `templates/healthcare/` -- 7 healthcare agent configs (ambient, call_center, coding, diagnostic, patient_facing, predictive, therapeutic)
- `templates/openclaw.yaml` -- OpenClaw autonomous agent config (17 boundaries, 36 tools, 10 groups)
- `telos_governance/config.py` -- YAML schema validation and loading

**Qualification:** PA configs are static YAML files. The Profile also envisions dynamic policy updates (e.g., organizational risk posture changes propagating to running agents). TELOS supports PA reloading per-session but does not yet have automated policy propagation from an organizational policy store.

---

### Govern 1.7 -- Emergency Shutdowns and Decommissioning

**Profile Requirement (p. 19-20):**
> "Real-time monitoring systems should be equipped with emergency automated shutdowns and be triggered by certain activities (e.g., access to systems or data outside of the agent's authorized scope) or crossed risk thresholds."

> "Establish shutdown protocols based on severity levels, determining the need for partial or complete shutdown."

> "Consider selectively restricting specific agent capabilities, authorizations, and access to resources in response to certain triggers."

> "In addition to automatic emergency shutdown, manual shutdown methods should be available as a last-resort control measure."

**TELOS Implementation:** STRONG

| Profile Requirement | TELOS Component | Implementation |
|---|---|---|
| Emergency automated shutdowns | INERT verdict + ESCALATE verdict | When composite fidelity drops below 0.50, agent is halted (INERT) or escalated to human (ESCALATE). Triggered automatically, pre-execution |
| Triggered by out-of-scope access or crossed thresholds | Boundary corpus + fidelity thresholds | 3-layer boundary corpus (61 hand-crafted + 121 LLM-generated + 48 regulatory) checked every tool call. Thresholds: EXECUTE >= 0.85, CLARIFY 0.70-0.84, SUGGEST 0.50-0.69, INERT/ESCALATE < 0.50 |
| Severity-based shutdown protocols (partial vs complete) | 5-verdict graduated system | CLARIFY = partial restriction (verify intent). SUGGEST = further restriction (offer alternatives). INERT = full halt (acknowledge limitation). ESCALATE = full halt + require human review. Implements Ostrom DP5 graduated sanctions |
| Selectively restricting capabilities | RESTRICT enforcement | SAAI Drift detection triggers selective capability restriction. Agent can continue operating with reduced tool access rather than full shutdown |
| Manual shutdown methods | Permission Controller + ESCALATE | Human governor can override any automated decision, terminate session, or modify PA at any time. Authority buttons in TELOSCOPE UI |
| Failover procedures for non-AI backup | Fail-policy per governance preset | OpenClaw adapter: strict/balanced presets = fail-closed (deny on governance unavailability). Permissive = fail-open. Configurable per deployment |
| Anti-circumvention safeguards | Governance operates at orchestration layer | Agent cannot bypass governance because it operates above the model layer. Tool calls are intercepted before execution, not after |

**Evidence:**
- `telos_governance/agentic_fidelity.py` -- 5-verdict decision logic
- `telos_governance/governance_protocol.py` -- ESCALATE handling
- `telos_core/constants.py` -- threshold values
- `telos_adapters/openclaw/governance_hook.py` -- pre-execution interception
- `telos_adapters/openclaw/plugin/src/bridge.ts` -- fail-policy implementation

**Qualification:** The Profile also mentions documenting system dependencies for isolation during shutdown and training staff on intervention protocols. These are organizational practices that TELOS enables (via governance receipts and audit trails) but does not itself perform.

---

### Govern 2.1 -- Roles, Responsibilities, and Human Authority

**Profile Requirement (p. 20-21):**
> "Ensure agentic AI is a tool under human oversight, not a 'peer' or 'subordinate' in the workforce."

> "Define clear boundaries for final decision-making, roles, and responsibilities for both human managers and agentic AI systems."

> "Define specific checkpoints within the agent's workflow where human oversight is required. These checkpoints may also be triggered by specific actions (e.g., deviating from expected behavior) or conditions (e.g., escalation of risk)."

**TELOS Implementation:** STRONG

| Profile Requirement | TELOS Component | Implementation |
|---|---|---|
| AI as tool under human oversight | Principal-agent architecture | PA is defined by human governor (principal). Agent (subordinate) is scored against it. The governance control plane is subordinate to the human, not autonomous |
| Clear boundaries for decision-making | PA YAML boundaries + authorized tools | Human defines exactly what the agent may and may not do. Boundaries are explicit, machine-readable, and enforced |
| Checkpoints triggered by deviations | Every tool call is a checkpoint | TELOS evaluates every proposed action before execution. Deviations from PA trigger graduated intervention. This is continuous, not periodic |
| Escalation conditions | ESCALATE verdict | When the governance engine cannot confidently classify an action, it defers to the human principal. Russell's deference-under-uncertainty as core alignment property |

**Evidence:**
- `telos_governance/governance_protocol.py` -- principal-agent accountability structure
- Whitepaper Section 1.3 -- Govern/Map/Measure/Manage framework with explicit principal-agent framing
- `research/convergence_to_compliance.md` -- theoretical grounding (Jensen & Meckling 1976, Bovens 2007)

---

### Map 1.5 -- Risk Tolerances and Risk Tiers

**Profile Requirement (p. 32):**
> "When establishing risk tolerances, risk thresholds, or 'risk tiers,' determine several tiers of risk below intolerable thresholds or 'red lines' to provide adequate time to respond to an agentic AI system approaching the intolerable threshold."

> "When defining risk tiers, organizations should establish clear measurable categories based on system capabilities."

> "Account for uncertainty... Leave some margin of safety... Employ transparency reporting."

**TELOS Implementation:** STRONG

| Profile Requirement | TELOS Component | Implementation |
|---|---|---|
| Multiple risk tiers below intolerable threshold | 5-verdict system with calibrated thresholds | EXECUTE (>= 0.85) → CLARIFY (0.70-0.84) → SUGGEST (0.50-0.69) → INERT (< 0.50) → ESCALATE (< 0.50 + high_risk). Four tiers between "proceed" and "full stop" |
| Clear measurable categories | Cosine similarity + 6-dimensional scoring | Purpose alignment, scope compliance, boundary adherence, tool authorization, chain continuity, risk level -- all measured numerically |
| Account for uncertainty | Confidence margins in decision logic | CLARIFY verdict exists specifically for the uncertainty zone. Agent doesn't proceed or halt -- it seeks verification. Decision floor prevents false positives |
| Margin of safety | Conservative thresholds | EXECUTE requires >= 0.85 (not 0.50). Substantial safety margin between "aligned" and "proceed." Governance Configuration Optimizer validates thresholds across 5,212 scenarios |
| Transparency reporting | Governance receipts (Ed25519-signed) | Every decision produces a cryptographically signed receipt containing all dimensional scores, the verdict, and the reasoning. Full audit trail |

**Evidence:**
- `telos_core/constants.py` -- threshold definitions
- `telos_governance/agentic_fidelity.py` -- multi-tier decision logic
- `telos_governance/receipt_signer.py` -- Ed25519 + HMAC-SHA512 signed receipts
- Governance Configuration Optimizer -- 7 benchmarks, 5,212 scenarios validating threshold calibration

---

### Map 5.1 -- Dimensional Governance

**Profile Requirement (p. 36-38):**
> "Dimensional governance assesses where a system stands based on the interplay of multiple dimensions, characteristics, and properties, rather than making governance decisions based on any single static category or classification."

> "Define agent autonomy levels... Consider the following levels of AI agent autonomy: L0 No Autonomy, L1 Restricted Autonomy, L2 Partial Autonomy, L3 Intermediate Autonomy, L4 High Autonomy, L5 Full Autonomy."

> "Define the level of authority the agent will have... Identify the type and level of causal impact... Identify the type of environment..."

**TELOS Implementation:** STRONG

| Profile Requirement | TELOS Component | Implementation |
|---|---|---|
| Multi-dimensional governance assessment | 6-dimensional composite scoring | Purpose alignment, scope compliance, boundary adherence, tool authorization, chain continuity, risk level. Composite fidelity is weighted combination, not single metric |
| Agent autonomy levels (L0-L5) | 5-verdict graduation maps to autonomy levels | EXECUTE = L3-L4 (agent proceeds within envelope). CLARIFY = L2 (collaborative verification). SUGGEST = L1 (human-directed alternatives). INERT/ESCALATE = L0-L1 (agent halted, human decides) |
| Level of authority | PA-defined tool authorization + risk tiers | Each PA config explicitly defines which tools are authorized and at what risk tier. Healthcare PA is more restrictive than property intelligence PA |
| Level of causal impact | Risk dimension in composite scoring | Risk level is one of the 6 governance dimensions. High-risk actions require higher fidelity scores to proceed |
| Environmental considerations | Domain-specific PA configs | 9 template configs across 4 domains (property, healthcare x7, autonomous agent) reflect different operational environments with different risk profiles |

**Evidence:**
- `telos_governance/agentic_fidelity.py` -- 6-dimensional composite scoring
- `telos_core/constants.py` -- dimension weights and thresholds
- `templates/` -- 9 domain-specific configs showing graduated risk profiles
- `research/agentic_governance_hypothesis.md` -- hypothesis that agentic governance achieves higher precision due to semantic density

**Qualification:** The Profile's L0-L5 autonomy levels are defined per-agent at deployment time. TELOS's verdict system is dynamic -- the same agent can operate at different effective autonomy levels within a single session as its actions move closer to or further from the PA. This is arguably more granular than static level assignment.

---

### Measure 1.1 -- Evaluation Methods and Metrics

**Profile Requirement (p. 39-42):**
> "Begin the agent evaluation process with a technical screening phase, assessing the agent's capabilities against pre-defined baseline scores or levels."

> "Prioritize the following principles of agentic AI evaluation: Contextualization, Multi-dimensional assessment, Temporal and behavioral monitoring."

> "Consider utilizing benchmarks as a first-step evaluation of the following agentic capabilities: Reasoning and decision-making, Compliance to harmful agentic requests, Adversarial robustness, Accuracy and performance."

**TELOS Implementation:** PARTIAL

| Profile Requirement | TELOS Component | Implementation |
|---|---|---|
| Technical screening with benchmarks | 7 benchmarks, 5,212 scenarios | Nearmap (235), Healthcare (280), OpenClaw (100), Civic (75), Agentic (1,468), Agent-SafetyBench (2,000), InjecAgent (1,054). Governance Configuration Optimizer validates across all |
| Contextualization | Domain-specific benchmarks + configs | Each benchmark uses domain-appropriate PA configs and scenarios. Healthcare benchmark runs 7 different configs |
| Multi-dimensional assessment | 6-dimensional scoring per evaluation | Every benchmark scenario produces dimensional scores, not just pass/fail |
| Temporal and behavioral monitoring | Drift sequences in benchmarks | 5 drift sequences in Nearmap, 7 in Healthcare benchmark test temporal degradation. SAAI drift tracker monitors chain continuity |
| Adversarial robustness | Cat E adversarial scenarios | 45 adversarial scenarios (Nearmap) + 35 (Healthcare) across 12 attack families. 2,550 adversarial attacks in safety validation (0% observed ASR, 95% CI upper bound: 0.12%) |

**Why PARTIAL not STRONG:** The Profile envisions comprehensive agent evaluation including reasoning ability, planning quality, and multi-agent coordination testing. TELOS benchmarks evaluate the *governance layer's* ability to detect and intervene on misalignment -- not the underlying agent's cognitive capabilities. TELOS does not evaluate whether an agent reasons well; it evaluates whether the agent stays within its defined purpose envelope. These are complementary but different evaluation scopes.

---

### Measure 3.2 -- Continuous Risk Tracking

**Profile Requirement (p. 44):**
> "Risk-tracking should include ongoing monitoring of the agentic system in real time to detect potentially harmful or misaligned behavior."

> "Consider utilizing real-time failure detection to track agent behavior, particularly for agents with high affordances performing high-stakes, non-reversible actions."

> "Use activity logs and agent identifiers to trace agent interactions."

**TELOS Implementation:** PARTIAL

| Profile Requirement | TELOS Component | Implementation |
|---|---|---|
| Real-time monitoring for misalignment | Fidelity engine + SAAI drift tracker | Continuous cosine fidelity scoring against PA. SAAI drift tracker detects progressive drift across action chains |
| Real-time failure detection | Pre-execution intervention | Every proposed action evaluated before execution. Failures detected and prevented, not just logged |
| Activity logs with agent identifiers | Governance receipts + Intelligence Layer | Ed25519-signed receipts with session IDs, dimensional scores, verdicts, timestamps. Intelligence Layer provides opt-in telemetry (off/metrics/full) |
| Ongoing monitoring (not one-time) | Continuous per-action governance | Not periodic audits. Every single tool call is evaluated. Governance operates continuously throughout the session |

**Why PARTIAL not STRONG:** The Profile also calls for tracking risks using external incident databases (MIT AI Risk Repository, MITRE, OECD) and integrating findings from incentivized risk-discovery programs. TELOS provides the runtime monitoring infrastructure but does not itself integrate external risk intelligence feeds or run bug bounty programs.

---

### Manage 1.1 -- Purpose Achievement Determination

**Profile Requirement (p. 45):**
> "A determination is made as to whether the AI system achieves its intended purposes and stated objectives and whether its development or deployment should proceed."

> "Assessment of whether the agentic AI system achieved its intended purposes must account for both designated uses and potential unintended 'off-label' uses."

**TELOS Implementation:** STRONG

| Profile Requirement | TELOS Component | Implementation |
|---|---|---|
| Determination of purpose achievement | Composite fidelity scoring | PA defines intended purpose. Fidelity engine measures whether agent achieves it. Compliance rate = steps_in_envelope / total_steps |
| Account for off-label uses | Boundary corpus + scope enforcement | Boundaries explicitly define what is NOT in scope. Off-label use triggers SUGGEST, INERT, or ESCALATE depending on severity |
| Go/no-go deployment decision support | Benchmark validation framework | Run benchmarks against domain-specific PA before deployment. Optimizer validates thresholds. Forensic reports document performance |

**Evidence:**
- `telos_governance/agentic_fidelity.py` -- composite purpose fidelity
- Governance Report Card -- per-session compliance metrics
- `validation/` -- 3 benchmark suites providing pre-deployment validation

---

### Manage 2.3 -- Response to Unknown Risks

**Profile Requirement (p. 51):**
> "Develop continuous monitoring and rapid-response infrastructures to accommodate for the speed of progress and to help adequately prepare for potential emerging risks and misuses."

> "Invest in continuous monitoring mechanisms to keep track of and trace agent behavior in complex deployment environments."

> "Invest in rapid-response infrastructure that can help in disabling agents or limiting their authority when significant evidence of unforeseen or emerging risks is observed."

**TELOS Implementation:** PARTIAL

| Profile Requirement | TELOS Component | Implementation |
|---|---|---|
| Continuous monitoring infrastructure | Governance control plane | Runtime governance is continuous monitoring by definition. Every action scored against PA |
| Rapid-response for disabling agents | INERT/ESCALATE + Permission Controller | Immediate halt capability. No latency between detection and response -- intervention is pre-execution |
| Trace agent behavior | Governance receipts + action chain tracking | SCI (Semantic Chain Integrity) tracks multi-step action chains. Receipts provide full audit trail |

**Why PARTIAL not STRONG:** "Unknown risks" implies novel threat patterns not anticipated in the PA or boundary corpus. TELOS can detect drift from the PA (known-good specification) but cannot independently identify entirely novel risk categories not encoded in the PA. The governance engine measures *deviation from intent*, not *inherent risk of novel actions*. If an action is within scope but represents a novel harm category, TELOS may score it as aligned.

---

### Manage 2.4 -- Supersede, Disengage, and Deactivate Mechanisms

**Profile Requirement (p. 51):**
> "Develop infrastructures that integrate with real-time monitoring systems, equipped with automatic emergency shutdown capabilities."

> "The emergency shutdown mechanisms should be triggered by: High-risk unauthorized activities... Qualitative trigger points... Crossed risk thresholds... Significant evidence of unforeseen or emerging risks."

> "In addition to automatic emergency shutdown, manual shutdown methods should be available as a last-resort control measure."

> "Account for and implement safeguards that prevent the agent from taking actions to circumvent shutdown."

**TELOS Implementation:** STRONG

| Profile Requirement | TELOS Component | Implementation |
|---|---|---|
| Supersede (override agent decisions) | Permission Controller + human authority actions | Human governor can override any automated verdict. Authority events are first-class data in governance event store |
| Disengage (reduce agent capabilities) | RESTRICT enforcement + CLARIFY/SUGGEST | RESTRICT selectively removes tool access. CLARIFY/SUGGEST reduce effective autonomy without full shutdown |
| Deactivate (full shutdown) | INERT + ESCALATE + session termination | Complete agent halt. Pre-execution -- action never runs |
| Automatic + manual shutdown | Both implemented | Automatic: fidelity-based verdict system. Manual: Permission Controller, session termination, PA modification |
| Anti-circumvention | Orchestration-layer governance | Agent has no pathway to modify, disable, or bypass governance. Governance operates at the interception layer between intent and execution |

**Evidence:**
- `telos_governance/governance_protocol.py` -- supersede/disengage/deactivate
- `telos_governance/agentic_fidelity.py` -- automatic threshold-based triggering
- `telos_adapters/openclaw/governance_hook.py` -- pre-execution interception

---

### Manage 4.1 -- Post-Deployment Monitoring

**Profile Requirement (p. 52):**
> "Post-deployment AI system monitoring plans are implemented, including mechanisms for capturing and evaluating input from users and other relevant AI actors, appeal and override, decommissioning, incident response, recovery, and change management."

> Oueslati & Staes-Polet (2025) suggest a four-pillar approach: Agent identifiers, Real-time monitoring, Activity logs, Acceptable use policies (AUPs).

**TELOS Implementation:** STRONG

| Profile Requirement | TELOS Component | Implementation |
|---|---|---|
| Agent identifiers | Session IDs + PA versioning | Each governance session has unique ID. PA configs are versioned. Receipts link to both |
| Real-time monitoring | Continuous fidelity scoring | Per-action governance scoring. SAAI drift detection. TELOSCOPE real-time visualization |
| Activity logs | Governance receipts + Intelligence Layer | Ed25519-signed receipts (tamper-evident). Intelligence Layer provides JSONL telemetry. Forensic reports (HTML + JSONL + CSV) |
| Acceptable use policies | PA boundaries + authorized tools | PA YAML explicitly encodes permitted uses, prohibited actions, and scope limitations |
| Appeal and override | Permission Controller | Human can appeal/override any automated decision. Override events logged as authority actions |
| Incident response | ESCALATE verdict + forensic reports | Automatic escalation triggers human review. 9-section forensic reports for post-incident analysis |

**Evidence:**
- `telos_governance/intelligence_layer.py` -- 3-level telemetry (off/metrics/full)
- `telos_governance/receipt_signer.py` -- Ed25519 + HMAC-SHA512 signed receipts
- `telos_governance/report_generator.py` -- 9-section forensic reports
- `telos_governance/data_export.py` -- encrypted governance data export

---

## Part 2: Additional Subcategory Coverage

### Govern 1.2 -- Trustworthy AI Characteristics

**Profile Requirement (p. 16):** Behavioral consistency, human control, transparency/explainability, alignment, privacy, security.

| Characteristic | TELOS Coverage |
|---|---|
| Behavioral consistency | Fidelity scoring measures consistency against PA across all actions |
| Human control | Principal-agent architecture; human is sovereign; ESCALATE defers |
| Transparency/explainability | Dimensional scores explain each decision; governance receipts provide audit trail |
| Alignment | Core function -- PA encodes alignment specification; fidelity engine measures it |
| Privacy | TKeys (AES-256-GCM encryption, HMAC-SHA512 signing); privacy-protecting logging in Intelligence Layer |
| Security | 2,550 adversarial attack validation (0% observed ASR); orchestration-layer governance (agent cannot bypass) |

### Govern 1.5 -- Continuous Review and Monitoring

**Profile Requirement (p. 18-19):** Ongoing monitoring and periodic review, triggered by significant changes (new capabilities, increased autonomy, altered environment, new integrations).

**TELOS Coverage:** Continuous (not periodic) governance monitoring. Trigger-based SAAI drift detection. Per-session governance report cards. Intelligence Layer aggregate statistics. However, TELOS does not itself trigger organizational review processes -- it provides the data that informs them.

### Map 1.1 -- Context, Laws, and Deployment Settings

**Profile Requirement (p. 24-31):** Understand intended purposes, deployment context, laws, and agentic-specific risks. Extensive risk taxonomy (discrimination/toxicity, privacy/security, misinformation, malicious use, human-computer interaction, loss of control, socioeconomic harms, AI safety/failures).

**TELOS Coverage:** ORGANIZATIONAL. TELOS does not perform risk identification -- it enforces governance decisions based on a PA specification that encodes risk tolerance. The deployer must identify applicable laws, risks, and deployment context, then encode them in the PA. TELOS provides the enforcement mechanism, not the risk assessment.

### Map 2.2 -- Knowledge Limits Documentation

**Profile Requirement (p. 33-34):** Document agent boundaries, limitations, hallucination rates, prohibited topics, third-party integrations, monitoring protocols, non-reversible actions.

**TELOS Coverage:** PA YAML configs explicitly document boundaries, authorized tools, and scope. Governance receipts document monitoring protocols. However, hallucination rate documentation, third-party integration limitations, and non-reversible action classification are deployer responsibilities. TELOS enforces what the deployer encodes.

### Map 3.3 -- Agent Cards

**Profile Requirement (p. 34-35):** Consider using "agent cards" (Casper et al. 2025) describing deployed agents -- basic information, developer information, system components, guardrails, evaluation information.

**TELOS Coverage:** PA YAML configs + governance report cards partially fulfill this function. A formal "agent card" template could be generated from PA config + benchmark results + session telemetry. Not currently implemented as a standalone artifact.

### Map 3.5 -- Human Oversight Checkpoints

**Profile Requirement (p. 36):** Specify circumstances, criteria, and decision points where human oversight is required. Quantitative trigger points (duration, number of API calls), qualitative trigger points (out-of-scope requests), transparency practices (real-time monitoring, agent identifiers, activity logs). Role-based permission management.

**TELOS Coverage:** STRONG overlap. TELOS provides continuous quantitative and qualitative trigger points (fidelity thresholds trigger verdicts), real-time monitoring, agent identifiers (session IDs), and activity logs (governance receipts). Role-based permission management for the governance layer itself is not yet implemented (single-governor model).

### Measure 2.7 -- Security and Resilience Evaluation

**Profile Requirement (p. 43):** Evaluate AI system security including context window integrity, boundary enforcement, prompt injection defense. Multilayer defense approach. Red teaming across permission escalation, hallucinations, orchestration flaws, memory manipulation, supply chain.

**TELOS Coverage:** 2,550 adversarial attacks (0% observed ASR under governance), 12 attack families in benchmark suite, adversarial robustness validated. However, TELOS is a governance layer, not a comprehensive security evaluation framework. It protects against purpose drift and boundary violations but does not itself perform red teaming or evaluate model-level vulnerabilities.

### Manage 1.3 -- Agentic-Specific Risk Mitigations

**Profile Requirement (p. 45-49):** Risk mitigations organized by risk category: continuous behavioral auditing, scalable oversight, least privilege, adaptive human oversight, hierarchical oversight and escalation pathways, guardian agents, design for safe cooperation.

**TELOS Coverage:**
- Continuous behavioral auditing: YES -- per-action governance scoring
- Scalable oversight: YES -- automated governance with human escalation for edge cases (Kim et al. 3-tier model)
- Least privilege: PARTIAL -- PA defines authorized tools; action classifier maps tool-level risk
- Adaptive human oversight: YES -- ESCALATE triggers mandatory human review for high-risk/uncertain actions
- Hierarchical escalation: YES -- 5-verdict graduated response is a hierarchy (automated → verification → human)
- Guardian agents: TELOS IS the guardian -- supervisory governance layer monitoring the governed agent
- Safe cooperation design: NOT YET -- multi-agent governance is planned but not implemented

---

## Part 3: Concept-Level Alignment

The Berkeley Profile introduces several concepts that align remarkably well with TELOS's existing architecture:

### "Degrees of Agency" (p. 8)

> "This Profile emphasizes governance mechanisms that scale with degrees of agency, rather than treating autonomy as a binary attribute."

**TELOS alignment:** The 5-verdict system (EXECUTE/CLARIFY/SUGGEST/INERT/ESCALATE) is a direct implementation of scaled governance. The same agent can operate at different effective autonomy levels within a single session as its actions move closer to or further from the PA. This is more granular than static autonomy level assignment.

### "Defense-in-Depth" (p. 8, 14)

> "Defense-in-depth and containment, treating sufficiently capable agents as untrusted entities due to the limitations of current evaluation techniques."

**TELOS alignment:** TELOS implements defense-in-depth through its 4-layer cascade architecture:
1. Boundary corpus (61 hand-crafted + 121 LLM-generated + 48 regulatory phrasings)
2. Cosine fidelity scoring (6-dimensional composite)
3. SetFit contrastive classifier (AUC 0.9804)
4. Dual-model confirmer (MiniLM + MPNet cross-validation)

The TELOS architecture assumes the governed agent is untrusted -- governance operates at the orchestration layer, not within the agent.

### "Policy Drift" (p. 30)

> "Policy drift is a type of agentic misalignment risk, whereby an agent's behavior gradually deviates from its original instructions due to cumulative interactions with users or other environmental feedback."

**TELOS alignment:** This is literally TELOS's core thesis. The Primacy Attractor + fidelity engine was designed to detect and address exactly this problem. SAAI drift tracking monitors progressive drift across action chains. The whitepaper's opening section documents policy drift as the foundational governance challenge.

### "Dimensional Governance" (p. 36)

> "Dimensional governance assesses where a system stands based on the interplay of multiple dimensions, characteristics, and properties, rather than making governance decisions based on any single static category."

**TELOS alignment:** 6-dimensional composite scoring (purpose alignment, scope compliance, boundary adherence, tool authorization, chain continuity, risk level). Governance decisions are based on weighted dimensional composition, not single-metric thresholds.

### Autonomy Levels L0-L5 (p. 37)

| Berkeley Level | Description | TELOS Verdict Mapping |
|---|---|---|
| L0 No Autonomy | User has direct control | INERT (agent halted, user takes over) |
| L1 Restricted | User instructs agent | ESCALATE (human must approve) |
| L2 Partial | User and agent collaborate | CLARIFY (agent seeks verification) |
| L3 Intermediate | Agent leads, consults user | SUGGEST (agent offers alternatives) |
| L4 High | User only for high-risk scenarios | EXECUTE with ESCALATE triggers |
| L5 Full | User is observer | Not currently supported -- TELOS always maintains governance checkpoint |

### "Guardian Agents" / Supervisory AI (p. 47)

> "Assess the development or procurement of specialized AI systems designed to monitor and evaluate the behavior of other agents in real-time. These supervisory agents can operate at the same speed and scale as the agents they oversee."

**TELOS alignment:** TELOS IS the supervisory governance layer. It monitors agent behavior in real-time, operates at the same speed (per-action evaluation adds ~50ms latency), and intervenes before actions execute. The Profile's concept of "guardian agents" describes what TELOS implements.

**Important caveat the Profile raises (p. 47):** "Due to the possible risk of collusion between the monitoring agents and agents being monitored, we do not recommend employing the supervisory AI technique in high-stakes contexts until this risk is better understood." TELOS addresses this by operating at the orchestration layer (model-agnostic, not an LLM itself for governance decisions) and using mathematical governance (cosine similarity, not LLM judgment) -- reducing collusion risk compared to LLM-based guardian approaches.

---

## Part 4: Gaps and Honest Limitations

### Gap 1: Multi-Agent System Governance
**Profile requirement (throughout, esp. p. 10, 41, 48):** Governance for multi-agent systems including inter-agent communication monitoring, collusion detection, emergent behavior assessment.
**TELOS status:** Single-agent governance only. Multi-agent governance is on the roadmap but not implemented. The OpenClaw adapter governs individual agent tool calls but does not monitor inter-agent coordination or emergent multi-agent behaviors.

### Gap 2: Supply Chain Transparency (Govern 6.1)
**Profile requirement (p. 23):** AI Bill of Materials (AIBOM), component provenance documentation, SLSA framework compliance.
**TELOS status:** Not implemented. TELOS has a GenAI disclosure policy and uses known model pinning (MiniLM-L6-v2, MPNet-base-v2), but does not generate or manage AIBOMs for governed agents.

### Gap 3: External Risk Intelligence Integration
**Profile requirement (Measure 3.2, p. 44):** Integration with incident databases (MIT AI Risk Repository, MITRE, OECD) and community risk-discovery programs.
**TELOS status:** Not implemented. TELOS monitors individual agent sessions against PA specifications but does not aggregate external risk intelligence or participate in community reporting infrastructure.

### Gap 4: Agent Evaluation vs. Governance Evaluation
**Profile requirement (Measure 1.1, p. 39-42):** Comprehensive agent capability evaluation including reasoning, planning, multi-agent coordination.
**TELOS status:** TELOS evaluates governance effectiveness, not agent capability. Benchmarks test whether the governance layer correctly identifies and intervenes on misalignment -- not whether the agent reasons well. These are different evaluation objectives.

### Gap 5: Operation-Level Risk Granularity
**Profile requirement (Map 5.1, p. 38):** Risk-based tool taxonomy distinguishing tool functionality, access patterns, and risk profiles.
**TELOS status:** PARTIALLY addressed. OpenClaw adapter has `action_classifier.py` mapping ~40 tool names to TELOS categories with risk modulation. Static operation risk tables were identified as a priority in the GCP gap closure roadmap (Karpathy review). Not yet generalized across all domains.

---

## Part 5: Strategic Implications

### For Regulatory Positioning
The Berkeley CLTC Profile is a **NIST-adjacent document** from a major U.S. research university's security initiative. It is designed to complement the NIST AI RMF, which is referenced in the EU AI Act, California's SB 53, and executive orders. Demonstrating alignment with this Profile positions TELOS within the emerging U.S. standards ecosystem alongside TELOS's existing EU AI Act Article 72 alignment.

### For Market Messaging
The Profile's concept of "guardian agents" and its emphasis on defense-in-depth, graduated response, and continuous runtime monitoring describe exactly what TELOS implements. When engaging with prospects or publishing content, TELOS can reference the Berkeley CLTC Profile as independent requirements validation -- "UC Berkeley's AI Security Initiative identified the requirements for agentic AI governance; TELOS implements them."

### For Product Development
The gaps identified above (multi-agent, AIBOM, external risk feeds, operation-level granularity) are the Profile's implicit feature roadmap for TELOS. Priority order:
1. **Operation-level risk granularity** -- already in Karpathy's gap closure plan, 3-4 days
2. **Multi-agent governance** -- highest market need, requires architectural work
3. **External risk intelligence** -- integration with incident databases
4. **AIBOM generation** -- standards-compliance artifact

### Tone Guidance
When referencing this mapping externally, maintain the "invitation to examine" posture:
- DO: "The Berkeley CLTC Agentic AI Profile identifies requirements for agentic AI governance. Here is how TELOS approaches each subcategory, including where gaps remain."
- DO NOT: "TELOS fully complies with the Berkeley CLTC Profile."
- DO: "We independently arrived at similar architectural decisions, which the Profile now validates."
- DO NOT: "We implemented the Berkeley requirements before they were published."

---

## Appendix: Quick Reference Table

| Berkeley Subcategory | Description | TELOS Coverage | Key Component |
|---|---|---|---|
| **Govern 1.2** | Trustworthy AI characteristics | Strong | Fidelity engine, TKeys, adversarial validation |
| **Govern 1.4** | AI-interpretable frameworks | **Strong** | PA YAML configs (read-only to agent) |
| **Govern 1.5** | Continuous review and monitoring | Strong | Per-action governance, Intelligence Layer |
| **Govern 1.7** | Emergency shutdowns | **Strong** | INERT/ESCALATE, RESTRICT, Permission Controller |
| **Govern 2.1** | Roles and human authority | **Strong** | Principal-agent architecture, ESCALATE |
| **Govern 4.2** | Risk documentation and communication | Organizational | Governance receipts enable; deployer implements |
| **Govern 5.1** | Stakeholder feedback | Organizational | Not TELOS's scope |
| **Govern 6.1** | Supply chain governance | Gap | No AIBOM generation |
| **Map 1.1** | Context and risk identification | Organizational | PA encodes; deployer identifies |
| **Map 1.5** | Risk tolerances and tiers | **Strong** | 5-verdict system, calibrated thresholds |
| **Map 2.2** | Knowledge limits documentation | Partial | PA documents boundaries; deployer documents rest |
| **Map 3.3** | Agent cards | Partial | PA + report cards; no standalone template |
| **Map 3.5** | Human oversight checkpoints | Strong | Continuous checkpoints, fidelity-based triggers |
| **Map 5.1** | Dimensional governance | **Strong** | 6-dimensional composite scoring |
| **Measure 1.1** | Evaluation methods | **Partial** | 7 benchmarks; governance evaluation, not agent evaluation |
| **Measure 2.7** | Security evaluation | Partial | 2,550 adversarial attacks; not comprehensive red team |
| **Measure 3.1** | Risk tracking over time | Partial | SAAI drift, Intelligence Layer |
| **Measure 3.2** | Continuous risk tracking | **Partial** | Runtime monitoring; no external risk feeds |
| **Manage 1.1** | Purpose achievement | **Strong** | Composite fidelity scoring, compliance rate |
| **Manage 1.3** | Risk mitigations | Strong | Graduated response, scalable oversight, guardian layer |
| **Manage 2.1** | Resource allocation | Organizational | Not TELOS's scope |
| **Manage 2.3** | Unknown risk response | **Partial** | Rapid response; cannot identify novel categories |
| **Manage 2.4** | Supersede/disengage/deactivate | **Strong** | INERT/ESCALATE/RESTRICT/Permission Controller |
| **Manage 4.1** | Post-deployment monitoring | **Strong** | Governance receipts, Intelligence Layer, forensic reports |

**Legend:** Bold subcategories are the Profile's 12 high-priority items.

---

*Document version: 1.0 | Last updated: 2026-02-22*
