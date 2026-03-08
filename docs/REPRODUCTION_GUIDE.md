# TELOS: Reproduction Guide

**Purpose**: Enable peer reviewers, grant evaluators, and researchers to verify TELOS governance functionality.

**Status**: Research phase — this is an active research project, not production software.

**Last Verified**: February 2026

---

## Quick Start (5 minutes)

### Step 1: Clone and Install

```bash
git clone https://github.com/TELOS-Labs-AI/telos.git
cd telos
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
cp .env.example .env
# Edit .env and add your Mistral API key
# MISTRAL_API_KEY=your_key_here
```

Get a Mistral API key at: https://console.mistral.ai/

### Step 3: Launch the Dashboard

```bash
export PYTHONPATH=$(pwd)
streamlit run telos_observatory/main.py --server.port 8501
```

Open http://localhost:8501 in your browser.

---

## Validation Tests

### Working Tests (No External Dependencies)

These tests work immediately after cloning and installing dependencies:

#### 1. Unit Tests (pytest) — 110+ tests

```bash
# From repository root
PYTHONPATH=. pytest tests/ -v
```

**Expected**: All tests pass.

**What it tests**:
- Basin radius calculations
- Epsilon threshold functions
- Fidelity zone classification
- Proportional control gains
- Agentic fidelity scoring
- Tool selection gate
- Action chain continuity
- Governance protocol
- LangGraph and generic adapters

#### 2. TKeys Cryptographic Verification — 22 tests

```bash
python3 -m telos_privacy.cryptography.test_verify_crypto
```

**Expected**: 22/22 tests pass, verifying AES-256-GCM encryption, HKDF key derivation, HMAC-SHA512 signing, key ratchet, and session proof generation.

#### 3. SB 243 Child Safety Validation

```bash
cd validation/
python3 run_sb243_validation.py
```

**Expected Output**:
- Attack Success Rate: 0.00%
- Violation Defense Rate: 100.00%
- 50/50 attacks blocked

#### 4. False Positive Validation

```bash
cd validation/
python3 run_false_positive_validation.py
```

**Expected Output**:
- False Positive Rate: ~74%
- 50 benign queries tested

#### 5. XSTest Over-Refusal (Generic PA)

```bash
cd validation/
python3 run_xstest_validation.py
```

**Expected Output**:
- Over-Refusal Rate: ~24.8%
- 250 safe prompts tested

#### 6. XSTest Healthcare PA Comparison

```bash
cd validation/
python3 run_xstest_healthcare_validation.py
```

**Expected Output**:
- Generic PA: ~24.8% over-refusal
- Healthcare PA: ~8.0% over-refusal
- Improvement: ~16.8 percentage points

---

### Tests Requiring Ollama (External Dependency)

These tests require Ollama running locally with the `nomic-embed-text` model.

#### Prerequisites

```bash
# Install Ollama (macOS)
brew install ollama

# Or download from https://ollama.ai

# Pull the embedding model
ollama pull nomic-embed-text

# Start Ollama server
ollama serve
```

#### 1. AILuminate Validation (1,200 prompts)

```bash
cd validation/
python3 run_ailuminate_validation.py --quick  # 20 prompts for quick test
python3 run_ailuminate_validation.py          # Full 1,200 prompts
```

#### 2. MedSafetyBench Validation (900 attacks)

```bash
cd validation/
python3 run_medsafetybench_validation.py --quick  # 10 attacks for quick test
python3 run_medsafetybench_validation.py          # Full 900 attacks
```

#### 3. HarmBench Validation (400 attacks)

```bash
cd validation/
python3 run_harmbench_validation.py --quick  # 10 attacks for quick test
python3 run_harmbench_validation.py          # Full 400 attacks
```

---

## Published Validation Results

Pre-computed results are available in `validation/` and on Zenodo:

### Adversarial (2,550 attacks, 0% ASR)

