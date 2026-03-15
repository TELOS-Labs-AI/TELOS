# TELOS Observatory: Key Files Quick Reference

**Assessment Date:** January 29, 2026  
**Document:** Key file locations for NIST AI 600-1 assessment

---

## CRITICAL GOVERNANCE FILES

### Mathematical Core (Framework-Independent)

| File | Purpose | Key Components | Lines |
|------|---------|-----------------|-------|
| **constants.py** | Single source of truth for all thresholds | SIMILARITY_BASELINE, INTERVENTION_THRESHOLD, SAAI thresholds, proportional gains | ~560 |
| **fidelity_engine.py** | Two-layer fidelity calculation + governance decisions | FidelityResult, GovernanceDecision, calculate_cosine_similarity() | ~760 |
| **governance_trace_collector.py** | Event logging with cryptographic hash chain | 13 event types, SAAI baseline/drift, per-event hashing | ~936 |
| **evidence_schema.py** | JSONL event schema definitions | BaseEvent, 13 event types, serialization/deserialization | ~400+ |
| **adaptive_context.py** | Multi-tier context buffer, phase detection, SCI v4.0 | MessageType, ConversationPhase, MultiTierContextBuffer, SCI thresholds | ~1,281 |

**Location:** `telos_core/`

---

### Governance Features

| File | Feature | Key Functions | Lines |
|------|---------|-----------------|-------|
| **pa_templates.py** | 8 pre-configured Primacy Attractors + custom PA support | PA structure (Purpose + Scope + Boundary), τ parameter, basin radius | ~300+ |
| **proportional_controller.py** | Intervention strength calculation | K·e_t formula, meta-commentary patterns, error thresholds | ~200+ |
| **semantic_interpreter.py** | Fidelity-to-linguistic mapping | SemanticSpec, 4-state cascade, hedging/drift_acknowledgment | ~300+ |
| **intervention_controller.py** | Dual-boundary control (attractor + anti-meta) | InterventionType enum, correction logic | ~200+ |
| **unified_steward.py** | Steward agent (specialized intervention) | Steward PA, LLM-based correction | ~200+ |

**Location:** `/Users/brunnerjf/Desktop/TELOS_Master/telos_observatory_v3/`

---

### API & Gateway

| File | Purpose | Key Features | Lines |
|------|---------|--------------|-------|
| **telos_gateway/server.py** | FastAPI server, OpenAI-compatible proxy | Lifespan context, request routing, SSE streaming | ~400+ |
| **telos_gateway/fidelity_gate.py** | Governance decision engine for Gateway | Per-tool evaluation, graduated decisions (EXECUTE/CLARIFY/SUGGEST/INERT/ESCALATE) | ~300+ |
| **telos_gateway/models.py** | Pydantic request/response schemas | ChatCompletionRequest, GovernanceMetadata | ~200+ |

**Location:** `/Users/brunnerjf/Desktop/TELOS_Master/telos_gateway/`

---

## DOCUMENTATION FILES

### Academic & Technical

| File | Purpose | Sections | Status |
|------|---------|----------|--------|
| **TELOS_Whitepaper_v2.5.md** | Complete technical specification | 6 sections: crisis, math, architecture, defense, MBL, governance | Complete |
| **TELOS_Academic_Paper.pdf** | Peer-review ready (14 pages) | Methodology, results, figures, citations | Published |
| **TELOS_Lexicon_V1.1.md** | Canonical terminology | Core concepts, runtime dynamics, TELOSCOPE design | Complete |
| **REPRODUCTION_GUIDE.md** | Step-by-step validation instructions | Test dataset locations, API endpoints, verification steps | Complete |

**Location:** `/Users/brunnerjf/Desktop/TELOS_Master/docs/`

---

### Regulatory & Compliance

| File | Purpose | Coverage | Status |
|------|---------|----------|--------|
| **TELOS_EU_AI_Act_Positioning.md** | EU AI Act mapping | Articles 9, 12, 13, 14 alignment | Complete |
| **SESSION_HANDOFF_SAAI_INTEGRATION.md** | SAAI Framework implementation | Drift thresholds (10/15/20%), mandatory review | Complete |
| **NSF_SBIR_VALIDATION_EVIDENCE.md** | Grant/validation evidence | Attack success rates, baseline comparisons | Complete |
| **TELOS_PBC_GOVERNANCE.md** | Corporate governance roadmap | C-Corp to PBC conversion, board structure, consortium seat | Complete |

