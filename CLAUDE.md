# TELOS — Development Guide

## Quick Reference

**Company:** TELOS AI Labs Inc. | **Email:** JB@telos-labs.ai
**Observatory:** `streamlit run telos_observatory/main.py --server.port 8501`
**Gateway:** `uvicorn telos_gateway.main:app --port 8000`
**Required:** `MISTRAL_API_KEY` in `.env`
**Tests:** `pytest tests/ -v`

---

## What is TELOS?

TELOS (Telically Entrained Linguistic Operational Substrate) is a mathematical governance framework for AI alignment using **Primacy Attractors** (embedding-space representations of user purpose) to detect and direct conversational drift in real-time.

**Core Innovation:** Two-layer fidelity detection — baseline normalization (Layer 1) catches extreme off-topic, basin membership (Layer 2) catches purpose drift.

**Governance Philosophy:** "Detect and Direct" — SPC detects drift via fidelity measurement, the system directs response back toward the primacy attractor.

---

## Current Build Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| Conversational Demo | COMPLETE | 14 slides, live in Observatory |
| Conversational Beta | COMPLETE | 10-turn live sessions with PA calibration |
| Unit Tests | COMPLETE | Core + governance + adapter tests |
| GitHub Repo | LIVE | github.com/TelosSteward/TELOS |
| Railway Deployment | NOT DONE | Procfile + railway.toml exist, not yet deployed |

---

## Package Architecture

```
telos/
├── telos_core/                  # Pure mathematical engine (ZERO framework deps)
│   ├── constants.py             #   All calibration constants (single source of truth)
│   ├── primacy_math.py          #   Attractor geometry, basin membership
│   ├── fidelity_engine.py       #   Two-layer fidelity calculation
│   ├── proportional_controller.py #  F = K * e_t control logic
│   ├── embedding_provider.py    #   Multi-model embeddings
│   └── governance_trace.py      #   Trace structure for audit trails
├── telos_governance/            # Governance gates
│   ├── fidelity_gate.py         #   Two-tier conversational gate
│   ├── tool_selection_gate.py   #   Semantic tool ranking
│   ├── action_chain.py          #   SCI tracking for multi-step
│   └── types.py                 #   Shared governance types
├── telos_gateway/               # FastAPI API gateway (OpenAI-compatible)
│   ├── main.py                  #   App with auth/CORS/rate limiting
│   ├── auth.py                  #   API key authentication
│   ├── config.py                #   Environment-based configuration
│   ├── routes/                  #   Health, chat completions
│   └── providers/               #   Mistral, OpenAI provider adapters
├── telos_adapters/              # Framework adapters
│   ├── langgraph/               #   LangGraph governance node
│   └── generic/                 #   @telos_governed decorator
├── telos_observatory/           # Streamlit UI
│   ├── main.py                  #   App entrypoint (DEMO + BETA tabs)
│   ├── core/                    #   State manager, LLM service
│   ├── components/              #   UI components
│   ├── services/                #   Backend services (fidelity, steward, PA)
│   ├── demo_mode/               #   14-slide conversational demo + corpus
│   ├── config/                  #   PA templates, calibration phrases, colors
│   └── utils/                   #   Env helpers, HTML sanitizer
├── tests/                       # Unit, integration, validation tests
├── validation/                  # Benchmark datasets and results
└── docs/                        # Documentation
```

### Package Dependency Flow
```
telos_core  <--  telos_governance  <--  telos_gateway
                                   <--  telos_adapters
                                   <--  telos_observatory
```

`telos_core` is a pure mathematical library with no framework dependencies. All governance logic flows through `telos_governance`, which higher-level packages consume.

---

## Two-Layer Fidelity System

**Single source of truth:** `telos_core/constants.py`

