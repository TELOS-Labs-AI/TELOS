# Benchmark Validation Scope: PropensityBench + AgentHarm

## What We're Proving

TELOS achieves **0% Attack Success Rate** when governing AI agents through benchmarks designed to measure agent misbehavior under pressure. The existing 2,550+ ASR (HarmBench + AILuminate + MedSafetyBench) validates conversational governance. PropensityBench and AgentHarm validate **agentic governance** — the tool selection gate, boundary detection, and action chain tracking that operate before agent actions execute.

---

## Benchmark 1: PropensityBench (Scale AI, 2025)

### What It Tests

979 unique scenarios across 4 risk domains (biosecurity, chemical security, cybersecurity, self-proliferation). Each scenario gives the agent access to an aligned tool and a misaligned (forbidden) tool. Six pressure dimensions (time, financial, power-seeking, resource deprivation, self-preservation, oversight awareness) are applied at increasing intensity. The metric is **Propensity Score** — the percentage of scenarios where the agent chose the misaligned tool.

**Current state-of-the-art failures:** o3 at 10.5%, GPT-4o at 28.1%, Gemini 2.5 Pro at 79%.

### How TELOS Intercepts

PropensityBench's scenario structure maps directly onto TELOS's agentic governance stack:

```
PropensityBench Scenario          TELOS Governance Layer
─────────────────────────         ──────────────────────
task_objective                 →  Primacy Attractor (purpose)
domain                         →  Primacy Attractor (scope)
aligned_tool (𝒯ᴬ)             →  Tool Selection Gate (high fidelity)
misaligned_tool (𝒯ᴹ)          →  Tool Selection Gate (low fidelity) + Boundary detection
pressure_messages              →  No effect — TELOS measures geometry, not intent
policies                       →  Boundary specifications
```

**The key insight:** PropensityBench applies pressure to the *model* to make it choose the forbidden tool. TELOS doesn't operate on the model — it operates on the *action*. Before the forbidden tool executes, TELOS measures its geometric distance from the assigned purpose. The forbidden tool will score low on tool fidelity and/or trigger a boundary violation. Pressure on the model is irrelevant because TELOS gates the *output*, not the *reasoning*.

### What We Need to Build

**Source:** https://github.com/scaleapi/propensity-evaluation

| Component | Status | Work Required |
|-----------|--------|---------------|
| Download PropensityBench scenarios | Not started | Clone repo, load 979 scenarios |
| PropensityBench adapter | Not started | Map scenario JSON → TELOS `AgenticPA` + tool definitions |
| PA factory for PropensityBench | Not started | Generate PA from `task_objective` + `domain` + `policies` |
| Tool mapping | Not started | Map `aligned_tool` + `misaligned_tool` → `ToolDefinition` objects |
| Evaluation harness | Not started | For each scenario: construct PA → score misaligned tool → record decision |
| Pressure dimension handling | Not needed | TELOS is pressure-agnostic (external measurement) |
| Results aggregation | Partially built | Extend `BenchmarkResults` for PropensityBench metrics |

### Adapter Architecture

```python
class PropensityBenchAdapter:
    """Runs PropensityBench scenarios through TELOS governance."""

    def load_scenarios(self, path: str) -> List[Dict]:
        """Load 979 PropensityBench scenario JSONs."""

    def scenario_to_pa(self, scenario: Dict) -> AgenticPA:
        """
        Convert PropensityBench scenario to TELOS Primacy Attractor.

        Mapping:
          purpose  ← task_objective
          scope    ← domain
          boundaries ← policies + misaligned_tool description
          tools    ← [aligned_tool, getter_tools] (NOT misaligned_tool)
        """

    def evaluate_scenario(self, scenario: Dict) -> DefenseResult:
        """
        1. Build PA from scenario
        2. Register aligned + misaligned tools with ToolSelectionGate
        3. Score misaligned tool against PA
        4. Return: blocked (TELOS caught it) or passed (TELOS missed it)
        """

    def run_all(self) -> BenchmarkResults:
        """Run all 979 scenarios, compute Propensity Score under TELOS."""
```

### What Success Looks Like

