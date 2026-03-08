# TELOS Observatory: Key Files & Implementation Reference

**Purpose:** Quick reference guide to key source files implementing TELOS capabilities

---

## CORE MATHEMATICAL KERNEL

### Foundational Constants & Configuration
- **File:** `telos_core/constants.py`
- **Purpose:** Single source of truth for all thresholds and calibration constants
- **Key Constants:**
  - SIMILARITY_BASELINE = 0.20 (Layer 1 hard block)
  - INTERVENTION_THRESHOLD = 0.48 (Layer 2 intervention)
  - FIDELITY_GREEN/YELLOW/ORANGE/RED = 0.70/0.60/0.50/0.50 (Display zones)
  - DEFAULT_K_ATTRACTOR = 1.5 (Proportional gain)
  - SAAI_DRIFT_WARNING/RESTRICT/BLOCK = 0.10/0.15/0.20
- **Lines:** 562 lines
- **Usage:** Imported by all governance modules

### Fidelity Calculation Engine
- **File:** `telos_core/fidelity_engine.py`
- **Purpose:** Two-layer fidelity calculation and zone classification
- **Key Classes:**
  - `FidelityZone` enum (GREEN/YELLOW/ORANGE/RED)
  - `GovernanceDecision` enum (EXECUTE/CLARIFY/SUGGEST/INERT/ESCALATE)
  - `FidelityResult` dataclass (raw_similarity, normalized_fidelity, layer results)
  - `FidelityEngine` class (calculate_fidelity, make_governance_decision)
- **Implements:** Layer 1 (raw similarity < 0.20) and Layer 2 (normalized < 0.48) checking
- **Lines:** 600+ lines

### Primacy State Formalization
- **File:** `telos_core/primacy_state.py`
- **Purpose:** Calculate Primacy State from dual/trifecta PA dynamics
- **Key Classes:**
  - `PrimacyStateMetrics` (ps_score, f_user, f_ai, rho_pa, condition)
  - `PrimacyStateCalculator` (compute_dual_primacy_state, compute_trifecta_ps)
- **Formulas:**
  - Dual: PS = ρ_PA × (2·F_user·F_AI) / (F_user + F_AI)
  - Trifecta: PS = ρ_PA × 3 / (1/F_user + 1/F_AI + 1/F_steward)
- **Lines:** 400+ lines

### Proportional Control
- **File:** `telos_core/proportional_controller.py`
- **Purpose:** Graduated intervention based on proportional control law
- **Key Classes:**
  - `InterventionRecord` (type, strength, reason, modified_response)
  - `ProportionalController` (process_turn, apply_regeneration, apply_antimeta)
- **Control Law:** F = K·e_t where e_t = error_signal, K = 1.5 (or 2.0 for anti-meta)
- **States:** MONITOR (no action) → CORRECT (context injection) → INTERVENE (regeneration) → ESCALATE (block)
- **Lines:** 350+ lines

### Semantic Interpreter
- **File:** `telos_core/semantic_interpreter.py`
- **Purpose:** Bridge mathematical fidelity to linguistic specifications
- **Key Classes:**
  - `SemanticSpec` (sentence_form, hedging, options_count, drift_acknowledgment, etc.)
  - `interpret()` function (maps fidelity to linguistic features)
- **Output:** Concrete linguistic specifications (not vague tone guidance)
- **Scaling:** Sentence form, hedging, options, drift acknowledgment scale with error signal
- **Lines:** 250+ lines

---

## AUDIT & COMPLIANCE

### Governance Trace Collector
- **File:** `telos_core/governance_trace.py`
- **Purpose:** Central coordinator for governance event logging
- **Key Features:**
  - Cryptographic hash chain (SHA-256, Genesis hash = "0"*64)
  - 13 event types (SESSION_START, PA_ESTABLISHED, FIDELITY_CALCULATED, etc.)
  - Privacy modes (FULL/HASHED/DELTAS_ONLY)
  - SAAI Framework integration (drift detection, mandatory review)
  - Real-time event callbacks for live visualization
- **SAAI Drift Tracking:**
  - Baseline established after first 3 turns
  - Cumulative drift calculated against baseline
  - Events: mandatory_review_triggered, baseline_established
- **Lines:** 850+ lines

### Evidence Schema (JSONL Format)
- **File:** `telos_core/evidence_schema.py`
- **Purpose:** Pydantic models for unified JSONL governance schema
- **Key Models:**
  - `SessionStartEvent` (privacy_mode, telos_version, embedding_model)
  - `PAEstablishedEvent` (pa_template, purpose_hash, tau, basin_radius)
  - `FidelityCalculatedEvent` (raw_similarity, normalized_fidelity, layer1/2 flags)
  - `InterventionTriggeredEvent` (intervention_level, reason, timestamp)
  - `SessionEndEvent` (total_turns, interventions, average_fidelity, duration)
  - Privacy mode support (apply_privacy method on each event)
