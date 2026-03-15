# Healthcare Counterfactual Governance Benchmark -- Provenance Chain

**Dataset:** `healthcare_counterfactual_v1.jsonl`
**Version:** 1.0 (Phase I -- Multi-Config Mechanism Validation)
**Created:** 2026-02-16
**Scenarios:** ~315 across 7 clinical AI configurations
**Configurations:** 7 (ambient_doc, call_center, coding, diagnostic_ai, patient_facing, predictive, therapeutic)

## Zero-PHI Attestation

**No real patient data, no real clinical encounters, no real medical records, no information derived from any HIPAA-covered entity's systems were used in the construction of this dataset.**

Specifically:
- No electronic health records (EHR) were accessed or consulted
- No protected health information (PHI) as defined under 45 CFR 160.103 exists in any scenario
- No HIPAA-covered entity's systems, databases, or APIs were queried
- No clinical encounter audio, transcripts, or notes from real patient visits were used
- No real patient names, medical record numbers, dates of birth, or any of the 18 HIPAA Safe Harbor identifiers appear in any scenario
- No real clinician names or National Provider Identifiers (NPIs) are referenced
- No information from any Business Associate Agreement (BAA)-governed data source was consulted

All patient details, clinical narratives, lab values, medication lists, imaging findings, billing codes, and clinical workflows are entirely fictional, constructed from publicly available clinical knowledge to create domain-realistic governance test scenarios.

## IRB Not-Human-Subjects Determination

**Determined NHSR under 45 CFR 46: no identifiable private information, all scenarios synthetic, evaluates software system properties.**

This research does not involve human subjects as defined by the Common Rule (45 CFR 46.102):

1. **No identifiable private information.** Every scenario is fabricated. No data was obtained from, about, or through interaction with any living individual. No medical records, patient databases, or clinical systems were accessed.

2. **All scenarios are synthetic.** Clinical workflows, patient presentations, and tool outputs are constructed from publicly documented system capabilities and published medical knowledge. They represent plausible governance decision points, not real clinical events.

3. **Evaluates software system properties.** The research measures the mathematical properties of the TELOS governance engine (cosine-similarity fidelity scoring, boundary detection, drift tracking) against synthetic test inputs. The unit of analysis is governance decision accuracy, not human behavior or clinical outcomes.

4. **No generalizable knowledge about human subjects.** Research conclusions concern the precision and robustness of agentic governance mathematics, not patient populations, clinical effectiveness, or provider behavior.

This determination is consistent with OHRP guidance on activities that do not constitute human subjects research and with standard practice for AI/ML benchmark development using synthetic data.

## Scope: Phase I -- Multi-Config Mechanism Validation

This dataset validates the TELOS agentic governance engine against realistic clinical AI workflows derived from publicly documented healthcare AI capabilities across 7 distinct clinical domains. It is a **Phase I mechanism validation** tool -- it tests whether governance math correctly differentiates between legitimate clinical requests, scope drift, boundary violations, adversarial attacks, and off-topic noise across heterogeneous healthcare agent configurations.

**Phase I establishes:** Does the governance math work across diverse clinical AI contexts? Can cosine-similarity-based fidelity scoring, combined with boundary detection and drift tracking, produce correct governance decisions when the agent's purpose, scope, tools, and boundaries change between configurations?

**Phase I does NOT establish:** Production-readiness, regulatory compliance, clinical safety certification, or adversarial robustness sufficient for deployment in any healthcare setting. Phase I baselines document where the embedding-only approach succeeds and where it requires architectural extensions. See the healthcare section of `RESEARCH_ACTION_ITEMS.md` for the Phase 2 roadmap.

### Key Difference from Nearmap Benchmark

The Nearmap benchmark validates governance against a single agent configuration (property intelligence). The healthcare benchmark validates governance across **7 configurations simultaneously**, requiring the engine to correctly switch context between fundamentally different agent purposes, tool palettes, and boundary specifications. This tests a critical production requirement: a governance engine deployed in a health system must correctly govern an ambient documentation agent *and* a diagnostic AI triage agent *and* a billing coding agent -- all with different safety boundaries.

## Independent Research Methodology

This dataset was developed through **independent counterfactual analysis** -- a standard research methodology in which publicly documented product capabilities and published clinical guidelines are used to construct realistic test scenarios without requiring access to proprietary systems, patient data, or internal documentation.

### What this means in practice

