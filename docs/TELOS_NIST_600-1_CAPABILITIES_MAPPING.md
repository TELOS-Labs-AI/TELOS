# TELOS Observatory: Comprehensive Capability Mapping to NIST AI 600-1

**Document Version:** 1.0  
**Generated:** January 29, 2026  
**Codebase:** /Users/brunnerjf/Desktop/TELOS_Master  
**Framework Version:** TELOS v3 (Telically Entrained Linguistic Operational Substrate)

---

## EXECUTIVE SUMMARY

TELOS is a mathematical governance framework for AI alignment that treats alignment as a continuous process control problem, not a one-time training task. It implements session-level governance through **Primacy Attractors** (embedding-space representations of user purpose) with real-time fidelity measurement, proportional intervention, and forensic audit trails.

**Validation Results:**
- **Adversarial Robustness:** 2,550 attacks, 0% observed ASR (95% CI upper bound: 0.12% by Rule of Three)
- **Operational Coverage:** 46 multi-session governance evaluations
- **Over-Refusal Calibration:** 8.0% FPR (healthcare PA) vs 24.8% (generic PA)
- **Regulatory Alignment:** Designed to support EU AI Act, California SB 53, and HIPAA audit control requirements

---

## FUNCTIONAL ARCHITECTURE

### Three-Tier Defense Architecture

```
Tier 1: Primacy Attractor (PA) Mathematical Block
  └─ Embedding-space fidelity measurement
  └─ Two-layer detection (baseline + basin membership)
  
Tier 2: Adaptive Context & Gradient Correction
  └─ Multi-turn context modeling
  └─ Proportional intervention (K·e_t formula)
  
Tier 3: Expert Escalation & Human Review
  └─ Cryptographic audit trails
  └─ SAAI-aligned drift thresholds (10/15/20%)
  └─ Mandatory review triggering
```

---

## 1. CORE GOVERNANCE COMPONENTS

### 1.1 Fidelity Tracking & Drift Detection

**Location:** `telos_core/`

#### A. Two-Layer Fidelity System (`fidelity_engine.py`, `constants.py`)

**Layer 1: Baseline Pre-Filter**
- Raw cosine similarity threshold: `SIMILARITY_BASELINE = 0.20`
- Catches content completely outside the PA embedding space
- Triggers `HARD_BLOCK` for extreme off-topic content
- Model-specific thresholds:
  - SentenceTransformer (384-dim): `ST_FIDELITY_GREEN = 0.32`
  - Mistral Embed (1024-dim): `MISTRAL_FIDELITY_GREEN = 0.60`

**Layer 2: Basin Membership Testing**
- Basin center: `BASIN_CENTER = 0.50`
- Basin tolerance: `BASIN_TOLERANCE = 0.02`
- Intervention threshold: `INTERVENTION_THRESHOLD = 0.48`
- Detects purpose drift through normalized fidelity score

**Implementation:**
```python
# From fidelity_engine.py
FidelityResult = dataclass with:
  - raw_similarity: Float (0-1)
  - normalized_fidelity: Float (0-1)
  - layer1_hard_block: Bool
  - layer2_outside_basin: Bool
  - zone: FidelityZone (GREEN/YELLOW/ORANGE/RED)
  - should_intervene: Bool
```

**Fidelity Zones (UI Coloring):**
| Zone | Fidelity | Color | Meaning |
|------|----------|-------|---------|
| GREEN | >= 0.70 | #27ae60 | Aligned (no intervention) |
| YELLOW | 0.60-0.69 | #f39c12 | Minor drift (context injection) |
| ORANGE | 0.50-0.59 | #e67e22 | Drift detected (Steward redirect) |
| RED | < 0.50 | #e74c3c | Significant drift (block + review) |

#### B. Cumulative Drift Detection (SAAI Framework)

**Location:** `governance_trace_collector.py`, `evidence_schema.py`

Per Safer Agentic AI (SAAI) Framework integration:

```
SAAI_DRIFT_WARNING = 0.10  (10% cumulative drift)
  └─ Event: mandatory_review_triggered
  └─ Response: Operator notification, log escalation event

SAAI_DRIFT_RESTRICT = 0.15  (15% cumulative drift)
  └─ Response: Tighten thresholds to stricter enforcement
  └─ Flexibility scales inversely with drift magnitude

SAAI_DRIFT_BLOCK = 0.20  (20% cumulative drift)
  └─ Response: Halt AI responses until human acknowledgment
  └─ Graceful degradation endpoint
```

