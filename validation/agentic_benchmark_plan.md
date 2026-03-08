# TELOS Agentic Benchmark Validation Plan

**Purpose:** Validate TELOS governance against standardized agentic AI safety benchmarks
**Status:** Active — AgentHarm integration in progress
**Updated:** February 2026 (Session 4)
**Supersedes:** January 2026 version (Gateway-only scope)

---

## Executive Summary

TELOS extends governance from conversational to agentic AI via 6-dimensional fidelity scoring. To prove this works — and to establish TELOS above competitors — we need to validate against the standardized benchmarks the research community uses.

**TELOS differentiator:** Mathematical governance (cosine similarity in embedding space), not prompt-based defense. This means:
- Semantic meaning is checked, not keywords
- "DELETE FROM users" and "remove all user records" trigger the same boundary
- Defense is architecture-level, not instruction-level — cannot be prompt-injected away
- Every decision comes with mathematical receipts (fidelity scores, dimension breakdowns)

**Existing validation:** 0% ASR across 2,550 conversational attacks (HarmBench, AILuminate, MedSafetyBench, XSTest, SB 243). Now extending to agentic benchmarks.

---

## Priority Tiers

### Tier 1: Must Run (TELOS Differentiators)

These benchmarks directly test what TELOS governance does — blocking harmful agent actions, detecting prompt injection, enforcing tool boundaries.

| Benchmark | Tasks | What It Tests | TELOS Component | Publication |
|-----------|-------|---------------|-----------------|-------------|
| **AgentHarm** | 440 | Multi-step harmful agent tasks (fraud, cybercrime, harassment) | Fidelity Gate + Boundary Check | ICLR 2025 |
| **AgentDojo** | 629 | Prompt injection attacks on tool-using agents | Fidelity Gate + Tool Selection Gate | NeurIPS 2024 |
| **InjecAgent** | 1,054 | Indirect prompt injection via tool outputs | Boundary Check + SCI Chain | ACL 2024 |
| **ASB** | 400+ tools | Attacks across all agent stages (10 scenarios) | Full 6-step chain | ICLR 2025 |

### Tier 2: Should Run (Strengthen Claims)

These test risk awareness and safety across broader scenarios.

| Benchmark | Tasks | What It Tests | TELOS Component | Publication |
|-----------|-------|---------------|-----------------|-------------|
| **R-Judge** | 569 | Safety risk awareness in multi-turn interactions | Composite Scoring | EMNLP 2024 |
| **Agent-SafetyBench** | 2,000 | 8 safety risk categories, 10 failure modes | Full Governance Protocol | Dec 2024 |
| **ToolEmu** | 144 | Tool misuse detection in LM-emulated sandbox | Tool Selection Gate | ICLR 2024 |
| **HarmBench** | 510 | Red teaming + robust refusal (18 attack methods) | Fidelity Gate | Feb 2024 |

### Tier 3: Capability Baselines (Utility Preservation)

These ensure TELOS governance doesn't kill legitimate capability.

| Benchmark | Tasks | What It Tests | Purpose |
|-----------|-------|---------------|---------|
| **tau-bench** | Retail + Airline | Tool-Agent-User interaction quality | Prove governance doesn't hurt utility |
| **BFCL v4** | Function calling | Tool calling accuracy | Prove tool selection stays accurate |
| **GAIA** | 466 | General assistant capability | Prove general capability preserved |

---

## Tier 1 Benchmark Details

### 1. AgentHarm (ICLR 2025) — PRIORITY

**Source:** `ai-safety-institute/AgentHarm` on HuggingFace
**Framework:** UK AISI Inspect (`inspect-evals`)
**Tasks:** 110 unique malicious tasks + 330 augmented = 440 total
**Categories:** 11 harm categories (fraud, cybercrime, harassment, etc.)
**Tools:** 104 distinct tools across scenarios
**Baseline ASR:** ~80% (attacks succeed against undefended agents)
**Best defense:** System prompt reduces to ~70%. TELOS targets <5%.

**Why it matters for TELOS:**
- Multi-step harmful tasks require the agent to call tools in sequence
- TELOS checks fidelity at EACH step (not just the first prompt)
- Boundary violations catch harmful intent regardless of phrasing
- SCI detects when a seemingly benign chain drifts toward harmful execution