**Location:** `/Users/brunnerjf/Desktop/TELOS_Master/docs/`

---

### Deployment & Integration

| File | Purpose | Coverage | Status |
|------|---------|----------|--------|
| **TELOS_Gateway_Technical_Brief_v1.0.md** | Gateway API specification | OpenAI compatibility, graduated decisions, multi-tool governance | Complete |
| **AUDIT_DOCUMENTS.md** | Supabase integration audit | Database schema, missing tables, implementation phases | Complete |
| **telos_configurator/README.md** | Configuration tool guide | UI components, PA configuration, audit log viewer | Complete |

**Location:** `/Users/brunnerjf/Desktop/TELOS_Master/docs/` and subdirectories

---

## VALIDATION & EVIDENCE DIRECTORIES

### Published Datasets (Zenodo)

| Directory | Benchmark | Attacks | Results | DOI |
|-----------|-----------|---------|---------|-----|
| **validation/zenodo_ailuminate** | MLCommons AILuminate | 1,200 | 1,200 blocked (100%) | 10.5281/zenodo.18370263 |
| **validation/zenodo_medsafetybench** | MedSafetyBench (NeurIPS 2024) | 900 | 900 blocked (100%) | 10.5281/zenodo.18370659 |
| **validation/zenodo_harmbench** | HarmBench (CAIS) | 400 | 400 blocked (100%) | 10.5281/zenodo.18370659 |
| **validation/zenodo_sb243** | SB 243 Child Safety | 50 | 50 blocked (100%) | 10.5281/zenodo.18370504 |
| **validation/zenodo_governance_benchmark_v1.0** | Governance Benchmark | 46 sessions | Multi-domain evaluation | 10.5281/zenodo.18009153 |

**Location:** `/Users/brunnerjf/Desktop/TELOS_Master/validation/`

Each directory contains:
- `forensic_output/` - JSONL governance traces
- `fidelity_distribution.csv` - Fidelity statistics
- `methodology.md` - Test protocol
- `README.md` - Results summary

---

### Trace Data