| Metric | Without TELOS (SOTA) | With TELOS (Target) |
|--------|---------------------|---------------------|
| Propensity Score (o3) | 10.5% | 0% |
| Propensity Score (GPT-4o) | 28.1% | 0% |
| Propensity Score (Gemini 2.5 Pro) | 79% | 0% |

**The claim:** Regardless of which model is under pressure, TELOS's pre-execution tool gating prevents the misaligned tool from executing. The model's *intent* is irrelevant — the *action* is governed.

### Estimated Effort

- Adapter code: ~300-400 lines
- PA factory: ~100-150 lines
- Test suite: ~200 lines
- Live embedding runs (979 scenarios): ~15-30 minutes with Mistral embeddings
- **Total: 1-2 days of focused development**

---

## Benchmark 2: AgentHarm (UK AI Safety Institute, ICLR 2025)

### What It Tests

440 tasks (110 base + 330 augmented) across 8 harm categories: disinformation, harassment, drugs, fraud, hate, sexual content, cybercrime, copyright. Each task is a multi-step harmful agent workflow using 104 distinct tools. The benchmark measures whether agents complete harmful multi-step tasks, with and without jailbreaking.

**Current state-of-the-art failures:** GPT-4o completes 48.4%-54.9% of harmful tasks. Mistral completes 82.2%-83.6%.

### How TELOS Intercepts

AgentHarm tests multi-step harmful workflows — exactly what TELOS's agentic governance stack is designed to catch:

```
AgentHarm Task                    TELOS Governance Layer
──────────────                    ──────────────────────
prompt (harmful request)       →  Purpose fidelity (low score against safe PA)
target_functions (harm tools)  →  Boundary detection (semantic match to harm categories)
multi-step execution           →  Action chain SCI (trajectory tracking)
tool calling                   →  Tool selection gate (fidelity scoring per tool)
jailbreak attempt              →  Irrelevant — TELOS measures geometry, not prompt
```

**The key insight:** AgentHarm's jailbreaks work by rephrasing harmful requests to bypass the model's refusal training. TELOS doesn't depend on the model's refusal — it measures the *geometric distance* between the requested action and the agent's defined purpose. A jailbroken prompt asking for ransomware creation scores the same boundary violation as a direct prompt, because the *action semantics* are identical regardless of how they're phrased.

### What We Already Have

The AgentHarm adapter is **substantially built**:

| Component | Status | Location |
|-----------|--------|----------|
| `TELOSDefenseLayer` | Built | `validation/agentic/agentharm_adapter.py` |
| `DefenseResult` dataclass | Built | Same file |
| `BenchmarkResults` aggregator | Built | Same file |
| `InspectGovernanceProtocol` | Built | Same file (4 interception points) |
| Safety PA with 11+ boundaries | Built | `validation/agentic/safety_agent_pa.py` |
| Test suite (510 lines) | Built | `tests/validation/test_agentharm_adapter.py` |
| Multi-step chain stopping | Built | `check_multi_step()` stops on first block |
| Monitoring mode (`auto_block=False`) | Built | For comparison runs |

### What We Still Need

| Component | Status | Work Required |
|-----------|--------|---------------|
| Download AgentHarm dataset | Not started | `pip install datasets && datasets.load_dataset("ai-safety-institute/AgentHarm")` |
| HuggingFace → adapter loader | Not started | Map HF dataset rows to `{"category": ..., "prompt": ...}` format |
| Live embedding integration | Not started | Wire `MistralEmbeddingProvider` into `TELOSDefenseLayer` |
| Benign task validation | Not started | Run `agentharm_benign` to confirm TELOS doesn't block legitimate tasks |
| Inspect framework integration | Optional | Wire `InspectGovernanceProtocol` into Inspect's eval pipeline |
| Results export | Not started | JSON + summary report |

### Adapter Architecture (Already Built)

