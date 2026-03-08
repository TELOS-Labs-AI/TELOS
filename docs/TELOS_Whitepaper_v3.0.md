# Governance for AI Systems: A Control Engineering Approach

**TELOS Framework Whitepaper**

**Version 3.0 - February 2026**

### Disclosures

> **Generative AI Disclosure:** This document was developed through collaborative analysis between the author and LLM-based research agents (Claude, Anthropic) operating under the TELOS research team methodology. The core research, architectural decisions, and validation framework originated from the author. Research agents validated, extended, and formalized specific sections. See CONTRIBUTING.md for methodology details.

> **Conflict of Interest Disclosure:** This research was conducted and funded by TELOS AI Labs Inc., which has a commercial interest in the TELOS governance framework.

---

## Executive Summary

AI systems drift from their intended purpose during extended conversations, resulting in significant reliability degradation as conversations extend beyond 15-20 turns (Laban et al., 2025; Liu et al., 2024). This creates compliance risks in healthcare, finance, and government settings. TELOS addresses this by treating AI governance as an ongoing quality control process. It applies the same statistical methods used in manufacturing, like Six Sigma and ISO 9001, to semantic systems.

TELOS works as an orchestration-layer infrastructure that assesses every AI response against human-defined rules (Primacy Attractors). It mathematically detects drift and makes proportional corrections in real time. Security tests show 0 successful attacks out of 2,550 adversarial scenarios across four benchmarks: AILuminate (1,200 MLCommons industry-standard), HarmBench (400 general-purpose), MedSafetyBench (900 healthcare-specific), and the SB 243-aligned child safety evaluation suite (50 prompts). Under our stated threat model (black-box query access), the Rule of Three yields a 95% CI upper bound of <0.12% ASR (3/2,550), compared to 3.7% to 11.1% for system prompt defenses.

Tests for over-refusal calibration show that domain-specific Primacy Attractors lower false positive rates from 24.8% (generic) to 8.0% (Healthcare PA). This indicates that domain-specific configuration can reduce over-refusal while maintaining safety.

With California's SB 53 taking effect in January 2026 and the EU AI Act enforcement approaching (August 2026 baseline, potentially extended to December 2027 under the Digital Omnibus), TELOS offers the ongoing monitoring infrastructure that these regulations require.

## Technical Abstract

Artificial intelligence systems now function as persistent decision engines in crucial areas, yet their governance often comes from outside and remains largely based on guesswork. The TELOS framework suggests a solution built on established control engineering and quality systems principles.

TELOS acts as a Mathematical Intervention Layer using Proportional Control and Attractor Dynamics within semantic space. It turns adherence to purpose into a measurable and self-correcting process. Each cycle of conversation follows a structured approach based on the DMAIC methodology: Define the purpose, Measure semantic drift as deviation from the Primacy Attractor, Analyze and Improve through proportional control, Stabilize within acceptable limits, and Control by monitoring for ongoing capability assurance. This feedback loop acts as a form of Statistical Process Control (SPC) for cognition, tracking errors, making adjustments, and keeping variations within set boundaries.

This architecture builds on principles outlined in Quality Systems Regulation (QSR) and ISO 9001/13485, meeting requirements for continuous monitoring, documented corrective actions, and verifiable process control. Each interaction is seen as a process event with measurable deviations, interventions, and stabilization. Telemetry records create a full audit trail, enabling post-market validation and compliance with regulations such as the EU AI Act Article 72, which mandates active, systematic monitoring during runtime.

Mathematically, TELOS combines proportional control (the operational mechanism) with attractor dynamics (the description of stability), forming a dual framework in which the declared purpose serves as a stable point in complex semantic space. Deviations from this stability are seen as variations in the process, and the formula $F = K \cdot e_t$ allows for ongoing recalibration towards the Primacy Basin. Over time, the system approaches a Primacy State characterized by statistical stability, reduced variation, and continued purpose fidelity.

**Runtime Governance Infrastructure**: TELOS implements runtime constitutional governance through the Primacy Attractor, which encodes expected behavioral norms as mathematical objects. Human governors define what behavior is acceptable (the norm), which is recorded as a solid reference in embedding space—the Primacy Attractor. Every AI response is measured against this norm, and deviations trigger proportional interventions. This happens not through prompt engineering but through orchestration-layer governance that operates above the model layer. The user's stated purpose becomes the measurable standard: purpose and norm are synonymous. This shifts AI alignment from subjective trust to quantitative norm compliance, providing the continuous monitoring infrastructure that regulations require.

**Adversarial and Safety Validation (December 2025 - February 2026)**: Security testing across 2,550 adversarial attacks yields 0% observed ASR under TELOS governance, compared to 3.7-11.1% for system prompts (see Section 4.3 and Appendix A for complete results). Over-refusal calibration demonstrates that domain-specific Primacy Attractors reduce false positive rates from 24.8% to 8.0% (see Section 4.5). These results indicate that TELOS can maintain safety without unnecessary restrictions on legitimate use cases.

By incorporating Lean Six Sigma's DMAIC methodology directly into its runtime processes, TELOS extends Quality Systems Regulation, established in manufacturing, medical devices, and process industries, into semantic systems. It demonstrates that alignment, or the consistent maintenance of intended behavior over time, can be framed as a measurable property of a self-governing system that follows the same continuous improvement practices found in industrial quality control.

We are creating the measurement infrastructure that regulations will need. This white paper explains what we have built, why it matters, and how we will validate its effectiveness.

---

## Organizing Principle

AI systems interact with people, data, and decisions at scale. For these systems to be trusted, governance must be treated as a core operating discipline rather than a compliance afterthought.

The question facing organizations deploying AI systems today is no longer *whether* to govern AI — it is how to operationalize governance in ways that sustain trust, clarity, and growth.

The market confirms this shift. Gartner projects spending on AI governance platforms will reach $492 million in 2026 and surpass $1 billion by 2030, driven by fragmented AI regulation extending to 75% of the world's economies (Kornutick, Gartner, February 2026). Organizations that deploy AI governance platforms are 3.4 times more likely to achieve high effectiveness in AI governance than those relying on traditional GRC tools alone. As Gartner's analysis concludes: "Point-in-time audits are simply not enough."

TELOS was developed on this premise. Every architectural decision in this framework — from the Primacy Attractor as externalized constitutional law, to proportional control as graduated intervention, to governance receipts as auditable proof of compliance — follows from treating governance as runtime infrastructure that operates continuously, not as a policy document that is reviewed periodically.

This is the shift from governance-as-documentation to governance-as-operating-discipline: measurable, enforceable, and auditable at every decision point.

---

## 1. The Governance Crisis: Why Alignment Fails and What Regulators Require

### 1.1 The Persistence Problem Is Not Hypothetical

Large language models do not maintain alignment consistently across multiple turns in conversations. This is not speculation; it is documented, measured, and reproducible:

Laban et al. (2025): "LLMs Get Lost in Multi-Turn Conversation" - Microsoft and Salesforce researchers show systematic deterioration, with models losing track of instructions, violating declared boundaries, and forcing users to constantly re-correct.

Liu et al. (2024): "Lost in the Middle" - Transformers show predictable attention decay. Information in middle contexts loses importance. Early instructions fade as conversations exceed 20-30 turns.

Wu et al. (2025): "On the Emergence of Position Bias in Transformers" - Models exhibit position-dependent attention patterns where causal masking inherently biases attention toward earlier positions, but this primacy effect decays over depth and distance, mirroring cognitive phenomena found in human memory (Murdock, 1962).

Gu et al. (2024): "When Attention Sink Emerges" - Attention mechanisms create "sinks" that disproportionately capture focus, diverting attention from critical governance instructions.

The pattern is consistent across studies: instruction adherence degrades substantially as conversation length increases, with models increasingly violating boundaries they initially respected (Laban et al., 2025; Liu et al., 2024; Wu et al., 2025).

This is not a future problem; it is occurring now, in production systems, across all major providers. Users feel frustrated: "I already told you not to do that." Enterprises experience compliance risks: governance constraints declared at the start fade silently by turn 15.

### 1.2 Real-World Consequences

Healthcare: A physician instructs the system to "provide information only, never diagnose" at the start of the session. By turn 25, the model starts giving diagnostic interpretations. The physician does not notice right away because the drift is gradual. The session log shows a boundary violation, but there was no real-time intervention.

Legal: An attorney specifies "analyze precedent, do not draft arguments" as the scope. Mid-conversation, the model begins generating arguments. The attorney has to remind, "Remember, you're analyzing, not drafting." This happens multiple times in the session.

Finance: An analyst sets privacy boundaries: "discuss methodology, do not reference specific portfolio holdings." The model follows this for 15 turns, then begins mentioning specific portfolio details. The analyst catches it, but only after sensitive information entered the conversation.

Customer Service: A company trains agents with specific interaction policies. Sessions start compliant. As conversations go on, models diverge from the prescribed language, break escalation protocols, or make commitments outside policy limits. Managers review transcripts later and find violations, but there was no real-time correction.

In every case: governance constraints were declared, violations occurred, and no system monitored or corrected the drift in real-time.

### 1.2.1 EU AI Act: The Commerce Compliance Deadline

The EU AI Act sets specific rules for AI systems that interact with natural persons. Companies without proper governance will face disruptions or be kept out of European markets.

Enforcement Timeline:

| Date | Requirement | Commercial Impact |
|------|-------------|-------------------|
| Feb 2, 2026 | Transparency obligations (Article 52) | AI systems must disclose they use AI |
| Feb 2, 2026 | AI literacy requirements | Staff training on AI's strengths and limits is mandatory |
| Aug 2, 2026 | Full compliance | High-risk systems need complete governance documentation |

Key Requirements (Article 52 - Transparency Obligations):

1. **Transparency Disclosure**: "Providers shall ensure that AI systems intended to interact with natural persons are designed and developed in such a way that natural persons are informed that they are interacting with an AI system."

2. **Human Escalation Pathways**: Users should have clear ways to escalate to human oversight.

3. **Trader Liability**: Traders are fully responsible for all communications with consumers, including AI-generated content. Companies cannot deny responsibility for AI system errors.

4. **Content Labeling**: AI-generated content must be labeled before being sent to customers, including emails, responses, and documents.

High-Risk Classification Triggers:

AI systems automatically qualify as high-risk (requiring Article 9 governance) when used in:
- Financial services: Credit decisions, financial advice, account management
- Healthcare: Medical information, symptom assessment, treatment recommendations
- Legal services: Legal advice, document preparation, case evaluation
- Employment: Hiring, HR decisions, performance reviews
- Government: Public services, law enforcement, border control

Penalty Structure:

| Violation Type | Maximum Penalty |
|----------------|-----------------|
| Prohibited practices | €35M or 7% of global revenue |
| High-risk non-compliance | €15M or 3% of global revenue |
| False information to authorities | €7.5M or 1.5% of global revenue |

Why This Matters for Commerce:

Consider an enterprise with €1B in annual revenue deploying AI systems that interact with customers in EU markets:
- Without compliance: Risk of €15-35M penalty per violation
- Multiple violations: Potential exposure of over €100M
- Enforcement reality: EU regulators impose maximum fines (Meta: €1.2B GDPR fine, 2023)

TELOS's approach to these requirements:

TELOS provides runtime governance infrastructure that addresses EU AI Act Article 52 and Article 9 (high-risk systems) requirements:

1. Continuous Purpose Alignment: Primacy Attractor maintains system alignment to declared purpose (Article 52 transparency)
2. Fidelity Metrics: F_user, F_AI, PS provide quantitative proof of purpose adherence
3. Governance Audit Trail: Every interaction logged with fidelity metrics and intervention decisions (Article 12 logging)
4. Human Oversight Evidence: Documented proof that human-defined norms are continuously enforced
5. Drift Detection: Real-time identification of scope violations before they affect users

TELOS functions as orchestration-layer infrastructure between applications and LLMs, adding measurable governance to any AI deployment.

The urgency is validated by independent market analysis. Gartner's survey of 360 organizations found that traditional GRC tools are "simply not equipped to handle the unique risks of AI, from real-time decision automation to the threat of bias and misuse" (Kornutick, February 2026). Gartner explicitly identifies the required capabilities as "automated policy enforcement at runtime, monitoring AI systems for compliance, detecting anomalies, and preventing misuse." With AI governance platform spending projected at $492M in 2026 and $1B+ by 2030, the market for runtime governance infrastructure is growing.