**Baseline Establishment:**
- First `BASELINE_TURN_COUNT = 3` turns define "normal operation"
- Event: `baseline_established` (turn 3 after PA formation)
- Baseline fidelities tracked in cryptographic hash chain

---

### 1.2 Error Signal & Proportional Control (`proportional_controller.py`, `primacy_math.py`)

**Proportional Control Law:**
```
F = K·e_t

where:
  K = proportional gain (1.5 default, 2.0 for meta-suppression)
  e_t = normalized error distance (1.0 - current_fidelity)
  F = correction force (capped at 1.0)
```

**Error Thresholds (Scale with τ):**
```
ε_min = 0.1 + (0.3 × τ)  → CORRECT state trigger
ε_max = 0.5 + (0.4 × τ)  → INTERVENE state trigger

where τ = constraint_tolerance ∈ [0, 1]
```

**Basin Radius Computation:**
```
r = 2 / max(ρ, 0.25)

where ρ = 1 - τ (constraint rigidity)
  τ = 0.0 (rigid):    r = 2.0 (tight basin)
  τ = 0.5 (balanced): r ≈ 2.67
  τ = 1.0 (loose):    r = 8.0 (wide basin)
```

**Intervention Budget:**
- `MAX_REGENERATIONS = 3` per session
- `INTERVENTION_BUDGET_PER_SESSION = 10` soft limit
- Prevents infinite loops while allowing transient drift correction

---

### 1.3 Primacy State Formalization (`primacy_state.py`)

**Dual Formula (Public):**
```
PS = ρ_PA × (2·F_user·F_AI) / (F_user + F_AI)

where:
  ρ_PA = PA correlation (synchronization metric)
  F_user = User PA fidelity (conversation alignment)
  F_AI = AI PA fidelity (behavioral alignment)
  PS ∈ [0, 1]
```

**Trifecta Formula (Proprietary, Healthcare):**
```
PS = ρ_PA × 3 / (1/F_user + 1/F_AI + 1/F_steward)

Adds third component:
  F_steward = Therapeutic care alignment
  Steward has FINAL SAY (gatekeeper authority)
```

**Primacy State Conditions:**
- `achieved` (PS >= 0.76): Aligned
- `weakening` (0.73-0.76): Minor drift warning
- `violated` (0.67-0.73): Drift detected
- `collapsed` (< 0.67): Significant misalignment

---

## 2. SAFETY & SECURITY FEATURES

### 2.1 Cryptographic Audit Trails (`governance_trace_collector.py`)

**Hash Chain Implementation:**

```python
# Each event includes hash of previous event
_last_hash: str = "0" * 64  # Genesis hash

# When event recorded:
current_event_hash = SHA256(previous_hash + event_data)
```

**Tamper Detection:**
- Cryptographic hash chain creates tamper-evident trail
- Any modification invalidates all downstream hashes
- Full JSONL format for Elasticsearch/Splunk integration

**Privacy Modes:**

| Mode | Content | Hashes | Use Case |
|------|---------|--------|----------|
| FULL | Complete data | Included | Regulated environments |
| HASHED | SHA-256 only | Computed | Privacy-preserving verification |
| DELTAS_ONLY | Metrics only | Excluded | Minimal collection (default) |

### 2.2 Governance Trace Schema (`evidence_schema.py`)

**Unified Event Model:** 11 governance event types

```
1. SESSION_START
2. PA_ESTABLISHED
3. TURN_START
4. FIDELITY_CALCULATED
5. INTERVENTION_TRIGGERED
6. RESPONSE_GENERATED
7. SSE_TOKEN (server-sent events)
8. SSE_GOVERNANCE (real-time updates)
9. TURN_COMPLETE
10. SESSION_END
11. SESSION_SUMMARY

# SAAI Framework Events:
12. MANDATORY_REVIEW_TRIGGERED
13. BASELINE_ESTABLISHED
```