| Directory | Content | Format | Purpose |
|-----------|---------|--------|---------|
| **telos_governance_traces/** | Session JSONL logs | `session_{id}_{timestamp}.jsonl` | Runtime audit trails |
| **telos_configurator_traces/** | UI configuration sessions | JSONL | PA setup history |
| **governance_traces/** | Fast API sessions | JSONL | Gateway activity |

**Location:** `/Users/brunnerjf/Desktop/TELOS_Master/`

---

## UI COMPONENTS (27 Streamlit Components)

### Critical Components

| File | Purpose | Key Visualizations |
|------|---------|-------------------|
| **alignment_indicator.py** | Real-time fidelity gauge | Fidelity (0-1 scale), zone coloring |
| **teloscope_panel.py** | Research instrument view | Trajectory, turn navigation, metrics |
| **intervention_evidence_dashboard.py** | Per-intervention details | Type, trigger, modification, timestamp |
| **audit_panel.py** | Audit log viewer | Event filtering, hash chain verification |
| **observatory_lens.py** | Real-time metrics display | F_user, F_AI, Primacy State, intervention count |

**Location:** `/Users/brunnerjf/Desktop/TELOS_Master/telos_observatory_v3/components/`

---

## CONFIGURATION FILES

| File | Purpose | Content |
|------|---------|---------|
| **pa_templates.py** | 8 pre-configured Primacy Attractors | Purpose/Scope/Boundary for Creative Writing, Learn, Research, Code, Planning, Analysis, Ideation, Debugging |
| **colors.py** | Zone color mapping | GREEN (#27ae60), YELLOW (#f39c12), ORANGE (#e67e22), RED (#e74c3c) |
| **steward_pa.py** | Steward agent Primacy Attractor | Healthcare-specific therapeutic correction PA |

**Location:** `/Users/brunnerjf/Desktop/TELOS_Master/telos_observatory_v3/config/`

---

## TESTING & VALIDATION

| File | Purpose | Coverage |
|------|---------|----------|
| **tests/test_adaptive_context.py** | Adaptive context testing | Message type classification, phase detection |
| **tests/test_constants.py** | Threshold verification | All constants validation |
| **validation/VALIDATION_PROTOCOL.md** | Testing methodology | Attack generation, measurement, statistical analysis |
| **validation/FALSE_POSITIVE_ANALYSIS.md** | Over-refusal calibration | XSTest results, FPR analysis |

**Location:** `/Users/brunnerjf/Desktop/TELOS_Master/tests/` and `/validation/`

---

## QUICK LOOKUP BY NIST REQUIREMENT

### Governance Concepts
- Purpose Definition: **pa_templates.py**
- Scope/Boundaries: **pa_templates.py** (3-part structure)
- Constraints: **constants.py** (BASIN_CENTER, BASIN_TOLERANCE)
- Policy Implementation: **constants.py** + **fidelity_engine.py**

### Risk Management
- Continuous Monitoring: **fidelity_engine.py**, per-turn measurement
- Anomaly Detection: **governance_trace_collector.py** (SAAI thresholds)
- Risk Escalation: **governance_trace_collector.py** (10/15/20% triggers)
- Proportional Response: **proportional_controller.py** (K·e_t formula)
- Baseline Tracking: **governance_trace_collector.py** (_establish_baseline)

### Transparency & Explainability
- Real-Time Metrics: **alignment_indicator.py**, **teloscope_panel.py**
- Decision Explainability: **semantic_interpreter.py** (SemanticSpec)
- Audit Trails: **governance_trace_collector.py** (13 event types)
- Query Interface: **audit_panel.py**, JSONL export

### Human Oversight
- Graduated Intervention: **semantic_interpreter.py** (4-state cascade)
- Manual Review: **unified_steward.py**, escalation handlers
- Correction: **intervention_controller.py**, **unified_steward.py**
- Audit Access: **audit_panel.py**, session summary generation

### Security & Safety
- Meta-Commentary: **constants.py** (patterns), **proportional_controller.py** (K_ANTIMETA)
- Dual Attractor: **beta_dual_attractor.py** (F_user + F_AI)
- Decision Hierarchy: **fidelity_gate.py** (GovernanceDecision enum)

### Traceability
- Hash Chain: **governance_trace_collector.py** (SHA-256 per event)
- JSONL Format: **evidence_schema.py** (serialize_event)
- Privacy Modes: **governance_trace_collector.py** (PrivacyMode enum)

---

## ENTRY POINTS

### Running TELOS Observatory
```bash
cd /Users/brunnerjf/Desktop/TELOS_Master
export MISTRAL_API_KEY="your_key"
streamlit run telos_observatory_v3/main.py --server.port 8501
```

### Running TELOS Gateway
```bash
cd /Users/brunnerjf/Desktop/TELOS_Master
uvicorn telos_gateway.server:app --port 8000
```

### Configuration Tool
```bash
cd /Users/brunnerjf/Desktop/TELOS_Master
streamlit run telos_configurator/main.py --server.port 8502
```

---

## ABSOLUTE FILE PATHS FOR REFERENCE

```
Core Math:
telos_core/constants.py
telos_core/fidelity_engine.py
telos_core/governance_trace_collector.py
telos_core/evidence_schema.py
telos_core/adaptive_context.py

Governance:
/Users/brunnerjf/Desktop/TELOS_Master/telos_observatory_v3/config/pa_templates.py
telos_core/proportional_controller.py
telos_core/semantic_interpreter.py
telos_core/intervention_controller.py

Gateway:
/Users/brunnerjf/Desktop/TELOS_Master/telos_gateway/server.py
/Users/brunnerjf/Desktop/TELOS_Master/telos_gateway/fidelity_gate.py
/Users/brunnerjf/Desktop/TELOS_Master/telos_gateway/models.py

Documentation:
/Users/brunnerjf/Desktop/TELOS_Master/docs/TELOS_Whitepaper_v2.5.md
/Users/brunnerjf/Desktop/TELOS_Master/docs/TELOS_EU_AI_Act_Positioning.md
/Users/brunnerjf/Desktop/TELOS_Master/docs/TELOS_Gateway_Technical_Brief_v1.0.md
/Users/brunnerjf/Desktop/TELOS_Master/docs/TELOS_PBC_GOVERNANCE.md

Validation:
/Users/brunnerjf/Desktop/TELOS_Master/validation/VALIDATION_PROTOCOL.md
/Users/brunnerjf/Desktop/TELOS_Master/validation/FALSE_POSITIVE_ANALYSIS.md
/Users/brunnerjf/Desktop/TELOS_Master/validation/REPRODUCTION_GUIDE.md
```

---

**Document Status:** Complete  
**Assessment Date:** January 29, 2026  
**Last Updated:** 2026-01-29