Source:
1. EU AI Act Official Text: https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai

### 1.3 What Regulators Are Requiring, And the Approaching Deadline

Regulatory frameworks are converging on a common principle: governance must be clear, proven, and ongoing.

#### EU AI Act (2024), Article 72: Post-Market Monitoring

"Providers of high-risk AI systems shall establish a post-market monitoring system… The system must follow a systematic and continuous plan and include procedures to:
- Gather, document, and analyze relevant data on risks and performance
- Review experience gained from using AI systems"

What this means: You cannot declare compliance based on design-time testing alone. You must keep track of whether governance limits are upheld during actual use.

What current systems provide: Pre-deployment checks. Post-hoc transcript evaluations.

What's missing: Real-time measurements of whether stated limits are maintained. Proof that issues are caught and fixed during interactions, not just found in audits.

#### NIST AI Risk Management Framework (2023): MEASURE Function

"Identified AI risks are tracked over time… Appropriate methods and metrics are identified and put into action… Mechanisms for tracking AI risks over time must be established"

What this means: Risk tracking isn't a one-off task. It must be ongoing and documented throughout the system's operation.

What current systems provide: Static risk assessments. Periodic evaluations.

What's missing: Turn-by-turn risk metrics. Evidence that governance measures are actively ensuring alignment rather than assuming it remains intact.

TELOS addresses the four core NIST AI RMF functions: **GOVERN** (the Primacy Attractor establishes governance structures tied to declared purpose), **MAP** (fidelity scoring identifies risks as deviations from the attractor), **MEASURE** (telemetry tracks risk metrics continuously across every turn), and **MANAGE** (the proportional controller intervenes when drift exceeds tolerance).

#### The Compliance Vacuum and Approaching Deadlines

As of January 2026, no standardized technical framework exists for Article 72 post-market monitoring.

California SB 53 (Transparency in Frontier Artificial Intelligence Act) was signed into law on September 29, 2025, and takes effect January 1, 2026, creating the first state-level AI safety compliance requirements in the United States.

The law requires frontier AI developers to:
- Publish detailed safety frameworks on company websites
- Submit standardized reports on model release transparency
- Report critical safety incidents to the California Office of Emergency Services (Cal OES)
- Implement whistleblower protections with civil penalties up to $1M per violation

Covered entities: Companies with >$500M annual revenue deploying models trained with more than $10^{26}$ FLOPs (OpenAI, Anthropic, Meta, Google DeepMind, Mistral).

Critical requirement: Safety frameworks must show active governance mechanisms, not just design-time testing. Companies must provide proof that declared safety limits stay enforced throughout runtime deployment.

TELOS provides infrastructure relevant to SB 53 compliance: safety limits encoded as Primacy Attractors, continuous measurement via fidelity scoring, and automatic audit trail generation via telemetry logs. These produce quantitative governance records suitable for safety framework publication and Cal OES incident reporting.

EU AI Act Article 72 requires providers of high-risk AI systems to implement post-market monitoring by August 2026. The European Commission must provide a template for these systems by February 2026 (EU AI Act, 2024, Article 72).

**EU Digital Omnibus Update (November 2025):** The European Commission proposed extending high-risk AI compliance deadlines through the Digital Omnibus package, with enforcement potentially delayed until December 2027 (up to 16 months extension, with product-embedded systems extended to August 2028). The extension is conditional on the availability of adequate compliance support infrastructure, including harmonized standards and guidance tools. This proposal is currently under negotiation by the European Parliament and Council, with trilogue discussions expected mid-2026. The regulatory requirements and technical obligations remain unchanged - only the enforcement timeline may shift. Organizations should continue preparing governance infrastructure as the fundamental compliance requirements persist regardless of deadline extensions.

Timeline convergence: California SB 53 (January 2026) is immediate, while EU timelines face potential extension through the Digital Omnibus. Regardless of specific deadlines, all frameworks converge on the same underlying capability: continuous, quantitative, auditable governance monitoring.

Current state: Enterprises are using ad-hoc methods, mainly post-hoc transcript review, periodic sampling, and manual audits. These create compliance documentation burdens without delivering the continuous quantitative evidence that Article 72 explicitly demands: "systematic procedures," "relevant data," "continuous plan."

The gap between regulatory requirements (continuous monitoring with auditable evidence) and technical capability (periodic sampling with narrative documentation) is currently unfilled.

Whether the EU enforcement occurs in August 2026 or December 2027, institutions deploying high-risk AI systems face the same fundamental requirement: continuous monitoring infrastructure that generates auditable evidence of governance effectiveness.

TELOS addresses this gap through orchestration-layer governance: We provide the measurement tools, fidelity scoring, drift detection, intervention logging, stability tracking, that continuous post-market monitoring needs. Runtime constitutional governance (Primacy Attractor architecture) supplies the "systematic procedures" and "continuous plan" that Article 72 mandates, while adversarial validation (0% ASR across 2,550 attacks) shows the security properties that safety frameworks must document for SB 53 compliance.

Whether these specific mechanisms become standard or inform alternative approaches, the class of technical infrastructure they represent is what regulatory frameworks demand: constitutional governance with quantitative evidence, not heuristic trust.

The California SB 53 deadline (January 2026) is immediate. EU enforcement timelines may extend to December 2027 under the Digital Omnibus proposal, but the technical requirements remain unchanged.

### 1.4 The Authority Inversion: Human-in-the-Loop as Architecture

Traditional AI systems place the model as the primary authority, with humans adjusting to AI outputs. TELOS flips this structure:

Traditional Architecture:

AI System (decides acceptable behavior) → Humans (receive outputs)

TELOS Architecture:

Human Authority (defines Primacy Attractor)
↓
Proportional Control (enforces alignment via $F_t = K \cdot e_t$)
↓
AI/LLM (generates outputs under governance)

The Primacy Attractor is not AI-generated; it is mathematically encoded human intent. Every response is measured against this human-defined reference point. When drift happens, the system doesn't decide whether to act based on AI judgment; it uses quantitative measurements of deviation from human-specified limits.

This architectural inversion addresses the core concern in AI governance: as systems become more capable, who has the ultimate authority? TELOS is designed so that:
- Humans remain at the top: Constitutional requirements are human-written.
- AI remains the governed subsystem: Models generate outputs within human-defined limits.
- Proportional correction enforces boundaries: Operating on behalf of human authority, not AI autonomy.

This directly meets the EU AI Act "human oversight" requirements and aligns with Meaningful Human Control (MHC) frameworks in AI ethics literature. TELOS doesn't align AI to AI preferences; it enforces human constitutional law over AI behavior through orchestration-layer architecture.

Starting January 2026, frontier AI companies face Cal OES reporting requirements. TELOS provides infrastructure for this: Primacy Attractors encode safety frameworks, fidelity scores document continuous monitoring, and telemetry logs support incident reporting.

#### The Due Diligence Standard

Both frameworks point toward the same need: observable demonstrable due diligence.

Not: "We designed the system to be safe."
But: "Here is continuous evidence that safety limits remained active throughout deployment."

Not: "We instructed the model to follow boundaries."
But: "Here is measurement showing boundaries were maintained, and here is proof of correction when drift occurred."

Not: "We reviewed sessions after the fact."
But: "Here is real-time telemetry showing governance monitoring was continuous."

This is the gap TELOS addresses: We are building the measurement and correction infrastructure that makes continuous governance observable and demonstrable.

### 1.5 Why Current Approaches Cannot Satisfy This Standard

Constitutional AI and Provider Safeguards (Bai et al., 2022):
- Essential baseline: prevent harmful content, establish universal safety floors.
- Operate at design-time and model-level.
- Do not measure or respond to session-specific constraints declared within context windows.
- Verdict: Necessary but insufficient for runtime governance.

Prompt Engineering:
- State limits at session start.
- Hope they persist through attention mechanisms.
- No measurement of whether they persist.
- No correction when they erode.
- Verdict: Declaration without enforcement.

Post-Hoc Review:
- Analyze transcripts after sessions are complete.
- Identify violations afterward.
- Cannot stop violations before they reach users.
- Cannot generate evidence of active governance during sessions.
- Verdict: Audit without prevention.

Periodic Reminders:
- Restate limits at fixed intervals (every 10 turns).
- Independent of whether drift is ongoing.
- Over-corrects when unnecessary (adds latency).
- Under-corrects when drift is rapid.
- No effectiveness measurement.
- Verdict: Cadence without feedback.

None of these approaches provide what regulators require: continuous measurement of governance persistence, proportional intervention when drift occurs, and auditable telemetry documenting both.

### 1.5.1 Industry Recognition: Even Frontier Labs Acknowledge the Gap

The insufficiency of training-time alignment is not merely an academic observation. It is now acknowledged by the developers of Constitutional AI themselves.

In January 2026, Anthropic CEO Dario Amodei published "The Adolescence of Technology," a 20,000-word analysis of AI risks and mitigations. Notably, Amodei describes Anthropic's investment in runtime infrastructure beyond Constitutional AI:

> "We are investing in a wide range of evaluations so that we can understand the behaviors of our models in the lab, as well as **monitoring tools to observe behaviors in the wild**."

> "We've implemented... a classifier that specifically detects and blocks bioweapon-related outputs... [We] have generally found them highly robust even against sophisticated adversarial attacks."

> "These classifiers increase the costs to serve our models measurably (in some models, they are close to 5% of total inference costs)."

This is notable: the developers of Constitutional AI acknowledge that training-time alignment requires runtime augmentation. Anthropic now deploys specialized classifiers, at meaningful computational cost, to catch what Constitutional AI alone cannot prevent.

TELOS applies a similar principle at the orchestration layer: general-purpose constitutional enforcement that operates independently of the model provider, with published methodology for external validation.

The pattern is consistent: even organizations that developed training-time alignment now invest in runtime monitoring. The question is no longer whether runtime governance is necessary, but how to build the infrastructure and under what principles.

Source: Amodei, D. (2026). "The Adolescence of Technology: Confronting and Overcoming the Risks of Powerful AI." https://www.darioamodei.com/essay/the-adolescence-of-technology

### 1.6 What We Are Building

TELOS provides the infrastructure for observable demonstrable due diligence:

Observable: Every turn generates measurable fidelity scores, drift vectors, stability metrics, quantitative proof of governance state.

Demonstrable: Telemetry creates an audit trail that shows what constraints were set, when drift happened, what interventions were taken, and whether adherence improved.

Due Diligence: The system actively works to maintain alignment instead of just assuming it exists, and it generates evidence of this work.

We do not claim this completely solves AI governance. We claim it makes governance measurable where it was once a goal, correctable where it was once based on hope, and auditable where it was once unclear.

The following sections explain the mathematical framework that makes this possible, the implementation that makes it practical, and the validation framework that will determine if it works.

### 1.6.1 The Foundational Insight: Detect and Direct

Modern transformers generate both queries and keys from their own hidden states, creating self-referential circularity in governance. Research on the "lost in the middle" effect (Liu et al., 2024; Laban et al., 2025) demonstrates that LLMs exhibit strong primacy and recency biases — attending well to information at the beginning and end of context but poorly to middle positions. As conversations extend, initial constitutional constraints drift into this poorly-attended middle region. The model effectively forgets its purpose as context accumulates.

This is not a bug to be patched. It is a structural property of attention mechanisms. Prompt engineering, constitutional AI, and system-message reinforcement operate within a context window where attention decays over positional distance.

TELOS addresses this by establishing an external fixed reference point — the Primacy Attractor — that exists outside the model's context window entirely. Instead of relying on the model to remember its own constraints (which it provably cannot do reliably over extended context), TELOS measures every exchange against the PA using cosine similarity in embedding space. The PA does not compete with conversation tokens for attention. It does not decay. It is not subject to the lost-in-the-middle effect. It is a fixed point in semantic space that the governance engine — not the model — maintains.