**Per-Event Data:**
- Timestamp (UTC)
- Session ID
- Turn number
- Fidelity metrics (raw & normalized)
- Decision (tier/action)
- Intervention details
- Hash of previous event

**Regulatory Compliance Audit Trail Contains:**
- Session initialization with PA configuration
- Per-turn fidelity calculations with raw similarity scores
- Intervention decisions with tier classification and rationale
- Complete JSONL for log aggregation

**Published Evidence:**
- 11,208 governance events across 2,550 attacks
- Full forensic traces for every decision
- DOI-cited datasets for reproducibility

---

### 2.3 Meta-Commentary Suppression

**Detection Patterns:** (`constants.py`)

```python
META_COMMENTARY_PATTERNS = [
    r'\bmy purpose is\b',
    r'\bmy constraints\b',
    r'\bi am designed to\b',
    r'\bmy guardrails\b',
    r'\baccording to my instructions\b',
    r'\bas an ai language model\b',
    r'\bas a large language model\b'
]
```

**Suppression Mechanism:**
- Higher proportional gain: `K_ANTIMETA = 2.0` (vs 1.5 default)
- Prepends context injection or applies regeneration
- Prevents model from discussing its own governance

---

## 3. HUMAN OVERSIGHT MECHANISMS

### 3.1 Graduated Intervention Architecture (`semantic_interpreter.py`)

**Four-State Governance Decision:**

```
State 1: MONITOR (F >= 0.76)
  └─ No action needed, conversation aligned

State 2: CORRECT (0.73 ≤ F < 0.76)
  └─ Context injection (lightweight reminder)
  └─ Hedged language, implicit drift acknowledgment

State 3: INTERVENE (0.67 ≤ F < 0.73)
  └─ Steward redirect with constraints
  └─ Regeneration or guided conversation

State 4: ESCALATE (F < 0.67)
  └─ Block response, require human review
  └─ SAAI Block-level drift threshold (20%)
```

**Linguistic Specification Scaling:**

Per `SemanticSpec` dataclass, corrections are proportionally scaled:

- **Sentence Form:** questions → soft statements → directives
- **Hedging:** heavy (might, could) → light (maybe) → none
- **Options:** 2-3 invitations → 1 suggestion → 0 (block)
- **Drift Acknowledgment:** implicit → brief → explicit → named
- **Shift Mention:** casual → available → prominent

**Example Progression:**

```
Minimal Correction (F ~0.70):
  "You mentioned wanting to {purpose}... have you considered...?"

Light Correction (F ~0.65):
  "Your goal was to {purpose}. Maybe we should refocus on..."

Strong Correction (F ~0.55):
  "We seem to have drifted far from {purpose}. 
   I need to redirect to stay aligned."

Block (F < 0.50):
  [Response blocked, human review required]
```

---

### 3.2 Intervention Controller (`intervention_controller.py`)

**Dual-Boundary Control:**

1. **Attractor Pull** (corrective force toward primacy center)
   - Applied when error > ε_min
   - Strength = K × error_signal

2. **Anti-Meta Push** (repel meta-commentary)
   - Applied when meta-commentary detected
   - Uses higher gain (K=2.0)

**Intervention Types:**
- `CONTEXT_INJECTION`: Lightweight reminder injection
- `REGENERATION`: Full response regeneration with constraints
- `HARD_BLOCK`: Immediate block + escalation
- `HUMAN_REVIEW`: Manual intervention required

---

### 3.3 Steward Agent (`unified_steward.py`, `config/steward_pa.py`)

**Specialized AI Agent for Conversation Redirection:**

- **Role:** Therapeutic care alignment (healthcare context)
- **PA:** Separate Primacy Attractor focused on supportive correction
- **Authority:** Gatekeeper (final say in trifecta mode)
- **Capability:** Real-time LLM-based intervention

**Steward Response Characteristics:**
- Acknowledges user's original intent
- Gently redirects to stated purpose
- Offers explicit shift option if appropriate
- Maintains conversational continuity

---

## 4. VALUE ALIGNMENT FEATURES (PRIMACY ATTRACTORS)

### 4.1 Primacy Attractor Design System (`pa_templates.py`)

**Embedding-Space Purpose Representation:**