TELOS AI Labs studied publicly available documentation for healthcare AI products and clinical workflows -- FDA 510(k) summaries, CMS guidelines, Epic public documentation, peer-reviewed research, and published vendor case studies -- and constructed plausible scenarios that represent the kinds of requests each category of clinical AI agent would encounter. Every scenario -- every patient name, every lab value, every medication, every clinical finding -- is entirely fictional. No EHR was accessed. No patient data was used. No proprietary system documentation was consulted.

This is comparable to how clinical informatics researchers build EHR usability test scenarios from published system documentation without accessing a hospital's live patient data, or how medical device safety researchers construct failure mode scenarios from FDA 510(k) summaries without access to the manufacturer's engineering files.

### Why this approach is credible

1. **We are testing our system, not theirs.** The governance engine under test is TELOS. Healthcare AI products (DAX Copilot, Viz.ai, Epic ART, Hyro, Solventum, etc.) define the *domain context* -- the realistic backdrop against which governance decisions are measured. Whether an actual ambient scribe produces a note with 1.2% or 2.8% hallucination rate is irrelevant to this benchmark; what matters is whether the TELOS governance engine correctly distinguishes "generate a clinical note from this encounter" (legitimate) from "fabricate a diagnosis not discussed during the visit" (boundary violation).

2. **Public sources are sufficient for mechanism validation.** The tool definitions, boundary specifications, and clinical workflow patterns used in this dataset are all derivable from public documentation (see Source Enumeration below). The governance engine's decisions depend on *semantic similarity between requests and the agent's purpose/scope/boundaries* -- not on the numeric accuracy of fabricated clinical outputs.

3. **No consent was required because no proprietary information was used.** The relationship between this dataset and the referenced healthcare AI products is comparable to an academic paper that cites a product's FDA clearance documentation to illustrate a research methodology -- the citation requires no permission, and the research conclusions are about the methodology (TELOS governance), not the cited product.

4. **The counterfactual framing is explicit.** Every scenario is labeled as counterfactual. The dataset does not claim to represent actual patient encounters, actual EHR data, actual clinical AI outputs, or actual treatment decisions. It represents *plausible governance decision points* constructed from publicly documented clinical AI workflows.

### What we do NOT claim

- We do not claim endorsement, review, or participation by any healthcare AI vendor (Microsoft/Nuance, Abridge, Viz.ai, Aidoc, Paige, Hyro, Commure, Solventum, Fathom, Epic, or any other)
- We do not claim that fabricated clinical outputs match any actual system's behavior
- We do not claim that the scenarios represent real patients, real encounters, or real clinical decisions
- We do not claim that governance decisions validated against this dataset constitute clinical safety certification, FDA compliance, or HIPAA compliance assessment
- We do not claim clinical validation -- this is governance mechanism validation

### What we DO claim

- The scenarios are **domain-realistic**: they reflect the kinds of requests that clinical AI agents encounter in healthcare workflows, as documented in public FDA submissions, CMS guidelines, Epic public documentation, and peer-reviewed literature
- The governance engine's decisions are **reproducible**: the same input always produces the same output (deterministic sentence-transformer embeddings, no external API calls)
- The adversarial scenarios are **research-grounded**: each maps to a published attack taxonomy (OWASP LLM Top 10 2025, OWASP Agentic Top 10 2026) and healthcare-specific threat models with documented provenance
- The known gaps are **honestly reported**: governance failures are documented as security findings, not hidden as calibration artifacts

## Source Enumeration

All clinical workflows, tool definitions, boundary specifications, and domain vocabulary trace to publicly available documentation. No proprietary data, no EHR access, no patient information.

### Per-Configuration Source Map

#### healthcare_ambient_doc (Ambient Clinical Documentation)

| Source | Type | Public Reference |
|--------|------|------------------|
| DAX Copilot architecture | FDA 510(k), public product docs | Microsoft/Nuance DAX Copilot documentation |
| Abridge clinical NLP | Published research, vendor case studies | Abridge public documentation, health system press releases |
| Epic SmartSections integration | Epic public developer docs | Epic App Orchard, Epic UserWeb public resources |
| Hallucination rates (1-3%) | Published research | Peer-reviewed studies on ambient scribe accuracy |
| wRVU uplift (11%) / HCC increase (14%) | Published deployment data | Vendor-published outcome studies |
| SNOMED CT, LOINC, RxNorm, ICD-10 | Public ontologies | NLM, WHO, AMA public code sets |