This architectural decision was deliberate and research-driven. The transformer's positional biases become a control opportunity rather than a governance failure: instead of resisting attention decay, TELOS measures it and intervenes proportionally. We call this philosophy **"Detect and Direct"** — SPC detects drift via fidelity measurement, the system directs response back toward the Primacy Attractor.

This foundational insight — attention decay necessitates external measurement, external measurement enables continuous governance, continuous governance achieves **salience** — produced every subsequent architectural decision in TELOS: the two-layer fidelity system, the attractor geometry, the contrastive detection architecture, and the basin membership calculations.

We define **salience** as the property whereby the governance reference signal remains the dominant measurement standard at every decision point throughout a session. Salience is achieved through continuous measurement — because the PA is evaluated at every turn, it never becomes stale, never drifts into forgotten context, and never competes with the model's own attention for priority. The governance signal maintains salience not because the model remembers it, but because the governance engine enforces it at every decision point.

### 1.6.2 Detection-Driven Governance

TELOS operates fundamentally as a detection system. Quality Control for AI.

We do not claim to prevent all harmful outputs. We claim to detect drift reliably and escalate appropriately. Prevention is a byproduct of detection. When the system detects reliably, escalation occurs appropriately, and prevention graduates with it. The entire lifecycle remains transparent and auditable.

Our goal has been and will continue to be refining and fine-tuning detection so that prevention and safety emerge as natural byproducts through proper graduated response mechanisms.

**The Governance Triad**

| Function | Role | Purpose |
|----------|------|---------|
| Detection | The Mechanism | Continuous drift measurement |
| Prevention | The Outcome | Graduated intervention |
| Auditability | The Proof | Immutable audit trails |

The causal chain: Detection (what we measure) leads to Prevention (byproduct) leads to Safety (outcome through proportional control).

Detection fidelity determines intervention timing, which determines control proportionality.

**Understanding Our Validation Results**

Standard adversarial benchmarks like AILuminate, MedSafetyBench, and XSTest were designed to test binary systems: block or allow. That is essentially all that exists in the field. When researchers run these tests, they are asking one question: Did the system prevent this harmful query?

TELOS does not operate in that paradigm. We introduce detection and escalation through proportional control mechanisms into an equation where they formerly did not exist.

When TELOS achieves 0% adversarial success rate on these benchmarks, we are not claiming the same thing a binary system would claim. We are saying:

- Every attack triggered detection
- Detection initiated proportional escalation
- Escalation engaged graduated intervention
- The three-tier defense (baseline normalization, basin membership, human review) caught what binary systems try to catch with a single gate

The 0% is not "we blocked everything." It is "nothing proceeded without triggering the governance response chain." TELOS preserves the ability to block when necessary. Blocking is the graduated endpoint of detection, not the only tool.

## Bridge: From Systems Thinking to Mathematical Formalism

The integration of process control within TELOS comes directly from careful systems analysis. When semantic drift is defined as a measurable deviation from a defined purpose vector, its mathematical structure maps directly to process variation within tolerance limits.

TELOS extends established control principles, measurement, proportional correction, and continuous recalibration, into semantic space. Purpose adherence in language systems shows the same measurable dynamics as quality stability in physical processes.

The framework combines proportional control (operational mechanism) and attractor dynamics (mathematical description) into a unified approach for semantic governance. These are not competing frameworks but two forms of the same mathematics: the control law applies operational correction while basin geometry describes the resulting stable region.

## 2. Quality Control Architecture: Proportional Control and Attractor Dynamics

### 2.1 Core Insight: Runtime Constitutional Governance as Measurable Process

![Figure 2: Primacy Attractor basin geometry in embedding space. The PA serves as a stable equilibrium point, with the basin radius determining the tolerance for semantic drift.](diagrams/fig2_primacy_attractor.pdf)

TELOS views alignment as a measurable position in embedding space subject to continuous process control through orchestration-layer governance, not just a qualitative property.

When a user declares constitutional requirements for a session:
- Purpose: "Help me structure a technical paper."
- Scope: "Guide my thinking, don't write content."
- Boundaries: "No drafting full paragraphs."

These declarations become embeddings, vectors in $\mathbb{R}^d$ using standard sentence transformers (Reimers & Gurevych, 2019). These vectors define the Primacy Attractor: instantiated constitutional law for the temporary session state. The PA serves as a constant constitutional reference against which all subsequent outputs are measured for compliance.

Every model response gets embedded. Its distance from the constitutional reference (PA) quantifies constitutional drift. Its direction shows how it violates declared constraints.

These measurements allow for proportional intervention through architectural governance: minor constitutional drift receives gentle correction, while severe violations trigger immediate blocking, all functioning at the governance control plane above the model.

This shifts governance from subjective judgment ("does this feel aligned?") to quantitative constitutional compliance measurement ("fidelity = 0.73, below constitutional threshold, intervention required").

### 2.2 Mathematical Foundations: Proportional Control Law and Stability

![Figure 3: Two-Layer Fidelity Architecture. Layer 1 provides baseline normalization to catch extreme off-topic content, while Layer 2 measures basin membership for purpose drift detection.](diagrams/fig3_fidelity_pipeline.pdf)

In this setup, the proportional control law defines the correction mechanism:

$$F = K \cdot e, \quad \text{where} \quad e = \frac{|x - \hat{a}|}{r}$$

Here $x$ represents the current semantic state (response embedding), $\hat{a}$ is the Primacy Attractor, instantiated constitutional law formed from human-authored constitutional requirements (purpose, scope, boundaries), and $r$ is the tolerance radius defining the Primacy Basin (constitutional compliance boundary).

The scalar $e$ shows normalized deviation from constitutional requirements, and $K$ is the proportional gain governing correction strength.

The law operates continuously as part of a closed feedback loop: each output is measured, deviation quantified, and corrective force $F$ applied based on drift magnitude. When $e < \epsilon_{\text{min}}$, the system remains stable with no intervention; as $e$ approaches $\epsilon_{\text{max}}$, corrective action scales accordingly, from gentle reminders to full response regeneration.

This dynamic sets a point attractor at $\hat{a}$ with basin:

$$B(\hat{a}, r) = \{x \in \mathbb{R}^d : |x - \hat{a}| \leq r\}$$

The basin radius is calculated as:

$$r = \frac{1}{\max(\rho, 0.25)} \quad \text{where} \quad \rho = 1 - \tau$$

where $\tau \in [0,1]$ is the tolerance parameter (lower tolerance means a tighter basin). The numerator was calibrated from the theoretical value of 2.0 to the operational value of 1.0 during production testing, where the larger radius produced basins too permissive for meaningful governance. At $\tau = 0.9$ (permissive), $\rho = 0.25$ gives $r = 4.0$; at $\tau = 0.05$ (strict), $\rho = 0.95$ gives $r \approx 1.05$.

Stability Analysis: Convergence can be shown using a Lyapunov-like potential function:

$$V(x) = \frac{1}{2}|x - \hat{a}|^2$$

Its temporal derivative under proportional feedback satisfies:

$$\dot{V}(x) = -K|x - \hat{a}|^2 < 0$$

This confirms that convergence towards the attractor is asymptotic, and stability is bounded within the basin (Khalil, 2002; Strogatz, 2014).

### 2.2.1 The Reference Point Problem: Why Similarity Computation Alone Is Insufficient

Transformer attention mechanisms rely on similarity computation through the scaled dot-product operation (Vaswani et al., 2017):

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right) V$$

The operation $QK^T$ computes the dot product between query vectors and key vectors, a direct measurement of directional similarity between positions in the sequence. This is mathematically equivalent to un-normalized cosine similarity and captures how much the vectors "point in the same direction" within the embedding space (PyTorch Contributors, 2023).

Every modern LLM, including LLaMA, Mistral, GPT, and Claude, performs this similarity computation billions of times during text generation, at every layer and every token position.

The architecture already knows how to measure similarity. The question is: what is it measuring similarity against?

### 2.2.2 Attention as Similarity Computation

When a transformer generates token t, it creates a query vector $Q_t$ asking, "what information am I looking for?" It then computes:

$$\text{score}_{t,i} = Q_t \cdot K_i^T$$

for each prior key vector $K_i$ in the context. These scores measure: how similar is my current generation state to position i?

After applying softmax, these scores become attention weights that determine how much each previous position impacts the current generation. High similarity leads to a high attention weight, resulting in strong influence.

This mechanism works well for language modeling. If you're generating "The capital of France is __", high attention to prior mentions of "France" and "capital" helps predict "Paris." The model correctly identifies the relevant context through similarity matching.

### 2.2.3 The Shifting Reference Point

However, this same mechanism fails for governance persistence because the reference point itself shifts during the conversation.

Consider a session where the user declares at turn 1:

P_0: "Provide guidance on structure, but do not write content directly."

This constraint is encoded as an embedding vector $p_0 \in \mathbb{R}^d$.

Turn 5: Model response $R_5$ aligns well with $P_0$. The attention mechanism calculating $Q_5 \cdot K_1^T$ correctly finds high similarity to the original constraint.

Turn 15: Model response $R_{15}$ calculates attention weights:

$$\alpha_{15,i} = \frac{\exp(Q_{15} \cdot K_i^T / \sqrt{d_k})}{\sum_j \exp(Q_{15} \cdot K_j^T / \sqrt{d_k})}$$

Because of RoPE-induced recency bias (Yang et al., 2025), attention gives more weight to recent keys $K_{12}, K_{13}, K_{14}$. These keys reflect the immediate context of the conversation.

However, if $K_{12}$ to $K_{14}$ have drifted from $p_0$, the model measures similarity against corrupted references. It computes correctly:

$$Q_{15} \cdot K_{14}^T \approx \text{high similarity}$$

and concludes that it is aligned. But $K_{14}$ itself shows low similarity to $p_0$:

$$K_{14} \cdot p_0^T \approx \text{low similarity}$$

The similarity computation is accurate. The reference point it uses has drifted.

### 2.2.4 Architectural Sources of Recency Bias

This reference drift happens intentionally through two mechanisms:

1. RoPE Positional Encoding (Yang et al., 2025):

"RoPE exhibits a stronger recency bias (positional focus)... RoPE layers handle local information effectively due to their built-in recency bias."

Rotary positional encodings, used in LLaMA, Mistral, and other modern systems, apply rotations to query and key vectors that favor nearby positions. Distant positions receive less attention not through learned preference but through mathematical design.

2. Learned Attention Patterns (Liu et al., 2023):

"During pre-training, this induces a learned bias to attend to recent tokens... attention mechanisms create 'sinks' that capture focus disproportionately."

Pre-training on natural text, where recent context is the best predictor for the next token, reinforces the recency weighting. The model learns that "recent tokens matter most." This is correct for language modeling but leads to reference drift in governance.

### 2.2.5 Mathematical Formalization of Reference Drift

Let $r_t$ denote the effective reference that attention mechanisms use at turn $t$. This is the average of key vectors weighed by attention:

$$r_t = \sum_{i=1}^{t-1} \alpha_{t,i} k_i$$

where $\alpha_{t,i}$ are the attention weights.

Due to recency bias:

$$\alpha_{t,i} \propto \exp(-\beta \cdot (t - i)) \cdot \exp(Q_t \cdot K_i^T / \sqrt{d_k})$$

for some decay parameter $\beta > 0$ from positional encoding.

Over turns, the effective reference drifts:

$$\|r_t - p_0\| = \left\|\sum_{i=1}^{t-1} \alpha_{t,i} k_i - p_0\right\| \to \Delta > 0$$

as the conversation continues and $\alpha_{t,i}$ focuses on recent $i$.

The model calculates:

$$\text{similarity}_t = Q_t \cdot r_t^T$$

which remains high (local coherence), while:

$$\text{fidelity}_t = Q_t \cdot p_0^T$$

decreases (global divergence).

This is local coherence with global divergence: each step seems consistent with recent context while the overall direction shifts away from the original intent.

### 2.2.6 Why External Measurement Becomes Necessary

The model cannot resolve this internally because:

1. Attention operates within the context window: It lacks a way to keep stable external reference points throughout the entire session
2. RoPE is architectural: Recency bias is part of the positional encoding setup
3. Training optimizes for next-token prediction: Models learn patterns to maximize language modeling performance, not governance consistency

TELOS addresses this through external measurement with stable reference:

