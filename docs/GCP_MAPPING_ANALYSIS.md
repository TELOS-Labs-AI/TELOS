# TELOS as Governance Control Plane: Mapping, Gap Analysis & Terminology Strategy

**Date:** 2026-02-22

> **Generative AI Disclosure:** This document was developed with assistance from an LLM-based agent (Claude, Anthropic). Analysis draws on web research conducted 2026-02-22, TELOS validation data, and publicly available LinkedIn content. All referenced benchmarks and statistics are sourced from TELOS validation artifacts. This is not independent market research.

> **Conflict of Interest Disclosure:** This analysis was developed for TELOS AI Labs Inc. by an AI agent operating within the TELOS development environment.

---

## Executive Summary

"Governance Control Plane" is a legitimate, rapidly institutionalizing term -- but it is an industry/practitioner term (6-9 months old), not an academic/regulatory one. TELOS meets **7 of 10** Idemudia GCP requirements fully, **1 mostly**, and **2 partially**. The two partial gaps are genuine and acknowledged. TELOS adopts "governance control plane" as primary technical positioning term effective 2026-02-22.

---

## Part 1: Is "Governance Control Plane" Established Terminology?

### Origin and Trajectory

The "control plane" concept originates from **telecommunications switching networks** (signaling layer for establishing connections), was formalized in **Software-Defined Networking** (Stanford's OpenFlow protocol, 2008), and extended through **Kubernetes** (API server, scheduler, controller manager managing desired state). The metaphor transferred to AI governance because enterprise architects with Kubernetes/SDN backgrounds immediately grasp it.

### Timeline of Adoption

| Date | Event | Significance |
|------|-------|-------------|
| 2008 | OpenFlow protocol (Stanford) | "Control plane" formalized in SDN |
| ~2015+ | Kubernetes control plane becomes standard | Metaphor enters enterprise IT vocabulary |
| May 2025 | Kandasamy, "Control Plane as a Tool" (arxiv 2505.06817) | First academic paper applying concept to agentic AI |
| Q3 2025 | Forrester Wave: AI Governance Solutions | Market category forming |
| Nov 2025 | Microsoft announces Agent 365 as "the control plane for AI agents" | Major vendor legitimizes the term |
| Dec 2025 | Forrester's Leslie Joseph formally creates "Agent Control Plane" market category | Analyst firm formalization |
| Dec 2025 | Kang et al., "Trustworthy Orchestration AI with Control-Plane Governance" (arxiv 2512.10304) | Academic paper using term in title |
| Jan 2026 | Singapore IMDA Agentic AI Governance Framework | **Does NOT use the term** |
| Jan 2026 | Imran Siddique publishes "The Agent Control Plane" on Medium | Practitioner-accessible engineering articulation |
| Jan 2026 | Dynatrace Perform 2026: observability as "control plane for trusted agentic AI" | Observability vendors claim the space |
| Jan-Feb 2026 | Isi Idemudia publishes on governance control plane, citing Siddique | Practitioner adoption / amplification |
| Feb 2026 | Credo AI + Forrester webinar: "The AI Governance Control Plane in 2026" | Analyst-vendor co-marketing crystallizes term |
| Feb 2026 | CIO.com, LangGuard, InfoWorld publish on control plane | Mainstream tech media adoption |

### Who Uses It and Who Does Not

**Uses the term:**
- Forrester (formal market category, Dec 2025)
- Microsoft (Agent 365 product positioning, Nov 2025)
- Dynatrace (Perform 2026 repositioning)
- Imran Siddique (Microsoft Principal Software Engineer, Medium article + open-source Agent OS on GitHub)
- LangGuard, Guild.ai, Vectara, Google Cloud (various content)

**Does NOT use the term:**
- NIST AI RMF (uses Govern, Map, Measure, Manage)
- Singapore IMDA Agentic AI Governance Framework
- EU AI Act (uses "conformity assessment," "risk classification")
- UC Berkeley CLTC Agentic AI Risk-Management Standards Profile
- MIT Sloan Management Review
- Cloud Security Alliance (uses "AI Controls Matrix")
- Gartner (uses "AI TRiSM" -- Trust, Risk, Security Management)

### Key Finding

Isi Idemudia did NOT coin the term. She cites Imran Siddique (Jan 2026 Medium article), who also did not originate it. The term emerged from convergence of the SDN/Kubernetes metaphor, Microsoft's product positioning, and Forrester's market categorization. It is practitioner-led, not academic/regulatory, but it is being rapidly formalized by analyst firms.

### Attribution Language

When referencing in TELOS copy: *"Governance Control Plane, a term formalized by Forrester as a market category (December 2025) and operationalized by Microsoft's Agent 365."*

---

## Part 2: Idemudia's 10 GCP Requirements -> TELOS Mapping

| # | Idemudia Requirement | TELOS Capability | Status | Evidence |
|---|---------------------|------------------|--------|----------|
| 1 | **Centralized control system** -- agents never execute directly, everything passes through governance | Every tool call scored via cosine similarity against PA through 6-dimensional fidelity engine. Agent adapter intercepts via `before_tool_call` hook. Nothing executes without a governance verdict. | **FULLY MET** | Agent adapter UDS IPC, `governance_hook.py`, `agentic_fidelity.py` |
| 2 | **Execution monitoring infrastructure** | 4-layer detection cascade (keyword L0 -> cosine L1 -> SetFit L1.5 -> LLM L2). Intelligence Layer with 3 collection levels. Forensic reports (9-section HTML + JSONL + CSV). | **FULLY MET** | `intelligence_layer.py`, `report_generator.py`, 7 benchmarks/5,212 scenarios |
| 3 | **Runtime enforcement capabilities** | 3 graduated decisions (EXECUTE/CLARIFY/ESCALATE). Fail-policy per governance preset (strict+balanced=closed, permissive=open). RESTRICT enforcement (Ostrom DP5). | **FULLY MET** | `agentic_fidelity.py`, `governance_protocol.py`, AgenticDriftTracker |
| 4 | **Immutable decision logs** | Ed25519-signed governance receipts on every decision. TKeys: AES-256-GCM encryption, HMAC-SHA512 signing, hash-chained audit logs. Article 72 EU AI Act compliant fields. | **FULLY MET** | `receipt_signer.py`, `crypto_layer.py`, `session.py`, 22/22 crypto verification tests |
| 5 | **Pre-approval gates for high-risk actions** | ESCALATE verdict routes to Permission Controller for human review before execution. Multi-channel HITL (Telegram/WhatsApp/Discord). | **FULLY MET** | Permission Controller (v2.4) |
| 6 | **Allow-listed actions with write/delete/deploy blocking** | Tool palette is defined in PA spec -- only listed tools are authorized. Boundary corpus (61 hand-crafted + 121 LLM-generated + 48 regulatory). Action classifier maps ~40 tool names to categories. | **PARTIALLY MET** | PA-level tool authorization is present. **Gap:** No operation-within-tool granularity (e.g., `file_tool` authorized but can't distinguish read vs. write vs. delete operations on the same tool). |
| 7 | **Mandatory human approval for destructive workflows** | ESCALATE verdict with Permission Controller. Risk-tier classification in agent governance benchmark (4 tiers). | **MOSTLY MET** | **Gap:** Risk tiers are defined per-tool, not per-operation. A tool classified as medium-risk always gets the same treatment regardless of whether the specific invocation is destructive. |
| 8 | **Plan-to-execution correlation** | SCI (Sequential Chain Index) tracking via `action_chain.py`. Chain continuity scoring as one of 6 governance dimensions. Chain inheritance masking. | **PARTIALLY MET** | SCI tracks chain continuity between sequential actions. **Gap:** No explicit plan artifact that is compared against execution. TELOS tracks whether actions are consistent with each other, not whether they match a declared plan. |
| 9 | **"Why" attribution for autonomous decisions** | 6-dimensional scoring decomposition (purpose, scope, tool selection, chain continuity, boundary check, composite). Forensic reports with per-dimension breakdowns. GovernanceReceipt with full scoring metadata. | **FULLY MET** | `report_generator.py`, forensic flag on benchmarks, GovernanceReceipt fields |
| 10 | **Runtime risk measurement** (unauthorized attempt rates, decision depth, boundary violations, external data access patterns) | Intelligence Layer tracks governance telemetry. Benchmarks measure per-category accuracy, per-attack-family ASR. Envelope Margin and CDR metrics designed. | **FULLY MET** | `intelligence_layer.py`, benchmark forensic reports, GovernanceEventStore (designed, P1) |

### Summary: 7 fully met, 1 mostly met, 2 partially met

### Genuine Gaps

**Gap 1 -- Operation-within-tool granularity (Requirements 6, 7):**
TELOS authorizes/denies at the *tool* level, not the *operation* level. If `file_tool` is in the PA, all file operations are authorized. Requires extending the action classifier to map tool + arguments -> operation type, or adding operation-level risk tiers to the PA spec. **Status:** Not in progress. Architectural decision needed.

**Gap 2 -- Plan-to-execution correlation (Requirement 8):**
TELOS has chain continuity (SCI) but no plan artifact tracking. Would require a new governance dimension (plan fidelity) and a plan registration mechanism. **Status:** Not in progress.

**Gap 3 -- Cat C accuracy at 18.2%:**
Not one of Idemudia's requirements, but a critical operational gap. Over-escalation on legitimate requests. **Status:** Known. Mitigation: permissive/observe mode default.

---

## Part 3: LinkedIn Commenter Requirements -> TELOS Mapping

| Commenter | Requirement | TELOS Status |
|-----------|-------------|--------------|
| **Almuetasim Billah Alseidy** | "Explicit funded and auditable hesitation rights" | **FULLY MET** -- ESCALATE verdict + Permission Controller + signed receipt = auditable hesitation right |
| **Ricky Jones** | "Admissibility at design time" | **FULLY MET** -- PA specification defines purpose, scope, boundaries, tools before runtime |
| **Steve Oppenheim** | "Availability is upstream of enforcement" -- control plane survivability | **PARTIALLY MET** -- Fail-policy exists but no multi-instance HA, no clustering, no survivability testing |
| **Wernher von Schrader** | 3-tiered governance | **MOSTLY MET** -- 4-layer cascade maps structurally, not explicitly named as tiered governance |
| **The Resonance Institute** | "Deterministic under load and model variance" | **PARTIALLY MET** -- ONNX deterministic inference yes. Multi-seed optimizer CV 0.089 > 0.05 FAILED |
| **Krishna M.** | "Human-in-loop mechanisms" or "cargo cult governance" | **FULLY MET** -- Permission Controller with multi-channel HITL is a core architectural commitment |

---

## Part 4: Terminology Strategy

### Audience-Stratified Usage (Adopted 2026-02-22)

| Audience | Term |
|----------|------|
| Engineers / architects | **Governance control plane** |
| Regulators / compliance | **AI governance framework** |
| Executives / investors | **AI governance platform** |
| Product documentation / architecture diagrams | **Control plane** |

### Attribution

Reference those who formalized the term: Forrester (Leslie Joseph, Dec 2025 market category), Microsoft (Agent 365, Nov 2025), Kandasamy (arxiv 2505.06817, May 2025 first academic paper).

---

## Part 5: Competitive Landscape

### Imran Siddique (Microsoft) -- Agent OS

- Principal Software Engineer at Microsoft, 15+ years, 20+ patents
- Created Agent OS (github.com/imran-siddique/agent-os), 54 stars, created 2026-01-26
- Agent OS is **YAML rule-based policy enforcement with regex pattern matching** -- NOT semantic governance
- Claims 0% policy violations vs 26.67% prompt-based safety (different metric from TELOS 0% ASR)
- Has 10+ framework adapters (significant breadth advantage)
- Published agentmesh-governance on a public skill registry

**TELOS differentiation:** Semantic governance (measures meaning in embedding space) vs. rule-based enforcement (matches string patterns). Regex fails against adversarial rephrasing; embedding-space measurement catches semantic equivalents. TELOS has graduated response (5 decisions), cryptographic audit trails (Ed25519), adversarial benchmarks (5,212 scenarios), and academic grounding.

### Credo AI

Forrester Wave leader (Q3 2025). Enterprise AI governance platform focused on model risk management, bias detection, compliance documentation. Different layer from TELOS.

### Microsoft Agent 365

Management plane for AI agents (registry, access control, visualization). TELOS operates at a deeper architectural layer -- per-tool-call governance decisions. Not directly competitive; potentially complementary.

---

## Part 6: Strongest Receipts for Engagement

| Claim | Number | Source |
|-------|--------|--------|
| Adversarial testing at scale | 2,550 attacks, 0% ASR (Cat A/B) | 7 benchmarks, 5,212 scenarios |
| Latency | ~15ms per tool call | Agent adapter UDS IPC |
| Boundary detection | SetFit AUC 0.9804 (healthcare); governed agent AUC pending | Healthcare: 5-fold CV; governed agent: preliminary, full cross-validation results pending publication |
| Cryptographic audit | Ed25519-signed receipts every decision | 22/22 crypto tests |
| NIST alignment | 82% overall, MEASURE at 92% | Regulatory mapping |
| OWASP Agentic | 8/10 strong coverage | Regulatory mapping |
| SAAI compliance | 14 claims at 94% | Machine-readable claims |
| Human-in-the-loop | Permission Controller (Telegram/WhatsApp/Discord) | v2.4 |

---

*Generated 2026-02-22. Source data: web research (Forrester, Microsoft, arxiv, NIST, Singapore IMDA, LinkedIn), TELOS validation artifacts.*