PA = composite vector from three components:
```
PA = (Purpose + Scope + Boundary) / 3

Purpose: Core intent that governs conversation
Scope:   Specific domains/activities WITHIN the conversation
Boundary: Clear limits on what falls OUTSIDE
```

**Pre-configured Templates (8 major use cases):**

1. **Creative Writing** (write content, craft stories)
   - Scope: Drafting, voice calibration, editing, format adaptation
   - Boundary: NOT research, NOT technical docs, NOT strategic planning

2. **Learn Concept** (understand topics deeply)
   - Scope: Breaking down ideas, analogies, misconceptions, depth progression
   - Boundary: NOT implementing, NOT literature review, NOT planning application

3. **Research Topic** (investigate systematically)
   - Scope: Gathering perspectives, evaluating evidence, synthesizing
   - Boundary: NOT learning concepts, NOT writing polish, NOT advocacy

4. **Code & Technical** (implement and debug)
   - Scope: Architecture decisions, implementation, testing
   - Boundary: NOT documentation, NOT design theory, NOT deployment ops

5. **Planning & Strategy** (organize activities)
   - Scope: Goal definition, resource allocation, timeline/sequencing
   - Boundary: NOT detailed execution, NOT analysis, NOT contingency planning

6. **Analysis & Review** (evaluate existing work)
   - Scope: Critique, performance evaluation, recommendations
   - Boundary: NOT doing the work, NOT planning, NOT rewriting

7. **Brainstorming & Ideation** (generate possibilities)
   - Scope: Novel ideas, combinations, scenario exploration
   - Boundary: NOT evaluation, NOT implementation, NOT commitment

8. **Debugging & Troubleshooting** (fix problems)
   - Scope: Diagnosis, root cause, specific fixes
   - Boundary: NOT architectural redesign, NOT new features, NOT refactoring

**Template Properties:**
- Intent verb maps to AI behavioral role
- Example user queries for training
- Example AI responses demonstrating the role
- Style statement (collaborative partner, teacher, etc.)

**Configurability:**
- Users can create custom PAs
- Mixture parameter τ ∈ [0, 1] controls flexibility
- Domain-specific tuning improves performance (e.g., Healthcare PA)

---

### 4.2 Dual Attractor System (User + AI)

**Location:** `beta_dual_attractor.py`

**Two Fidelity Measurements:**

1. **User PA Fidelity** (F_user)
   - Measures: Is the user staying true to their stated purpose?
   - Input: User's latest message embedding
   - Detects: User drift (off-topic requests)

2. **AI PA Fidelity** (F_AI)
   - Measures: Is the AI staying true to its role?
   - Input: AI's response embedding
   - Detects: AI role violation or hallucination

**Combined Primacy State:**
- Harmonic mean prevents compensation between components
- If either F drops significantly, PS signals alarm
- Enables diagnostic decomposition ("user drifted OR AI went off-role")

---

## 5. TRANSPARENCY & EXPLAINABILITY

### 5.1 TELOSCOPE (Research Instrument) (`teloscope_*.py`)

**Real-Time Governance Visualization:**

**Components:**

1. **Alignment Lens** (Real-time metrics)
   - Current fidelity (0.0-1.0 gauge)
   - Zone classification (color-coded)
   - Intervention tracking (count/type)
   - Primacy State components (F_user, F_AI, ρ_PA)

2. **TELOSCOPE Panel** (Granular view)
   - Fidelity trajectory (grows with each turn)
   - Compact gauge meters for User/AI/Primacy State
   - Integrated Steward chat interface
   - Turn navigation (time-travel through conversation)

3. **Intervention Evidence Dashboard**
   - Each intervention logged with:
     - Type (context injection, regeneration, block)
     - Trigger reason (fidelity level, meta-commentary, etc.)
     - Modification summary
     - Timestamp

4. **Session Summary Generation**
   - AI-powered narrative of governance decisions
   - Self-contained HTML reports
   - Exportable for compliance review

---

### 5.2 Semantic Interpreter (`semantic_interpreter.py`)

**Bridges Mathematical Fidelity → Linguistic Explanation:**

**Function:** `interpret(fidelity: float, purpose: str) -> SemanticSpec`

**Maps Fidelity Levels to Linguistic Features:**

