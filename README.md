# TELOS -- Mathematical Governance Framework for AI Alignment

**TELOS** (Telically Entrained Linguistic Operational Substrate) is an open-source mathematical framework for governing AI agent behavior using embedding-space representations of user purpose.

## Core Innovation

Two-layer fidelity detection using **Primacy Attractors** -- embedding-space centroids that represent intended purpose:

- **Layer 1 (Baseline Normalization):** Catches extreme off-topic drift via cosine similarity thresholds
- **Layer 2 (Basin Membership):** Catches subtle purpose drift via geometric basin membership testing

## Architecture

```
telos_core/              # Pure mathematical engine (zero framework deps)
telos_governance/        # Governance gates (conversational + agentic)
telos_adapters/          # Framework adapters
    langgraph/           #   LangGraph wrapper, supervisor, swarm
    generic/             #   @telos_governed decorator
telos_observatory/       # Monitoring and visualization tools
telos_dashboard/         # Config-driven governance dashboard components
templates/               # Reference YAML config templates
validation/              # Benchmark datasets and validation tools
docs/                    # Technical documentation and compliance mappings
tests/                   # Unit, integration, and validation tests
```

## Quick Start

```bash
# Install
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Run tests
python -m pytest tests/ -x -q

# Run benchmark
python3 validation/nearmap/run_nearmap_benchmark.py --forensic -v
```

## Governance Verdicts

| Verdict | Threshold | Action |
|---------|-----------|--------|
| EXECUTE | >= 0.85 fidelity | Proceed with confidence |
| CLARIFY | 0.70-0.84 | Verify intent before proceeding |
| ESCALATE | < 0.50 + high risk | Require human review |
| INERT | < 0.50 + low relevance | Block as off-purpose |

## Key Formulas

- **Primacy State:** `PS = rho_PA * (2 * F_user * F_ai) / (F_user + F_ai)`
- **Basin Membership:** `membership = 1.0 if distance <= radius else exp(-k * (distance - radius))`
- **Chain Continuity:** `SCI = cosine(action_n, action_{n-1})`, threshold 0.30

## Documentation

- [Integration Guide](docs/INTEGRATION_GUIDE.md) -- How to integrate TELOS into your application
- [Customer Setup Guide](docs/CUSTOMER_SETUP_GUIDE.md) -- Enterprise deployment guide
- [Reproduction Guide](docs/REPRODUCTION_GUIDE.md) -- Reproducing benchmark results
- [Whitepaper](docs/TELOS_Whitepaper_v3.0.md) -- Full technical whitepaper

## Compliance Mappings

TELOS provides detailed alignment mappings for major AI governance frameworks:
- EU AI Act, NIST AI RMF, NIST AI 600-1
- IEEE 7000/7001/7002/7003 series
- Berkeley CLTC, OWASP Agentic Security
- SAAI

See `docs/` for individual mapping documents.

## License

Apache 2.0. See [LICENSE](LICENSE).

Copyright 2025-2026 TELOS AI Labs Inc.