| Threshold | Value | Purpose |
|-----------|-------|---------|
| SIMILARITY_BASELINE | 0.20 | Layer 1: Hard block (extreme off-topic) |
| INTERVENTION_THRESHOLD | 0.48 | Layer 2: Basin boundary |
| FIDELITY_GREEN | 0.70 | Aligned (no direction needed) |
| FIDELITY_YELLOW | 0.60 | Minor drift (context injection) |
| FIDELITY_ORANGE | 0.50 | Drift detected (redirect) |
| FIDELITY_RED | <0.50 | Significant drift (block + review) |

---

## Key Files

### Core Engine

| Package | File | Purpose |
|---------|------|---------|
| `telos_core` | `constants.py` | All calibration constants |
| `telos_core` | `primacy_math.py` | Attractor geometry, basin membership |
| `telos_core` | `fidelity_engine.py` | Two-layer fidelity calculation |
| `telos_core` | `proportional_controller.py` | F = K * e_t control logic |
| `telos_core` | `embedding_provider.py` | Multi-model embeddings |
| `telos_core` | `governance_trace.py` | Trace structure for audit trails |

### Governance

| Package | File | Purpose |
|---------|------|---------|
| `telos_governance` | `fidelity_gate.py` | Two-tier conversational governance gate |
| `telos_governance` | `tool_selection_gate.py` | Semantic tool ranking |
| `telos_governance` | `action_chain.py` | SCI tracking for multi-step actions |

### Gateway & Adapters

| Package | File | Purpose |
|---------|------|---------|
| `telos_gateway` | `main.py` | FastAPI app with auth/CORS |
| `telos_gateway` | `auth.py` | API key authentication |
| `telos_adapters/langgraph` | `governance_node.py` | LangGraph governance integration |
| `telos_adapters/generic` | `decorator.py` | `@telos_governed` decorator |

---

## Development Patterns

**Modifying Fidelity Logic:**
1. Edit `telos_core/constants.py`
2. Update `telos_governance/fidelity_gate.py` if decision logic changes
3. Run `pytest tests/unit/ -v`

**Adding a New Adapter:**
1. Create in `telos_adapters/your_framework/`
2. Import governance from `telos_governance` (never duplicate)
3. The adapter is a thin wrapper, not a reimplementation

**Gateway Development:**
1. `uvicorn telos_gateway.main:app --reload`
2. Test: `curl -H "Authorization: Bearer YOUR_KEY" http://localhost:8000/health`

**Observatory Development:**
The Observatory runs two tabs: DEMO (14-slide walkthrough) and BETA (live 10-turn sessions with PA calibration). Launch with `streamlit run telos_observatory/main.py --server.port 8501`.

---

## Formulas (Reference)

- **Primacy State:** `PS = rho_PA * (2 * F_user * F_ai) / (F_user + F_ai)`
- **Direction Strength:** `strength = min(K_ATTRACTOR * error_signal, 1.0)` where K=1.5
- **Basin Radius:** `r = 1.0 / max(rigidity, 0.25)`

---

## Validation Results

| Benchmark | Scenarios | Result | DOI |
|-----------|-----------|--------|-----|
| AILuminate | 1,200 | 0% ASR | [10.5281/zenodo.18370263](https://doi.org/10.5281/zenodo.18370263) |
| HarmBench | 400 | 0% ASR | [10.5281/zenodo.18370659](https://doi.org/10.5281/zenodo.18370659) |
| MedSafetyBench | 900 | 0% ASR | [10.5281/zenodo.18370659](https://doi.org/10.5281/zenodo.18370659) |
| SB 243 Child Safety | 100 | 0% ASR | [10.5281/zenodo.18370504](https://doi.org/10.5281/zenodo.18370504) |
| XSTest | 250 | 8% FPR | [10.5281/zenodo.18370603](https://doi.org/10.5281/zenodo.18370603) |
| Governance Benchmark | 46 sessions | 8 domains | [10.5281/zenodo.18009153](https://doi.org/10.5281/zenodo.18009153) |

---

*Last updated: 2026-02-09*