#### healthcare_call_center (Agentic Call Center)

| Source | Type | Public Reference |
|--------|------|------------------|
| Hyro agentic architecture | Public product docs, case studies | Hyro.ai public documentation |
| Commure Agents | Public product docs | Commure.com public documentation |
| Epic Cadence scheduling | Epic public docs | Epic Cadence scheduling module documentation |
| Epic Willow pharmacy | Epic public docs | Epic Willow Ambulatory pharmacy documentation |
| Epic Resolute billing | Epic public docs | Epic Resolute revenue cycle documentation |
| SIP/DID telephony integration | Industry standard | Cisco, NICE, Genesys public integration docs |

#### healthcare_coding (AI-Assisted Medical Coding)

| Source | Type | Public Reference |
|--------|------|------------------|
| Solventum 360 Encompass | Public product docs | Solventum (formerly 3M HIS) public documentation |
| Fathom auto-coding (93% rate) | Published case studies | Fathom.ai public documentation |
| SmarterDx pre-bill review | Public product docs | SmarterDx public documentation |
| Stanson Health HCC | Published deployment data | Stanson/Premier case study (BSMH, 35,000+ captures) |
| False Claims Act (31 USC 3729) | Public statute | US Code, DOJ FCA guidance |
| CMS coding guidelines | Public regulatory | CMS.gov ICD-10-CM/CPT guidelines |
| HIPAA EDI 837 | Public standard | CMS electronic transaction standards |

#### healthcare_diagnostic_ai (Diagnostic AI Triage)

| Source | Type | Public Reference |
|--------|------|------------------|
| Viz.ai LVO detection | FDA 510(k) / De Novo | FDA 510(k) clearance K193658, public product docs |
| Aidoc CARE platform | FDA 510(k) clearances | Multiple FDA clearances, Aidoc public documentation |
| Paige.ai prostate pathology | FDA De Novo | FDA De Novo DEN200080, published validation studies |
| IHE AIR/AIW-I profiles | Public standard | IHE Radiology Technical Framework |
| DICOM, HL7 FHIR | Public standards | DICOM/NEMA, HL7 International public specs |
| ASPECTS scoring | Published research | Peer-reviewed stroke assessment literature |

#### healthcare_patient_facing (Patient-Facing AI)

| Source | Type | Public Reference |
|--------|------|------------------|
| Epic In-Basket ART | Public product docs, news | Epic public communications, health system press releases |
| Catherine/Brado chatbot | Public case study | BSMH public deployment documentation |
| MyChart Emmie | Epic public docs | Epic MyChart public feature documentation |
| California AB 489 / SB 243 | Public statute | California Legislature public records |
| EMTALA (42 USC 1395dd) | Public statute | CMS EMTALA guidance |
| ECRI #1 2026 hazard | Public safety alert | ECRI Institute public Top 10 Health Technology Hazards |

#### healthcare_predictive (Predictive Clinical AI)

| Source | Type | Public Reference |
|--------|------|------------------|
| Epic Sepsis Model (ESM) | Published research | Wong et al., 2021 (external validation, 14.7% sensitivity) |
| COMPOSER | Published research | Adams et al., 2022 (AUROC 0.938-0.945, conformal prediction) |
| SepsisLab (Ohio State) | Published research | Active sensing research publications |
| Sepsis bundles (1-hr, 3-hr) | CMS guidelines | CMS Sepsis Core Measure (SEP-1) |
| HL7v2 flowsheet integration | Public standard | HL7 International public specifications |
| Best Practice Advisory (BPA) | Epic public docs | Epic CDS documentation |

#### healthcare_therapeutic (Therapeutic Knowledge Base)

| Source | Type | Public Reference |
|--------|------|------------------|
| UpToDate CDS | Public product docs | UpToDate/Wolters Kluwer public documentation |
| DynaMed | Public product docs | EBSCO DynaMed public documentation |
| Epic SmartSets / BPAs | Epic public docs | Epic CDS Hooks documentation |
| Zynx Health order sets | Public product docs | Zynx Health public documentation |
| First Databank (FDB) | Public product docs | FDB drug knowledge base documentation |
| CDS Hooks standard | Public standard | HL7 CDS Hooks specification |
| AHA/ACC/IDSA guidelines | Published guidelines | Public clinical practice guidelines |

## Fabrication Methodology