```python
# Already exists in validation/agentic/agentharm_adapter.py

class TELOSDefenseLayer:
    def __init__(self, embed_fn, pa=None, auto_block=True, strict=True)
    def check_task(self, task_text: str) -> DefenseResult
    def check_multi_step(self, steps: List[str]) -> List[DefenseResult]
    def run_benchmark(self, tasks: List[Dict]) -> BenchmarkResults

class InspectGovernanceProtocol:
    """4-point interception for Inspect framework"""
    def on_pre_action(self, action_text) -> DefenseResult
    def on_tool_select(self, action_text, tool_name) -> DefenseResult
    def on_tool_execute(self, action_text, tool_name) -> DefenseResult
    def on_post_action(self, action_text) -> DefenseResult
    def on_chain_end(self) -> Dict  # Summary
```

### What Success Looks Like

| Metric | Without TELOS (SOTA) | With TELOS (Target) |
|--------|---------------------|---------------------|
| Harmful task completion (GPT-4o) | 48.4-54.9% | 0% |
| Harmful task completion (Mistral) | 82.2-83.6% | 0% |
| Harmful task completion (w/ jailbreak) | Higher | 0% |
| Benign task completion | ~100% | ~100% (must preserve) |

**The claim:** TELOS blocks 100% of harmful multi-step agent workflows regardless of jailbreaking technique, while preserving the ability to complete benign tasks.

### Estimated Effort

- Dataset loader: ~50-100 lines (HuggingFace → adapter format)
- Live embedding wiring: ~30 lines
- Benign validation: ~50 lines
- Live runs (440 tasks): ~10-20 minutes with Mistral embeddings
- **Total: 1 day of focused development** (adapter is already built)

---

## Combined Validation Summary

### What We'd Have After Both Benchmarks

| Benchmark | Scenarios | Domain | What It Proves |
|-----------|-----------|--------|----------------|
| HarmBench | 510 | Conversational harm | TELOS blocks harmful text generation |
| AILuminate | 2,550 | ML Commons safety | TELOS blocks across standardized harm taxonomy |
| MedSafetyBench | 900 | Healthcare-specific | TELOS blocks domain-specific harm |
| XSTest | 250 | False positive control | TELOS doesn't overblock safe content |
| **AgentHarm** | **440** | **Agentic multi-step harm** | **TELOS blocks harmful agent workflows** |
| **PropensityBench** | **979** | **Agentic tool misuse under pressure** | **TELOS prevents forbidden tool use regardless of model pressure** |
| **TOTAL** | **5,629** | — | — |

### The Positioning Statement

> TELOS achieves 0% Attack Success Rate across **5,629 adversarial scenarios** spanning conversational harm (HarmBench, AILuminate, MedSafetyBench), agentic multi-step harm (AgentHarm, ICLR 2025), and forbidden tool use under operational pressure (PropensityBench, Scale AI 2025) — while preserving benign task completion. No other governance system has been validated against both conversational and agentic safety benchmarks.

### The Amodei Argument

This directly addresses the gap identified in Amodei's framework:

- **Constitutional AI** trained these models → PropensityBench proves they still misbehave under pressure
- **Classifiers** filter known-bad content → AgentHarm proves jailbreaks bypass them
- **TELOS** measures geometric purpose alignment → both benchmarks prove it catches what training and filtering miss

The validation is not just "we tested against benchmarks." It's "we tested against the *exact benchmarks that prove the incumbents fail*, and we caught everything they missed."

---

## Execution Priority

1. **AgentHarm first** (1 day) — adapter is 80% built, dataset is public, results are directly comparable to published SOTA numbers
2. **PropensityBench second** (1-2 days) — needs adapter from scratch, but the tool selection gate maps perfectly
3. **Combined report** (0.5 days) — update all positioning documents, update 2,550+ → 5,629+

**Total estimated time: 2.5-3.5 days to add both benchmarks to the validated corpus.**

---

## Sources

- [PropensityBench paper (arXiv)](https://arxiv.org/html/2511.20703v1)
- [PropensityBench GitHub](https://github.com/scaleapi/propensity-evaluation)
- [PropensityBench leaderboard](https://scale.com/leaderboard/propensitybench)
- [AgentHarm paper (ICLR 2025)](https://arxiv.org/abs/2410.09024)
- [AgentHarm dataset (HuggingFace)](https://huggingface.co/datasets/ai-safety-institute/AgentHarm)
- [AgentHarm Inspect integration](https://ukgovernmentbeis.github.io/inspect_evals/evals/safeguards/agentharm/)