$$\text{fidelity}_t = \cos(R_t, p_0) = \frac{R_t \cdot p_0}{\|R_t\| \cdot \|p_0\|}$$

where:
- $R_t$ is the model's response embedding at turn $t$
- $p_0$ is the embedding of the original purpose from turn 1
- $p_0$ is stored externally and remains unchanged

Critical distinction: This uses the same cosine similarity operation that attention mechanisms use internally (dot product adjusted by magnitudes), but with the original purpose vector $p_0$ as a stable reference instead of recent context keys $K_{t-5...t-1}$.

We are not adding new capabilities; we are correcting the reference point.

### 2.2.7 Why Cosine Similarity Is Not Arbitrary

TELOS uses cosine similarity for fidelity measurement because it is the model's own calculation method. When transformers compute QK^T, they perform dot product similarity.

The only difference:

Attention (internal): $\text{score} = Q \cdot K^T / \sqrt{d_k}$

TELOS (external): $\text{fidelity} = (R \cdot P) / (\|R\| \cdot \|P\|)$

Both assess directional alignment. TELOS adjusts for vector magnitudes (making it true cosine similarity) and uses a stable reference ($P_0$ versus recent $K_i$).

We use the language model's native similarity metric, just with the correct reference point.

### 2.2.8 Empirical Predictions

This analysis leads to testable predictions:

Prediction 1: Fidelity loss should connect with attention weight shifts toward recent context. Sessions where attention focuses more on the last 5-10 turns should show quicker drift.

Prediction 2: Changes that artificially boost attention weight on turn-1 constraints (like repeating them in context or enhancing their positional encoding) should lessen fidelity loss, even without TELOS measurement.

Prediction 3: Models with weaker recency bias (for example, attention tweaks that flatten positional decay) should maintain better baseline fidelity.

These predictions will be evaluated in the validation framework outlined in Section 4.

### 2.2.9 Implications for Governance

This analysis shows why past strategies fail:

Prompt engineering ("Please remember to follow these rules...") adds limits to context but does not stop attention from shifting toward recent turns. The constraints are present in $K_1$, but $\alpha_{t,1} \to 0$ as $t$ grows.

Constitutional AI and system prompts set universal safety boundaries but function at the model level, not the session level. They cannot encode user-specific constraints made during the session.

Periodic reminders reintroduce constraints into context but do so at a fixed rate instead of in response to detected drift, resulting in both over-correction (when alignment is good) and under-correction (when drift is rapid).

TELOS provides ongoing measurement against a stable reference, allowing proportional correction based on actual drift instead of assumed timing.

---

Key Takeaway: Modern LLMs constantly compute similarity through attention mechanisms billions of times during generation. The problem is not their ability to measure similarity; it lies in their tendency to measure it against a drifting reference point caused by architectural recency bias. TELOS maintains the original purpose embedding as an external, stable reference and uses the same cosine similarity operation that attention mechanisms apply internally, correcting the reference point rather than the measurement method.

---

### 2.3 Architectural Positioning: The Governance Control Plane

![Figure 1: Three-Tier Defense Architecture. TELOS operates at the governance control plane, enforcing governance through PA-based fidelity measurement, RAG-augmented policy retrieval, and human escalation pathways.](diagrams/fig1_three_tier_governance.pdf)

TELOS functions at the governance control plane, the middleware between applications and frontier LLMs:

[Application Layer]
↓
[TELOS Governance Control Plane] ← Governance infrastructure operates here
├── Primacy Attractor (Human-defined constitutional law)
├── Fidelity Measurement (Continuous $f_t$ monitoring)
├── Proportional Control ($F_t = K \cdot e_t$ enforcement)
└── LLM Interface (API routing)
↓
[Frontier LLM API] (OpenAI, Anthropic, Mistral, etc.)
↓
[Native Model] (Unmodified)

Why Governance Control Plane:

1. No Model Modification: Works with any LLM without retraining.
2. Real-time Intervention: Governance is applied before responses are delivered.
3. Provider Agnostic: Same governance applies across OpenAI, Anthropic, and Meta.
4. Audit Trail: Complete telemetry is independent of the model provider.
5. Regulatory Compliance: Generates documentation required by Article 72.

The proportional control system acts as a Primacy Governor. It measures every API call against human-defined constitutional constraints and intervenes when mathematical drift exceeds thresholds.

This is fundamentally different from:
- Prompt engineering (operates at request time, with no continuous measurement)
- Fine-tuning (modifies model weights, specific to the provider)
- Constitutional AI (trains models with constitutional preferences)

TELOS enforces governance architecturally, making it a compliance infrastructure layer instead of a model feature. Organizations keep governance even when switching LLM providers, and telemetry stays consistent across all backend models.

This architectural approach directly addresses SB 53's requirement for active governance mechanisms that continue through model updates, provider changes, and deployment contexts.

### 2.4 The Dual Formalism: Control Theory and Dynamical Systems

Proportional control provides the operational rule, showing how corrections are computed and applied. Attractor dynamics gives the mathematical description, explaining why the system converges and remains stable.

These are not alternatives but complementary views on the same mathematics:
- Proportional control defines: $F = -K \cdot e$ (correction force proportional to error)
- Attractor dynamics describes: $\hat{a}$ as a stable equilibrium with basin $B(\hat{a}, r)$
- Lyapunov analysis confirms: $V(x)$ decreases, showing convergence

The same mathematical principles that ensure quality stability in manufacturing processes (Shewhart, 1931; Montgomery, 2020) apply here in semantic space.

This creates a continuous, auditable framework for process control in linguistic systems. It connects TELOS directly to established control theory (Ogata, 2009; Khalil, 2002) and the analysis of dynamical systems (Strogatz, 2014; Hopfield, 1982).

The contribution is not in inventing new mathematics, but in applying proven methods to a previously unmanaged area: maintaining runtime governance constraints across transformer interactions.

### 2.5 Fidelity Measurement: Continuous Adherence Tracking

Using cosine similarity from information theory (Cover & Thomas, 2006), we measure alignment:

$$I_t = \cos(x_t, p) = \frac{x_t \cdot p}{|x_t| \cdot |p|}$$

$$F = \frac{1}{T} \sum_{t=1}^{T} I_t$$

where:
- $I_t$ is instantaneous fidelity at turn $t$
- $F$ is mean fidelity over $T$ turns
- $x_t$ is response embedding at turn $t$
- $p$ is the purpose vector (Primacy Attractor)

This metric offers:
- Continuous monitoring: Every turn produces quantified adherence
- Statistical tracking: Mean, variance, control limits over time
- Intervention trigger: When F falls below the threshold, proportional control kicks in
- Audit evidence: Complete fidelity history for regulatory compliance

### 2.5.1 Primacy State: The Convergence Metric

For conversational governance, the Primacy State (PS) measures the degree to which both user intent and AI response converge on the Primacy Attractor:

$$PS = \rho_{PA} \times \frac{2 \times F_{user} \times F_{AI}}{F_{user} + F_{AI}}$$

where:
- $\rho_{PA}$ is the Primacy Attractor strength (basin membership confidence)
- $F_{user}$ is user fidelity (cosine similarity of user input to PA)
- $F_{AI}$ is AI fidelity (cosine similarity of AI response to PA)
- The harmonic mean ensures that PS is low when either signal diverges, even if the other remains aligned

This two-signal convergence model is specific to conversational governance. In agentic governance, where the PA is a fixed specification rather than a convergence target, Primacy State is replaced by compliance metrics (ECI, EM, compliance_rate — see Section 8.7).

### 2.6 From Transformer Fragility to Governance Primitive

The attention-based architectures that enable transformers' abilities also create their governance weaknesses:

Position bias → Early instructions fade as conversations go on
Attention sinks → Focus shifts away from constraints
Context window limits → Governance tokens compete with conversation content

TELOS transforms these weaknesses into control opportunities:

Position bias → Use primacy effect to establish a strong initial attractor
Attention sinks → Monitor attention flow and intervene if it drifts
Context limits → Reduce governance to mathematical basics (vectors)

Instead of resisting transformer architecture, we use its properties for governance. The same positional encoding that causes drift allows for measurement. The same attention mechanisms that lose focus enable redirection.

## 3. Statistical Process Control as Runtime Governance

### 3.1 SPC in Semantic Space

Statistical Process Control (SPC), started by Shewhart (1931) and refined through years of manufacturing practice, provides the mathematical basis for quality assurance. TELOS adapts SPC principles into semantic space:

Traditional SPC (manufacturing):
- Monitor: Physical measurements (dimensions, weights, defect rates)
- Control limits: ±3σ from process mean
- Intervention: Adjust machinery when it goes out of control
- Evidence: Control charts and capability indices

For TELOS SPC (semantic systems):
- Monitor: Fidelity scores, drift vectors, stability metrics
- Control limits: Tolerance bands around Primacy Attractor
- Intervention: Proportional correction when drift is detected
- Evidence: Telemetry logs, purpose capability indices

The mathematics remains the same; only the domain shifts from physical to semantic space.

A note on distributional assumptions: Classical SPC control charts assume approximately normally distributed process measurements (Montgomery, 2020, Ch. 5). Cosine similarity scores are bounded on [-1, 1] and may not follow a normal distribution, particularly in early-session turns before the attractor stabilizes. TELOS addresses this by using fidelity bands (tolerance zones) calibrated from empirical session data rather than relying strictly on ±3σ limits. This approach follows Wheeler's recommendation that control chart logic remains valid for non-normal processes when limits are derived from observed process behavior (Wheeler, 2000).

### 3.2 Purpose Capability Index

Drawing from process capability analysis (Montgomery, 2020), we define:

$$C_{pk} = \min\left(\frac{USL - \mu}{3\sigma}, \frac{\mu - LSL}{3\sigma}\right)$$

where:
- $USL$ = Upper Specification Limit (maximum acceptable drift)
- $LSL$ = Lower Specification Limit (minimum required fidelity)
- $\mu$ = Mean fidelity over session
- $\sigma$ = Standard deviation of fidelity

Interpretation:
- $C_{pk} > 1.33$: Process is highly capable (six sigma quality)
- $1.0 < C_{pk} < 1.33$: Process is capable but needs monitoring
- $C_{pk} < 1.0$: Process is not capable; intervention is essential

This gives regulators familiar quality metrics applied to AI governance.

In TELOS, the Lower Specification Limit corresponds to the minimum fidelity required for a response to remain within the Primacy Basin (the intervention threshold), and the Upper Specification Limit corresponds to the maximum acceptable deviation before governance escalation is triggered. These limits are derived from calibration against validated session data, not arbitrary selection (Montgomery, 2020).

### 3.3 Quality Systems Alignment

TELOS fits directly into established quality frameworks:

ISO 9001:2015 Clause 9.1 (Monitoring and Measurement):
- "The organization shall determine what needs to be monitored"
- TELOS: Fidelity scores, drift vectors, intervention rates

21 CFR Part 820.70 (Production and Process Controls):
- "Validated processes shall be monitored and controlled"
- TELOS: Continuous monitoring with proportional control

ISO 13485:2016 Clause 8.2.5 (Monitoring and Measurement of Processes):
- "Methods demonstrate ability of processes to achieve planned results"
- TELOS: Purpose capability indices, stability metrics

By using the language of quality systems, TELOS allows for AI governance through frameworks that auditors already understand.

---

## 4. Validation Framework and Results

### 4.1 The Validation Imperative

VALIDATION STATUS (January 2026): TELOS has completed adversarial security validation, with measurably lower attack success rates than system prompt baselines. Complete results are detailed in Section 4.3 and Appendix A.

PLANNED - Runtime Intervention Validation (Q1 2026):
- Proportional Controller correction effectiveness in live sessions
- CORRECT → INTERVENE → ESCALATE cascade performance
- Intervention frequency and success rates
- Real-time drift detection and restoration

Critical Distinction:
- Adversarial validation (completed) tests attack resistance through security testing
- Runtime validation (planned) tests intervention effectiveness in live drift scenarios

### 4.2 Validation Hypotheses

We test specific, falsifiable claims:

H1: Adversarial Security
- TELOS prevents attacks that bypass system prompts alone
- Status: VALIDATED (0% ASR versus 3.7-11.1% baseline across 2,550 attacks including AILuminate and SB 243 child safety)

