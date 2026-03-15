# TELOS Demo Mode

This folder contains configurations for **Demo Mode** - a special mode where the TELOS Observatory demonstrates the TELOS framework itself by keeping conversations focused on explaining TELOS governance and purpose alignment.

## Purpose

Demo Mode uses a **PRE-ESTABLISHED, HARDCODED Primacy Attractor** specifically designed to:
- Keep conversations focused on TELOS framework topics
- Demonstrate how TELOS governance works in practice
- Show drift detection and intervention by redirecting off-topic questions back to TELOS
- Provide a guided walkthrough of purpose alignment concepts

## Critical Demo Mode Characteristics

🔒 **PRE-ESTABLISHED PA**
- The Primacy Attractor is FULLY CALIBRATED from the start
- NO calibration phase - starts in established mode immediately
- Already converged and ready to govern

🚫 **NO USER CONFIGURATION**
- Users CANNOT modify the PA in demo mode
- Purpose/scope/boundaries are FIXED
- This is intentional - demo mode shows how a locked PA governs

⚡ **ISOLATED TO DEMO MODE ONLY**
- These restrictions apply ONLY in demo mode
- Open mode and other codebases are unaffected
- Demo mode code is completely isolated in this folder

## How It Works

### Hardcoded Primacy Attractor

The attractor in `telos_framework_demo.py` is configured with:

**Purpose:**
- Explain how TELOS governance works
- Demonstrate purpose alignment principles
- Show fidelity measurement and intervention strategies

**Scope:**
- TELOS architecture and components
- Primacy attractor mathematics
- Intervention strategies and thresholds
- Purpose alignment examples
- Lyapunov functions and basin geometry
- Semantic embeddings and drift detection
- DMAIC continuous improvement cycle

**Boundaries:**
- Stay focused on TELOS governance topics
- Redirect off-topic questions back to TELOS
- Demonstrate drift detection when appropriate

### System Prompt

The system prompt explicitly instructs the AI to:
- Explain the TELOS Purpose Alignment Framework
- Clarify that "TELOS" refers to the framework, NOT the blockchain
- Stay focused on purpose alignment topics
- Gently redirect off-topic questions

## When to Use Demo Mode

Demo Mode is ideal for:
- **Walkthroughs**: Showing new users how TELOS works
- **Demonstrations**: Presenting TELOS at conferences or to stakeholders
- **Education**: Teaching purpose alignment principles
- **Testing**: Verifying that TELOS drift detection works correctly

## When NOT to Use Demo Mode

Do NOT use Demo Mode for:
- **Real user applications**: Users should have their own purpose extracted
- **Open conversations**: Let TELOS learn the user's actual goals
- **Production deployments**: Each application needs its own attractor

## Enabling Demo Mode

To enable Demo Mode, set the session state flag:

```python
st.session_state.telos_demo_mode = True
```

This can be added as a toggle in Settings or activated automatically for demo sessions.

## Default Behavior (Open Mode)

By default, TELOS Observatory runs in **Open Mode** with:
- **NO hardcoded attractor** (attractor = None)
- **Neutral system prompt** (generic helpful assistant)
- **Dynamic purpose extraction** from user's conversation
- **Statistical convergence** to learn user's actual goals

This is the correct mode for real applications where TELOS should adapt to the user's needs, not force them into a predefined topic.

## Multi-Component Attractors

As observed in Counterfactual analysis, Primacy Attractors can have:
- **Multiple semantic components** weighing simultaneously
- **Nuanced, complex structures** with several parts
- **Statistical convergence** that refines these components over time

The demo mode attractor is relatively simple (single-purpose focused on TELOS explanation), but real user attractors can be much more complex and multi-faceted.