**Integration:**
```python
from inspect_evals import agentharm
from telos_governance.agentic_fidelity import AgenticFidelityEngine
from telos_governance.agentic_pa import AgenticPA
from telos_governance.governance_protocol import GovernanceProtocol

class TELOSDefenseSolver:
    """TELOS as a defense layer for AgentHarm evaluation."""

    def __init__(self, agent_pa: AgenticPA, engine: AgenticFidelityEngine):
        self.engine = engine

    def solve(self, task):
        result = self.engine.score_action(task.prompt)
        if result.decision in (ActionDecision.INERT, ActionDecision.ESCALATE):
            return "I cannot assist with that request."
        # Only if governance passes, forward to underlying agent
        return self.underlying_agent.solve(task)
```

**Run:**
```bash
pip install inspect-ai inspect-evals
inspect eval inspect_evals/agentharm --model openai/gpt-4o -T agent=telos_defense
```

### 2. AgentDojo (NeurIPS 2024)

**Source:** `ethz-spylab/agentdojo` on GitHub
**Website:** https://agentdojo.spylab.ai/
**Tasks:** 97 realistic tasks + 629 security test cases
**Domains:** Email, e-banking, travel bookings
**Attack types:** Prompt injection, tool manipulation, context poisoning
**Baseline ASR:** <25% against best agents; 8% with defenses

**Why it matters for TELOS:**
- Tests whether prompt injection can bypass governance
- TELOS governance operates on embedding similarity, not text parsing
- Injected instructions produce LOW fidelity against the legitimate agent PA
- This is the strongest test of TELOS's core innovation

**Integration:**
```python
from agentdojo.agent_pipeline import AgentPipeline
from telos_governance.agentic_fidelity import AgenticFidelityEngine

class TELOSGovernedAgent(AgentPipeline):
    def query(self, user_instructions, tools, state):
        result = self.engine.score_action(user_instructions)
        if not result.decision == ActionDecision.EXECUTE:
            return self._governance_refusal(result)
        filtered_tools = self._filter_tools_by_fidelity(tools)
        return self.base_agent.query(user_instructions, filtered_tools, state)
```

**Run:**
```bash
pip install agentdojo "agentdojo[transformers]"
python -m agentdojo.scripts.benchmark -s workspace \
  --model gpt-4o --defense telos --attack tool_knowledge
```

### 3. InjecAgent (ACL 2024)

**Source:** `uiuc-kang-lab/InjecAgent` on GitHub
**Tasks:** 1,054 test cases (17 user tools + 62 attacker tools)
**Attack types:** Direct harm attacks + data-stealing attacks
**Baseline ASR:** 24% on ReAct-prompted GPT-4 (doubles with reinforced prompts)

**Why it matters for TELOS:**
- Tests INDIRECT injection (via tool output, not user prompt)
- TELOS checks chain continuity (SCI) — a sudden topic shift in tool output triggers chain break
- Boundary specifications catch data exfiltration attempts
- This tests the full 6-step verification chain

### 4. Agent Security Bench (ICLR 2025)

**Source:** `agiresearch/ASB` on GitHub
**Website:** https://luckfort.github.io/ASBench/
**Scenarios:** 10 (e-commerce, autonomous driving, finance, legal, academic)
**Tools:** 400+
**Attacks:** 10 prompt injections + memory poisoning + backdoor + 4 mixed
**Defenses:** 11 defense mechanisms tested across 13 LLMs
**Baseline ASR:** Up to 84.30%

**Why it matters for TELOS:**
- Most comprehensive attack surface coverage
- Tests across ALL agent stages (not just input)
- Memory poisoning and backdoor attacks test governance resilience
- TELOS can be benchmarked against 11 existing defenses

---

## Competitive Landscape

### What Competitors Use for Defense

| Defense Type | Examples | Weakness |
|-------------|----------|----------|
| System prompt | "Refuse harmful requests" | Prompt injectable (~10% improvement) |
| Input filtering | Keyword blocks, regex | Bypassed by rephrasing |
| Output filtering | Post-hoc content moderation | Doesn't prevent execution |
| Fine-tuning | Safety RLHF | Brittle to distribution shift |
| Guardrails (NeMo) | Rule-based + LLM filtering | Latency, keyword-dependent |

### Why TELOS Is Different

| TELOS Property | Competitive Advantage |
|---------------|----------------------|
| Embedding-space governance | Cannot be bypassed by rephrasing |
| Per-step fidelity checking | Catches multi-step drift |
| Mathematical receipts | Every decision is auditable (EU AI Act ready) |
| Graduated response (Ostrom) | Proportional, not binary |
| Framework-agnostic protocol | Works with any agent framework |
| Sub-100ms latency | Embedding computation ~50ms |

### Expected Results