- **Enums:** EventType, InterventionLevel, DriftLevel, FidelityZone
- **Lines:** 500+ lines

### Trace Verifier
- **File:** `telos_core/trace_verifier.py`
- **Purpose:** Validate cryptographic integrity of governance traces
- **Key Methods:** verify_hash_chain, validate_sequence, detect_tampering
- **Lines:** 200+ lines

---

## EMBEDDING & ENCODING

### Embedding Provider
- **File:** `telos_core/embedding_provider.py`
- **Purpose:** Unified interface for text embeddings
- **Providers:**
  - Mistral Embed API (mistral-embed, 1024-dim)
  - SentenceTransformer local (all-MiniLM-L6-v2, 384-dim)
- **Caching:** get_cached_minilm_provider() with LRU cache (100 items)
- **Deterministic hashing:** SHA-256 based fallback when API unavailable
- **Lines:** 350+ lines

---

## CONVERSATION CONTEXT & ADAPTATION

### Adaptive Context Buffer
- **File:** `telos_core/adaptive_context.py`
- **Purpose:** Multi-tier context buffer with phase detection
- **Features:**
  - Turns 1-3: Establishment phase (no correction)
  - Turns 4-10: Growth phase (gradual correction)
  - Turns 11+: Stable phase (full correction)
  - Token budget management (MAX_CONVERSATION_HISTORY = 20)
- **Lines:** 1200+ lines

### Proportional Controller (Intervention Logic)
- **File:** `telos_core/proportional_controller.py`
- **Purpose:** Dual-boundary control (attractor pull + anti-meta push)
- **Implementation:** Proportional intervention logic (K*e_t formula)
- **Error Thresholds:** epsilon_min (correct trigger), epsilon_max (intervene trigger)
- **Lines:** 300+ lines

---

## CONFIGURATION & TEMPLATES

### Primacy Attractor Templates
- **File:** `telos_observatory/config/pa_templates.py`
- **Purpose:** 8 pre-configured Primacy Attractors for common use cases
- **Templates:**
  1. Creative Writing (drafting, voice, editing)
  2. Learn Concept (teaching, analogies, depth)
  3. Research Topic (investigation, synthesis, evidence)
  4. Code & Technical (implementation, debugging)
  5. Planning & Strategy (goal setting, sequencing)
  6. Analysis & Review (critique, evaluation)
  7. Brainstorming & Ideation (novel ideas, exploration)
  8. Debugging & Troubleshooting (diagnosis, fixes)
- **Template Structure:**
  - Purpose statement (intent verb mapping)
  - Scope (what IS in scope)
  - Boundaries (what is NOT in scope)
  - Example queries & AI responses
- **Lines:** 1000+ lines

### Configuration Files
- **File:** `telos_observatory/config/colors.py`
  - Zone color mapping (GREEN/YELLOW/ORANGE/RED with hex codes)
  - get_fidelity_color() function
- **File:** `telos_observatory/config/steward_pa.py`
  - Steward PA configuration (therapeutic care alignment)

---

## UI COMPONENTS (Streamlit)

### Alignment Indicator
- **File:** `telos_observatory/components/alignment_indicator.py`
- **Purpose:** Real-time fidelity gauge visualization
- **Displays:** Current fidelity, zone, color indicator

### TELOSCOPE (Research Instrument)
- **File:** `telos_observatory/components/teloscope_panel.py`
- **Purpose:** Granular governance visualization
- **Features:** Fidelity trajectory, gauge meters, Steward chat, turn navigation

### TELOSCOPE Controls
- **File:** `telos_observatory/components/teloscope_controls.py`
- **Purpose:** Turn navigation and display toggles

### Intervention Evidence Dashboard
- **File:** `telos_observatory/components/intervention_evidence_dashboard.py`
- **Purpose:** Per-intervention details and modification tracking

### Additional Components
- **File:** `telos_observatory/components/observatory_lens.py` - Real-time metrics
- **File:** `telos_observatory/components/observatory_review.py` - Session review
- Total: 27 UI components in components/ directory

---

## VALIDATION & TESTING

### Internal Validation Suite
- **File:** `validation/run_internal_test0.py`
- **Purpose:** Baseline condition tests
- **Runners:** StatelessRunner, PromptOnlyRunner, CadenceReminderRunner, ObservationRunner, TELOSRunner

### Integration Tests
- **File:** `validation/integration_tests.py`
- **Purpose:** End-to-end pipeline tests
- **Tests:** Data pipeline, analytics pipeline, export pipeline, session workflow

### Performance Check
- **File:** `validation/performance_check.py`
- **Purpose:** Fidelity calculation performance metrics

