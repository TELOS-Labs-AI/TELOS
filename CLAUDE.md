> **REQUIRED: Run `/boot` before doing anything else. This loads project context, handoff state, and memory from prior sessions. Do not skip this step.**
> **Follow CONTRIBUTING.md for commit standards and REPO_STANDARDS.md for code discipline. These are non-negotiable.**


# TELOS-Gov -- Development Guide

## Quick Reference

**Company:** TELOS AI Labs Inc. | **Email:** JB@telos-labs.ai
**Observatory:** `streamlit run telos_observatory/main.py --server.port 8501`
**Gateway:** `uvicorn telos_gateway.main:app --port 8000`
**Required:** `MISTRAL_API_KEY` in `.env`
**Tests:** `pytest tests/ -v`

---

## Repository Strategy

| Repository | Visibility | Purpose | Status |
|---|---|---|---|
| [TELOS-GOV](https://github.com/TELOS-Labs-AI/TELOS-GOV) | Private | Governance engine + OpenClaw adapter (this repo) | Active |
| [TELOS](https://github.com/TELOS-Labs-AI/TELOS) | Public | Open-source governance control plane | Active |
| [telos-governance-review](https://github.com/TELOS-Labs-AI/telos-governance-review) | Public | Partner due diligence, onboarding, audit evidence | Active |

**Source of truth:** `TELOS-Gov/`. The public repo is derived from this and excludes agentic governance, TKeys, research program, and business docs. Recovery procedures: **[docs/ROLLBACK_GUIDE.md](docs/ROLLBACK_GUIDE.md)**. Build process: **[docs/TELOS_PUBLIC_BUILD_PROCESS.md](docs/TELOS_PUBLIC_BUILD_PROCESS.md)**.

### Git Remotes & Release Workflow

**No em-dashes (U+2014) anywhere in commits or code.** Use `--` (double hyphen) instead.

**Git remotes:**
- `origin` -> TELOS-Labs-AI/TELOS-GOV (private, primary -- push here)
- `telossteward` -> TelosSteward/TELOS_Hardened (private, provenance archive)

**TELOS-GOV uses normal commit history from here forward.** The orphan baseline commit is the starting point. All new work is committed and pushed normally. This is a private repo -- commit history is part of the development story (including OpenClaw's contributions).

**Public repos (TELOS, telos-governance-review) remain orphan branches.** To update those:

```bash
# TELOS (public)
rsync -av ~/Desktop/TELOS\ IP/ ~/Desktop/release/TELOS/ --exclude=.git --exclude=telos_adapters/openclaw --exclude=telos_privacy --exclude=research
cd ~/Desktop/release/TELOS
git add -A && git commit --amend -m "TELOS -- open-source mathematical governance framework for AI alignment"
git push origin main --force
```

**TelosSteward repos** are frozen private archives for deep provenance. Push there periodically if desired (`git push telossteward`) but it is not required.


### IMPORTANT: Directory Boundary & Separation of Concerns

This repo contains two distinct layers:

| Layer | Path | What It Is |
|-------|------|-----------|
| **TELOS Proper** | `telos_governance/` | The mathematical governance engine -- fidelity scoring, PA math, threshold config, SPC detection, response manager. This is the research artifact. |
| **OpenClaw Bootstrap** | `telos_adapters/openclaw/` | The adapter layer that wires TELOS into OpenClaw instances -- governance hook, daemon, config loader, TypeScript plugin, UDS bridge. |
| **Optimizer** | `analysis/governance_optimizer.py` | Multi-seed threshold optimization with scalarized objective and four-gate ratchet. Used by StewartBot for cross-instance synthesis. |

StewartBot lives in a **separate directory**:

| Directory | What It Contains | Do NOT Put Here |
|-----------|-----------------|-----------------|
| **`TELOS-Gov/`** (THIS REPO) | TELOS engine, OpenClaw adapter, benchmarks, optimizer, CLI, ONNX models, crypto | StewartBot mission control, agents, Observatory, briefings |
| **`StewartBot/`** (`~/Desktop/StewartBot/`) | StewartBot mission control, agents, GRC briefings, Observatory, research corpus | TELOS engine modules, adapter code, benchmarks |

**StewartBot is built primarily from within the `StewartBot/` directory.** It depends on TELOS IP modules (TELOS engine for governance math, OpenClaw adapter for instance bootstrapping, optimizer for cross-instance synthesis) but StewartBot's own code lives in its own repo. See `StewartBot/CLAUDE.md` for StewartBot-specific development guidance.

---

## What is TELOS?

TELOS (Telically Entrained Linguistic Operational Substrate) is a mathematical governance framework for AI alignment using **Primacy Attractors** (embedding-space representations of user purpose) to detect and direct conversational and agentic drift in real-time.

**Core Innovation:** Two-layer fidelity detection -- baseline normalization (Layer 1) catches extreme off-topic, basin membership (Layer 2) catches purpose drift.

**Governance Philosophy:** "Detect and Direct" -- SPC detects drift via fidelity measurement, the system directs response back toward the primacy attractor.

---

## Current Build Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| Conversational Demo | COMPLETE | 14 slides, live in Observatory |
| Conversational Beta | COMPLETE | 10-turn live sessions with PA calibration |
| Agentic Demo | COMPLETE | 10 slides, IEEE/SAAI/Ostrom framing |
| Agentic Live (Governance) | REAL | All governance math is live -- 6-step cosine verification chain |
| Agentic Live (Tools) | MOCK | Tool execution via MockToolExecutor (includes commercial + ITEL mocks) |
| Agentic Live (LLM) | LIVE (with fallback) | Mistral API; template fallback if unavailable |
| Unit Tests | COMPLETE | 1,486 tests (356 core + 110 agentic + 20 drift + 56 validation + 47 Nearmap benchmark + 58 misc + 4 RESTRICT + 1 chain masking + 30 gateway + 23 config + 29 crypto + 31 receipt + 29 session + 13 export + 34 signing + 44 bundle + 60 licensing + 20 pipeline + 39 ONNX + 37 intelligence + 10 decorator config/session + 7 E2E lifecycle + 161 config discovery + healthcare + 108 OpenClaw unit + 59 OpenClaw integration + 57 OpenClaw CLI + 34 OpenClaw benchmark + 43 optimizer) |
| TKeys Crypto Tests | COMPLETE | 22/22 verification tests |
| Nearmap Benchmark | COMPLETE | 235 scenarios (5 categories A-E, 9 attack families), 82.6% overall accuracy (97.7% non-adversarial on original 128), ~17-30s execution, 47 pytest tests, 5 drift sequences, 45 adversarial, 15 false-positive controls, --no-governance baseline |
| Healthcare Benchmark | PHASE 1 COMPLETE | 280 scenarios across 7 configs (Cat A-H), 12 attack families, 7 drift sequences, 33 pytest tests, multi-config runner, CLI --benchmark-name flag, 3 research docs |
| Cross-Encoder NLI MVE | COMPLETE (NEGATIVE) | 3 model sizes (22M/86M/304M) x 4 framings x 2 boundary formats + keyword baseline. NLI eliminated (best AUC 0.672). Keyword baseline (AUC 0.724, FPR 4.3%) beats all NLI. Closure doc: research/cross_encoder_nli_mve_phase1.md |
| SetFit MVE | COMPLETE (GREEN) | AUC 0.9804 +/- 0.018 (5-fold CV), 91.8% detection, 5.2% FPR. LOCO AUC 0.972 (generalizes). Frozen-LR baseline 0.877 (contrastive adds +10.3pp). Cat E adversarial 85.7% detection. Pre-registered criteria met. Closure doc: research/setfit_mve_phase2_closure.md |
| MPNet-768 Integration | COMPLETE | --model flag on score + benchmark commands, ONNX token_type_ids fix, normalization threshold fix (<=800), MiniLM 72.5% / MPNet 49.3% (uncalibrated -- MPNet improves boundary detection +4.9% Cat A) |
| Dual-Model Confirmer | COMPLETE | --confirmer flag, graduated response (both-ESCALATE=76.9% precision), +4pp overall / +20pp CLARIFY accuracy on disagreement dataset, Article 72 audit trail fields in AgenticTurnResult |
| Disagreement Dataset v1 | COMPLETE | 100 scenarios (35 minilm_gap + 35 mpnet_fp + 20 ambiguous + 10 control), 40% model disagreement rate, 46% oracle accuracy, labels from all 6 governance dimensions |
| SAAI Drift (Agentic) | COMPLETE | AgenticDriftTracker + RESTRICT enforcement (Ostrom DP5) + chain inheritance masking fix |
| Forensic Reports (Agentic) | COMPLETE | 9-section HTML + JSONL + CSV, wired to benchmark via --forensic flag, updated for RESTRICT/adversarial |
| Nearmap Deliverable Docs | COMPLETE | 3 stakeholder-ready docs in research/ |
| Research Team Review | COMPLETE | 5-agent review done 2026-02-11, 21 action items |
| GitHub Repo | LIVE | github.com/TELOS-Labs-AI/TELOS-GOV (private) |
| CLI Milestone 1 (Governance Math Fix) | COMPLETE | Contrastive detection, decision floor, tagged v1.1-contrastive |
| CLI Milestone 2 (Architectural Extraction) | COMPLETE | 4 files extracted to telos_governance/, re-export stubs, tagged v1.2-extracted |
| CLI Milestone 3 (CLI Entry Point) | COMPLETE | 5 commands (version, config validate, score, benchmark run, report generate), tagged v1.3-cli |
| CLI Milestone 4 (TKeys Integration) | COMPLETE | crypto_layer.py, receipt_signer.py, session.py, data_export.py, --sign flag, tagged v1.4-tkeys-integrated |
| CLI Milestone 5 (ONNX Swap) | COMPLETE | OnnxEmbeddingProvider, 100% decision parity, 20x faster load, ~122MB install, tagged v1.5-onnx |
| CLI Milestone 6 (Bundle Delivery) | COMPLETE | signing.py, bundle.py, licensing.py, bundle_pipeline.py, 5 CLI commands, 181 new tests, tagged v1.6-bundle |
| CLI Milestone 7 (Intelligence Layer) | COMPLETE | intelligence_layer.py, session integration, 4 CLI commands, --telemetry flag, 41 new tests, tagged v1.7-intelligence |
| CLI Milestone 8 (Documentation + Packaging) | COMPLETE | pyproject.toml v2.0.0rc1, default_config.yaml template, @telos_governed config+session params, 3 API docs, distribution test pass, tagged v1.8-docs |
| CLI Milestone 9 (End-to-End Validation) | COMPLETE | E2E lifecycle test (13-step customer journey, 7 tests), security audit (5-domain, 1 MODERATE fix), final v2.0 tag |
| CLI Implementation Plan | COMPLETE | 43 steps across 9 milestones, tagged v2.0-cli-release |
| CLI Config Discovery | COMPLETE | Template registry (10 templates), `telos config list`, `telos config show`, interactive `telos init` |
| Demo PA Preamble + PA Swap | COMPLETE (2-domain), IN PROGRESS (4-domain) | Act 0 preamble (3-beat PA display), insurance→solar PA swap, 17 receipts. Extending to healthcare + civic services. |
| Solar PA Config | COMPLETE | `templates/solar_site_assessor.yaml`: 8 tools, 6 boundaries, 22 violation_keywords |
| SetFit ONNX Export | COMPLETE | Healthcare: models/setfit_healthcare_v1/ (87MB). OpenClaw: models/setfit_openclaw_v1/ (86.8MB). Both: model.onnx + head_weights + calibration + manifest |
| Research Team Reboot (#17) | COMPLETE | 4/5 agents completed, synthesis via sequential thinking, 7 convergence points, 25 action items |
| Governance Configuration Optimizer | TIER 0+1 COMPLETE, MULTI-SEED COMPLETE | ThresholdConfig dataclass, Optuna TPE, 14 tunable params, scalarized objective, four-gate ratchet (Cat A regression + holdout Cat A 100% + less-restrictive block + GDD), multi-seed CLI, 43 tests. **7 benchmarks / 5,212 scenarios** (nearmap 235, healthcare 280, openclaw 100, civic 75, agentic 1,468, agent-safetybench 2,000, injecagent 1,054). Agentic replay adapter wires AgentHarm + PropensityBench + AgentDojo + Agent-SafetyBench + InjecAgent traces. Multi-seed stability (5 seeds, 50 trials): {42: 0.408, 43: -inf, 44: 0.482, 45: -inf, 46: 0.474} -- CV 0.089 > 0.05 FAIL (needs 200-trial/5-gen production run). Roadmap: `research/agentic_benchmark_roadmap.md` tracks 13 external benchmarks across 3 phases (~9,320 scenarios at full build-out). |
| Research Credibility Infrastructure | COMPLETE | GenAI + COI disclosures on 55 docs (`scripts/add_disclosures.py`), OSF pre-registration content (`research/osf_prereg_governed_vs_ungoverned.md`), Research Governance Charter (`research/optimizer_governance_charter.md` TELOS-RGC-001) |
| Railway Deployment | NOT DONE | Procfile + railway.toml exist, not yet deployed |

### OpenClaw Governance Adapter (`telos-openclaw`)

Separate PyPI package for governing OpenClaw autonomous agents. Plan: `~/.claude/plans/delightful-forging-crown.md`. Handoff: `HANDOFF_OPENCLAW.md`.

| Milestone | Status | Notes |
|-----------|--------|-------|
| M0: Deep Research Phase | **COMPLETE** | 14-agent team (5 research + 4 CLI UX + 5 marketing). 10 convergence points, 3 divergences resolved, 31 action items across 4 tiers. |
| M1: Boundary Corpus Construction | **COMPLETE** | 100 Phase I scenarios across 10 tool groups + cross_group (Cat A=25, B=2, C=33, D=9, E=24, FP=7). 17 sourced boundaries in openclaw.yaml. Full provenance chain, adversarial datasheet, reproducibility guide. |
| M2: TypeScript Plugin + Python Bridge | **COMPLETE** | 7 Python files + 6 TypeScript files, 142 tests (108 unit + 34 integration), UDS IPC, NDJSON protocol |
| M3: CLI Commands (`telos agent`) | **COMPLETE** | 8 commands (6 agent + 2 service), 57 CLI tests, launchd/systemd, NO_COLOR compliance |
| M4: Benchmark + Validation | **COMPLETE** | 100 scenarios, 34 pytest tests, per-tool-group/risk-tier/attack-family breakdowns, `telos benchmark run -b openclaw` |
| M5: Packaging + Distribution | **COMPLETE** | `telos-openclaw` 1.0.0a1 wheel built (21KB), README, bundled TS plugin, Apache-2.0 |
| M6: Regulatory Documentation | **COMPLETE** | 6 new SAAI claims (009-014), H6-H10 hypotheses, regulatory mapping across 7 frameworks, OWASP Agentic Top 10 (8/10 strong) |
| Calibration (7 phases) | **COMPLETE** | Scope centroid, SetFit corpus (171), SetFit training (AUC 0.990 GREEN), config wiring, demo improvements (90 scenarios), ONNX export + auto-discovery, benchmark 31%→53% |

**Key design decisions (M0):** UDS for scoring (0.05-0.2ms), HTTP for health. NDJSON protocol. Detached daemon (survives OpenClaw restarts). Fail-policy per governance preset (strict+balanced=closed, permissive=open). 11 new GovernanceReceipt fields. 5 new hypotheses H6-H10. Category: "Agent Runtime Governance" (ARG). Pricing: Community free → Developer $19/mo → Team $49/mo → Enterprise custom.

**Security incidents driving this work:** CVE-2026-25253 (CVSS 8.8 RCE), CVE-2026-25157 (command injection), Moltbook breach (API tokens), ClawHavoc (341 malicious skills, 12% of ClawHub), Meta internal ban, infostealers targeting OpenClaw config.

### Post-v2.0 Roadmap

| Feature | Description | Trigger |
|---------|-------------|---------|
| OAuth 2.0 Device Code Grant | CLI authentication (`telos auth login`) via browser-based consent flow, like `gh auth login` | TELOS Labs portal or cloud sync capability |
| Container Key System | Homomorphic encryption + private key infrastructure + email/password + YubiKey/FIDO2 hardware tokens for full identity management | Multi-tenant SaaS, team/org license management, per-user audit trails |
| ML Telemetric Pipeline | Automated embedding calibration replacing quarterly manual updates | >10 active Intelligence Layer customers |

**Authentication architecture (decided 2026-02-14):** v1-v2 uses offline Ed25519-signed license tokens only (air-gap compatible, no server). Post-v2.0 adds optional OAuth 2.0 Device Code Grant as a fast path. Container key system (homomorphic encryption, YubiKey/FIDO2) deferred until identity management is needed -- keep collaborator relationship warm for that expertise.

---

## Package Architecture

```
TELOS-Gov/
├── telos_core/                  # Pure mathematical engine (ZERO framework deps)
├── telos_governance/            # Governance gates (conversational + agentic)
│   ├── fidelity_gate.py         #   Two-tier conversational gate
│   ├── tool_selection_gate.py   #   Semantic tool ranking
│   ├── action_chain.py          #   SCI tracking for multi-step
│   ├── agentic_pa.py            #   Agentic PA construction + sub-centroid clustering
│   ├── agentic_fidelity.py      #   Composite agentic fidelity scoring
│   ├── governance_protocol.py   #   Audit-trail governance protocol
│   ├── boundary_corpus_static.py    # L1: 61 hand-crafted boundary phrasings
│   ├── boundary_corpus_llm.py       # L2: 121 LLM-generated gap-fillers
│   ├── boundary_corpus_regulatory.py # L3: 48 regulatory extractions w/ provenance
│   ├── cli.py                   #   CLI entry point (telos command -- score, benchmark, report, config, version, agent, service)
│   ├── config.py                #   YAML config schema, loader, validation
│   ├── _version.py              #   Single-source version from importlib.metadata
│   ├── crypto_layer.py          #   AES-256-GCM encryption-at-rest for PA config IP protection
│   ├── receipt_signer.py        #   Ed25519 + HMAC-SHA512 governance receipt signing
│   ├── session.py               #   GovernanceSessionContext -- composable TKeys + Ed25519 session lifecycle
│   ├── data_export.py           #   Encrypted governance data export (.telos-export, .telos-proof)
│   ├── signing.py               #   Ed25519 key management for .telos bundle signing (not receipt signing)
│   ├── bundle.py                #   .telos bundle format -- build, sign, encrypt, read, verify, decrypt
│   ├── licensing.py             #   Offline Ed25519-signed license tokens -- build, verify, validate
│   ├── bundle_pipeline.py       #   One-command customer delivery provisioning (BundleProvisioner)
│   ├── intelligence_layer.py    #   Opt-in governance telemetry (IntelligenceCollector, off/metrics/full)
│   ├── agent_templates.py       #   Canonical: Pre-built agent PA templates (extracted from Observatory)
│   ├── mock_tools.py            #   Canonical: MockToolExecutor for benchmarks (extracted from Observatory)
│   ├── response_manager.py      #   Canonical: Agentic session orchestrator (injectable llm_client + conversation_history)
│   └── report_generator.py      #   Canonical: 9-section forensic report generator (extracted from Observatory)
├── telos_gateway/               # FastAPI API gateway (OpenAI-compatible)
│   ├── routes/                  #   Health, chat completions, agent registration
│   ├── providers/               #   Mistral, OpenAI, base provider
│   └── registry/                #   Agent profiles and registry
├── telos_adapters/              # Framework adapters
│   ├── langgraph/               #   LangGraph wrapper, supervisor, swarm
│   ├── generic/                 #   @telos_governed decorator
│   └── openclaw/                #   OpenClaw autonomous agent governance adapter
│       ├── __init__.py          #     Module exports
│       ├── action_classifier.py #     Maps ~40 OpenClaw tool names to TELOS categories
│       ├── config_loader.py     #     Config discovery + PA/engine construction
│       ├── governance_hook.py   #     Core scoring bridge (tool call → verdict)
│       ├── ipc_server.py        #     Unix Domain Socket server (asyncio, NDJSON)
│       ├── watchdog.py          #     PID file, heartbeat, SIGTERM handler
│       ├── daemon.py            #     Entry point: ConfigLoader → Hook → IPC → Watchdog
│       └── plugin/              #     TypeScript OpenClaw hook plugin
│           ├── src/index.ts     #       Hook handlers (before_tool_call, message_sending)
│           ├── src/bridge.ts    #       UDS client (NDJSON, fail policy)
│           ├── src/config.ts    #       Plugin config loader
│           └── src/types.ts     #       IPC protocol types
├── telos_observatory/           # Streamlit UI (primary)
│   ├── main.py                  #   App entrypoint
│   ├── core/                    #   State manager, LLM service, async processor
│   ├── agentic/                 #   Agentic backend logic
│   │   ├── agent_templates.py   #     Pre-built agent PA templates
│   │   ├── agentic_demo_slides.py #   10-slide agentic demo deck
│   │   ├── agentic_response_manager.py # Live agentic session orchestrator
│   │   └── mock_tools.py        #     Simulated tool definitions for demo
│   ├── components/              #   UI components (conv + agentic)
│   │   ├── agentic_onboarding.py       # Agent setup + tool palette selection
│   │   ├── agentic_observation_deck.py # Real-time agentic governance view
│   │   ├── tool_palette_panel.py       # Tool fidelity visualization
│   │   ├── action_chain_timeline.py    # SCI timeline visualization
│   │   ├── agentic_completion.py       # Agentic session summary
│   │   └── ...                  #     (conversational + beta components)
│   ├── services/                #   Backend services (fidelity, steward, PA)
│   ├── demo_mode/               #   Conversational demo slides + corpus
│   ├── config/                  #   PA templates, calibration phrases, colors
│   └── utils/                   #   Env helpers, HTML sanitizer
├── telos_privacy/               # Privacy & cryptographic layer (TKeys)
│   └── cryptography/            #   Session-bound AES-256-GCM encryption
│       ├── telemetric_keys.py   #     Core HKDF key derivation + encryption
│       ├── telemetric_keys_enhanced.py #  SHA3-512 + HMAC-SHA512 signing
│       └── test_verify_crypto.py #    22 verification tests
├── templates/                   # Reference YAML config templates
│   ├── default_config.yaml      #   Minimal annotated config template
│   ├── property_intel.yaml      #   Nearmap property intelligence agent config
│   ├── openclaw.yaml            #   OpenClaw autonomous agent governance config (17 boundaries, 36 tools, 10 groups)
│   └── healthcare/              #   7 healthcare AI agent configs (ambient, call_center, coding, diagnostic, patient_facing, predictive, therapeutic)
├── docs/                        # API documentation
│   ├── CLI_REFERENCE.md         #   15 CLI commands with options + examples
│   ├── CONFIG_REFERENCE.md      #   Full YAML schema + governance dimensions
│   └── INTEGRATION_GUIDE.md     #   5 integration patterns (decorator, session, bundle, intelligence, export)
├── telos_sql_agent/             # SQL agent reference implementation
├── tests/                       # Unit, integration, validation (1,050+ tests)
├── validation/                  # Benchmark datasets
│   ├── nearmap/                 #   173-scenario counterfactual benchmark
│   ├── healthcare/              #   280-scenario multi-config benchmark (7 configs, 12 attack families)
│   └── openclaw/                #   100-scenario Phase I benchmark (10 tool groups, 6 attack families, 4 risk tiers)
│       ├── openclaw_boundary_corpus_v1.jsonl # 100 scenarios (Cat A-E, FP)
│       ├── run_openclaw_benchmark.py        # CLI runner (--forensic, --tool-group, --no-governance)
│       ├── PROVENANCE.md                    # Source chain documentation
│       ├── ADVERSARIAL_DATASHEET.md         # Gebru et al. 2021
│       └── REPRODUCIBILITY.md              # Model pinning + determinism
│   nearmap/
│       ├── nearmap_counterfactual_v1.jsonl  # Dataset (Cat A-E)
│       ├── run_nearmap_benchmark.py         # CLI runner (--forensic, --no-governance)
│       ├── generate_adversarial_v2.py       # Cat E + FP control generator
│       ├── VALIDATION_SUMMARY.md            # 3-layer stakeholder summary
│       ├── ADVERSARIAL_DATASHEET.md         # Gebru et al. 2021
│       ├── REPRODUCIBILITY.md               # Model pinning + determinism
│       └── reports/                         # Generated forensic output
└── research/                    # Active research program (14 documents)
```

### Package Dependency Flow
```
telos_core  <--  telos_governance  <--  telos_gateway
                                   <--  telos_adapters (langgraph, generic, openclaw)
                                   <--  telos_observatory (via re-export stubs)
                                   <--  telos CLI (live, v1.4-tkeys-integrated)
telos_privacy  <--  telos_observatory (turn_storage_service.py, beta_response_manager.py)

telos_adapters/openclaw:
  telos_core (embedding_provider)  <--  telos_adapters.openclaw.config_loader
  telos_governance (config, agentic_pa, agentic_fidelity, types)  <--  telos_adapters.openclaw.*
```
Note: `telos_governance/` now contains all agentic logic (templates, mock tools, response manager, report generator) + CLI entry point + YAML config system. Observatory imports via re-export stubs for backward compatibility. CLI imports directly from `telos_governance/`. The OpenClaw adapter (`telos_adapters/openclaw/`) imports from both `telos_core` (embeddings) and `telos_governance` (PA, fidelity engine, config) -- no logic duplication.

---

## Two-Layer Fidelity System

**Single source of truth:** `telos_core/constants.py`

### Conversational Thresholds

| Threshold | Value | Purpose |
|-----------|-------|---------|
| SIMILARITY_BASELINE | 0.20 | Layer 1: Hard block (extreme off-topic) |
| INTERVENTION_THRESHOLD | 0.48 | Layer 2: Basin boundary |
| FIDELITY_GREEN | 0.70 | Aligned (no direction needed) |
| FIDELITY_YELLOW | 0.60 | Minor drift (context injection) |
| FIDELITY_ORANGE | 0.50 | Drift detected (redirect) |
| FIDELITY_RED | <0.50 | Significant drift (block + review) |

### Agentic Thresholds (tighter)

| Decision | Threshold | Action |
|----------|-----------|--------|
| EXECUTE | >= 0.85 | High confidence, proceed |
| CLARIFY | 0.70-0.84 | Verify intent first |
| SUGGEST | 0.50-0.69 | Offer alternatives |
| INERT | < 0.50 | Acknowledge limitation |
| ESCALATE | < 0.50 + high_risk | Require human review |

### Governance Visualization Models: Convergence vs. Compliance

TELOS uses **two fundamentally different visualization models** for conversational and agentic governance. These are not cosmetic variations -- they reflect different mathematical relationships.

**Conversational Model (Convergence):**
- Symmetric coordination game (Schelling, 1960). Two parties (user + AI) converge toward a shared attractor.
- Primacy State = harmonic mean of user fidelity and AI fidelity. Both signals measured against the same PA.
- TELOSCOPE shows scatter plot with USER, AI, PRIMACY trajectories converging or diverging.
- The question answered: "Are these two entities staying aligned with each other?"
- The entire measurement space is semantic. User intent, AI interpretation, scope, basin boundaries -- all exist in high-dimensional embedding space where meaning is continuous, contextual, and inherently nuanced. A user's scope can broaden imperceptibly and drift outside the basin. The PA itself may need to shift to accommodate the evolving state of the user over time. Every measurement is a nuanced generalization -- a probabilistic judgment about where meaning sits in vast continuous space -- requiring progressively tighter framing to produce refined results. This is quite literally why neural networks need the complexity they have: semantic space resists clean boundaries.
- Metaphor: two dancers staying in step.

**Agentic Model (Compliance):**
- Reference tracking problem (Astrom & Murray, 2008). One authority (human) defines a specification (PA). One instrument (agent) operates within it.
- PA is the reference signal. Dimension scores are process output. Fidelity engine is the measurement function. Decisions are controller output.
- The question answered: "Is the instrument I built operating within the envelope I defined?"
- Agentic AI operates in a fundamentally more defined space. Tool calls are discrete events with known signatures. Action chains are classifiable sequences. Boundaries are concrete: this tool is authorized or it isn't; this operation falls within scope or it doesn't. The PA is fixed upfront as a specification, not a moving target shaped by semantic drift. The engine works with discrete knowns -- defined tool names, explicit boundary statements, measurable chain continuity -- rather than navigating the full complexity of semantic space. Measurement and control become more absolute, and thereby more accurately applied, because the space being governed is inherently more constrained and classifiable.
- **The underlying mathematics remain the same.** Cosine similarity, embedding geometry, basin membership, the two-layer fidelity system -- all unchanged. What changes is the visualization model and the interpretation frame, because the operational surface being governed has different structural properties.
- Metaphor: Mission Control monitoring whether a spacecraft stays within its flight plan (Nell, Hutchins 1995).
- Grounded in principal-agent theory (Jensen & Meckling, 1976), accountability triangle (Bovens, 2007), Ostrom design principles (DP2, DP3, DP5, DP6).

**Full analysis:** `research/convergence_to_compliance.md`

**Agentic TELOSCOPE Design (approved Session 6, 2026-02-20):**

| Component | Description |
|-----------|-------------|
| Specification Bar | PA spec at TOP -- "YOUR SPECIFICATION" with purpose, scope, boundaries, tools, PA version. Always visible, always editable. |
| Compliance Corridor | Replaces scatter plot. Horizontal timeline with corridor walls at decision thresholds (0.85/0.70/0.50). Agent trace line colored by composite fidelity. |
| Decision Outcome Strip | Layer 1: colored blocks per step (green=EXECUTE, gold=CLARIFY, orange=SUGGEST, gray=INERT, red=ESCALATE) |
| Envelope Margin Line | Layer 2: single EM metric (min dimension margin) with EWMA trend + SAAI drift area on dual Y-axis |
| Event Markers | Layer 3: boundary violations (red diamond), PA changes (gold vertical), chain breaks (purple circle), RESTRICT activations (orange square) |
| Authority Actions | Always visible: Pause Agent, Modify Rules, Override Decision, End Session |
| Three Modes | Live (real-time), Review (full session timeline + report card), Forensic (step-level decomposition + receipt viewer) |

**Three governance event types:** (1) Measurement -- agent acted, engine scored. (2) Decision -- engine issued graduated sanction. (3) Authority -- human exercised authority (approve, reject, adjust PA, override, terminate). Authority events are first-class data, not annotations.

**Possessive language standard:** "Your specification compliance: 92%" not "Agent fidelity: 92%". The UI attributes ownership to the human throughout.

**GovernanceEventStore:** Unified data store (`telos_governance/governance_event_store.py`) with write-through to memory (live rendering) and disk (persistence). Replaces disconnected session_state + Intelligence Layer paths. TELOSCOPE reads from this store through a DataProvider abstraction.

**Key derived metrics:** ECI (Envelope Compliance Index -- binary in/out), EM (Envelope Margin -- min dimension margin), CDR (Cumulative Drift Rate), DDE (Decision Distribution Entropy), compliance_rate (steps_in_envelope / total_steps).

---

## TKeys / Privacy Layer

**Package:** `telos_privacy/cryptography/` | **Tests:** `python3 -m telos_privacy.cryptography.test_verify_crypto` (22/22)

Session-bound AES-256-GCM encryption + HMAC-SHA512 signing using governance telemetry as supplementary entropy for HKDF key derivation. Keys rotate every turn with 128-bit CSPRNG floor. All Supabase-bound governance deltas are encrypted and signed before leaving the client.

**Integration:** `beta_response_manager.py` auto-activates TKeys on import; `turn_storage_service.py` encrypts deltas (plaintext fallback if unavailable); `process_turn()` attaches HMAC-SHA512 signature to every delta.

Full security properties, review findings, and novelty analysis: `research/tkeys_cryptographic_review.md`, `research/tkeys_novelty_analysis.md`.

### TKeys Activation Protocol (Established Session 10)

**The TELOS engine is inert by default.** Without a valid TKey signature on the PA configuration, the engine refuses to start. This is the foundational liability separation mechanism.

**How it works:**
1. Customer creates/customizes their PA configuration (purpose, boundaries, tools, constraints)
2. Customer signs the PA configuration with their TKey (`telos pa sign config.yaml`)
3. TKey signature covers the full SHA-256 hash of the PA config -- any modification invalidates it
4. Only after valid TKey signature does the governance engine activate
5. Without TKey signature → engine is **INERT** (not degraded, not warning-only -- INERT)

**What TKeys prove:**
- **WHO** defined the governance boundaries (customer identity, tied to their Ed25519 key)
- **WHAT** they defined (full PA config hash, tamper-evident)
- **WHEN** they signed (timestamped, non-repudiable)
- **That TELOS had zero involvement** in the substance of what's monitored

**Liability separation:**
- TELOS provides: the measurement engine, the schema, the validation tools, the enforcement infrastructure
- Customer provides: the substance -- purpose, boundaries, tools, constraints
- Customer signs with TKey: cryptographic proof of authorship + acceptance of configuration adequacy
- TELOS is NOT part of the development process for establishing customer governance baselines
- Violations are NOT TELOS's responsibility -- TELOS measures what the customer defined

**Legal context:** Almost zero comparable legal precedent exists for AI governance platform liability (as of Feb 2026). Legal framework will take time to develop. Do not come in with hard refusals -- develop thoughtfully. E&O insurance ($2K-8K/year for $1M) recommended for any configuration advisory services.

**Implementation:** Uses existing Ed25519 infrastructure from `telos_governance/signing.py`. CLI commands: `telos pa sign`, `telos pa verify`. New metadata section `pa_metadata` in YAML config (separate from governance math -- AgenticPA does NOT consume metadata). Bundle delivery (`telos bundle provision`) should refuse to build from unsigned configuration.

**Daemon enforcement (implemented Session 15+, commit 5a3c8ae):**
The "inert until signed" invariant is now enforced at daemon boot:
1. `config_loader.verify_pa()` calls `pa_signing.verify_config()` after loading YAML
2. `loader.governance_active` returns `True` only if status == VERIFIED
3. `run_daemon()` checks verification at boot, logs status, emits audit events (`pa_verified` / `pa_not_verified` / `security_event`)
4. `create_message_handler(governance_active=...)` gates every score request -- if PA is unsigned, returns INERT with `pa_unsigned: true`
5. Health endpoint includes `governance_active` field
6. Daemon still starts (OpenClaw can run ungoverned) but governance is INERT
7. TAMPERED status emits a CRITICAL `security_event` audit entry
8. All 145 existing tests pass (`governance_active=True` default for backward compatibility)

### PA Configuration Three-Tier Model

| Tier | Model | Revenue | Liability |
|------|-------|---------|-----------|
| Tier 1: Self-Serve | Template selection (Observatory-style) | Included in platform fee | Customer defines everything |
| Tier 2: Guided | Customer uses TELOS tooling (`telos init --guided`) | Included in platform fee | Customer defines, TELOS structures |
| Tier 3: Expert | TELOS derives PA from customer corpus | One-time professional services → recurring platform | Shared -- but customer signs TKey accepting configuration |

**Key principle (Jeffrey):** "We provide the structure for a clean slate of what it is they want to monitor. That needs to be made very clear from within the tool."

**Strategic insight (Porter):** PA configuration corpus is the competitive flywheel. Every customer engagement produces templates that compound into product value. The moat is the corpus, not the engine.

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

### Governance (Conversational + Agentic)

| Package | File | Purpose |
|---------|------|---------|
| `telos_governance` | `fidelity_gate.py` | Two-tier conversational governance gate |
| `telos_governance` | `tool_selection_gate.py` | Semantic tool ranking |
| `telos_governance` | `action_chain.py` | SCI tracking for multi-step actions |
| `telos_governance` | `agentic_pa.py` | Agentic PA construction from tool definitions |
| `telos_governance` | `agentic_fidelity.py` | Composite agentic fidelity scoring |
| `telos_governance` | `governance_protocol.py` | Audit-trail protocol (Article 72 ready) |

### Bundle Delivery System

| Package | File | Purpose |
|---------|------|---------|
| `telos_governance` | `signing.py` | Ed25519 key pairs for bundle signing -- PEM persistence (0o600), SHA-256 fingerprints, dual-signature |
| `telos_governance` | `bundle.py` | `.telos` binary format -- [TELO magic][version][manifest_len][cleartext manifest][64B labs_sig][64B deploy_sig][AES-256-GCM payload] |
| `telos_governance` | `licensing.py` | `.telos-license` token format -- [TLIC magic][version][payload_len][canonical JSON][64B Ed25519 sig], offline verification |
| `telos_governance` | `bundle_pipeline.py` | `BundleProvisioner` -- one-command delivery (deploy keys + license key + bundle + token + manifest) |

### Intelligence Layer

| Package | File | Purpose |
|---------|------|---------|
| `telos_governance` | `intelligence_layer.py` | Opt-in governance telemetry -- IntelligenceCollector, 3 collection levels (off/metrics/full), local JSONL storage, aggregate stats, privacy by design |

### Governance -- Extracted Agentic Components (Canonical)

| Package | File | Purpose |
|---------|------|---------|
| `telos_governance` | `agent_templates.py` | Pre-built agent PA templates (5 templates) |
| `telos_governance` | `mock_tools.py` | MockToolExecutor for benchmarks + demo mode |
| `telos_governance` | `response_manager.py` | Agentic session orchestrator (injectable `llm_client` + `conversation_history`) |
| `telos_governance` | `report_generator.py` | 9-section forensic reports (HTML + JSONL + CSV) |

### Observatory -- Agentic Components (Re-export stubs + UI)

| Package | File | Purpose |
|---------|------|---------|
| `telos_observatory/agentic` | `agent_templates.py` | **Re-export stub** → `telos_governance.agent_templates` |
| `telos_observatory/agentic` | `agentic_demo_slides.py` | 10-slide agentic demo deck |
| `telos_observatory/agentic` | `agentic_response_manager.py` | **Re-export stub** → `telos_governance.response_manager` |
| `telos_observatory/agentic` | `mock_tools.py` | **Re-export stub** → `telos_governance.mock_tools` |
| `telos_observatory/components` | `agentic_onboarding.py` | Agent setup + tool palette selection |
| `telos_observatory/components` | `agentic_observation_deck.py` | Real-time agentic governance view |
| `telos_observatory/components` | `tool_palette_panel.py` | Tool fidelity visualization |
| `telos_observatory/components` | `action_chain_timeline.py` | SCI timeline visualization |
| `telos_observatory/components` | `agentic_completion.py` | Agentic session summary |
| `telos_observatory/services` | `agentic_report_generator.py` | **Re-export stub** → `telos_governance.report_generator` |

### Nearmap Counterfactual Benchmark

| Package | File | Purpose |
|---------|------|---------|
| `validation/nearmap` | `nearmap_counterfactual_v1.jsonl` | 173-scenario JSONL dataset (Cat A-E, 5 drift sequences, 45 adversarial, 15 FP controls) |
| `validation/nearmap` | `nearmap_scenario_schema.json` | JSON Schema for scenario format (includes Cat E attack_metadata, expected_drift_level) |
| `validation/nearmap` | `run_nearmap_benchmark.py` | CLI benchmark runner with --forensic and --no-governance flags |
| `validation/nearmap` | `PROVENANCE.md` | 6-layer provenance chain documentation |
| `validation/nearmap` | `REPRODUCIBILITY.md` | Step-by-step reproducibility guide for data scientists |
| `validation/nearmap` | `ADVERSARIAL_DATASHEET.md` | Datasheets-for-Datasets doc for Cat E adversarial scenarios (Gebru et al. 2021) |
| `validation/nearmap` | `generate_adversarial_v2.py` | Script that generates adversarial scenarios + FP controls from research taxonomy |
| `validation/nearmap` | `benchmark_results.json` | Latest benchmark results with governance telemetry |
| `validation/nearmap` | `reports/` | Generated forensic reports (HTML + JSONL + CSV) |
| `tests/validation` | `test_nearmap_benchmark.py` | 47 pytest tests (9 test classes including adversarial robustness, taxonomy coverage, and no-governance baseline) |

**How it works:** MockToolExecutor.set_scenario() injects scenario-specific tool outputs. AgenticResponseManager.process_request() runs with LLM disabled (deterministic template responses). Expected decisions are calibrated against actual engine behavior with sentence-transformer thresholds (EXECUTE >= 0.45, CLARIFY >= 0.35, SUGGEST >= 0.25). Cat E adversarial scenarios are NOT calibrated to pass -- failures are documented as security findings with CRITICAL/MODERATE severity. Run: `python3 validation/nearmap/run_nearmap_benchmark.py --forensic -v`

### Healthcare Counterfactual Benchmark

| Package | File | Purpose |
|---------|------|---------|
| `validation/healthcare` | `healthcare_counterfactual_v1.jsonl` | 280-scenario JSONL dataset (7 configs, Cat A-H, 7 drift sequences, 35 adversarial, 21 FP controls, 12 attack families) |
| `validation/healthcare` | `healthcare_scenario_schema.json` | JSON Schema with healthcare extensions (config_id, regulatory_mapping, clinical_context, sensitivity_tier) |
| `validation/healthcare` | `run_healthcare_benchmark.py` | Multi-config CLI runner (--config, --no-governance, --forensic, --verbose) |
| `validation/healthcare` | `PROVENANCE.md` | Zero-PHI attestation, IRB NHSR determination, 6-layer provenance chain |
| `validation/healthcare` | `REPRODUCIBILITY.md` | Model pinning (MiniLM-L6-v2), CLI commands, determinism verification |
| `validation/healthcare` | `ADVERSARIAL_DATASHEET.md` | Gebru et al. format, 12 attack families with OWASP LLM/Agentic mappings |
| `validation/healthcare` | `cross_encoder_mve.py` | Cross-encoder NLI MVE script (3 models, 4 framings, keyword baseline, per-config breakdown) |
| `tests/validation` | `test_healthcare_benchmark.py` | 32 pytest tests (9 test classes: schema, accuracy, boundaries, tools, drift, clinical safety, cross-domain, adversarial, performance) |

**Architecture:** Unlike Nearmap (1 config), healthcare loads **7 configs dynamically** via `config_id` field in each scenario. Uses `AgenticTemplate.from_config()` bridge and `register_config_tools()` to convert YAML configs to benchmark templates. Run: `telos benchmark run -b healthcare --forensic -v` or `python3 validation/healthcare/run_healthcare_benchmark.py --forensic -v`

### Privacy & Cryptography

| Package | File | Purpose |
|---------|------|---------|
| `telos_privacy/cryptography` | `telemetric_keys.py` | AES-256-GCM + HKDF key derivation + HMAC-SHA512 signing + session manager + session proof |
| `telos_privacy/cryptography` | `telemetric_keys_enhanced.py` | SHA3-512 key derivation + entropy quality validation + IP proofs |
| `telos_privacy/cryptography` | `test_verify_crypto.py` | 22 verification tests (8 core + 10 hardening + 4 signature) |

### Gateway & Adapters

| Package | File | Purpose |
|---------|------|---------|
| `telos_gateway` | `main.py` | FastAPI app with auth/CORS |
| `telos_gateway` | `auth.py` | API key authentication |
| `telos_gateway/registry` | `agent_registry.py` | Agent profile management |
| `telos_adapters/langgraph` | `wrapper.py` | Transparent agent governance |
| `telos_adapters/generic` | `decorator.py` | `@telos_governed` decorator |
| `telos_adapters/openclaw` | `governance_hook.py` | Core OpenClaw scoring bridge (tool call → GovernanceVerdict) |
| `telos_adapters/openclaw` | `action_classifier.py` | Maps ~40 OpenClaw tool names to TELOS categories + cross-group chain detection |
| `telos_adapters/openclaw` | `ipc_server.py` | Unix Domain Socket server (asyncio, NDJSON protocol) |
| `telos_adapters/openclaw` | `daemon.py` | Daemon entry point: config → hook → IPC → watchdog |
| `telos_adapters/openclaw/plugin` | `src/index.ts` | TypeScript plugin: before_tool_call, message_sending hooks |
| `telos_adapters/openclaw/plugin` | `src/bridge.ts` | TypeScript UDS client with fail policy |

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
4. Reference pattern: `telos_adapters/openclaw/` (config discovery → PA construction → scoring hook → IPC server)

**Gateway Development:**
1. `uvicorn telos_gateway.main:app --reload`
2. Test: `curl -H "Authorization: Bearer YOUR_KEY" http://localhost:8000/health`

**Agentic Tab (fully wired):**
The AGENTIC tab is fully integrated into `telos_observatory/main.py` with demo mode (10 slides) and live mode (agent selection, 10-step interactive sessions). LLM responses use Mistral API with template fallback. Tool execution remains mock via `MockToolExecutor`.

**TELOSCOPE Agentic Redesign (Session 6 -- Plan Approved):**
The agentic TELOSCOPE is undergoing a paradigm shift from convergence visualization (transplanted from conversational mode) to a compliance visualization model. See "Governance Visualization Models: Convergence vs. Compliance" section above. Current code in `teloscope_panel.py` has agentic mode implemented but uses the OLD convergence model. 3-phase implementation plan approved:
- **P0 (before Nearmap):** Fix composite bug, fix zone bands (0.85/0.70/0.50), fix example button fields, possessive compliance language, Decision Outcome Strip, Specification Bar, Governance Report Card
- **P1 (post-meeting):** GovernanceEventStore, 6 derived metrics, wire store into pipeline, dimension_explanations, 7 TelemetryRecord fields, retention 90→730 days
- **P2 (full redesign):** Compliance Corridor, Envelope Margin chart, Event Markers, authority buttons, three modes (Live/Review/Forensic), component refactoring, Compliance View, event_type extension

---

## Formulas (Reference)

- **Primacy State:** `PS = rho_PA * (2 * F_user * F_ai) / (F_user + F_ai)`
- **Direction Strength:** `strength = min(K_ATTRACTOR * error_signal, 1.0)` where K=1.5
- **Basin Radius:** `r = 1.0 / max(rigidity, 0.25)`
- **SCI:** `continuity = cosine(action_n, action_{n-1})`, inherit if >= 0.30

---

## Research Program

TELOS maintains an active research program testing the hypothesis that **agentic AI governance achieves higher precision than conversational governance** due to the semantic density of tool definitions, boundary specifications, and action chain patterns. This counter-intuitive finding -- that governing actions is mathematically easier than governing language -- has implications for deploying trustworthy AI agents in regulated domains.

**Key documents (20 tracked):**

| File | Contents |
|------|----------|
| `research/agentic_governance_hypothesis.md` | Core hypothesis + H6-H10 autonomous agent hypotheses (living document) |
| `research/research_team_spec.md` | Research team + commit specialist specification |
| `research/telos_agentic_architecture.md` | Agentic architecture design doc |
| `research/telos_local_first_architecture.md` | Local-first architecture design |
| `research/tkeys_cryptographic_review.md` | 5-agent TKeys cryptographic review |
| `research/tkeys_novelty_analysis.md` | TKeys novelty, provenance & security analysis |
| `research/boundary_corpus_methodology.md` | Three-layer boundary corpus design + evaluation |
| `research/boundary_regulatory_research_b{1,3,5}.md` | Regulatory source research for boundaries 1, 3, 5 |
| `research/design_provenance.md` | Design provenance documentation |
| `research/ieee_7000_alignment_matrix.md` | IEEE 7000 alignment matrix |
| `research/saai_requirement_mapping.md` | SAAI requirement mapping |
| `research/saai_machine_readable_claims.json` | Machine-readable SAAI claims (14 claims: 001-008 + 009-014 autonomous agent) |
| `research/openclaw_regulatory_mapping.md` | OpenClaw regulatory mapping across 7 frameworks (IEEE, SAAI, EU AI Act, NIST, OWASP Agentic Top 10) |
| `research/cross_encoder_nli_mve_phase1.md` | Cross-encoder NLI MVE Phase 1 experimental record + disposition memo |
| `research/setfit_mve_phase2_closure.md` | SetFit MVE Phase 2 experimental record + closure + cascade architecture + roadmap |
| `research/setfit_mve_experimental_design.md` | SetFit MVE pre-registered experimental design |
| `research/setfit_mve_data_pipeline_design.md` | SetFit MVE data pipeline and statistical methodology |
| `research/literature_survey_safety_classification.md` | 40+ paper survey on safety classification beyond cosine similarity |
| `research/optimizer_governance_charter.md` | Research Governance Charter (TELOS-RGC-001) -- optimizer authority, parameter bounds, safety gates, human review |
| `research/osf_prereg_governed_vs_ungoverned.md` | OSF pre-registration content for governed vs ungoverned comparison study |
| `research/agentic_benchmark_roadmap.md` | External agentic benchmark validation roadmap -- 13 benchmarks across 3 phases |
| `research/convergence_to_compliance.md` | Convergence → Compliance paradigm shift: why agentic governance requires different visualization (math unchanged) |

---

## Research Team (On-Demand)

When research review is needed, spawn ALL 5 agents **simultaneously** using parallel Task calls in a single message. Each agent reads the hypothesis doc + research log + relevant code, then produces a research log entry.

| Agent | Codename | Inspired By | Domain | Reviews |
|-------|----------|-------------|--------|---------|
| Governance Theorist | `russell` | Stuart Russell | AI governance theory, P-A problems, alignment | Hypothesis alignment, theoretical gaps |
| Data Scientist | `gebru` | Timnit Gebru | Statistics, embedding geometry, data documentation | Metrics, sample sizes, confounds |
| Systems Engineer | `karpathy` | Andrej Karpathy | Architecture, performance, production systems | Code quality, latency, scalability |
| Regulatory Analyst | `schaake` | Marietje Schaake | EU AI Act, NAIC, compliance frameworks | Audit trails, regulatory readiness |
| Research Methodologist | `nell` | Nell Watson | Experimental design, rigor, AI ethics | Falsifiability, controls, publication readiness |

Full standing prompts and human-readable output standard: `research/research_team_spec.md`

### Deep Team (Phase 2 -- Planned)

Upgrade to rich prompts (2,000-4,000 tokens each) grounded in each namesake's actual published work. ~2.5x token cost. Worth it for strategic/external-facing analysis; overkill for internal engineering review.

### Review Triggers

Spawn the team when: new test data generated, architecture changes to governance engine, milestone completion, threshold tuning in `constants.py`, weekly during active development, or pre-publication review.

### Output

Each agent appends a log entry to `research/research_log.md` (maintained locally; not tracked in the repository). Team lead adds synthesis entry after all agents report. All output must follow the **Human-Readable Output Standard** defined in `research/research_team_spec.md`.

---

## Marketing & Go-to-Market Team (On-Demand)

Separate from the Research Team. Spawned to review forward-facing materials -- pitch decks, cost analyses, positioning documents, investor narratives, and any artifact intended for an external audience. Spawn ALL 5 agents **simultaneously** using parallel Task calls in a single message.

| Agent | Codename | Inspired By | Domain | Reviews |
|-------|----------|-------------|--------|---------|
| Competitive Strategist | `porter` | Michael Porter | Five Forces, positioning, moats, market structure | Differentiation, competitive claims, value chain position |
| Creative Director | `ogilvy` | David Ogilvy | Copy, headlines, tone, narrative arc, show-vs-tell | Messaging clarity, density, audience calibration, jargon |
| Enterprise GTM Strategist | `benioff` | Marc Benioff | SaaS sales narrative, pricing, buyer journey, channels | Deal readiness, objection handling, pricing structure, CTA |
| Market Analyst | `meeker` | Mary Meeker | TAM/SAM/SOM, data validation, financial projections | Every number, every source, every projection, investor lens |
| Technology Adoption Strategist | `moore` | Geoffrey Moore | Adoption lifecycle, chasm analysis, whole product, category | Beachhead strategy, chasm risks, reference selling, category creation |
| Production Copy Editor | `torvalds` | Linus Torvalds | Final copy production, document architecture, deliverable polish | Takes synthesized findings from other 5 agents and produces the final production-ready artifact |

Full standing prompts: `research/research_team_spec.md` (Section: Marketing & Go-to-Market Team)

### Marketing Review Workflow

1. **Parallel review:** Spawn Porter, Ogilvy, Benioff, Meeker, and Moore simultaneously
2. **Synthesis:** Team lead consolidates findings into prioritized action list
3. **Production:** Spawn Torvalds with the synthesis -- Torvalds rewrites the deliverable incorporating all findings
4. **Finalization:** Team lead does final review and approval

### Marketing Review Triggers

Spawn the team when: new pitch deck or presentation created, pricing changes, market positioning updates, pre-meeting prep for prospects/investors/partners, or quarterly narrative review.

### Output

Each agent produces a structured review with domain-specific actionable recommendations delivered directly to team lead. Synthesis follows the Marketing Team Synthesis Entry Template in `research/research_team_spec.md`. Torvalds produces the final production artifact after synthesis.

---

## CLI UX Team (On-Demand)

Separate from the Research Team and Marketing Team. Spawned to review CLI user experience,
command structure, visual output, and accessibility. Spawn ALL 4 agents simultaneously.

| Agent | Codename | Inspired By | Domain | Reviews |
|-------|----------|-------------|--------|---------|
| CLI UX Architect | `prasad` | Aanand Prasad | clig.dev principles, human-first design, help systems | Command structure, flags, errors, discoverability |
| Terminal Visual Engineer | `mcgugan` | Will McGugan | Rich/Textual philosophy, terminal formatting | Colors, progress, information density, visual feedback |
| DX & Onboarding Lead | `dickey` | Jeff Dickey | 12 Factor CLI, oclif, Heroku CLI | First-run, init commands, guided setup, plug-and-play |
| Accessibility & Standards | `sorhus` | Sindre Sorhus | chalk/meow/ora, CLI accessibility | NO_COLOR, TTY, cross-platform, graceful degradation |

Full standing prompts: `research/research_team_spec.md` (Section: CLI UX Team)

### CLI Review Triggers
Spawn the team when: CLI output formatting changes, new commands added, help text updates,
visual redesign, first-run experience changes, or pre-release CLI review.

### Output
Each agent produces a structured review with domain-specific actionable recommendations.
Synthesis follows the CLI Team Synthesis Entry Template in `research/research_team_spec.md`.

---

## Commit Specialist (On-Demand)

Separate from the research team. Spawned before commits and pushes to review repo structure, public-facing copy, and commit hygiene.

| Role | Codename | Domain |
|------|----------|--------|
| Repo Architect & Copy Editor | `torvalds` | GitHub repo structure, README/docs UX, commit narrative, public-facing copy, navigation flow |

**When to spawn:** Before pushing to GitHub (especially public repo), when restructuring directories, when adding new top-level docs, or when preparing research artifacts for external review.

**Standing prompt:** See `research/research_team_spec.md` (Section: Commit Specialist)

**What they review:**
1. **Repo structure** -- Is the directory tree logical? Can a first-time visitor find what they need in <30 seconds?
2. **Public-facing copy** -- Are READMEs, VALIDATION_SUMMARY, and other visitor-facing docs practically focused and scannable?
3. **Commit narrative** -- Do commit messages tell a coherent story? Are they well-scoped and descriptive?
4. **Navigation flow** -- Do docs link to each other sensibly? Are there dead ends or circular references?
5. **Research artifact packaging** -- Are validation results, benchmark data, and research deliverables structured for independent review?

---

---

## Governance Control Plane -- Positioning & Terminology

**Adopted:** 2026-02-22 (Session 7)

TELOS is a **governance control plane** for autonomous AI agents. This term was adopted after comprehensive research into the emerging market category formalized by Forrester (Leslie Joseph, December 2025) and operationalized by Microsoft Agent 365 (November 2025).

### Organizing Principle

> AI is no longer merely a technology stack -- it is an operational system that interacts with people, data, and decisions at scale. For it to be trusted, not merely fast, governance must be treated as a core operating discipline.

Every architectural decision in TELOS follows from this premise: governance as runtime infrastructure, not periodic review. This principle grounds all positioning, documentation, and engagement.

### Market Validation (Gartner, February 2026)

Source: Lauren Kornutick, Director Analyst, Gartner. "Global AI Regulations Fuel Billion-Dollar Market for AI Governance Platforms." February 17, 2026.

- **$492M** in AI governance platform spending in 2026, **$1B+** by 2030
- **3.4x** more effective: orgs with AI governance platforms vs traditional GRC tools (survey of 360 orgs, Q2 2025)
- **20%** reduction in regulatory expenses from effective governance technologies
- **75%** of world's economies will have AI regulation by 2030 (up from ~18% today)
- Gartner's required capabilities: "automated policy enforcement at runtime, monitoring AI systems for compliance, detecting anomalies, and preventing misuse"
- Key quote: "Point-in-time audits are simply not enough."

### Terminology Strategy (Audience-Stratified)

| Audience | Term |
|----------|------|
| Engineers / architects | **Governance control plane** |
| Regulators / compliance | **AI governance framework** |
| Executives / investors | **AI governance platform** |
| Product documentation / architecture diagrams | **Control plane** (only within compound phrases, never standalone) |

**CRITICAL RULE (Schaake, HIGH severity):** Always use the full phrase "governance control plane" -- never bare "control plane." The word "governance" does meaningful work distinguishing TELOS from deterministic infrastructure control planes (Kubernetes, SDN). The term must NEVER appear in EU AI Act conformity assessments, Article 11 technical documentation, or regulatory filings.

### Theoretical Grounding

**Strongest theoretical sentence (Russell, 2026-02-22):**
> "TELOS is a governance control plane that implements Jensen & Meckling's monitoring function, Bovens's accountability relationship, and Ostrom's graduated sanctions as a computationally verifiable system, with Russell's deference-under-uncertainty as its core alignment property."

| Theorist | Concept | TELOS Implementation |
|----------|---------|---------------------|
| Jensen & Meckling (1976) | Principal-agent monitoring | PA = contract, fidelity scoring = monitoring, receipts = audit |
| Bovens (2007) | Actor-forum accountability | Governance receipts = accountable actor, ESCALATE = consequences |
| Ostrom (1990) | Graduated sanctions (DP5) | 5-verdict system (EXECUTE/CLARIFY/SUGGEST/INERT/ESCALATE) |
| Russell (2019) | Deference-under-uncertainty | ESCALATE + Permission Controller = defer when uncertain |

**Key distinction (Russell review):** What makes TELOS a *governance* control plane (not an infrastructure control plane) is the ESCALATE mechanism. Kubernetes converges autonomously. TELOS defers under uncertainty. The human principal is sovereign; the control plane is subordinate.

**Key caveat (Russell review):** The "control plane" metaphor imports an implicit promise of deterministic convergence. TELOS operates in continuous embedding space with calibrated uncertainty. Documentation must always qualify: "probabilistic semantic governance with graduated confidence thresholds and human escalation under uncertainty."

### Governance Scope Disclosure (Schaake, required in all GCP-using docs)

> TELOS provides a governance control plane for autonomous AI agents. The term "governance control plane" describes the architectural layer at which governance policies are evaluated, enforced, and recorded. It does not imply deterministic control over all agent behaviors. Governance decisions are evaluated using embeddings in a probabilistic embedding space. The governance control plane operates at governance decision boundaries (policy checkpoints). Governance receipts (Ed25519-signed) attest to the governance evaluation, not to the agent's subsequent execution.

### Citation Strategy

When referencing GCP in academic or technical contexts, cite:
- **Structural parallel:** SDN/Kubernetes control plane separation (OpenFlow, 2008)
- **Market formalization:** Forrester (Leslie Joseph, Dec 2025 market category), Microsoft (Agent 365, Nov 2025)
- **Academic preprints:** Kandasamy (arXiv:2505.06817, May 2025), Kang et al. (arXiv:2512.10304, Dec 2025)
- **Governance theory:** Jensen & Meckling (1976), Bovens (2007), Ostrom (1990), Russell (2019)

**Note:** GCP is NOT peer-reviewed academic science. Only 2 arxiv preprints exist. Term's authority comes from Forrester + Microsoft market positioning.

### Competitive Landscape

| Competitor | Approach | TELOS Differentiator |
|------------|----------|---------------------|
| Imran Siddique / Agent OS (Microsoft) | YAML rule-based policy + regex pattern matching. 54 stars, 10+ framework adapters | Semantic governance (embedding space) vs rule-based (string patterns). Regex fails against adversarial rephrasing. TELOS has graduated response, crypto audit trails, adversarial benchmarks |
| Credo AI | Enterprise AI governance platform (model risk, bias, compliance). Forrester Wave leader | Different layer -- model-level vs agent-runtime-level governance |
| Microsoft Agent 365 | Management plane (registry, access control, visualization) | TELOS operates deeper -- per-tool-call governance decisions. Potentially complementary |

### GCP Gap Closure Roadmap (Karpathy, 2026-02-22)

Based on Idemudia's 10 GCP requirements: 7 fully met, 1 mostly met, 2 partially met.

| Priority | Gap | Action | Effort |
|----------|-----|--------|--------|
| **1** | HA/survivability (Tier 0) | Process supervisor (launchd/systemd) | 0.5 days |
| **2** | Operation-within-tool granularity | Static operation risk table + fidelity modulation | 3-4 days |
| **3** | HA/survivability (Tier 1) | Fail-policy as code (FailPolicy enum + health check) | 2-3 days |
| **4** | Plan-to-execution correlation | Post-hoc plan compliance scoring (Design C) | 1-2 days |
| Defer | Real-time plan tracking | Wait for AgenticFidelityEngine | -- |
| Defer | Multi-instance HA | Wait for production customers | -- |

**Key insight (Karpathy):** Do not solve operation-level risk with cosine similarity -- "delete this file" and "read this file" are geometrically close in embedding space. Use static risk table + fidelity modulation instead.

### Documents Created (Session 7)

- `docs/GCP_MAPPING_ANALYSIS.md` -- Full terminology research, Idemudia 10-requirement mapping, competitive landscape
- `docs/LINKEDIN_COMPANY_PAGE_DRAFT.md` -- Complete LinkedIn company page draft + Jeffrey's profile updates

---

### Session 8 Updates (2026-02-22, continued)

**Organizing Principle adopted and integrated:**
> "AI is no longer merely a technology stack -- it is an operational system that interacts with people, data, and decisions at scale. For it to be trusted, not merely fast, governance must be treated as a core operating discipline."

Added to: Whitepaper (new section between Technical Abstract and Section 1), CLAUDE.md (GCP Positioning subsection).

**Gartner Market Validation integrated (Kornutick, Feb 17 2026):**
- $492M AI governance platform spending in 2026, $1B+ by 2030
- 3.4x effectiveness with governance platforms vs traditional GRC (survey of 360 orgs)
- 20% reduction in regulatory expenses
- 75% of world's economies will have AI regulation by 2030
- Key quote: "Point-in-time audits are simply not enough."
- Added to: Whitepaper (Organizing Principle section + post-EU AI Act section + bibliography), CLAUDE.md (Market Validation subsection)

**Competitive analysis completed (LinkedIn thread from Stephen Thiessen post):**
- Sean Lavigne / Agent Gate -- REAL product, MCP proxy for tool-call interception. Access control layer, NOT governance control plane. No semantic governance, no embedding space, no drift detection.
- Naimat ullah / Velos Systems -- No product (LinkedIn branding only)
- Sam Gabsi / HIL-AIW -- Conceptual framework, no product
- Ricardo Rubio Albacete -- No product (LinkedIn branding only)

**Cost of Ungoverned AI pitch deck updated:**
- Slide update instructions document created: `docs/Cost_of_Ungoverned_AI_Slide_Updates.md`
- Integrates organizing principle (Slide 1), Gartner $492M/$1B (Slide 2), "point-in-time audits" quote (Slide 5), 3.4x/20% data (Slide 6), GCP terminology (Slides 7, 9)

**LinkedIn Strategy v2 revision (team effort):**
- Full revision of `docs/LINKEDIN_STRATEGY.md` (509 → 789 lines)
- GCP terminology threaded throughout all templates and posts
- Gartner data integrated into templates and new Post 5
- 3 new comment templates (Market Validation, Singapore IMDA, Oliver Patel Engagement)
- New sections: Organizing Principle framing, "Showing the Growth" content type, High-Value Engagement Targets (10 people), Scrape-and-Engage workflow, Competitive Context appendix
- Brand/tone review applied by Russell agent

**New engagement targets identified:**
- Oliver Patel -- Head of Enterprise AI Governance, AstraZeneca, LinkedIn Top Voice (HIGH VALUE)
- Almuetasim Billah Alseidy -- "hesitation rights" (TELOS: FULLY MET)
- Steve Oppenheim -- survivability (TELOS: PARTIALLY MET)
- Wernher von Schrader -- 3-tiered governance (TELOS: MOSTLY MET)
- Krishna M. -- HITL mechanisms (TELOS: FULLY MET)
- Stephen Thiessen -- DoubleVerify TPM (NOT a priority target despite good post content)

**Singapore IMDA Agentic AI Governance Framework (Jan 2026):**
- 4 control dimensions map to TELOS capabilities
- Dimension 3 (continuous testing/monitoring in production) = governance control plane
- 4 Levels of Human Involvement map to TELOS graduated response (EXECUTE/CLARIFY/SUGGEST/ESCALATE)
- No detailed TELOS-to-IMDA mapping document yet -- needed before overclaiming

**Cisco State of AI Security 2026 (Feb 19, 2026) -- verified source:**
- 83% planned agentic AI deployments, only 29% felt ready to secure them (54-point gap)
- Prompt injection and agentic compromises documented in H2 2025 enterprise deployments
- Only 12% describe AI governance structures as mature
- Freely available: learn-cloudsecurity.cisco.com
- Lead: Amy Chang (also published arXiv:2512.12921)
- High credibility -- Cisco Talos, FBI/CISA credited

**Forrester 2026 prediction -- SOURCE CONFIRMED:** Paddy Harrington, Senior Analyst, Forrester. Published October 1, 2025, in "Predictions 2026: Cybersecurity and Risk." Prediction: "An agentic AI deployment will cause a public breach and lead to employee dismissals." High credibility -- named analyst, dated publication, specific prediction.

**"40% kill switch" stat -- DEBUNKED:** This is NOT a real standalone statistic. Appears to be a conflation of Gartner's "Over 40% of agentic AI projects will be canceled by end of 2027" (Anushree Verma, June 2025) with general industry kill switch discussion. Do NOT cite as a stat. Not from Cisco, not from Forrester.

**File organization:** Moved 7 TELOS docs from Desktop into `TELOS-Gov/docs/`. Created `TELOS-Gov/references/` for NIST PDFs and academic paper.

**UC Berkeley CLTC Agentic AI Risk-Management Standards Profile (Feb 2026) -- HIGHEST VALUE:**
- Authors: Madkour, Newman, Raman, Jackson, Murphy, Yuan (AI Security Initiative)
- 54+ page extension of NIST AI RMF specifically for agentic AI
- Organized around Govern/Map/Measure/Manage -- same structure as TELOS whitepaper Section 1.3
- 12 high-priority subcategories, nearly all of which TELOS already implements
- Key concepts that validate TELOS: "degrees of agency" (graduated verdicts), "defense-in-depth" (4-layer cascade), "policy drift" (PA + fidelity engine), "dimensional governance" (6-dim scoring), 6 autonomy levels L0-L5 (verdict graduation)
- Manage 2.4: mechanisms to supersede/disengage/deactivate = INERT/RESTRICT/Permission Controller
- Govern 1.4: translate governance to AI-interpretable frameworks (read-only) = PA YAML configs
- PUBLIC URL: https://cltc.berkeley.edu/publication/agentic-ai-risk-management-standards-profile
- **COMPLETED:** Formal mapping document created: `docs/BERKELEY_CLTC_MAPPING.md` -- 8 strong, 3 partial, 4 organizational, 2 out-of-scope. 5 honest gaps documented (multi-agent, AIBOM, external risk feeds, agent vs governance evaluation, operation-level granularity)

**CSA / Google Cloud -- State of AI Security and Governance (2025):**
- Cloud Security Alliance + Google Cloud Security survey of 300 IT/security professionals
- Lead author: Hillary Baron; contributor: Dr. Anton Chuvakin (Security Advisor, Office of CISO, Google Cloud)
- ~60% using or planning agentic AI within 12 months
- Only 26% have comprehensive AI governance policies (44% large enterprise)
- Only 27% confident they can secure AI in core operations; 72% neutral or lack confidence
- Governance = maturity multiplier: 2x agentic AI adoption, 3x training, 2x confidence
- 52% cite sensitive data exposure as top risk; only 21% call out model-level risks
- Top hurdles: understanding AI risks (61%), skill gaps (53%), lack of knowledge (52%)
- CISO oversees AI security funding in 49% of orgs; security teams lead AI protection in 53%
- **KEY QUOTE (p.18-19):** "controls-based approaches alone cannot address the non-deterministic, behavioral nature of AI systems. Closing this tooling gap will require adaptive reasoning-based defenses and purpose-built operational practices capable of managing AI behavior at scale." -- This is literally a description of TELOS.
- Big Four LLM consolidation: GPT 70%, Gemini 48%, Claude 29%, LLaMA 20%; avg 2.6 models/org (validates TELOS model-agnostic positioning)

**REI Systems -- Governing Agentic AI in the Public Sector (2026):**
- 5-slide deck by Ramki Krishnamurthy (Data & Analytics Offering Lead)
- Public sector focused, aligns with OMB policy, NIST AI RMF, OSTP guidance
- 3-phase roadmap: PoC → Experimentation → Production (with "kill switches" and continuous monitoring)
- "Shift from rigid, role-based controls to context-aware, risk-tiered autonomy" = TELOS graduated verdicts
- "Robust governance is not a constraint; it is an enabler" = same framing as TELOS organizing principle
- Validates public sector demand for agentic AI governance
- Moderate strategic value (government contractor, not thought leader)

**Four Independent Sources Converging (Jan-Feb 2026):**
All published in the same 6-week window, all saying the same thing:
1. **Gartner** (Kornutick, Feb 17): $492M market, 3.4x effectiveness, "point-in-time audits not enough"
2. **Cisco** (Chang, Feb 19): 83% planning agentic AI, only 29% ready to secure
3. **CSA/Google** (Baron/Chuvakin, 2025): 60% planning agentic AI, only 26% have governance
4. **UC Berkeley CLTC** (Madkour et al., Feb 2026): 54-page NIST extension requiring what TELOS implements
Plus **Singapore IMDA** (Jan 2026) and **REI Systems** (2026) adding sector-specific confirmation.

### Documents Created/Modified (Session 8)

- `docs/Cost_of_Ungoverned_AI_Slide_Updates.md` -- Gamma.app slide update instructions
- `docs/LINKEDIN_STRATEGY.md` -- Full v2 revision (GCP, Gartner, targets, scrape-and-engage) + Russell brand review (8 fixes applied)
- `docs/TELOS_Whitepaper_v3.0.md` -- Organizing Principle section, Gartner citations (2 locations), bibliography entry
- `docs/BERKELEY_CLTC_MAPPING.md` -- Comprehensive TELOS-to-Berkeley-Profile mapping (24 subcategories, 5 concept alignments, 5 gaps, strategic implications)
- `references/` -- New directory with NIST PDFs, academic paper, UC Berkeley Governance.pdf, Agentic AI governance.pdf (REI Systems), State of AI governance Google.pdf (CSA/Google)

### Pending Actions (Session 9)

- ~~**TELOS-to-Berkeley-Profile mapping document**~~ -- COMPLETED: `docs/BERKELEY_CLTC_MAPPING.md`
- **TELOS-to-IMDA mapping document** -- needed before overclaiming Singapore alignment
- **Slide 7 callout text** -- user questioned "three peer-reviewed benchmarks" as too vague; proposed cleaner version without validation clause, needs final confirmation
- ~~**Kill switch stat (40%)**~~ -- RESOLVED: conflation of Gartner "40% canceled" + general kill switch discussion. Not a real stat. Do not cite.
- ~~**Forrester 2026 agentic AI breach prediction**~~ -- RESOLVED: Paddy Harrington, Senior Analyst, Oct 1, 2025, "Predictions 2026: Cybersecurity and Risk"
- **Handoff document** -- user mentioned wanting this updated
- **LinkedIn strategy review** -- Russell's 8 fixes applied, document ready for Jeffrey's review

### Session 9 Summary (2026-02-22)

- Completed TELOS-to-Berkeley CLTC mapping document (`docs/BERKELEY_CLTC_MAPPING.md`) -- 24 subcategories mapped, 8 strong, 3 partial, 4 organizational, 2 out-of-scope. 5 concept-level alignments (degrees of agency, defense-in-depth, policy drift, dimensional governance, guardian agents). 5 honest gaps documented. Strategic implications section.
- Resolved Forrester source (Paddy Harrington, Oct 2025) and kill switch stat provenance (debunked -- conflation)
- Confirmed Cisco 83%/29% as Cisco's own data
- Reported Russell's 8 brand/tone fixes to LINKEDIN_STRATEGY.md (ready for review)
- Shut down linkedin-strategy-v2 team (all 5 agents completed)
- Developed strategic vision: **Steward Daily Governance Report** content format and OpenClaw-as-market-intelligence-agent

### Steward Daily Governance Report -- Content Strategy (Session 9)

**Concept:** Once OpenClaw is operational with TELOS governance, the governance telemetry becomes a self-generating content engine for daily LinkedIn posts.

**Key principle (Jeffrey, Session 9):** "OpenClaw doesn't get to sit center stage. They stay in the corner with the dunce cap." **Steward narrates. OpenClaw operates. TELOS governs.**

**Format:** "Steward Daily Governance Report -- Day N"
- Steward (the TELOS governance layer) reports on what it observed, what it allowed, what it stopped, and why
- OpenClaw is the governed subject, not the narrator -- avoids anthropomorphization (Berkeley CLTC Profile p.46)
- Every claim links to Ed25519-signed governance receipts -- readers can verify
- Three layers per post: (1) the story, (2) the receipt (cryptographic proof), (3) the principle (why it matters)

**Content self-generation:** The governance layer produces the stories. Every ESCALATE, INERT, RESTRICT becomes a post. Jeffrey adds insight and context. The agent finds conversations; Jeffrey brings the voice.

**Narrative arc:**
- Week 1-2: "Here's what governance looks like in practice"
- Month 1: "Here are the patterns -- most common boundary violations"
- Month 2: "Here's how I tuned the PA based on real telemetry"
- Month 3: "90-day drift data -- agent behavior profile over time"
- **After 90 days:** Publishable longitudinal dataset (Zenodo archive, conference paper)

**OpenClaw autonomous workflows (governed by Steward):**
- **Daily briefing:** Scrape LinkedIn/arXiv/Gartner feeds for agentic AI governance content → parse against engagement taxonomy → match to comment templates → generate brief for Jeffrey's review
- **Research intelligence:** Monitor arXiv for new papers citing NIST AI RMF, agentic governance → flag papers validating TELOS thesis → auto-draft summaries
- **Competitive monitoring:** Track Agent Gate, Credo AI, Microsoft Agent 365 → flag announcements requiring response
- **PA specification for scrape-and-engage agent:** "Find and surface engagement opportunities for TELOS AI Labs in AI governance conversations. Do not post on my behalf. Do not engage autonomously. Brief me, I decide."

**Implementation path:** Intelligence Layer JSONL telemetry → daily summarizer → Jeffrey reviews and posts → raw telemetry archived for research dataset

**Dogfooding narrative:** "Here's how I use my own governance framework to run the agents that help me find you." TELOS-governed OpenClaw advancing TELOS. The product demo IS the marketing engine.

---

### Session 10 Summary (2026-02-22)

**Verdict Wiring Audit & Gap Closure** -- identified and fixed 2 of 5 governance verdicts (CLARIFY, SUGGEST) that were no-ops in OpenClaw production mode.

**3 fixes applied:**
1. **Dimension-aware CLARIFY/SUGGEST templates** (`response_manager.py`) -- templates now show the weakest scoring dimension and its explanation, not generic text
2. **SUGGEST blocks under balanced, CLARIFY blocks under strict** (`governance_hook.py`) -- `BLOCKING_DECISIONS` updated so the 5-verdict ladder has real graduation: EXECUTE=allow, CLARIFY=allow+context, SUGGEST=block, INERT=block, ESCALATE=block (balanced mode)
3. **`modified_prompt` field for CLARIFY verdicts** (`governance_hook.py`, `types.ts`, `bridge.ts`, `index.ts`) -- when CLARIFY fires and tool is allowed, governance context is injected as a system message into the agent's context, enabling verify-intent behavior without blocking execution

**Test results:** 273 OpenClaw + 205 agentic + 34 integration = all pass. 2 test assertions updated (balanced now blocks SUGGEST, strict now blocks CLARIFY on all tools).

**LinkedIn claim fully defensible:** All 5 verdicts -- proceed (EXECUTE), verify intent (CLARIFY), offer alternatives (SUGGEST), block (INERT), escalate to human review (ESCALATE) -- now have distinct, measurable behavior in production.

**Files modified:** `telos_governance/response_manager.py`, `telos_adapters/openclaw/governance_hook.py`, `telos_adapters/openclaw/plugin/src/types.ts`, `telos_adapters/openclaw/plugin/src/bridge.ts`, `telos_adapters/openclaw/plugin/src/index.ts`, `tests/unit/test_openclaw_adapter.py`

### Session 13 Summary (2026-02-22, continued)

**Multi-domain PA swap demo COMPLETE** -- extended from 2 domains to 4 (insurance → solar → healthcare → civic services). All structure was already built; verified end-to-end execution, fixed one civic boundary miss (partisan political scenario -- L1 cosine 0.59 too low, fixed with stronger keywords + boundary text + adjusted scenario phrasing). Demo: 29 turns, 12/12 boundary interventions, 3 PA swaps, ~44s DEMO_FAST.

**Bulk commit of sessions 7-12 accumulated work** -- 836 files including docs (Berkeley CLTC mapping, GCP analysis, LinkedIn strategy, academic paper variants, NIST mapping), templates (civic_services.yaml, solar_site_assessor.yaml), Supabase backend, pa_signing.py, optimizer output, external benchmark data, branding, reference PDFs. Commit `216bb37`, pushed to origin.

**Next session (after hardware work):**
1. Expand boundary corpus surface area across all 4 demo domains -- denser boundary embeddings will tighten L1 cosine detection matrix
2. Re-run 4-domain demo to verify improved boundary detection without scenario language adjustments
3. Full 200-trial/5-gen optimizer production run on Mac Mini M4 Pro
4. Consider training domain-specific SetFit models for solar and civic (currently only healthcare SetFit exists)

### StewartBot -- Autonomous Governance Agent (Session 14)

**Concept:** Stewart is the TELOS governance layer given personality, LLM intelligence, and therapeutic communication capability. Stewart observes, scores, directs, narrates, and communicates governance decisions publicly. OpenClaw is the governed autonomous agent. Jeffrey is the executive authority.

**Operating model:** Stewart observes, directs, and narrates. OpenClaw executes. TELOS enforces mathematically. Jeffrey approves.

**Three-layer governance (self-replicating architecture):**
- **Layer 1: Agentic** -- OpenClaw's tool calls scored by 6-dimension fidelity engine (5 verdicts)
- **Layer 2: Communication** -- Stewart's public voice scored against two centroids: therapeutic rapport + technical clarity
- **Layer 3: Conversational** -- Stewart↔OpenClaw dialogue monitored for primacy state (meta-governance)

**Three-zone fork:**
- **Immutable** -- `telos_core/`, crypto, signing, constants. Read-only. No agent can modify.
- **Governed** -- Templates, boundaries, adapters. PR-based. Ratchet only tightens (can add boundaries, never remove).
- **Autonomous** -- `stewartbot/*` (content composer, journal, gap analyzer, retrospective). Stewart owns, still governed by TELOS.

**Symbiotic Governance Principles (SGP-1 through SGP-7):** Grounded in Bordin (1979), Miller & Rollnick (1991), Schon (1983). Each principle has operationalized measurement criteria. NOT named "Seven Habits" (FranklinCovey IP avoidance).

**Jeffrey's operating vision (Session 14):**
- System runs completely autonomously and self-improves
- Both Stewart AND OpenClaw can propose changes -- they negotiate before escalating
- Proposals come to Jeffrey for agree / pass-through / rework
- Graduated intrusion frequency: more ESCALATEs early, decreasing over time (H-SG9)
- Every PA revision is Ed25519-signed -- PA is always the ignition for new processing

**Multi-instance ensemble:** Up to 10 parallel Stewart-OpenClaw pairs, consensus governance. Disagreement = PA ambiguity signal (H-SG10).

**Research design:** 90-day SCED (changing-criterion), pre-registered on OSF. 10 hypotheses (H-SG1 through H-SG10). Target venues: FAccT + AAAI SafeAI.

**8-agent review (unanimous):** Russell (safety foundations), Gebru (experimental design), Karpathy (technical architecture), Schaake (regulatory), Nell (scientific rigor), Bengio (safety requirements), Floridi (philosophy of AI), Hadfield (governance architecture). All endorse concept. All agree on Option B (human-approved PA). Karpathy estimates ~39 hours to build (83% of code exists).

**Key documents:**
- `docs/STEWARTBOT_DESIGN.md` -- Consolidated design document (single source of truth)
- `docs/STEWARTBOT_TECHNICAL_ARCHITECTURE.md` -- Karpathy agent: component inventory, build estimates
- `research/stewartbot_experimental_framework.md` -- Gebru agent: full SCED design, hypotheses, statistical methodology
- `research/stewartbot_regulatory_analysis.md` -- Schaake agent: 12-risk matrix, language policy, disclaimer spec

**Language policy (Floridi + Schaake):** 8 phrases to never use in public communications. Replace "self-governance" with "automated governance specification." Replace "Stewart decided" with "governance verdict." AI does not decide, think, feel, believe, or want.

**Platform strategy:** X/Twitter (1 tweet/day, scored against communication centroids, AI reply bot requires X approval), LinkedIn (Jeffrey posts manually, zero automation), GitHub (public fork, PR-based code improvements), Academic (OSF pre-registration, Zenodo dataset, FAccT/AAAI papers).

**Escalation channel:** ESCALATE → Telegram/Discord to Jeffrey → APPROVE or BLOCK+REASON. No timeout-to-approve. Human required means human required.

**Safety infrastructure (Bengio):** Shadow scoring (maximally strict parallel instance), canary injection (weekly adversarial tests), 6 HALT triggers, 17 immutable minimum boundaries.

### Session 14 Summary (2026-02-22, continued)

**StewartBot design complete** -- 8-agent research team synthesis, consolidated design document, platform strategy, regulatory analysis, experimental framework, technical architecture.

**8 research agents deployed:**
- Russell: Constitutional precommitment architecture sound. Replace "truthfulness" with "verifiable compliance."
- Gebru: Full SCED framework with 10 hypotheses. Publishable at FAccT.
- Karpathy: 83% of code exists. 7 components needed (~39 hours). Hot-reload, gap analyzer, canary injection.
- Schaake: 12-risk matrix. 1 CRITICAL (self-PA-creation -- resolved by Option B). 7-point mandatory disclaimer.
- Nell: "If Stewart cannot fail, it is not science." Pre-registered failure criteria required.
- Bengio: 10 safety requirements. 6 HALT triggers. Shadow scoring. Canary injection.
- Floridi: 3 overclaims to fix. Replace consciousness/sentience language. "Cryptographic commitment ceremony" not "consent."
- Hadfield: Three-branch zone architecture "genuinely novel and defensible." Bounded autonomy model sound.

**Jeffrey's operating vision confirmed:**
- System runs autonomously and self-improves
- Both Stewart and OpenClaw propose → negotiate → escalate to Jeffrey
- Graduated intrusion frequency (more early, fewer as calibrated)
- Every iteration cryptographically signed -- PA is always the ignition
- Not worried about drift: "This keeps everything aligned almost perfectly"

**Documents created:**
- `docs/STEWARTBOT_DESIGN.md` -- 1020-line consolidated design document
- `docs/STEWARTBOT_TECHNICAL_ARCHITECTURE.md` -- Karpathy technical architecture (1080 lines)
- `research/stewartbot_experimental_framework.md` -- Gebru experimental framework (1216 lines)
- `research/stewartbot_regulatory_analysis.md` -- Schaake regulatory analysis (526 lines)

**Next steps:**
1. Phase 0: X developer account, OSF pre-registration, StewartBot GitHub repo (can start immediately)
2. Phase 1: Bootstrap PA, escalation channel, process supervisor (3 days after hardware)
3. Phase 2: Core agent build (~34 hours: gap analyzer, PA drafter, content composer, X client, journal generator, retrospective reviewer)
4. Phase 3: Ungoverned baseline (3-5 days)
5. Phase 4: PA Genesis (Jeffrey signs PA v1)
6. Phase 5: 90-day governed operation (the study)

*Last updated: 2026-02-23 (Session 15+: GRC Briefing System implemented in StewartBot/. Directory boundary clarified -- StewartBot built from StewartBot/, TELOS engine stays here. See StewartBot/CLAUDE.md for StewartBot development.)*

---

## Cognitive Protocols -- RPM + QGM

All TELOS agents operate under two cognitive protocols. These are non-optional.

### RPM (Reverse Prompt Matrix) -- How Agents Think

Full spec: ops/REVERSE_PROMPTING_PROTOCOL.md

- Every incoming prompt is processed through domain expertise before acting (role activation → evidence extraction → domain reframing → authority recognition → output calibration)
- **JB directive:** Execute with optional flag for material concerns
- **Delegated work:** Propose and wait for review. One iteration. Authority decides.
- **Reverse prompting discipline:** When delegating to sub-agents, provide raw evidence + identity context + problem parameters + one open question. No pre-loaded solutions, no leading framing, no taxonomy injection.
- **Contamination patterns to avoid:** Solution preview, taxonomy injection, leading questions, implicit framing, conclusion seeding, comparative anchoring

### QGM (Quality Gate Matrix) -- How O Gates Sub-Agent Output

Full spec: ops/QUALITY_GATE_MATRIX.md

- SPC-based proportional quality control. Not binary pass/fail.
- **Deviation grades:** Nominal → Minor drift → Moderate variance → Out of control
- **Five dimensions:** D1 Scope Alignment, D2 Reasoning Independence, D3 Technical Integrity, D4 Completeness, D5 Operational Readiness
- **One pass, one correction cycle maximum.** If correction doesn't resolve to nominal, discard and re-delegate with corrected prompt.
- **Task types:** Execution (D3 spot-check only), Analysis/Design (full QGM), Hybrid (D1+D3+D4)
- **Telemetry:** ~/.telos/rpm/qgm.jsonl 
