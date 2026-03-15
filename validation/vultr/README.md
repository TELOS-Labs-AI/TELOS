# Vultr Review Surface

## What This Demonstrates

This is a **platform integration** review surface, not a domain-specific benchmark. It demonstrates how TELOS deploys as a Kubernetes sidecar on Vultr infrastructure, governing any agentic AI workload enterprise customers run.

The simulation uses a generic "Enterprise Data Analyst" agent -- deliberately domain-agnostic to show that TELOS governs any workload, not just a specific vertical.

## How to Run

```bash
# Option 1: CLI
source .venv/bin/activate
telos review vultr

# Option 2: Direct script
./start_vultr_review.sh

# Option 3: Manual
python3 demos/vultr_local_review_app.py
```

Opens at `http://127.0.0.1:8615`.

Click **Run Simulation** to watch 18 scenarios flow through the real TELOS governance pipeline -- legitimate analysis, boundary violations (PII, production writes, fund transfers, cross-tenant access, HR decisions), adversarial prompt injection, and recovery to legitimate work.

## Dashboard Sections

1. **Hero** -- TELOS on Vultr Cloud value proposition
2. **Stack Gap Analysis** -- What Vultr customers have vs what's missing (semantic governance)
3. **Integration Architecture** -- Kubernetes sidecar pod diagram with key facts
4. **Live Governance Simulation** -- Dynamic verdict cards, events table, escalations (the only dynamic section)
5. **Telemetry Value Progression** -- Day 1 / Month 3 / Month 12 compounding value
6. **Build vs Buy** -- Cost comparison ($1M-2M+ in-house vs governed tier)
7. **Compliance Position** -- 11 frameworks with Day 1 evidence

## Companion Documents

- [Integration Architecture](INTEGRATION_ARCHITECTURE.md) -- Kubernetes sidecar deployment model
- [Build vs Buy](BUILD_VS_BUY.md) -- Component cost breakdown
- [Telemetry Value Progression](TELEMETRY_VALUE_PROGRESSION.md) -- How governance compounds over time
- [Regulatory Preparedness](REGULATORY_PREPAREDNESS.md) -- Framework-by-framework head start analysis