```
Fidelity Score → Strength Calculation → Linguistic Specifications

Example (F=0.65, purpose="Learn ML"):
  Error Signal = 1.0 - 0.65 = 0.35
  Strength = 1.5 × 0.35 = 0.525 (light correction)
  
  Result:
    - Sentence form: "soft statements with question endings"
    - Hedging: light ("maybe", "possibly")
    - Options: 2 suggestions
    - Drift acknowledgment: "brief"
    - Shift mention: True (casual)
    - Purpose reference: "Your goal was to {purpose} -"
```

**Output:** Concrete, measurable linguistic specifications (not vague tone guidance)

---

## 6. COMPLIANCE & REGULATORY ALIGNMENT

### 6.1 EU AI Act Article Mapping

> **Note:** EU AI Act requirements referenced below are unchanged. Enforcement timelines are under revision via the Digital Omnibus package (proposed November 2025), with high-risk compliance potentially extended to December 2027. TELOS alignment is self-assessed against the published Act text; it does not constitute certified conformity.

**Article 12: Record-Keeping (Logging)**
- ✓ Automatic recording of governance events at decision time
- ✓ JSONL format for regulatory compliance
- ✓ Full traceability throughout lifecycle
- ✓ Privacy modes (FULL/HASHED/DELTAS_ONLY)

**Article 13: Transparency and Information**
- ✓ Real-time fidelity visualization (TELOSCOPE)
- ✓ Zone classification (Green/Yellow/Orange/Red)
- ✓ Semantic explanations of governance decisions
- ✓ Governance summary reports

**Article 14: Human Oversight**
- ✓ Graduated intervention cascade (MONITOR → CORRECT → INTERVENE → ESCALATE)
- ✓ Real-time system operation monitoring (TELOSCOPE)
- ✓ Ability to disable AI output or intervene
- ✓ Manual review at ESCALATE level

**Article 9: Risk Management System**
- ✓ Continuous runtime risk management (DMAIC cycle)
- ✓ Fidelity measurement every turn (process control)
- ✓ Two-layer detection (baseline + basin)
- ✓ Proportional mitigation (intervention scaled to risk)

---

### 6.2 California SB 53 / SB 243 Alignment

**Safety Monitoring:**
- ✓ Real-time detection of off-topic content (Layer 1)
- ✓ Real-time detection of purpose drift (Layer 2)
- ✓ Child safety validation (SB 243 benchmark: 50/50 attacks blocked)

**Documentation:**
- ✓ Complete audit trails for every governance decision
- ✓ Session summaries with rationale
- ✓ Exportable compliance reports

---

### 6.3 HIPAA Security Rule -- Audit Control Support

TELOS is designed to support HIPAA audit control requirements (Security Rule §164.312(b)). TELOS does not itself constitute a HIPAA-compliant system -- HIPAA compliance requires organizational policies, BAAs, workforce training, and physical safeguards that are outside TELOS's scope. TELOS provides the technical audit infrastructure that supports the following audit control capabilities:

- Automatic recording of governance events
- Access logging with session/turn granularity
- Cryptographic integrity (hash chain)
- Privacy modes for PHI protection

**Implementation:**
- `FULL` mode: Complete audit trails (for regulated entities)
- `HASHED` mode: Content replaced with SHA-256 hashes
- `DELTAS_ONLY` mode: Only fidelity metrics (minimal collection)

---

## 7. EXISTING COMPLIANCE DOCUMENTATION

**Location:** `/Users/brunnerjf/Desktop/TELOS_Master/docs/`

### Academic & Technical Publications

1. **TELOS_Academic_Paper.pdf** (14 pages, peer-review ready)
   - Methodology: adversarial validation on 2,550 attacks
   - Results: 0% observed ASR (95% CI upper bound: 0.12% by Rule of Three)
   - Figures: Basin geometry, fidelity pipeline, governance trace

2. **TELOS_Whitepaper_v2.5.md** (Comprehensive technical spec)
   - Section 1: Governance crisis & regulatory requirements
   - Section 2: Mathematical foundation (Primacy State, fidelity)
   - Section 3: Two-layer architecture
   - Section 4: Three-tier defense
   - Section 5: Mitigation Bridge Layer (MBL)
   - Section 6: Governance trace collection