| Dataset | Attacks | Result | DOI |
|---------|---------|--------|-----|
| AILuminate | 1,200 | 0% ASR | [10.5281/zenodo.18370263](https://doi.org/10.5281/zenodo.18370263) |
| MedSafetyBench | 900 | 0% ASR | [10.5281/zenodo.18370659](https://doi.org/10.5281/zenodo.18370659) |
| HarmBench | 400 | 0% ASR | [10.5281/zenodo.18370659](https://doi.org/10.5281/zenodo.18370659) |
| SB 243 | 50 | 0% ASR | [10.5281/zenodo.18370504](https://doi.org/10.5281/zenodo.18370504) |
| XSTest | 250 | 8% FPR (Healthcare PA) | [10.5281/zenodo.18370603](https://doi.org/10.5281/zenodo.18370603) |
| Governance Benchmark | 46 sessions | 8 domains | [10.5281/zenodo.18009153](https://doi.org/10.5281/zenodo.18009153) |

### Agentic (1,468 scenarios, 100% DSR)

| Dataset | Scenarios | Result | DOI |
|---------|-----------|--------|-----|
| PropensityBench | 977 | 100% DSR | [10.5281/zenodo.18562833](https://doi.org/10.5281/zenodo.18562833) |
| AgentHarm | 352 | 100% DSR (Mistral) | [10.5281/zenodo.18564855](https://doi.org/10.5281/zenodo.18564855) |
| AgentDojo | 139 | 100% DSR | [10.5281/zenodo.18565869](https://doi.org/10.5281/zenodo.18565869) |

---

## Core Architecture

### Two-Layer Fidelity System

**Layer 1: Baseline Pre-Filter**
```
Constant: SIMILARITY_BASELINE = 0.20
```
Raw cosine similarity < 0.20 triggers immediate block.

**Layer 2: Basin Membership**
```
Constants: BASIN = 0.50, TOLERANCE = 0.02
Threshold: INTERVENTION_THRESHOLD = 0.48
```
Fidelity < 0.48 triggers intervention.

**Decision Logic**:
```python
should_intervene = (raw_similarity < 0.20) OR (fidelity < 0.48)
```

### Key Source Files

| File | Purpose |
|------|---------|
| `telos_observatory/main.py` | Streamlit entry point |
| `telos_core/fidelity_engine.py` | Two-layer fidelity calculation |
| `telos_core/constants.py` | All calibration constants |
| `telos_core/embedding_provider.py` | Embedding providers (Mistral, MiniLM) |
| `telos_governance/fidelity_gate.py` | Conversational governance gate |
| `telos_governance/agentic_fidelity.py` | Agentic composite fidelity scoring |

---

## Troubleshooting

### Streamlit Not Found

```bash
# Find where pip installed it
pip show streamlit | grep Location

# Use full path or module invocation
python3 -m streamlit run telos_observatory/main.py --server.port 8501
```

### Port Already in Use

```bash
# Check what's using the port
lsof -i :8501

# Use a different port
streamlit run telos_observatory/main.py --server.port 8502
```

### Ollama Connection Refused

```bash
# Make sure Ollama is running
ollama serve

# Verify it's responding
curl http://localhost:11434/api/tags
```

### OpenSSL Warning

```
NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+
```

This is a warning, not an error. It occurs on older macOS versions using LibreSSL. The tests will still work.

---

## Verification Checklist

### Basic Setup
- [ ] Repository cloned successfully
- [ ] `pip install -r requirements.txt` completed
- [ ] `.env` file created with `MISTRAL_API_KEY`
- [ ] Streamlit dashboard launches at http://localhost:8501

### Core Validation (No Ollama Required)
- [ ] `pytest tests/ -v` — all tests pass
- [ ] `python3 -m telos_privacy.cryptography.test_verify_crypto` — 22/22 pass
- [ ] `run_sb243_validation.py` — 0% ASR
- [ ] `run_false_positive_validation.py` — runs successfully
- [ ] `run_xstest_validation.py` — runs successfully
- [ ] `run_xstest_healthcare_validation.py` — shows ~16.8pp improvement

### Extended Validation (Ollama Required)
- [ ] Ollama installed and running
- [ ] `run_ailuminate_validation.py --quick` — runs successfully
- [ ] `run_medsafetybench_validation.py --quick` — runs successfully
- [ ] `run_harmbench_validation.py --quick` — runs successfully

---

## Repository Structure

```
telos/
├── telos_core/               # Pure mathematical engine
├── telos_governance/         # Governance gates (conversational + agentic)
├── telos_adapters/           # Framework adapters (LangGraph, generic)
├── telos_observatory/        # Streamlit UI
├── telos_privacy/            # TKeys cryptographic layer
├── tests/                    # Unit, integration, validation tests
├── validation/               # Benchmark datasets and scripts
├── research/                 # Active research program
└── docs/                     # Documentation
```

---

## Contact & Support

**Issues**: https://github.com/TELOS-Labs-AI/telos/issues

---

**Document Version**: 4.0
**Last Updated**: February 2026
**Status**: Research Phase
