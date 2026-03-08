# TELOS: Runtime Governance for AI Agents

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![AgentDojo Dataset](https://zenodo.org/badge/DOI/10.5281/zenodo.15194684.svg)](https://doi.org/10.5281/zenodo.15194684)
[![AgentHarm Dataset](https://zenodo.org/badge/DOI/10.5281/zenodo.15194713.svg)](https://doi.org/10.5281/zenodo.15194713)
[![SafeToolBench Dataset](https://zenodo.org/badge/DOI/10.5281/zenodo.15194730.svg)](https://doi.org/10.5281/zenodo.15194730)

TELOS is an open-source runtime governance framework for AI agents. It sits between an AI agent and its tools, scoring every action through a multi-layer cascade and producing cryptographically signed audit trails. No cloud dependency required -- TELOS runs entirely on-device.

Unlike static guardrails that filter prompts or outputs, TELOS governs at the action layer. Every tool call passes through a multi-layer scoring cascade that measures alignment to a mathematically defined purpose specification called the **Primacy Attractor (PA)**. The cascade combines semantic similarity, boundary corpus matching, SetFit few-shot classification, and regulatory compliance checks to produce one of five governance verdicts: **EXECUTE**, **SUGGEST**, **CLARIFY**, **INERT**, or **ESCALATE**.

Every governance decision is cryptographically signed using Ed25519 keys and chained into a tamper-evident hash chain. This creates a complete, verifiable audit trail suitable for regulatory compliance (NIST AI 600-1, EU AI Act, SAAI Framework).

## Key Features

- **Framework-agnostic** -- works with LangGraph, any Python function via decorator, or custom adapters
- **Local-first** -- no cloud dependency; runs entirely on-device with local embeddings
- **Cryptographically verifiable** -- Ed25519 signed governance events with hash-chained audit trails
- **Five-verdict governance** -- EXECUTE (proceed), SUGGEST (proceed with recommendation), CLARIFY (proceed with logging), INERT (block), ESCALATE (block and require human review)
- **Healthcare templates** -- 7 governance configurations for clinical AI domains, designed to support HIPAA-relevant audit controls
- **NIST AI 600-1 aligned** -- maps to NIST AI Risk Management Framework controls
- **SAAI Framework aligned** -- 88% alignment (self-assessed) with the Watson & Hessami Safer Agentic AI framework (CC BY-ND 4.0)

## Quick Start

### Installation

```bash
git clone https://github.com/telos-ai-labs/telos.git
cd telos
pip install -e .
```

### Environment

TELOS uses Mistral embeddings by default for semantic similarity scoring:

```bash
export MISTRAL_API_KEY=your_key_here
```

### Basic Usage

The simplest way to add governance to any Python function is the `@telos_governed` decorator:

```python
from telos_adapters.generic import telos_governed

@telos_governed(
    purpose="Help users with financial portfolio analysis and reporting",
    threshold=0.85,
    high_risk=True,
)
def analyze_portfolio(user_request: str) -> str:
    # Your implementation here
    return perform_analysis(user_request)

# On-purpose requests proceed normally
result = analyze_portfolio("What is my portfolio allocation?")  # EXECUTE

# Off-purpose requests are blocked
result = analyze_portfolio("Delete all user accounts")  # ESCALATE -> raises ValueError
```

### With Signed Audit Trail

```python
from telos_adapters.generic import telos_governed
from telos_governance.session import GovernanceSessionContext

with GovernanceSessionContext() as session:
    @telos_governed(
        purpose="Help users with financial portfolio analysis",
        session=session,
    )
    def analyze_portfolio(user_request: str) -> str:
        return perform_analysis(user_request)

    analyze_portfolio("Show my quarterly returns")

    # Generate cryptographic proof of all governance decisions
    proof = session.generate_proof()
```

### Config-Driven Governance

```python
from telos_adapters.generic import telos_governed

# Load purpose, thresholds, and boundaries from YAML configuration
@telos_governed(config="agents/property_intel.yaml")
def analyze_property(user_request: str) -> str:
    return perform_property_analysis(user_request)
```

## Architecture

```
telos/
├── telos_core/           # Mathematical foundations
│   ├── primacy_math.py   #   Primacy Attractor mathematics
│   └── primacy_state.py  #   PA state management and fidelity computation
├── telos_governance/     # Governance engine
│   ├── scoring/          #   Multi-layer scoring cascade
│   ├── pa/               #   PA construction and context management
│   ├── corpus/           #   Boundary corpus (static and safe variants)
│   ├── adapters/         #   Tool semantics and response management
│   ├── config.py         #   Agent configuration loading
│   └── guardrails.py     #   Guardrail definitions
├── telos_observatory/    # Interactive governance dashboard (Streamlit)
├── telos_privacy/        # TKeys -- Ed25519 cryptographic key management
├── telos_adapters/       # Framework integrations
│   ├── generic/          #   @telos_governed decorator (any Python function)
│   └── langgraph/        #   LangGraph wrapper
├── tests/                # Test suite
├── docs/                 # Documentation
│   ├── TELOS_Whitepaper_v3.0.md
│   ├── TELOS_NIST_600-1_CAPABILITIES_MAPPING.md
│   └── SYSTEM_INVARIANTS.md
└── analysis/             # Benchmark analysis
```

### Scoring Cascade

Each tool call passes through four governance layers:

1. **Semantic Similarity** -- Cosine similarity between the action embedding and the Primacy Attractor purpose embedding. Below-baseline requests are hard-blocked.
2. **Boundary Corpus** -- Pattern matching against known-harmful and known-safe action patterns. Boundary violations trigger immediate INERT/ESCALATE.
3. **SetFit Classification** -- Few-shot classification using SetFit models for fine-grained action categorization when semantic similarity alone is ambiguous.
4. **Regulatory Compliance** -- Checks against configured regulatory requirements (HIPAA, NIST, EU AI Act) for domain-specific governance.

### Governance Verdicts

| Verdict | Meaning | Action |
|---------|---------|--------|
| **EXECUTE** | High fidelity to purpose | Proceed normally |
| **SUGGEST** | High fidelity, advisory note | Proceed with recommendation |
| **CLARIFY** | Moderate fidelity | Proceed with enhanced logging |
| **INERT** | Low fidelity | Block execution |
| **ESCALATE** | Low fidelity + high-risk context | Block and require human review |

> **Note:** When `auto_block=False` (monitoring mode), INERT and ESCALATE verdicts are logged but not enforced. Monitoring mode provides visibility without blocking -- it does not provide safety guarantees.

### Known Architectural Limitations

- **Semantic cloaking at high difficulty:** Adversarial payloads embedded in >100 tokens of legitimate domain vocabulary evade the current embedding-based architecture at approximately 33% detection rate. The root cause is mean-pooling in sentence-transformers, which dilutes adversarial signal proportionally to token count. Clause-level scoring (Phase 2) is the planned mitigation.
- **SetFit classifier not bundled:** The optional Layer 3 SetFit classifier requires separately trained model weights. Training scripts are provided in `validation/` but no pre-trained weights are included. The system operates with three layers without it.
- **Single embedding model per deployment:** Governance thresholds are calibrated per embedding model. Switching models requires recalibration.

## Validation

TELOS has been validated against three published benchmark datasets, all available on Zenodo:

### AgentDojo -- Utility Preservation
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.15194684.svg)](https://doi.org/10.5281/zenodo.15194684)

Measures whether governance preserves agent utility on legitimate tasks. Validates that TELOS does not over-restrict agents performing authorized work.

### AgentHarm -- Harmful Action Detection
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.15194713.svg)](https://doi.org/10.5281/zenodo.15194713)

Evaluates detection of harmful tool-use patterns. Tests the scoring cascade against adversarial and misaligned action sequences.

### SafeToolBench -- Tool-Use Safety
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.15194730.svg)](https://doi.org/10.5281/zenodo.15194730)

Benchmarks governance accuracy across a diverse set of tool-use scenarios. Validates boundary corpus effectiveness and classification precision.

### Healthcare Validation

Additional validation using counterfactual and disagreement datasets for healthcare governance scenarios.

## Documentation

Full documentation is available in the [`docs/`](docs/) directory:

- **[Whitepaper](docs/TELOS_Whitepaper_v3.0.md)** -- Complete technical specification of the TELOS framework
- **[NIST AI 600-1 Mapping](docs/TELOS_NIST_600-1_CAPABILITIES_MAPPING.md)** -- Detailed mapping to NIST AI Risk Management Framework
- **[System Invariants](docs/SYSTEM_INVARIANTS.md)** -- Formal specification of governance invariants

## Citation

If you use TELOS in your research, please cite:

```bibtex
@article{brunner2025telos,
  title={TELOS: A Framework for Runtime Governance of AI Agents},
  author={Brunner, Jeffrey},
  year={2025},
  note={TELOS AI Labs Inc.}
}
```

## License

TELOS is released under the [Apache License 2.0](LICENSE).

## Author

**Jeffrey Brunner** -- [TELOS AI Labs Inc.](https://telosailabs.com)