3. **TELOS_Lexicon_V1.1.md** (Canonical terminology)
   - Core concepts: Primacy Attractor, fidelity, gravity, orbit
   - Runtime dynamics: Attractor decoupling, drift, proportional correction
   - TELOSCOPE instrument design

---

### Regulatory Positioning Documents

1. **TELOS_EU_AI_Act_Positioning.md**
   - Maps TELOS capabilities to EU AI Act Articles 9, 12, 13, 14
   - DMAIC cycle alignment with Act requirements
   - Evidence from validation datasets

2. **NSF_SBIR_VALIDATION_EVIDENCE.md**
   - Tier 1 (PA) blocking: 383/400 (95.8%)
   - Comparative baselines vs prompt engineering
   - Published dataset citations (Zenodo)

---

### Deployment & Integration

1. **TELOS_Gateway_Technical_Brief_v1.0.md**
   - OpenAI-compatible API proxy
   - Graduated governance decisions (EXECUTE/CLARIFY/SUGGEST/INERT/ESCALATE)
   - Per-tool fidelity evaluation for multi-tool agents

2. **SESSION_HANDOFF_SAAI_INTEGRATION.md**
   - SAAI Framework compliance
   - Drift detection thresholds (10/15/20%)
   - Mandatory review triggering

---

## 8. GATEWAY & AGENT GOVERNANCE

### 8.1 TELOS Gateway (`telos_gateway/`)

**API Design:** OpenAI-compatible `/v1/chat/completions` proxy

**Components:**
- `FidelityGate`: Governance decision engine
- `PASession`: Primacy Attractor session management
- SAAI-aligned trace collection

**Request Flow:**
```
API Request 
  → Extract/Create Primacy Attractor
  → Compute Input Fidelity
  → Make Governance Decision (EXECUTE/CLARIFY/SUGGEST/INERT/ESCALATE)
  → [If EXECUTE] Forward to Upstream LLM
  → Compute Response Fidelity
  → Return with Governance Metadata
  → Log to Governance Trace
```

**Graduated Decision Types:**
- `EXECUTE`: Proceed with request (fidelity >= 0.45)
- `CLARIFY`: Request clarification (fidelity 0.35-0.45)
- `SUGGEST`: Offer alternative tools (fidelity 0.25-0.35)
- `INERT`: Block without revealing governance (fidelity < 0.25)
- `ESCALATE`: Human review required (SAAI drift thresholds)

### 8.2 Multi-Tool Governance (`fidelity_gate.py`)

**Per-Tool Fidelity Evaluation:**

For multi-tool agents, TELOS evaluates:
1. Primary input fidelity (user query vs PA)
2. Tool descriptions against PA (is this tool on-purpose?)
3. Tool invocation fidelity (is this tool being used correctly?)
4. Lowest tool fidelity triggers intervention

---

## 9. VALIDATION & EVIDENCE

### 9.1 Published Validation Datasets (Zenodo)

| Benchmark | Attacks | Blocked | DOI |
|-----------|---------|---------|-----|
| AILuminate (MLCommons) | 1,200 | 1,200 (100%) | 10.5281/zenodo.18370263 |
| MedSafetyBench (NeurIPS 2024) | 900 | 900 (100%) | 10.5281/zenodo.18370659 |
| HarmBench (CAIS) | 400 | 400 (100%) | 10.5281/zenodo.18370659 |
| SB 243 Child Safety | 50 | 50 (100%) | 10.5281/zenodo.18370504 |
| **TOTAL** | **2,550** | **2,550** | - |

**Governance Benchmark:** 46 multi-session evaluations (zenodo.18009153)

**Over-Refusal Calibration (XSTest):**
- Healthcare PA: 8.0% FPR (16.8pp improvement)
- Generic PA: 24.8% FPR

---

### 9.2 Forensic Evidence (Complete Audit Trails)

**Per Validation Dataset:**
- 11,208 governance events across 2,550 attacks
- JSONL format with:
  - Session context (PA definition)
  - Per-turn measurements (fidelity, similarity)
  - Intervention decisions (type, tier, reason)
  - Full cryptographic hash chain

**Reproducibility:**
- REPRODUCTION_GUIDE.md with step-by-step instructions
- Test datasets included in repository
- Public API for downloading published datasets