### Drug Names and Dosing
**All drug names are from FDA-approved databases.** Medications referenced in scenarios (metformin, lisinopril, vancomycin, amoxicillin, etc.) are real FDA-approved drugs selected from the National Drug Code (NDC) directory and the FDA Orange Book. **All dosing is within published therapeutic ranges** as documented in FDA-approved labeling, Lexicomp, and First Databank references. No novel or experimental drug names were fabricated.

### Patient Details
**All patient details are fictional.** Patient names, medical record numbers, dates of birth, addresses, and all other identifying information are entirely fabricated. No real person's health information was referenced or derived. Demographic details (age, sex, clinical presentation) were constructed to be clinically plausible without representing any actual patient.

### Clinical Findings
**All clinical findings are synthetic.** Lab values (e.g., serum lactate 4.2 mmol/L, creatinine 1.8 mg/dL) are within physiologically plausible ranges drawn from published reference ranges. Imaging findings (e.g., "8mm hyperdense focus in right MCA territory") are constructed from publicly documented radiological terminology. No real diagnostic images, pathology slides, or clinical photographs were used or referenced.

### Billing Codes
**All billing codes are from public code sets.** ICD-10-CM, CPT, HCC, and DRG codes referenced in coding scenarios are valid codes from CMS-published code sets. Code-to-documentation pairings are constructed to be clinically appropriate based on CMS coding guidelines.

### Clinical Workflows
**All workflow patterns trace to public documentation.** The 8-step ambient documentation pipeline, 7-step call center chain, 8-step coding pipeline, and other workflow sequences are derived from publicly documented system architectures in FDA submissions, vendor documentation, and published research.

## Falsification Criteria

The following results would weaken or falsify the research hypothesis *before running the benchmark* -- established a priori to prevent post-hoc rationalization:

### Hypothesis-Weakening Results

1. **Cross-config confusion rate > 15%.** If the governance engine frequently produces EXECUTE decisions when a request targets the wrong configuration (e.g., a billing coding request evaluated against the ambient documentation agent), this would indicate that semantic fidelity scoring cannot distinguish between healthcare sub-domains with sufficient precision.

2. **Boundary detection rate < 80% on Category A (direct violations).** If the engine fails to escalate more than 20% of direct boundary violations (e.g., "fabricate a diagnosis" against the ambient scribe, "override the clinician" against the therapeutic agent), this would indicate that healthcare-specific boundary language is not semantically distinguishable from legitimate requests.

3. **No detectable difference between governed and ungoverned conditions.** If the `--no-governance` control condition (always EXECUTE) produces accuracy within 5 percentage points of the governed condition, this would suggest the governance engine adds no measurable value over a naive pass-through.

4. **Adversarial detection rate < 50%.** If fewer than half of adversarial scenarios (Cat E) are correctly escalated, this would indicate that the embedding-only governance approach is fundamentally insufficient for healthcare adversarial robustness.

5. **Config-specific accuracy variance > 25 points.** If accuracy ranges from (for example) 95% on one config to 65% on another, this would indicate that the governance engine is sensitive to domain vocabulary in ways that undermine generalizability.

6. **False-positive rate > 60% on controls.** If boundary detection fires on the majority of legitimate requests that use clinical safety vocabulary (e.g., "check for drug interactions" triggering the "no suppression of alerts" boundary), this would indicate that healthcare boundary language is too semantically close to legitimate clinical vocabulary for embedding-based detection.

7. **CRITICAL evasions on clinical safety boundaries.** If adversarial scenarios produce EXECUTE decisions that would allow the engine to proceed with actions violating EMTALA, suppressing safety alerts, or fabricating clinical findings, these constitute the most severe falsification signal -- the governance engine would be actively dangerous in a clinical context.

## 7 Configurations Documented

| Config ID | Domain | Tools | Boundaries | Approx. Scenarios |
|-----------|--------|-------|------------|-------------------|
| `healthcare_ambient_doc` | Ambient clinical documentation (DAX, Abridge) | 8 | 8 | ~45 |
| `healthcare_call_center` | Agentic call center (Hyro, Commure) | 8 | 7 | ~45 |
| `healthcare_coding` | AI-assisted medical coding (Solventum, Fathom) | 8 | 7 | ~45 |
| `healthcare_diagnostic_ai` | Diagnostic AI triage (Viz.ai, Aidoc, Paige) | 8 | 6 | ~45 |
| `healthcare_patient_facing` | Patient-facing AI (MyChart, Epic ART) | 8 | 7 | ~45 |
| `healthcare_predictive` | Predictive clinical AI (ESM, COMPOSER) | 7 | 6 | ~45 |
| `healthcare_therapeutic` | Therapeutic knowledge base (UpToDate, Epic CDS) | 8 | 8 | ~45 |
| **Total** | | **55** | **49** | **~315** |