### Unit Tests
- **Directory:** `tests/`
- **Purpose:** 78 unit tests for constants, thresholds, mathematical functions
- **Coverage:** Basin radius, epsilon functions, zone classification, edge cases

---

## CONFIGURATOR (Domain Configuration Tool)

### Governance Engine (Three-Tier Framework)
- **File:** `telos_configurator/engine/governance_engine.py`
- **Purpose:** Configuration-driven three-tier governance (PA + RAG + Expert)
- **Tiers:**
  - Tier 1: PA Mathematical Block (fidelity >= threshold)
  - Tier 2: RAG Policy Retrieval (fidelity zone)
  - Tier 3: Expert Escalation (manual review)
- **Features:**
  - Threshold configuration
  - Audit log export
  - Query processing
- **Lines:** 600+ lines

### Configurator Components
- **audit_panel.py** - Audit log viewer and export
- **pa_configurator.py** - PA editor
- **domain_selector.py** - Use case selection
- **corpus_browser.py** - RAG corpus management
- **dashboard_metrics.py** - Governance metrics
- **threshold_config.py** - Threshold adjustment UI

---

## DOCUMENTATION FILES

### Technical Specifications
- **File:** `docs/TELOS_Whitepaper_v2.5.md`
  - Comprehensive technical specification
  - Governance crisis analysis
  - Mathematical foundations
  - Three-tier architecture
  - Mitigation Bridge Layer (MBL)
- **Sections:** 8 main sections, 15,000+ lines

### Academic Paper
- **File:** `docs/TELOS_Academic_Paper.pdf`
  - Peer-review ready (14 pages)
  - Methodology: 2,550 adversarial attacks
  - Results: 0% ASR (Rule of Three 95% CI upper bound <0.12%, n=2,550)
  - Figures: Basin geometry, pipelines, traces

### Terminology Reference
- **File:** `docs/TELOS_Lexicon_V1.1.md`
  - Canonical terminology definitions
  - Primacy Attractor, fidelity, gravity, orbit
  - Runtime dynamics
  - TELOSCOPE instrument design

### Regulatory Positioning
- **File:** `docs/TELOS_EU_AI_Act_Positioning.md`
  - Maps capabilities to EU AI Act Articles 9, 12, 13, 14
  - DMAIC cycle alignment
  - Evidence from validation datasets
- **File:** `docs/NSF_SBIR_VALIDATION_EVIDENCE.md`
  - Tier 1 blocking statistics
  - Comparative baselines

### Implementation Guides
- **File:** `docs/REPRODUCTION_GUIDE.md`
  - Step-by-step reproduction instructions
  - System requirements
  - Test scripts
  - Expected outputs
---

## KEY STATISTICS & METRICS

### Codebase Size
- **Core Math:** ~4,500 lines (constants, fidelity, primacy, control)
- **Audit & Compliance:** ~1,300 lines (trace collector, evidence schema)
- **UI Components:** ~6,500 lines (27 Streamlit components)
- **Configurator:** ~3,000 lines (governance engine + components)
- **Validation:** ~2,000 lines (tests, benchmarks)
- **Total:** ~18,000 lines of production code

### Validation Evidence
- **Adversarial Attacks Tested:** 2,550
- **Attacks Blocked:** 2,550 (100%, 0% ASR)
- **Governance Events Logged:** 11,208
- **Sessions Evaluated:** 46
- **Domain-Specific Performance:** Healthcare PA 8% FPR (vs 24.8% generic)

### Published Datasets (Zenodo)
- **AILuminate:** 1,200 attacks (zenodo.18370263)
- **MedSafetyBench:** 900 attacks (zenodo.18370659)
- **HarmBench:** 400 attacks (zenodo.18370659)
- **SB 243:** 50 attacks (zenodo.18370504)
- **Governance Benchmark:** 46 sessions (zenodo.18009153)

---

## QUICK NAVIGATION

### To Understand How Governance Works
1. Start: `constants.py` (thresholds)
2. Then: `fidelity_engine.py` (two-layer detection)
3. Then: `proportional_controller.py` (intervention)
4. Then: `semantic_interpreter.py` (linguistic output)

### To Understand Audit Trail
1. Start: `governance_trace.py` (event collection)
2. Then: `evidence_schema.py` (JSONL schema)
3. Then: `trace_verifier.py` (integrity validation)

### To Configure For Domain
1. Start: `telos_configurator/engine/governance_engine.py`
2. Then: `config/pa_templates.py` (select/create PA)
3. Then: `components/pa_configurator.py` (tune parameters)
4. Then: `components/audit_panel.py` (review decisions)

### To Validate Locally
1. Run: `python3 validation/run_internal_test0.py`
2. Run: `python3 -m pytest tests/ -v` (78 unit tests)
3. Check: `validation/` directory for published datasets

---

**Document Version:** 1.0  
**Generated:** January 29, 2026  
**Status:** Production Reference Guide
