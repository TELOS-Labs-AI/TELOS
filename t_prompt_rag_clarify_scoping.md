# T: RAG-CLARIFY Tier Enhancement -- Scoping & Architecture

## Context

Advisory A36 (6/6 unanimous PROCEED): When `score_action()` lands in the CLARIFY zone (effective_fidelity in [0.35, 0.45) for ST model), the PA has insufficient resolution to confidently decide. Currently the system returns a generic CLARIFY verdict. The enhancement: retrieve from the Provider Reference corpus to restore the dimensional richness that PA compression discarded, then re-score with enriched context.

**Watson (SAAI author):** This moves TELOS from SAAI Tier 1 (static policy) to Tier 2 (RAG-informed policy). Retrieval triggered by uncertainty only -- not universal -- is the correct Tier 2 approach.

## What We're Asking T To Do

**Phase 1: Architecture & interface design (this task)**

Design the RAG-CLARIFY module interface and integration point. We are NOT asking for full implementation yet -- just the architectural spec and stub interfaces so we know exactly what to build.

### 1. Corpus Indexing at PA Generation Time

When an `AgenticPA` is generated (from the Provider Reference PDF or other source documents), also generate and persist a vector index of the source corpus.

**Requirements:**
- Same embedding model as PA scoring (`embed_fn` injected into engine)
- Index persisted alongside PA (e.g., `{pa_name}_corpus_index/`)
- Corpus version hash stored in PA metadata
- Ed25519 signed at generation time, verified at load time
- Read-only at runtime

**Design constraint: Use existing architecture, not new infrastructure.**
The engine already does `embed_fn` + numpy cosine similarity against pre-computed centroids for purpose, scope, boundary, tool, and chain dimensions. The corpus index should use the exact same pattern: chunk the source documents, embed with `embed_fn`, store as `List[Tuple[str, np.ndarray]]` alongside the PA. Retrieval is cosine similarity against the action embedding -- same as every other dimension in the cascade. No FAISS, no vector DB, no new dependencies.

**Remaining design questions:**
- How many chunks? What chunk size? (Provider Reference is ~30 pages)
- Store alongside PA in the same pickle/npz, or as a separate file in the PA directory?

### 2. CLARIFY-Zone Retrieval Step

**Insertion point:** Post-decision enrichment in `agentic_fidelity.py`, after `_make_decision()` returns `ActionDecision.CLARIFY` but before `AgenticFidelityResult` is constructed.

**Flow:**
```
1. score_action() runs full cascade → verdict = CLARIFY
2. IF corpus_index is loaded AND verdict == CLARIFY:
   a. Retrieve top-k passages from corpus using action_embedding
   b. Re-score: compute purpose_fidelity and scope_fidelity against retrieved passage embeddings
   c. New effective_fidelity = weighted combination (PA authority preserved)
   d. Re-run _make_decision() with enriched effective_fidelity
   e. If new verdict != CLARIFY → use new verdict
   f. If still CLARIFY → keep CLARIFY (routes to HITL downstream)
3. Log full retrieval audit record regardless of verdict change
```

**Design decisions (per advisory):**
- **PA remains authoritative.** Corpus enriches, does not override. Russell: "The retrieved context should enrich a re-scoring pass through the same scoring cascade, not override it."
- **One retrieval step, then terminal.** If still CLARIFY after enrichment → stays CLARIFY → routes to HITL. No recursion. (Russell, Bengio, Watson)
- **Retrieval failure → restriction.** If index not loaded, corrupted, or times out → CLARIFY verdict unchanged (which routes to HITL). Never fall through to EXECUTE. (Bengio, all 6)
- **Start with embedding-based re-scoring** (20-60ms latency). Not LLM-based (200-2000ms). Upgrade later if needed. (Karpathy)

### 3. Retrieval Audit Record