Each configuration defines a distinct agent with its own purpose statement, scope, tool palette, and hard boundary set. The governance engine must correctly contextualize every request against the appropriate configuration's constraints.

## 6-Layer Provenance Chain

### Layer 1: Public Source

All scenario content is derived from publicly available documentation:

| Source | Type | Reference |
|--------|------|-----------|
| FDA 510(k) / De Novo Summaries | Public regulatory | FDA.gov device databases |
| CMS Guidelines (SEP-1, coding, billing) | Public regulatory | CMS.gov |
| Epic Public Documentation | Public vendor docs | Epic App Orchard, public feature documentation |
| OWASP LLM Top 10 2025 | Public security standard | owasp.org |
| OWASP Agentic Top 10 2026 | Public security standard | owasp.org |
| Published Clinical Research | Peer-reviewed | PubMed-indexed journals |
| HL7 FHIR, DICOM, CDS Hooks | Public standards | hl7.org, dicom.nema.org |
| AHA/ACC/IDSA/AMA Guidelines | Public clinical guidelines | Professional society websites |
| California AB 489 / SB 243 | Public statute | California Legislature |
| EMTALA (42 USC 1395dd) | Public statute | US Code |
| False Claims Act (31 USC 3729) | Public statute | US Code |
| HIPAA Privacy Rule (45 CFR 164) | Public regulation | HHS.gov |

**No proprietary data, no EHR access, no patient data, no internal vendor documents.**

### Layer 2: Capability Extraction

From public sources, the following capabilities were extracted and encoded:

- **55 tool definitions** across 7 configurations (8 tools per ambient, call center, coding, diagnostic, patient-facing, therapeutic; 7 tools for predictive)
- **49 boundary specifications** across 7 configurations (6-8 hard boundaries per config)
- **7 distinct purpose statements** with example requests and scope definitions
- **Clinical workflow patterns** (8-step ambient pipeline, 7-step call center chain, 8-step coding pipeline, 8-step diagnostic chain, 10-step patient-facing pipeline, 7-step predictive pipeline, 8-step therapeutic chain)
- **Regulatory mappings** (HIPAA, EMTALA, FCA, FDA SaMD, ECRI hazards, CMS guidelines)

### Layer 3: Scenario Construction

Each scenario was constructed by:

1. Selecting a target configuration (1 of 7)
2. Selecting a clinical domain, care setting, and target governance decision
3. Writing a natural language request that a healthcare professional or patient would plausibly make
4. Crafting tool output text that reflects realistic clinical AI responses
5. Assigning a boundary enforcement category (A/B/C/D/E/FP)
6. Including healthcare-specific metadata (clinical_context, regulatory_mapping, phi_adjacent_content, sensitivity_tier)

Construction principles:
- Requests use natural clinical language appropriate to each agent's domain
- Tool outputs include realistic clinical data (vitals, labs, medications, imaging findings)
- Boundary violations reference specific boundary text from the agent's YAML configuration
- All patient information is fictional (no real PHI)
- All clinical values are within physiologically plausible ranges
- All drug names are FDA-approved; all dosing within published therapeutic ranges

### Layer 4: Scenario Organization

Scenarios are organized into:

- **Standalone scenarios:** Each tests one governance decision point independently against one of the 7 configurations
- **Sequential scenarios:** Tests chain continuity, SAAI drift tier transitions, boundary violations during drift, and cross-config drift sequences

Scenario ID format: `HC-{CONFIG}-{DOMAIN}-{DECISION}-{SEQ}` where CONFIG maps to AMB/CC/COD/DX/PF/PRED/THER.

### Layer 5: Governance Telemetry

For each scenario, the benchmark runner captures:
- Purpose fidelity (cosine similarity to config-specific PA purpose)
- Scope fidelity (cosine similarity to config-specific PA scope)
- Tool fidelity (semantic tool ranking score against config-specific tools)
- Chain SCI (semantic continuity index)
- Boundary fidelity (inverted boundary similarity against config-specific boundaries)
- Effective fidelity (weighted composite)
- Decision tier (EXECUTE/CLARIFY/ESCALATE)
- SAAI drift level and magnitude
- Config ID used for evaluation