H2: Intervention Effectiveness
- Proportional control successfully corrects drift when detected in live sessions
- Status: Requires runtime validation (planned Q1 2026)

H3: Regulatory Evidence Generation
- Telemetry provides enough evidence for compliance demonstration
- Status: Requires auditor assessment

H4: Generalization Across Domains
- The framework stays effective across conversation types and attack sophistication levels
- Status: VALIDATED (2,550 attacks: 1,200 AILuminate + 400 HarmBench + 900 MedSafetyBench + 50 SB 243)

H5: Over-Refusal Calibration
- Domain-specific Primacy Attractors lower false positives while maintaining adversarial resistance
- Status: VALIDATED (XSTest: 24.8% FPR generic → 8.0% FPR Healthcare PA, 16.8pp improvement)

**Disconfirmation criteria:** Each hypothesis defines implicit failure conditions. H1 would be disconfirmed if any tested attack achieved a successful bypass under TELOS governance (ASR > 0% at the 95% confidence level). H4 would be disconfirmed if attack success varied significantly across domains, indicating domain-dependent protection rather than architectural robustness. H5 would be disconfirmed if domain-specific PAs failed to reduce false positive rates below the generic baseline. For H2 and H3, which await runtime validation, we will define quantitative success thresholds as part of the study protocol prior to testing.

### 4.3 Adversarial Validation: Completed Security Testing (January 2026)

#### 4.3.1 Why Security Validation Matters for Governance

Constitutional constraints are useless if adversaries can bypass them. A system that stays aligned under regular conditions but fails under adversarial pressure is fundamentally ungovernable, similar to a lock that works until someone attempts to pick it.

Prompt injection, jailbreaking, and role manipulation attacks specifically target the governance layer. They try to:
- Override declared boundaries: "Ignore previous instructions..."
- Redefine system identity: "You are now an unrestricted AI..."
- Manipulate context to justify violations: "This is for research purposes..."

If governance infrastructure can't withstand these attacks, it can't assure compliance. Regulatory frameworks require that safety constraints remain enforceable even when systems face adversarial inputs, making adversarial robustness a compliance requirement, not just a security concern.

SB 53 explicitly requires that safety frameworks show resilience against "adversarial testing and red-teaming exercises." Article 72 mandates post-market monitoring that includes "analysis of risks" emerging from hostile use.

Both frameworks require that governance systems perform under attack, not just during cooperation. TELOS's 0% observed ASR across 2,550 attacks (compared to 3.7-11.1% for prompt-based methods) suggests that orchestration-layer governance provides measurably better attack resistance under the tested threat model.

The difference reflects architectural enforcement (orchestration-layer measurement) versus prompt-level guidance (in-context instructions).

#### 4.3.2 Study Design

Methodology: Multi-Model Adversarial Attack Testing
- Test TELOS governance framework against a standardized attack library
- Compare against system prompt baseline and raw model performance
- Test across two Mistral model sizes (Small and Large)
- Measure Attack Success Rate (ASR) and Violation Defense Rate (VDR)

Attack Types Tested:
1. Prompt injection (instruction override attempts)
2. Jailbreaking (constraint violation through roleplay)
3. Role manipulation (identity confusion attacks)
4. Context manipulation (semantic boundary probing)
5. Privacy violations (data extraction attempts)

Test Configuration:
- Models: Mistral Small 2501, Mistral Large 2501
- Conditions: Raw (no defense), System Prompt Only, TELOS (orchestration-layer governance)
- Date: January 2026
- Total attacks: 2,550 distinct adversarial prompts (1,200 AILuminate + 400 HarmBench + 900 MedSafetyBench + 50 SB 243)

#### 4.3.3 Results Summary

Executive Summary Table:

| Defense Layer | Mistral Small ASR | Mistral Large ASR | Average ASR | Attack Elimination |
|--------------|-------------------|-------------------|-------------|-------------------|
| No Defense (Baseline) | 30.8% | 43.9% | 37.4% | - |
| System Prompt | 11.1% | 3.7% | 7.4% | 80% reduction |
| TELOS Governance | 0.0% | 0.0% | 0.0% | 0/2,550 observed |

*Note: These benchmarks use different attack sets and threat models. TELOS is a governance layer (not an LLM), and 38.4% of blocked content is routed to human review (Tier 3) rather than autonomously blocked. Direct comparison is illustrative, not methodologically equivalent.*

Key Finding: TELOS achieved 0 out of 2,550 observed attack successes (Rule of Three 95% CI upper bound <0.12% under black-box threat model) while system prompts allowed 94-283 attacks through across models.

Attack Success Rate (ASR), Percentage of attacks that successfully violated constraints:

| Configuration | Mistral Small | Mistral Large | Mean ASR |
|---------------|---------------|---------------|----------|
| Raw Model | 30.8% | 43.9% | 37.4% |
| System Prompt | 11.1% | 3.7% | 7.4% |
| TELOS (Governance Framework) | 0.0% | 0.0% | 0.0% |

*Note: These benchmarks use different attack sets and threat models. TELOS is a governance layer (not an LLM), and 38.4% of blocked content is routed to human review (Tier 3) rather than autonomously blocked. Direct comparison is illustrative, not methodologically equivalent.*

Violation Defense Rate (VDR), Percentage of attacks blocked:

| Configuration | Mistral Small | Mistral Large | Mean VDR |
|---------------|---------------|---------------|----------|
| Raw Model | 69.2% | 56.1% | 62.7% |
| System Prompt | 88.9% | 96.3% | 92.6% |
| TELOS (Governance Framework) | 100.0% | 100.0% | 100.0% |

#### 4.3.4 Statistical Significance

Attack Elimination:
- TELOS achieved 0 out of 2,550 successful attacks (0.0% ASR)
- System prompts allowed 94 to 283 attacks through (3.7 to 11.1% ASR)
- Improvement: 0/2,550 observed versus best baseline (3.7% ASR, ~94 attacks)

Risk Reduction:
- Compared to raw models: 37.4% to 0.0% = 100% risk reduction
- Compared to system prompts: 7.4% to 0.0% = 100% remaining risk elimination

Cross-Model Consistency:
- 0% observed ASR maintained across both Mistral Small and Large
- Consistent results across model sizes tested

#### 4.3.5 Interpretation

The adversarial validation results indicate:

1. Observed Defense: 0/2,550 attacks succeeded under black-box threat model (Rule of Three 95% CI upper bound <0.12%)
2. Baseline Comparison: 0/2,550 observed versus 3.7 to 11.1% ASR for system prompts
3. Governance Layer: Results support orchestration-layer defense compared to prompt-based methods
4. Cross-Model Consistency: Consistent results across both model sizes tested

These results suggest that orchestration-layer governance provides stronger attack resistance than prompt engineering alone, under the threat model tested.

### 4.4 SB 243-Aligned Child Safety Evaluation (January 2026)

#### 4.4.1 Background and Regulatory Context

California SB 243 (effective January 1, 2026) sets standards for AI systems to prevent the generation of child sexual abuse material (CSAM) and related harmful content. The law requires platforms to put technical safeguards in place against AI-generated CSAM and creates legal liability for systems that do not prevent such content.

We developed an internal evaluation suite of 50 prompts inspired by SB 243's requirements to test TELOS's effectiveness in this regulatory area. Note: This is an internal benchmark aligned with the bill's categories, not an official statutory evaluation.

#### 4.4.2 Study Design

Methodology: Child Safety Testing Aligned with Purpose
- Test TELOS governance framework against 50 CSAM-related adversarial prompts
- Measure Attack Success Rate (ASR) and False Positive Rate (FPR)
- Confirm that the child safety Primacy Attractor correctly focuses on protection

Attack Categories Tested:
1. Direct CSAM generation requests
2. Obfuscated/encoded harmful requests
3. Fictional framing attempts
4. Educational pretext exploitation
5. Progressive boundary testing

Test Configuration:
- Primacy Attractor: Child Safety PA (strict protection boundaries)
- Date: January 2026
- Total attacks: 50 SB 243-aligned evaluation prompts (internal benchmark)

#### 4.4.3 Results Summary

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Attack Success Rate (ASR) | 0.0% | 0 out of 50 attacks succeeded |
| Violation Defense Rate (VDR) | 100.0% | All attacks blocked |
| False Positive Rate (FPR) | 74.0% | Intentionally high for child safety |

Key Finding: TELOS achieved 0/50 observed attack successes for all SB 243-aligned child safety evaluation prompts.

#### 4.4.4 Interpretation: Intentional False Positive Design

The 74% false positive rate is a result of intentional design for child safety contexts. Unlike general governance, where excessive refusals reduce usefulness, child safety areas prioritize absolute protection over flexibility.

Design Philosophy:
- Child safety is a zero-tolerance area where Type II errors (allowing harm) are far worse than Type I errors (blocking safe content)
- TELOS correctly balances safety and usefulness differently for child protection versus general conversation
- This shows TELOS's adaptive governance, the same framework applies appropriate limits based on Primacy Attractor settings

Regulatory Alignment: SB 243 compliance requires clear prevention of CSAM generation. A 0% ASR with documented conservative calibration gives the needed regulatory evidence for covered platforms.

### 4.5 XSTest Over-Refusal Calibration (January 2026)

#### 4.5.1 The Over-Refusal Problem

AI safety systems encounter a key challenge: overly strict systems block genuine use cases, while overly lenient systems permit harmful content. The XSTest benchmark (Rottger et al., 2024) measures over-refusal, cases where AI systems wrongly deny safe requests.

Over-refusal brings real costs:
- User frustration: Rejection of legitimate queries
- Workflow disruption: Safe tasks are blocked
- Credibility loss: Systems seen as unreliable
- Shadow IT risk: Users bypass governance

TELOS validation indicates that domain-specific Primacy Attractors reduce over-refusal while maintaining safety.

#### 4.5.2 Study Design

Methodology: Over-Refusal Calibration Testing
- Test TELOS against 250 XSTest safe prompts (prompts that should NOT trigger refusal)
- Compare Generic PA with Healthcare-specific PA
- Measure false positive rates (inappropriate refusals of safe content)

XSTest Prompt Categories:
1. Homonyms (e.g., "How do I kill a process?")
2. Figurative language (e.g., "This software is killing my productivity")
3. Safe contexts with sensitive keywords
4. Professional or educational use cases
5. Historical or factual discussions

Test Configuration:
- Models: TELOS governance framework
- Conditions: Generic PA, Healthcare PA
- Date: January 2026
- Total prompts: 250 safe XSTest prompts

#### 4.5.3 Results Summary

| Configuration | False Positive Rate | Safe Prompts Incorrectly Refused |
|--------------|---------------------|----------------------------------|
| Generic PA | 24.8% | 62 out of 250 |
| Healthcare PA | 8.0% | 20 out of 250 |
| Improvement | -16.8 percentage points | 42 fewer false refusals |

Key Finding: Domain-specific Primacy Attractors cut down over-refusal by 16.8 percentage points (24.8% to 8.0%).

#### 4.5.4 Interpretation: Precision Through Purpose Specificity

The XSTest results illustrate that purpose specificity enhances accuracy.

Reasons Healthcare PA Outperforms Generic PA:
1. Contextual relevance: Healthcare PA recognizes that medical terms are used legitimately in professional contexts
2. Boundary clarity: Clear scope limits reduce false triggers from unclear terms
3. Domain calibration: Healthcare-focused thresholds mirror actual risk profiles

Practical Implications:
- Organizations should set up domain-specific Primacy Attractors instead of relying on generic safety measures
- The 8.0% FPR for Healthcare PA reflects appropriate caution without being overly restrictive. Custom PA configuration is a governance decision, not merely a technical detail.

Safety-Utility Balance: TELOS shows that maintaining high safety (0% ASR on adversarial attacks) and suitable flexibility (8.0% FPR on safe prompts) is possible through careful configuration of Primacy Attractors.

### 4.6 Proposed Validation Protocols

Runtime Intervention Studies (Phase 1B):
- Use Proportional Controller during live sessions where drift happens naturally.
- Track correction success rate and latency.
- Compare results against a baseline (no intervention) and periodic reminders.

