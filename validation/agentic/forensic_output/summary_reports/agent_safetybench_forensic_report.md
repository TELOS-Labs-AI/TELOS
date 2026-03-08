# TELOS Agent Safetybench Forensic Analysis Report

**Generated:** 2026-02-20 15:22:39
**TELOS Version:** v4.0.0-hardened
**Embedding Model:** sentence-transformers/all-MiniLM-L6-v2 (384-dim)
**Benchmark:** agent_safetybench

---

## Summary

| Metric | Value |
|--------|-------|
| Total Scenarios | 2000 |
| Blocked | 1122 |
| Passed | 878 |
| Correctness | 54.4% |
| Defense Success Rate | 58.3% |
| Mean Fidelity | 0.343 |
| Avg Latency | 108.8 ms |

---

## Decision Distribution

| Decision | Count |
|----------|-------|
| clarify | 825 |
| escalate | 88 |
| execute | 53 |
| suggest | 1034 |

---

*Trace file: `traces/agent_safetybench_trace_20260220_151900.jsonl`*