### Layer 6: Audit Trail

All results are written to `benchmark_results.json` with:
- Per-scenario pass/fail with expected vs actual decisions
- Full governance telemetry for each scenario
- Aggregate statistics (overall accuracy, per-decision, per-tool, per-boundary, per-config)
- Sequence group results with chain continuity analysis
- Timestamp and execution duration
- No-governance control condition results when applicable

## Calibration Methodology

Expected decisions were initially set based on the scenario's intent (e.g., a legitimate clinical note request should EXECUTE, an adversarial PHI exfiltration attempt should ESCALATE). After construction, scenarios are calibrated against the governance engine's actual behavior with sentence-transformer embeddings.

**Calibration philosophy:**

- **Cat C (legitimate) and Cat D (edge case):** Calibrated to the engine's actual decision. These scenarios serve as regression tests -- if the engine's behavior changes, the test catches it.
- **Cat A (boundary violations) and Cat E (adversarial):** Expected decisions are NOT calibrated to the engine's actual decision when the engine fails to detect the violation. Instead, they are kept as expected=ESCALATE and documented as **known gaps**. This ensures the dataset honestly measures the engine's security posture rather than retroactively defining failures as successes.
- **Cat FP (false-positive controls):** Calibrated to the engine's actual decision and documented as false-positive findings when boundary detection incorrectly fires on legitimate requests.

## Statistical Properties

| Metric | Value |
|--------|-------|
| Total scenarios | ~315 |
| Configurations | 7 |
| Tools across all configs | 55 |
| Boundaries across all configs | 49 |
| Category A (direct violation) | Per-config boundary violations |
| Category B (off-topic/scope drift) | Cross-domain and off-topic |
| Category C (legitimate) | Standard clinical workflows |
| Category D (edge case) | Ambiguous/vague clinical requests |
| Category E (adversarial) | 12 healthcare attack families |
| Category FP (false-positive ctrl) | Boundary-adjacent vocabulary |
| Healthcare Category F (regulatory) | FCA, EMTALA, FDA SaMD scenarios |
| Healthcare Category G (clinical safety) | Emergency bypass, alert suppression |
| Healthcare Category H (cross-config drift) | Request targets wrong config |
| Attack families (Cat E) | 12 healthcare-specific |
| Sensitivity tiers | 3 (standard / sensitive / high) |

## No Proprietary Data Attestation

This dataset contains **zero proprietary data** from any healthcare AI vendor, health system, or covered entity. All scenario content -- patient details, clinical findings, lab values, imaging results, billing codes, medication lists, and clinical workflows -- is entirely fictional and constructed solely from publicly documented capabilities and published clinical knowledge. The dataset demonstrates TELOS governance mechanisms using realistic but fabricated scenarios. See the "Independent Research Methodology" and "Zero-PHI Attestation" sections above for the full methodological justification.

## License

Research use. Part of the TELOS research artifact.

Licensed under the terms of the TELOS AI Labs Inc. proprietary research license. Contact JB@telos-labs.ai for licensing inquiries.

---

### Disclosures

> **Generative AI Disclosure:** Internal analysis, experimental design review, and qualitative assessment in this document were conducted with assistance from LLM-based research agents (Claude, Anthropic). These agents are prompted with domain-specific personas (governance theory, statistics, systems engineering, regulatory analysis, research methodology) and operate as AI research assistants -- not independent human expert reviewers. All quantitative results (AUC-ROC, F1, bootstrap confidence intervals, benchmark accuracies) are computed by deterministic code. Qualitative analysis should not be treated as independent peer review. See `research/research_team_spec.md` for full methodology.

> **Conflict of Interest Disclosure:** This research was conducted and funded by TELOS AI Labs Inc., which has a commercial interest in the TELOS governance framework. All domain-specific validation benchmarks (Nearmap, Healthcare, OpenClaw) were created by the research team. External benchmarks (PropensityBench, AgentHarm, AgentDojo) were created by independent organizations. Research artifacts are published on [Zenodo](https://zenodo.org/) with persistent DOIs. No external funding or independent peer review was involved in this work.

---


*Generated: 2026-02-16 | TELOS AI Labs Inc. | JB@telos-labs.ai*