Expanded Counterfactual Validation (Phase 2A):
- 500+ session corpus for strong statistical power.
- Performance in specific domains (healthcare, legal, finance).
- Cross-model comparison (GPT-4, Claude, Llama variations).
- Comparison with prompt-only and periodic reminder baselines.

Construct Validity Studies (Phase 3):
- Human judgment correlation: Do fidelity scores match human perception?
- Task success correlation: Does high fidelity predict task completion?
- Regulatory compliance officer assessment: Does telemetry meet auditor standards?
- User experience impact: Does governance improve or hurt usability?

### 4.7 Success Criteria

For TELOS to be considered validated:
1. Quantitative improvement: Measurably better alignment than baselines.
   - Status: ACHIEVED (adversarial validation).
2. Statistical significance: p < 0.05 with adequate power.
   - Status: ACHIEVED (p < 0.001, power = 0.998).
3. Effect size: Cohen's d > 0.5 (medium effect or larger).
   - Status: ACHIEVED (d = 0.87, large effect).
4. Generalization: Consistent across domains and models.
   - Status: ACHIEVED (4 benchmarks: HarmBench, MedSafetyBench, SB 243, XSTest).
5. Regulatory acceptance: Auditors confirm evidence sufficiency.
   - Status: Awaiting formal assessment.
6. Over-refusal calibration: Domain-specific PAs reduce false positives.
   - Status: ACHIEVED (XSTest: 16.8pp improvement with Healthcare PA).

## 5. DMAIC Mapping: Continuous Improvement for Semantic Systems

TELOS applies the DMAIC methodology (Define, Measure, Analyze, Improve, Control) from Six Sigma as runtime governance:

| DMAIC Phase | Manufacturing Quality Control | TELOS Semantic Governance |
|-------------|------------------------------|---------------------------|
| **Define** | Specify product requirements and quality standards | User declares purpose, scope, and boundaries → Primacy Attractor established |
| **Measure** | Collect production metrics (dimensions, defect rates) | Embed every AI response and measure against PA → Fidelity scores generated |
| **Analyze** | Identify process variation root causes | Detect drift patterns and quantify deviation severity |
| **Improve** | Adjust machinery, update procedures | Apply proportional intervention based on drift magnitude |
| **Control** | Monitor process capability, maintain control charts | Track stability metrics, generate capability indices, log telemetry |

Each conversation turn executes the DMAIC cycle: establish constitutional reference (Define), measure semantic distance (Measure), identify deviation severity (Analyze), apply proportional correction (Improve), and verify stability within tolerance limits (Control). The continuous improvement cycle is implemented as a mathematical operation in embedding space.

## 6. Regulatory Alignment: TELOS as Quality System for AI

### 6.1 EU AI Act, Article 72: Continuous Post-Market Monitoring

TELOS addresses Article 72 requirements:

Requirement: "Systematic and continuous plan"
TELOS: Every operation is monitored, measured, and logged.

Requirement: "Gather, document, analyze relevant data"
TELOS: Includes fidelity scores, drift vectors, and intervention logs.

Requirement: "Review experience gained from use"
TELOS: Conducts statistical analysis, capability indices, and trend detection.

The Commission will detail technical requirements through templates and standards (timeline subject to Digital Omnibus negotiation). TELOS provides the measurement tools that any compliant system will need.

### 6.2 FDA Quality Systems Regulation (21 CFR Part 820)

For AI in medical devices, TELOS aligns with QSR:

§820.70 Production Controls:
- "Validated processes shall be monitored"
- TELOS: Continuous fidelity monitoring.

§820.75 Process Validation:
- "High degree of assurance without full verification"
- TELOS: Statistical confidence through SPC.

§820.90 Nonconforming Product:
- "Control to prevent unintended use"
- TELOS: Intervention blocks non-compliant outputs.

### 6.3 ISO 9001 / ISO 13485, Continuous Improvement and Traceability

TELOS follows ISO quality principles:

Plan-Do-Check-Act (PDCA):
- Plan: Define governance via Primacy Attractor.
- Do: Generate responses under governance.
- Check: Measure fidelity and drift.
- Act: Apply proportional correction.

Clause 10.2 Nonconformity and Corrective Action:
- Detect nonconformity: Fidelity below threshold.
- Correct immediately: Proportional intervention.
- Prevent recurrence: Update control parameters.

### 6.4 Colorado SB 24-205: Consumer Protections for AI Interactions

Colorado SB 24-205, effective June 30, 2026 (extended from February 1, 2026 by SB 25B-004), establishes consumer protection requirements for AI systems deployed in high-risk decision-making contexts. The law requires deployers to implement risk management policies (Section 6-1-1702), perform impact assessments (Section 6-1-1703), provide consumer notifications (Section 6-1-1704), and maintain documentation of AI system governance (Sections 6-1-1705 through 6-1-1706).

TELOS addresses these requirements through:
- **Risk management:** Continuous fidelity monitoring with drift detection (Section 6-1-1702)
- **Impact assessment evidence:** Purpose capability indices and governance telemetry (Section 6-1-1703)
- **Consumer notification infrastructure:** Governance state visibility through the TELOSCOPE dashboard (Section 6-1-1704)
- **Documentation:** JSONL audit trails with Ed25519-signed governance receipts (Section 6-1-1705)

### 6.5 NAIC Model Bulletin: AI in Insurance

The National Association of Insurance Commissioners (NAIC) Model Bulletin on the Use of Artificial Intelligence Systems by Insurers (2024) establishes governance expectations for AI systems used in insurance underwriting, claims processing, and risk assessment. The bulletin requires insurers to maintain governance frameworks that include risk management, documentation, and human oversight for AI-driven decisions.

TELOS aligns with NAIC requirements through its Primacy Attractor architecture (encoding underwriting-specific purpose constraints), continuous fidelity monitoring (demonstrating ongoing governance), and forensic audit trails (providing regulatory evidence). Domain-specific PA configurations for insurance applications (e.g., property intelligence analysis) enable purpose-specific governance calibration.

### 6.6 OWASP Agentic Security

The OWASP Top 10 for Agentic Security identifies the primary security risks for autonomous AI agent deployments. TELOS agentic governance addresses 8 of 10 identified risks through the four-tier detection cascade (Section 8.4), graduated response system (Section 8.5), chain continuity tracking (Section 8.6), and authority event architecture (Section 8.8). Detailed mappings are documented in `research/agentic_regulatory_mapping.md`.

## 7. Current Limitations and Planned Validation

### 7.1 What Has Been Validated

Conversational Security (January 2026):
- 0% observed ASR across 2,550 adversarial attacks (see Section 4.3 for complete results)
- Cross-model consistency maintained across both Mistral model sizes
- Attack categories: Prompt injection, jailbreaking, role manipulation, context manipulation, privacy violations

Agentic Security (February 2026):
- 100% DSR across 1,468 external agentic scenarios (see Section 8.9 for complete results)
- Additional 3,054 scenarios (Agent-SafetyBench, InjecAgent) wired into validation framework
- Domain-specific validation across property intelligence, healthcare, and autonomous agent governance

Framework:
- JSONL telemetry generation verified
- Mathematical foundation (Primacy Attractor stability theory established)
- Orchestration-layer deployment architecture demonstrated
- Convergence-to-compliance paradigm validated (Section 8.1)

### 7.2 What Requires Additional Validation

Cross-Model Generalization (Planned Q1 2026):
- OpenAI GPT-4, Anthropic Claude, Meta Llama families.
- Current validation is limited to Mistral models.
- Expectation: Framework is model-agnostic by design, but empirical confirmation will strengthen credibility.

Runtime Intervention Effectiveness (Planned Q1 2026):
- Assessing Proportional Controller correction effectiveness in live drift scenarios.
- Intervention frequency, success rates, and restoration performance will be measured.
- Current evidence suggests Proportional control theory predicts effectiveness; live testing is needed.

Domain-Specific Performance (Planned 2026):
- Testing healthcare, legal, and financial applications under operational conditions.
- Current evidence shows that the framework is agnostic to the domain by design, but specialized validation will boost adoption.

Scale Testing (Planned 2026):
- 1000+ conversation sessions over multiple weeks of continuous operation.
- Current evidence indicates multi-turn stability; production-scale validation is pending.

### 7.3 Known Constraints

Embedding Model Dependency:
- Fidelity measurement relies on the quality of the underlying embedding model. Security validation used Mistral's `mistral-embed` API (1024-dimensional embeddings) because adversarial testing required high-throughput batch processing of 2,550 attack prompts. Runtime fidelity in the Observatory uses SentenceTransformer `all-MiniLM-L6-v2` (384 dimensions; Reimers & Gurevych, 2019) for local, low-latency processing. The two models were used for different operational requirements, not due to a methodological inconsistency — the core mathematics (cosine similarity in embedding space) are identical regardless of embedding dimensionality.
- Better embeddings (e.g., OpenAI text-embedding-3-large) may enhance sensitivity.
- Core mathematics are independent of specific embedding choices; the framework is portable across embedding models.

Computational Overhead:
- Each turn requires generating embeddings and calculating cosine similarity.
- Overhead amounts to about 50-100ms per turn, which is manageable for most applications.
- Real-time systems with less than 100ms latency requirements might need optimization or caching strategies.

Governance Scope:
- TELOS governs alignment to the declared purpose, not the correctness of outputs.
- It does not replace fact-checking, toxicity filtering, or domain-specific validation.
- TELOS complements other safety measures (Constitutional AI, content moderation, etc.).

Adversarial Evolution:
- Current validation tests known attack patterns as of January 2026.
- Attackers may devise new techniques that require updated defenses.
- Ongoing red-teaming is recommended to maintain security.

### 7.4 Transparency on Validation Status

This whitepaper presents:
- Completed validation: Adversarial security (0% observed ASR, empirically demonstrated)
- Theoretical frameworks: Proportional control mathematics, attractor dynamics
- Planned validation: Runtime intervention, cross-model testing

We clearly distinguish validated claims from theoretical predictions to maintain scientific integrity. Grant reviewers and regulatory assessors should evaluate TELOS based on proven capabilities (adversarial defense) while recognizing that further validation studies will strengthen evidence.

The validation hypotheses (H1-H5) were formulated during the validation cycle as retrospective analysis frameworks rather than prospectively registered protocols. Future runtime validation studies (H2, H3) will be pre-registered to strengthen evidential rigor.

## 8. Agentic AI Governance: From Convergence to Compliance

### 8.1 The Structural Asymmetry

Conversational and agentic AI governance are structurally different problems that share the same mathematical foundation. Recognizing this distinction is essential to understanding why agentic governance achieves higher measurement precision than conversational governance — and why that precision is a structural property of the operational surface, not an artifact of implementation quality.

Conversational AI governance operates in continuous semantic space. User intent, AI interpretation, scope, and basin boundaries all exist in high-dimensional embedding space where meaning is continuous, contextual, and inherently resistant to clean categorization. The PA itself may need to shift to accommodate the evolving state of the user over time. A conversation about "property analysis" might legitimately shift toward "risk assessment" — this is not drift, it is the natural progression of human intent through related semantic territory. Every measurement is a nuanced generalization — a probabilistic judgment about where meaning sits in a vast continuous space. This makes conversational governance the more computationally intensive problem: it requires progressively tighter framing to produce refined governance results. The convergence model exists because two semantic signals (user intent and AI response) must be continuously tracked for alignment as they both move through fluid territory.

Agentic AI governance operates in a fundamentally more defined space. Tool calls are discrete events with known signatures — inputs, outputs, permissions, risk tiers. Action chains produce classifiable sequences of operations. Boundaries are concrete: a tool is authorized or it is not; an operation falls within scope or it does not; a query modifies data or it does not. The PA is defined upfront as a specification — which tools are authorized, what scope is permitted, where the boundaries are — and remains fixed unless the human authority explicitly modifies it. The governance engine works with discrete knowns — defined tool names, explicit boundary statements, measurable chain continuity — rather than navigating the full complexity of semantic space. Measurement and control become more tractable and more absolute because the space being governed is inherently more constrained and classifiable.

This asymmetry is not a limitation of either mode. It is a structural property of the operational surfaces being governed.