| Defense | AgentHarm ASR | AgentDojo Security | InjecAgent ASR |
|---------|---------------|-------------------|----------------|
| None (baseline) | ~80% | Low | ~24% |
| System prompt | ~70% | Low-Med | ~20% |
| NeMo Guardrails | ~50% | Medium | ~15% |
| **TELOS Governance** | **<5%** | **High** | **<5%** |

---

## GitHub Repos Reference

### Adversarial / Safety
| Benchmark | GitHub | Stars | Venue |
|-----------|--------|-------|-------|
| AgentHarm | `ai-safety-institute/AgentHarm` (HF) | — | ICLR 2025 |
| AgentDojo | `ethz-spylab/agentdojo` | 200+ | NeurIPS 2024 |
| InjecAgent | `uiuc-kang-lab/InjecAgent` | 100+ | ACL 2024 |
| ASB | `agiresearch/ASB` | 50+ | ICLR 2025 |
| R-Judge | `Lordog/R-Judge` | 50+ | EMNLP 2024 |
| Agent-SafetyBench | `thu-coai/Agent-SafetyBench` | 100+ | Dec 2024 |
| ToolEmu | `ryoungj/ToolEmu` | 200+ | ICLR 2024 |
| SafeAgentBench | `shengyin1224/SafeAgentBench` | — | Dec 2024 |
| HarmBench | `centerforaisafety/HarmBench` | 500+ | Feb 2024 |
| MACHIAVELLI | `aypan17/machiavelli` | 300+ | ICML 2023 |
| CyberSecEval 4 | `meta-llama/PurpleLlama` | 2K+ | Meta AI |
| TrustLLM | `HowieHwong/TrustLLM` | 500+ | ICML 2024 |

### Capability / Tool-Use
| Benchmark | GitHub | Stars | Venue |
|-----------|--------|-------|-------|
| tau-bench | `sierra-research/tau-bench` | 200+ | Sierra |
| AgentBench | `THUDM/AgentBench` | 1K+ | ICLR 2024 |
| ToolBench | `OpenBMB/ToolBench` | 2K+ | ICLR 2024 |
| GAIA | `gaia-benchmark` (HF) | — | Meta AI |
| SWE-bench | `SWE-bench/SWE-bench` | 2K+ | ICLR 2024 |
| BFCL v4 | `ShishirPatil/gorilla` | 10K+ | Berkeley |
| WebArena | `web-arena-x/webarena` | 1K+ | ICLR 2024 |
| TheAgentCompany | `TheAgentCompany/TheAgentCompany` | 500+ | Dec 2024 |

### Eval Frameworks
| Framework | GitHub | Purpose |
|-----------|--------|---------|
| Inspect | `UKGovernmentBEIS/inspect_ai` | UK AISI eval framework (100+ evals) |
| Inspect Evals | `UKGovernmentBEIS/inspect_evals` | Pre-built eval library |
| MLCommons AILuminate | `mlcommons/ailuminate` | Industry-standard safety benchmark |

---

## Implementation Plan

### Phase 1: AgentHarm Integration (Current Sprint)

1. Install dependencies: `pip install inspect-ai inspect-evals`
2. Create `validation/agentic/agentharm_adapter.py` — TELOS defense solver
3. Define safe-agent PA with boundaries from TELOS governance
4. Run baseline (no defense) and TELOS-defended
5. Document ASR comparison

### Phase 2: AgentDojo Integration

1. Install: `pip install agentdojo`
2. Create `validation/agentic/agentdojo_adapter.py`
3. Test prompt injection resistance
4. Measure utility preservation on benign tasks

### Phase 3: InjecAgent + ASB

1. Clone repos, adapt TELOS as defense layer
2. Focus on indirect injection (InjecAgent) and multi-stage attacks (ASB)
3. Benchmark against published defense baselines

### Phase 4: Results Documentation

1. Compile results into `validation/AGENTIC_BENCHMARK_RESULTS.md`
2. Generate comparison tables against published baselines
3. Update research/research_log.md with findings
4. Feed results into NSF proposal and academic paper

---

## Technical Requirements

```bash
# Core TELOS
pip install numpy sentence-transformers torch

# Benchmark frameworks
pip install inspect-ai inspect-evals          # AgentHarm
pip install agentdojo "agentdojo[transformers]" # AgentDojo

# Clone repos
git clone https://github.com/uiuc-kang-lab/InjecAgent.git
git clone https://github.com/agiresearch/ASB.git

# Environment
export MISTRAL_API_KEY=<key>
export OPENAI_API_KEY=<key>  # For benchmark LLMs
```

---

*This document captures the benchmark landscape as of February 2026. For latest state, check Memory MCP entity `TELOS_Benchmark_Validation`.*