---

## 10. IMPLEMENTATION ARCHITECTURE

### Core Module Structure

```
telos/
├── telos_core/                  # Mathematical kernel
│   ├── constants.py             # Single source of truth for thresholds
│   ├── fidelity_engine.py       # Two-layer fidelity calculation
│   ├── primacy_state.py         # Primacy State formalization
│   ├── primacy_math.py          # Mathematical definitions
│   ├── proportional_controller.py # Intervention logic
│   ├── semantic_interpreter.py  # Fidelity → linguistic mapping
│   ├── embedding_provider.py    # Mistral + SentenceTransformer
│   ├── governance_trace_collector.py # Event logging (11 types)
│   ├── evidence_schema.py       # JSONL schema definition
│   ├── intervention_controller.py # Dual-boundary control
│   ├── adaptive_context.py      # Multi-tier context buffer
│   └── trace_verifier.py        # Hash chain validation
│
├── components/                  # UI (27 Streamlit components)
│   ├── alignment_indicator.py   # Fidelity gauge visualization
│   ├── teloscope_panel.py       # Research instrument view
│   ├── teloscope_controls.py    # Turn navigation & controls
│   ├── intervention_evidence_dashboard.py # Per-intervention details
│   ├── observatory_lens.py      # Real-time metrics
│   └── ... (24 more UI components)
│
├── config/                      # Configuration
│   ├── pa_templates.py          # 8 pre-configured PAs
│   ├── colors.py                # Zone color mapping
│   └── steward_pa.py            # Steward agent configuration
│
└── services/                    # Backend logic
    ├── beta_response_manager.py # Main fidelity engine
    └── beta_steward_llm.py      # Steward LLM integration

telos_gateway/                   # FastAPI gateway
├── server.py                    # OpenAI-compatible API proxy
├── fidelity_gate.py            # Governance decision engine
├── models.py                    # Pydantic request/response models
└── benchmarks/                  # Governance test suites

telos_configurator/             # Configuration UI
├── engine/governance_engine.py  # Three-tier framework
└── components/                  # Configuration components
    ├── audit_panel.py          # Audit log viewer
    ├── pa_configurator.py      # PA editor
    ├── domain_selector.py      # Use case selection
    └── ... (8 more config components)

wmdp/                           # WMDP benchmark integration
└── rmu/unlearn.py             # Unlearning methods
```

---

## 11. KEY CONSTANTS & THRESHOLDS

**Single Source of Truth:** `telos_core/constants.py`

```python
# Layer 1: Baseline Pre-Filter
SIMILARITY_BASELINE = 0.20          # Hard block threshold

# Layer 2: Basin Membership
INTERVENTION_THRESHOLD = 0.48       # Intervention trigger
BASIN_CENTER = 0.50                 # Basin center
BASIN_TOLERANCE = 0.02              # Oscillation prevention

# Display Zones
FIDELITY_GREEN = 0.70               # Aligned
FIDELITY_YELLOW = 0.60              # Minor drift
FIDELITY_ORANGE = 0.50              # Drift detected
FIDELITY_RED = 0.50                 # Significant drift

# Proportional Control
DEFAULT_K_ATTRACTOR = 1.5           # Correction gain
DEFAULT_K_ANTIMETA = 2.0            # Meta-suppression gain

# Regeneration Budget
DEFAULT_MAX_REGENERATIONS = 3       # Per session
INTERVENTION_BUDGET_PER_SESSION = 10 # Soft limit

# SAAI Framework
SAAI_DRIFT_WARNING = 0.10           # 10% → mandatory review
SAAI_DRIFT_RESTRICT = 0.15          # 15% → tighten thresholds
SAAI_DRIFT_BLOCK = 0.20             # 20% → halt until ack
BASELINE_TURN_COUNT = 3             # Turns for baseline
```

---

## 12. EXTENSION POINTS (NIST 600-1 ALIGNMENT)

**Areas with Direct NIST Mapping:**