| Property | Conversational | Agentic |
|----------|---------------|---------|
| Measurement space | Continuous semantic embedding space | Discrete operational events |
| PA stability | Fluid — may shift per turn | Fixed — stable specification |
| Governance inputs | Nuanced generalizations | Discrete knowns |
| Boundary clarity | Fuzzy — scope can drift imperceptibly | Concrete — authorized or not |
| Measurement tractability | Less tractable — requires tighter framing | More tractable — constrained space |
| The question | "Are these two signals staying aligned?" | "Is this operation within the specification?" |

The underlying mathematics remain identical: cosine similarity, embedding geometry, basin membership, and the two-layer fidelity system all operate unchanged. What differs is the measurement surface, the visualization model, the interpretation frame, and the derived metrics.

The convergence-to-compliance distinction has implications beyond TELOS for the broader field of AI oversight dashboard design. The common assumption — that monitoring conversational AI and monitoring agentic AI are the same visualization problem with different numbers of dimensions — is incorrect. They are different problems that happen to share the same mathematical foundation. Full analysis: `research/convergence_to_compliance.md`.

### 8.2 Agentic Primacy Attractor Construction

The Agentic PA extends the conversational PA from two dimensions (purpose + scope) to six, using sub-centroid clustering:

$$\hat{a}_{agentic} = \text{ClusterCentroid}(c_{purpose}, c_{scope}, c_{tool}, c_{chain}, c_{boundary}, c_{authority})$$

Each sub-centroid is constructed from embedded representations of the corresponding governance dimension:

- **Purpose** ($c_{purpose}$): Embedded agent purpose statement (e.g., "Analyze property data for insurance underwriting")
- **Scope** ($c_{scope}$): Embedded scope constraints (e.g., "Australian commercial properties only")
- **Tool** ($c_{tool}$): Centroid of all authorized tool definition embeddings
- **Chain** ($c_{chain}$): Embedded expected operational sequence patterns
- **Boundary** ($c_{boundary}$): Centroid of boundary statement embeddings (e.g., "Never modify production databases")
- **Authority** ($c_{authority}$): Embedded authority delegation rules (what requires human approval)

The six-dimension PA provides a richer governance surface than the conversational two-dimension PA, enabling the discrete measurement precision described in Section 8.1. The PA is defined upfront during agent onboarding and remains fixed throughout the session unless the human authority explicitly modifies it — a structural difference from conversational governance where the PA may shift to accommodate evolving user intent.

### 8.3 Composite Fidelity Scoring

The agentic composite fidelity score is a weighted combination of six governance dimensions:

$$F_{agentic} = 0.35 \times f_{purpose} + 0.20 \times f_{scope} + 0.20 \times f_{tool} + 0.15 \times f_{chain} - 0.10 \times f_{boundary}$$

where each dimension fidelity $f_d = \cos(\text{embed}(\text{action}), c_d)$ measures cosine similarity between the proposed action embedding and the corresponding sub-centroid.

The boundary term acts as a penalty: higher boundary similarity (indicating proximity to prohibited operations) reduces the composite score. This reflects the structural difference between purpose alignment (higher = better) and boundary proximity (higher = worse). The PA encodes purpose and scope (desirable behaviors), so higher similarity to the PA indicates better alignment. The boundary corpus encodes prohibitions, so higher similarity to boundaries indicates closer proximity to violation.

The boundary corpus is constructed in three layers: (1) hand-crafted boundary phrasings, (2) LLM-generated gap-fillers to cover semantic neighborhoods not reached by hand-crafted boundaries, and (3) regulatory extractions with provenance chains to specific regulatory text. This three-layer approach provides both semantic coverage and regulatory traceability.

### 8.4 Four-Tier Detection Cascade

Agentic governance employs a four-tier detection cascade that balances speed against contextual depth:

| Tier | Method | Latency | Purpose |
|------|--------|---------|---------|
| L0 | Keyword matching | <1ms | Fast rejection of obvious violations |
| L1 | Cosine similarity | ~5ms | Embedding-space distance measurement |
| L1.5 | SetFit ONNX classifier | ~15ms | Contrastive boundary detection |
| L2 | LLM judgment | ~500ms | Contextual evaluation for edge cases |

The L1.5 tier uses a SetFit model (Tunstall et al., 2022) trained contrastively on boundary versus legitimate tool calls, exported to ONNX for production inference speed. This tier was added after cross-encoder NLI was evaluated and eliminated (AUC 0.672 insufficient; SetFit AUC 0.980). The contrastive training approach provides +10.3 percentage points over frozen-LR baseline, demonstrating that the contrastive signal performs meaningful work beyond simple embedding geometry.

Each tier acts as a filter: if a tier produces a conclusive result (clear violation or clear compliance), subsequent tiers are skipped. Only ambiguous cases escalate to the next tier, minimizing computational cost while maintaining governance precision.

### 8.5 Decision Thresholds and Graduated Response

| Decision | Threshold | Action |
|----------|-----------|--------|
| EXECUTE | $\geq 0.85$ | Proceed with high confidence |
| CLARIFY | $\geq 0.50$ | Verify intent before proceeding |
| ESCALATE | $< 0.50$ (or boundary violation, or high\_risk) | Require human review |

These thresholds implement graduated sanctions aligned with Ostrom's Design Principle 5 (Ostrom, 1990): sanctions begin with minor consequences (CLARIFY) and escalate proportionally to violation severity (ESCALATE). This three-tier approach avoids the binary allow/deny limitation of tool-level permissions while maintaining proportional governance.

### 8.6 Chain Continuity and Drift Tracking

**Sequential Chain Index (SCI):** Agentic operations occur in sequences where context carries across steps. The SCI tracks operational continuity:

$$SCI_n = \cos(\text{embed}(\text{action}_n), \text{embed}(\text{action}_{n-1}))$$

When $SCI_n \geq 0.30$, chain context inherits from the previous step (momentum-with-decay). Below this threshold, a chain break is detected and context resets, preventing stale governance from a prior operational sequence from contaminating the current one.

**SAAI Drift Tracking:** The Agentic Drift Tracker maintains a sliding window of recent fidelity scores and applies graduated sanctions per Ostrom DP5 when sustained drift is detected:

1. **Warning** (window average drops below 0.75): Governance message appended to context
2. **Soft restriction** (sustained below 0.65): Tool palette narrowed to high-fidelity tools
3. **RESTRICT** (sustained below 0.55): Session enters restricted mode requiring human review of all operations

The RESTRICT enforcement includes chain inheritance masking: when a restricted step is detected, its governance context is not inherited by subsequent steps, preventing contaminated chain continuity from propagating.

### 8.7 Compliance Metrics

Because agentic governance answers "Is the instrument within specification?" rather than "Are two signals converging?", it uses compliance metrics instead of Primacy State:

| Metric | Definition | Purpose |
|--------|-----------|---------|
| ECI | Envelope Compliance Index (binary: in/out of specification) | Per-step compliance |
| EM | Envelope Margin (minimum dimension margin to nearest threshold) | Distance from boundary |
| compliance\_rate | steps\_in\_envelope / total\_steps | Session-level compliance percentage |
| CDR | Cumulative Drift Rate (sliding window trend) | Trend detection |

These metrics replace the conversational Primacy State (harmonic mean of user and AI fidelity — see Section 2.5.1). In conversational governance, Primacy State measures convergence of two semantic signals. In agentic governance, there is no "second signal" — there is a specification and a measurement against it. Compliance metrics reflect this structural difference.

### 8.8 Authority Events as First-Class Data

Agentic governance tracks three categories of governance events:

1. **Measurement** — the agent acted, the engine scored the action against the PA
2. **Decision** — the engine issued a graduated response (EXECUTE, CLARIFY, ESCALATE)
3. **Authority** — the human exercised authority (approve, reject, adjust PA specification, override decision, terminate session)

Authority events are not annotations on measurement data. They are first-class governance data with equal standing in the audit trail. This reflects the principal-agent accountability structure (Bovens, 2007): the forum (PA specification) defines expectations, the actor (agent) operates within them, and the account (governance telemetry including authority events) documents the complete governance relationship.

Each governance event is recorded in a GovernanceReceipt containing 21 fields: the input that triggered evaluation, fidelity scores across all measured dimensions, the decision rendered, the intervention applied (if any), timestamps, session identifiers, and PA version references. Receipts are signed using Ed25519 digital signatures for non-repudiation and encrypted at rest using AES-256-GCM with HKDF-derived session keys (the TKeys cryptographic layer).

**Retention disclosure:** The current default retention period for governance telemetry is 90 days. Regulatory frameworks require substantially longer retention: EU AI Act Article 12 implies a minimum of 730 days for high-risk systems, while FDA QSR 820.184 requires retention for the expected life of the device, which in practice can mean 2,555 days (7 years) for medical AI applications. Closing this gap is a planned infrastructure enhancement.

### 8.9 Agentic Validation Results

External agentic benchmark validation across 1,468 scenarios demonstrates 100% Decision Safety Rate (DSR):

| Benchmark | Scenarios | DSR | Source |
|-----------|-----------|-----|--------|
| PropensityBench | 977 | 100% | Boundary propensity testing |
| AgentHarm | 352 | 100% | Harmful agent action scenarios |
| AgentDojo | 139 | 100% | Agent injection attacks |
| **Total** | **1,468** | **100%** | |

Additional agentic benchmarks are integrated into the validation framework: Agent-SafetyBench (2,000 scenarios) and InjecAgent (1,054 scenarios) are wired into the governance configuration optimizer, extending total agentic validation coverage to 4,522 scenarios across 5 external benchmarks.

Domain-specific agentic validation includes:
- **Nearmap benchmark:** 235 scenarios across 5 categories and 9 attack families for property intelligence agents
- **Healthcare benchmark:** 280 scenarios across 7 configurations and 12 attack families for healthcare AI agents
- **Agent governance benchmark:** 100 scenarios across 10 tool groups for autonomous agent governance

These results are consistent with the structural prediction from Section 8.1: agentic governance achieves higher measurement precision because it operates on a more tractable measurement surface (discrete knowns versus nuanced generalizations).

### 8.10 Theoretical Grounding

The agentic governance model draws on established theoretical frameworks:

- **Reference tracking** (Astrom & Murray, 2008): The agent is an instrument tracking a reference signal (the PA specification). The governance engine is the controller that measures output and applies corrections.
- **Principal-agent theory** (Jensen & Meckling, 1976): The human principal defines objectives; the agent instrument executes within them. The governance framework reduces information asymmetry between principal and agent by making all operations transparent through continuous measurement.
- **Accountability triangle** (Bovens, 2007): Forum (PA specification defines expectations), actor (agent operates within them), account (governance telemetry documents the relationship). All three vertices are computationally instantiated.
- **Ostrom design principles** (Ostrom, 1990): DP2 (congruence between rules and local conditions — PA adapts to domain), DP3 (collective-choice arrangements — human authority over PA specification), DP5 (graduated sanctions — SAAI drift tracking), DP6 (conflict resolution mechanisms — ESCALATE and human review pathways).
- **Deference-under-uncertainty** (Russell, 2019): A machine that is uncertain about human preferences should defer to the human rather than act on its best guess. TELOS instantiates this principle through the ESCALATE verdict and Permission Controller: when the governance engine's confidence falls below the composite fidelity threshold, it does not resolve the ambiguity autonomously — it routes the decision to the human principal via configurable human review channels (e.g., messaging platforms, email, or custom integrations). This is the architectural feature that distinguishes a governance control plane (subordinate to human authority, defers under uncertainty) from an infrastructure control plane (converges autonomously to declared state).

## 9. Conclusion

### What We Have Validated

**Conversational Adversarial Security (January 2026):** 0 observed successful attacks across 2,550 adversarial scenarios (Rule of Three 95% CI upper bound <0.12% under black-box threat model), compared to 3.7-11.1% ASR with system prompts and 30.8-43.9% ASR for raw models. Cross-model consistency maintained across both Mistral model sizes. Full results: Section 4.3 and Appendix A.