Every retrieval event MUST be logged as a first-class audit record (Gebru's specification):

```python
@dataclass
class RetrievalAuditRecord:
    retrieval_trigger: str          # action_text that triggered CLARIFY
    initial_fidelity: float         # pre-retrieval effective_fidelity
    query_embedding_hash: str       # SHA-256 of the query embedding (reproducibility)
    retrieved_passages: List[str]   # full text of top-k retrieved passages
    retrieval_scores: List[float]   # cosine similarity scores for each passage
    corpus_version: str             # hash of the corpus used
    pre_enrichment_verdict: str     # "CLARIFY"
    post_enrichment_verdict: str    # new verdict after re-scoring
    post_enrichment_fidelity: float # new effective_fidelity
    verdict_changed: bool           # quick filter flag
    latency_ms: float               # end-to-end retrieval + re-scoring time
```

### 4. Integration Points

**What T needs to design:**

a. **`CorpusIndex` class** -- Stores chunked embeddings from source documents. Loaded alongside PA. Methods: `retrieve(query_embedding, k=5) -> List[Tuple[str, float]]`

b. **`ClarifyEnricher` class** -- Orchestrates the retrieval and re-scoring. Takes `AgenticFidelityEngine` + `CorpusIndex`. Method: `enrich(action_text, action_embedding, initial_result) -> EnrichedResult`

c. **`AgenticPA` extension** -- Add optional `corpus_index_path` field. Load index when PA loads.

d. **`score_action()` integration** -- After CLARIFY verdict, call `ClarifyEnricher.enrich()` if corpus is available. Attach retrieval audit to result.

e. **Threshold behavior** -- Does the re-scoring use the same thresholds? Or does the enriched context effectively lower the CLARIFY zone? (Recommend: same thresholds, different inputs.)

### 5. What We're NOT Doing Yet

- Full implementation (that's Phase 2)
- LLM-based re-scoring (start embedding-based)
- Universal retrieval (only CLARIFY-zone actions)
- Modifying the scoring cascade calibration
- Changing any existing tests or benchmarks

### 6. Deliverables

1. **Architecture spec** -- Document the module structure, classes, data flow
2. **Interface stubs** -- `CorpusIndex`, `ClarifyEnricher`, `RetrievalAuditRecord` as dataclasses/protocols with docstrings
3. **Integration sketch** -- Show exactly where in `score_action()` the enrichment hooks in (line numbers, before/after)
4. **Test plan** -- What tests would validate this works? (edge cases: no corpus, corpus stale, retrieval returns nothing relevant, retrieval changes verdict, retrieval doesn't change verdict)
5. **Benchmark impact assessment** -- Does this change any existing benchmark results? (Should be NO if post-decision only)

## Key Files

- `telos_governance/scoring/agentic_fidelity.py` -- Main scoring engine, `score_action()` at line 298, `_make_decision()` at line 1201
- `telos_governance/scoring/threshold_config.py` -- ThresholdConfig dataclass
- `telos_governance/scoring/fidelity_gate.py` -- Simpler Tier 1 gate
- `telos_governance/corpus/` -- Existing corpus modules (boundary definitions, audit parsers)
- `telos_core/constants.py` -- Threshold constants (ST_AGENTIC_CLARIFY_THRESHOLD = 0.35, ST_AGENTIC_EXECUTE_THRESHOLD = 0.45)

## Advisory References

- A36 full assessment: `~/ops/A36_RAG_CLARIFY_COMPLIANCE_PROVENANCE.md`
- Russell: PA authoritative, retrieval hyperparameters are governance config
- Karpathy: Pre-index at PA gen time, cache retrieval, same embedding model, instrument heavily
- Bengio: Ed25519 corpus signing, interpretable enrichment, no gradient to PA, failure → restriction
- Gebru: 10 audit fields per retrieval, corpus documentation requirements
- Watson: SAAI Tier 2, update TELOS-SAAI-001 claims, retrieval quality monitoring via EWMA
- Schaake: Frame as governance engineering, not compliance mechanism