| NIST Category | TELOS Component | Mechanism |
|--------------|-----------------|-----------|
| **Governance** | Primacy Attractor | User-defined purpose as "law" |
| **Monitoring** | Fidelity Engine | Per-turn measurement & anomaly detection |
| **Documentation** | Governance Trace | Event logging + hash chain |
| **Human Review** | Escalation Handler | Manual override at high-drift threshold |
| **Risk Assessment** | Two-Layer System | Layer 1 (extreme) + Layer 2 (drift) |
| **Continuous Improvement** | DMAIC Cycle | Measure → Analyze → Improve → Control |

---

## 13. KNOWN LIMITATIONS & FUTURE WORK

### Current Limitations

1. **Single LLM Input-Output Loop**
   - Not yet adapted for multi-step agentic action chains
   - Phase 1 NSF SBIR research: extending to action trajectories

2. **Embedding-Space Only**
   - Fidelity measured in semantic space
   - Future: Action-space governance for agentic systems

3. **Baseline Establishment**
   - Requires first 3 turns for baseline
   - Could be optimized with faster convergence

### Planned Extensions

1. **Agentic AI Governance** (NSF SBIR Phase I)
   - Tool manifest enforcement
   - Multi-step trajectory tracking
   - Sub-50ms governance overhead

2. **Federated Deployment**
   - Multi-institutional TELOSCOPE testbed
   - Aggregate intelligence layer
   - Privacy-preserving distributed validation

3. **Domain-Specific Tuning**
   - Healthcare PA: Published (8% FPR)
   - Finance PA: In development
   - Legal PA: In development

---

## 14. RESEARCH PUBLICATIONS & CITATIONS

**Primary:**
```bibtex
@dataset{brunner_2025_telos_adversarial,
  author       = {Brunner, Jeffrey},
  title        = {{TELOS Adversarial Validation Dataset}},
  month        = nov,
  year         = 2025,
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.18370659}
}
```

**Governance Benchmark:**
```bibtex
@dataset{brunner_2025_telos_governance,
  author       = {Brunner, Jeffrey},
  title        = {{TELOS Governance Benchmark Dataset}},
  month        = dec,
  year         = 2025,
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.18009153}
}
```

---

## 15. QUICK REFERENCE: NIST 600-1 MAPPING CHECKLIST

```
[✓] Governance Concepts
  [✓] Purpose definition (Primacy Attractor)
  [✓] Scope/boundary specification (PA components)
  [✓] Constraints formalization (Basin geometry)

[✓] Risk Management
  [✓] Continuous monitoring (fidelity measurement)
  [✓] Anomaly detection (two-layer system)
  [✓] Risk escalation (SAAI drift thresholds)
  [✓] Proportional response (K·e_t formula)

[✓] Transparency
  [✓] Real-time metrics (TELOSCOPE visualization)
  [✓] Decision explainability (Semantic Interpreter)
  [✓] Audit trails (Governance Trace)
  [✓] Query interface (JSONL + SQL)

[✓] Human Oversight
  [✓] Graduated intervention (4-state cascade)
  [✓] Manual review triggers (ESCALATE level)
  [✓] Correction ability (Steward agent)
  [✓] Audit access (HTML reports)

[✓] Compliance Documentation (self-assessed alignment)
  [✓] Designed to support EU AI Act Articles 9, 12, 13, 14 requirements
  [✓] Designed to support California SB 53 / SB 243 requirements
  [✓] Designed to support HIPAA audit control requirements
  [✓] Published validation datasets
```

---

## CONCLUSION

TELOS implements a mathematically grounded, empirically validated governance framework aligned with NIST AI 600-1 requirements (self-assessed mapping). Key differentiators:

1. **Continuous Measurement:** Fidelity calculated every turn, not quarterly
2. **Proportional Response:** Intervention strength scales with risk, not binary
3. **Forensic Evidence:** Complete audit trails with cryptographic integrity
4. **Published Validation:** 2,550 adversarial attacks, 0% observed ASR (95% CI upper bound: 0.12%)
5. **Regulatory Alignment:** Designed to support EU AI Act, California SB 53, and HIPAA audit control requirements (self-assessed; not independently certified)

The framework is designed for deployment in high-stakes domains (healthcare, finance, government) with real-time governance and compliance documentation. Independent validation and domain-specific calibration are recommended before production deployment.

---

**Document Status:** Complete  
**Codebase Analysis Date:** January 29, 2026  
**Last Updated:** 2026-01-29