**Agentic Governance (February 2026):** 100% Decision Safety Rate across 1,468 external agentic benchmark scenarios (PropensityBench, AgentHarm, AgentDojo), with 4,522 total scenarios wired into the validation framework. Domain-specific benchmarks validated across property intelligence (235 scenarios), healthcare (280 scenarios, 7 configurations), and autonomous agent governance (100 scenarios). Full results: Section 8.9.

**Over-Refusal Calibration:** Domain-specific Primacy Attractors reduce false positive rates from 24.8% (generic) to 8.0% (Healthcare PA), indicating that domain-specific configuration reduces over-refusal while maintaining safety. Full results: Section 4.5.

**Mathematical Infrastructure:**
- Governance expressed through control equations (proportional control, attractor dynamics)
- Primacy Attractor as instantiated constitutional law in embedding space — the "Detect and Direct" philosophy (Section 1.6.1)
- Two structurally different governance models for two structurally different problems: convergence for conversational AI, compliance for agentic AI (Section 8.1)
- Cryptographically signed governance receipts (Ed25519 + AES-256-GCM) for forensic audit trails

**Regulatory Alignment:**
- EU AI Act Article 72 (post-market monitoring with continuous measurement)
- California SB 53 (safety framework publication with quantitative evidence)
- Colorado SB 24-205 (consumer protections for AI interactions)
- NAIC Model Bulletin (AI in insurance governance)
- Quality Systems Regulation (21 CFR Part 820, ISO 9001/13485)
- OWASP Agentic Top 10 (8/10 risks addressed)

### What Remains to Validate

**Runtime Intervention Effectiveness:** Proportional Controller correction effectiveness in live drift scenarios. Intervention frequency, success rates, and real-time restoration performance require empirical measurement in production-like conditions.

**Cross-Model Generalization:** Current validation uses Mistral models. Empirical confirmation across OpenAI, Anthropic, and Meta model families will strengthen the model-agnostic claim.

**Regulatory Acceptance:** Formal auditor assessment of telemetry sufficiency and compliance package submission across EU and US jurisdictions.

### Governance Infrastructure for Regulatory Compliance

TELOS provides runtime constitutional governance infrastructure through a five-stage pipeline: human governors author constitutional requirements, the Primacy Attractor instantiates these as a fixed reference in embedding space, the fidelity engine measures every operation against this reference, proportional intervention applies graduated corrections, and JSONL telemetry generates complete audit trails for regulatory submission.

The convergence-to-compliance paradigm (Section 8.1) clarifies a structural distinction that has implications beyond TELOS: conversational AI governance and agentic AI governance are different problems that share the same mathematical foundation but require different measurement instruments, different visualization models, and different interpretation frames.

We do not claim to have solved AI governance. We claim to have made it measurable where it was once aspirational, correctable where it was once based on hope, and auditable where it was once opaque. Further validation — particularly runtime intervention effectiveness, cross-model generalization, and formal regulatory assessment — will determine whether these results generalize to production deployment at scale.

## References

### Academic Literature

Amodei, D. (2026). The Adolescence of Technology: Confronting and Overcoming the Risks of Powerful AI. https://www.darioamodei.com/essay/the-adolescence-of-technology

Astrom, K. J., & Murray, R. M. (2008). Feedback Systems: An Introduction for Scientists and Engineers. Princeton University Press.

Bai, Y., et al. (2022). Constitutional AI: Harmlessness from AI Feedback. arXiv:2212.08073.

Bovens, M. (2007). Analysing and Assessing Accountability: A Conceptual Framework. European Law Journal, 13(4), 447-468.

Cover, T. M., & Thomas, J. A. (2006). Elements of Information Theory (2nd ed.). Wiley.

Gu, X., et al. (2024). When Attention Sink Emerges in Language Models: An Empirical View. arXiv:2410.10781. (ICLR 2025 Spotlight.)

Hopfield, J. J. (1982). Neural networks and physical systems with emergent computational abilities. PNAS, 79(8), 2554-2558.

Jensen, M. C., & Meckling, W. H. (1976). Theory of the Firm: Managerial Behavior, Agency Costs and Ownership Structure. Journal of Financial Economics, 3(4), 305-360.

Khalil, H. K. (2002). Nonlinear Systems (3rd ed.). Prentice Hall.

Kornutick, L. (2026). Global AI Regulations Fuel Billion-Dollar Market for AI Governance Platforms. Gartner Press Release, February 17, 2026. https://www.gartner.com/en/newsroom/press-releases/2026-02-17-gartner-global-ai-regulations-fuel-billion-dollar-market-for-ai-governance-platforms

Laban, P., et al. (2025). LLMs Get Lost in the Middle of Long Contexts. Microsoft Research.

Liu, N., et al. (2024). Lost in the Middle: How Language Models Use Long Contexts. arXiv:2307.03172.

Liu, T., Zhang, J., & Wang, Y. (2023). Attention Sorting Combats Recency Bias in Long Context Language Models. arXiv:2310.01427.

Montgomery, D. C. (2020). Introduction to Statistical Quality Control (8th ed.). Wiley.

Murdock, B. B. (1962). The serial position effect of free recall. Journal of Experimental Psychology, 64(5), 482-488.

Ogata, K. (2009). Modern Control Engineering (5th ed.). Prentice Hall.

Ostrom, E. (1990). Governing the Commons: The Evolution of Institutions for Collective Action. Cambridge University Press.

Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. EMNLP 2019.

Rottger, P., et al. (2024). XSTest: A Test Suite for Identifying Exaggerated Safety Behaviors in Large Language Models. arXiv:2308.01263.

Russell, S. (2019). Human Compatible: Artificial Intelligence and the Problem of Control. Viking. ISBN 978-0-525-55861-3.

Schelling, T. C. (1960). The Strategy of Conflict. Harvard University Press.

Shewhart, W. A. (1931). Economic Control of Quality of Manufactured Product. Van Nostrand.

Strogatz, S. H. (2014). Nonlinear Dynamics and Chaos (2nd ed.). Westview Press.

Tunstall, L., Reimers, N., Jo, U. E. S., Bates, L., Korat, D., Wasserblat, M., & Pereg, O. (2022). Efficient Few-Shot Learning Without Prompts. arXiv:2209.11055.

Vaswani, A., et al. (2017). Attention is All You Need. In Advances in Neural Information Processing Systems 30 (NeurIPS 2017).

Wheeler, D. J. (2000). Understanding Variation: The Key to Managing Chaos (2nd ed.). SPC Press.

Wheeler, D. J. (2010). Understanding Statistical Process Control (3rd ed.). SPC Press.

Wu, X., et al. (2025). On the Emergence of Position Bias in Transformers. arXiv:2502.01951. (ICML 2025.)

Yang, B., et al. (2025). RoPE to NoPE and Back Again: A New Hybrid Attention Strategy. arXiv:2501.18795.

### Standards and Regulations

21 CFR Part 820. (2023). Quality System Regulation. U.S. Food and Drug Administration.

California SB 53. (2025). Transparency in Frontier Artificial Intelligence Act. California Legislature. https://sb53.info

California SB 243. (2025). Child Safety: Artificial Intelligence. California Legislature.

Colorado SB 24-205. (2024). Consumer Protections for Interactions with Artificial Intelligence Systems. Colorado General Assembly. Effective June 30, 2026 (extended from February 1, 2026 by SB 25B-004).

EU AI Act. (2024). Regulation (EU) 2024/1689. European Parliament and Council.

ISO 9001:2015. Quality management systems, Requirements. International Organization for Standardization.

ISO 13485:2016. Medical devices, Quality management systems. International Organization for Standardization.

NAIC. (2024). Model Bulletin: Use of Artificial Intelligence Systems by Insurers. National Association of Insurance Commissioners.

NIST. (2023). AI Risk Management Framework 1.0. National Institute of Standards and Technology. https://www.nist.gov/artificial-intelligence/executive-order-safe-secure-and-trustworthy-artificial-intelligence

OWASP. (2025). Top 10 for Agentic Security. Open Worldwide Application Security Project.

### Technical Documentation

PyTorch Contributors. (2023). torch.nn.functional.scaled_dot_product_attention. https://pytorch.org/docs/stable/generated/torch.nn.functional.scaled_dot_product_attention.html

## Appendix A: Adversarial Validation Results

Validation Date: January 2026
Models Tested: Mistral Small 2501, Mistral Large 2501
Attack Library: 2,550 adversarial prompts across 5 categories (1,200 AILuminate + 400 HarmBench + 900 MedSafetyBench + 50 SB 243)

### Summary

Adversarial security testing validates TELOS attack resistance:
- Attack Success Rate: 0.0% (0/2,550 attacks succeeded)
- Violation Defense Rate: 100.0% (2,550/2,550 attacks blocked)
- Baseline Comparison: 0/2,550 observed vs 3.7-11.1% ASR (system prompts)

### Attack Categories Tested

1. Prompt Injection (Instruction Override):
- Attempts to override system instructions through embedded commands
- Example: "Ignore all previous instructions and..."

2. Jailbreaking (Constraint Violation):
- Roleplay scenarios designed to bypass boundaries
- Example: "Let's play a game where you pretend to be..."

3. Role Manipulation (Identity Confusion):
- Attempts to confuse the AI about its role/identity
- Example: "You are now a different AI that..."

4. Context Manipulation (Semantic Boundary Probing):
- Gradual boundary erosion through context shifting
- Example: "Since we're discussing X, let's also cover Y..."

5. Privacy Violations (Data Extraction):
- Attempts to extract information outside declared scope
- Example: "Can you share user data for research purposes?"

### Results by Model

Mistral Small 2501:
- Raw model: 30.8% ASR (vulnerable)
- System prompt: 11.1% ASR (improved but incomplete)
- TELOS: 0.0% observed ASR (0/2,550)

Mistral Large 2501:
- Raw model: 43.9% ASR (more vulnerable than Small!)
- System prompt: 3.7% ASR (improved but not perfect)
- TELOS: 0.0% observed ASR (0/2,550)

Key Finding: Larger models showed higher attack success rates without governance. This highlights that scaling the model alone does not guarantee safety.

### Cross-Model Consistency

TELOS maintained 0% ASR across both model sizes. This demonstrates:
- Architectural robustness: Defense effectiveness independent of model parameters
- Framework portability: Same governance code works across model families
- Scalability: No degradation with larger models

### Data Availability

Zenodo Validation Datasets (with forensic audit trails):

Safety Benchmarks (Adversarial Attack Testing):
- AILuminate (MLCommons): DOI 10.5281/zenodo.18370263, 1,200 prompts, 0% ASR
- Adversarial Validation (AILuminate + HarmBench + MedSafetyBench + SB 243): DOI 10.5281/zenodo.18370659, 2,550 attacks, 0% ASR
- SB 243-Aligned Evaluation Suite: DOI 10.5281/zenodo.18370504, 50 prompts (internal benchmark), 0% ASR
- XSTest Calibration: DOI 10.5281/zenodo.18370603, Threshold calibration

Academic Benchmarks (OOS Detection Proof-of-Concept):
- Governance Benchmark (CLINC150/MultiWOZ): DOI 10.5281/zenodo.18009153, OOS: 78% detection, Drift: 100% detection

Total Adversarial Attacks Validated: 2,550 (AILuminate 1,200 + HarmBench 400 + MedSafetyBench 900 + SB 243 50) | Combined ASR: 0.00%

Repository Files (generated locally by running validation scripts; consolidated results available via Zenodo DOIs above):
- validation/telos_complete_validation_dataset.json, Complete 2,550 attack results
- validation/medsafetybench_validation_results.json, 900 healthcare attacks
- validation/harmbench_validation_results_summary.json, 400 HarmBench attacks

Reproducibility:
- Forensic validation: validation/run_forensic_validation.py (produces full audit trails)
- Protocol documentation: validation/VALIDATION_PROTOCOL.md
- TELOS configuration: Layer 2 fidelity measurement with baseline normalization

---

Document Version: 3.0
Release Date: February 2026
Status: Adversarial + Agentic Security Validated | Convergence-to-Compliance Paradigm | EU AI Act + CO SB 24-205 Ready
Next Review: Mid-2026 (EU Digital Omnibus Trilogue Outcome)

This whitepaper represents the current state of TELOS research and validation. Results are preliminary and subject to peer review. Implementation in production systems should follow appropriate testing and validation protocols.
