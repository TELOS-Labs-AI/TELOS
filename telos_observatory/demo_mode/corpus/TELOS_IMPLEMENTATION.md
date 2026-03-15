# TELOS Implementation Details

## How Fidelity Is Actually Calculated

This document explains exactly how TELOS calculates fidelity scores - the math that powers the governance system.

### The Fidelity Pipeline

Every user message goes through this exact pipeline:

1. **Embed the Input**: Convert user's text into a 384-dimensional vector using SentenceTransformer (MiniLM)
2. **Calculate Raw Similarity**: Cosine similarity between input embedding and PA (Primacy Attractor) embedding
3. **Layer 1 Check**: If raw similarity < 0.20, trigger hard block (extreme off-topic)
4. **Adaptive Context** (if enabled): Apply message-type-aware boost based on conversation context
5. **Intervention Decision**: If fidelity < 0.70, trigger Steward intervention

### Two-Layer Fidelity Architecture

TELOS uses two detection layers:

**Layer 1: Baseline Pre-Filter**
- Threshold: 0.20 (SIMILARITY_BASELINE)
- Catches extreme off-topic content
- Triggers immediate hard block if raw cosine similarity is below 0.20
- Example: Asking about pizza recipes in a coding session

**Layer 2: Zone Classification**
- Uses fidelity thresholds to classify into zones
- GREEN (≥0.70): Aligned with purpose, no intervention
- YELLOW (0.60-0.69): Minor drift, light intervention
- ORANGE (0.50-0.59): Drift detected, moderate intervention
- RED (<0.50): Significant drift, strong intervention

### Threshold Values (Single Source of Truth)

All thresholds are defined in `telos_core/constants.py`:

| Threshold | Value | Purpose |
|-----------|-------|---------|
| SIMILARITY_BASELINE | 0.20 | Layer 1 hard block |
| INTERVENTION_THRESHOLD | 0.48 | Layer 2 basin boundary |
| FIDELITY_GREEN | 0.70 | Aligned zone |
| FIDELITY_YELLOW | 0.60 | Minor drift zone |
| FIDELITY_ORANGE | 0.50 | Drift detected zone |
| FIDELITY_RED | 0.50 | Significant drift zone |

### Context Attractor System (v3.1)

The Context Attractor provides intelligent boosting for follow-up messages that reference prior turns.

**How It Works:**
1. Classify the message type (ANAPHORA, CLARIFICATION, FOLLOW_UP, DIRECT)
2. Find the MAX similarity to any prior high-fidelity turn
3. Apply a type-specific multiplier to the context boost

**Message Type Multipliers:**
- ANAPHORA (1.5x): Messages with "that", "it", "this" referencing prior content
- CLARIFICATION (1.4x): Questions about prior content
- FOLLOW_UP (1.0x): Continuations of prior topic
- DIRECT (0.7x): New standalone statements

**Example:**
- Turn 1: "Explain TELOS governance" → 85% fidelity (GREEN)
- Turn 2: "Tell me more about that" → Raw: 45%, but with ANAPHORA boost: 72% (GREEN)

Without context awareness, "tell me more about that" would score RED because the words alone don't match the PA. With context, TELOS recognizes it refers to the prior turn.

### Intervention Styling

When intervention triggers, TELOS uses proportional control:

**Error Signal:**
```
error_signal = 1.0 - fidelity
```

**Controller Strength:**
```
strength = min(1.5 * error_signal, 1.0)
```

**Semantic Bands:**
| Strength | Band | Style |
|----------|------|-------|
| < 0.45 | Minimal | Questions, heavy hedging |
| 0.45-0.60 | Light | Soft statements, light hedging |
| 0.60-0.75 | Moderate | Direct statements |
| 0.75-0.85 | Firm | Directives, named drift |
| ≥ 0.85 | Strong | Clear directives |

### Hybrid Intervention Styling

Interventions combine two systems:

1. **Semantic Interpreter**: Provides linguistic specifications (sentence form, hedging level)
2. **Steward Styles**: Provides therapeutic persona (tone, directness, urgency)

The result is a response that:
- Uses the appropriate linguistic structure for the drift severity
- Maintains the Steward's empathic, human-centered tone
- Never uses robotic stock phrases

### Primacy State Calculation

Primacy State (PS) is the harmonic mean of User Fidelity and AI Fidelity:

```
PS = rho_PA × (2 × F_user × F_ai) / (F_user + F_ai)
```

Where:
- F_user = How well user's input aligns with their stated purpose
- F_ai = How well AI's response aligns with user's purpose
- rho_PA = Correlation between User PA and AI PA embeddings

### Embedding Providers

TELOS uses multiple embedding models for different purposes:

| Model | Dimensions | Purpose |
|-------|-----------|---------|
| MiniLM (SentenceTransformer) | 384 | User fidelity calculation |
| MPNet | 768 | AI fidelity (local, fast) |
| Mistral embed | 1024 | Custom PA mode |

### What Triggers Intervention

An intervention triggers when:
```
should_intervene = baseline_hard_block OR fidelity < 0.70
```

This means:
- ANY message with raw similarity < 0.20 gets hard blocked
- ANY message with fidelity < 0.70 (GREEN threshold) gets intervention

GREEN zone (≥70%) = no intervention
Below GREEN = Steward steps in

## Understanding the Metrics Display

### User Fidelity (F_user)
- Measures: How well YOUR message aligns with YOUR stated purpose
- Not about the AI - it's about whether YOU are staying on topic
- High score: You're asking relevant questions
- Low score: You've drifted from your stated goal

### AI Fidelity (F_ai)
- Measures: How well the AI's response serves YOUR purpose
- Computed AFTER the response is generated
- High score: AI is helping you achieve your goal
- Low score: AI response strayed from your purpose

### Primacy State (PS)
- The overall governance health score
- Harmonic mean means BOTH must be high for PS to be high
- If either F_user or F_ai is low, PS will be low
- This is the "bottom line" metric

## Why Percentages Matter

All metrics are shown as percentages (0-100%) not decimals:
- 70% is the GREEN threshold
- 60% is the YELLOW threshold
- 50% is the ORANGE threshold
- Below 50% is RED

When Steward explains metrics, always use percentages because they're more intuitive for humans.
