# TELOS Quick Reference: Common Questions Answered

## Why TELOS Exists

### What's the point of TELOS?

To give you control. AI should serve your purposes, not wander off on its own. TELOS keeps conversations focused on what actually matters to you.

### Why does human dignity matter here?

Because AI shouldn't lecture, explain itself, or make you feel managed. It should respond to what you ask, trust that you understand, and stay in the background as infrastructure. You're in control, not the machine.

### How is TELOS different from other AI tools?

Most AI either drifts anywhere or feels rigid and scripted. TELOS lets conversations feel natural while staying aligned with your actual purpose. You get both: natural conversation AND consistent focus.

## Basic Concepts

### What is a Primacy Attractor?

A Primacy Attractor is like a compass for AI conversations. It defines the "true north" - the purpose the conversation should stay aligned with. When responses start pointing in different directions, the attractor pulls them back toward the original intent.

### What does "fidelity" mean?

Fidelity is a score from 0 to 1 that measures how well aligned a response is with the intended purpose. Think of it like a percentage - 0.85 means 85% aligned, 0.92 means 92% aligned. Higher is better.

### What is drift?

Drift is when conversations gradually move away from their original purpose. Like a boat slowly drifting off course without a rudder. TELOS acts as the rudder that keeps conversations on track.

## How TELOS Works

### How does TELOS detect drift?

TELOS converts messages into mathematical representations that capture meaning. It then measures the distance between each response and the intended purpose. If responses are getting too far away, drift is detected.

### What happens when drift is detected?

TELOS can respond in different ways depending on severity:
- **Minor drift**: Just monitor, might self-correct
- **Moderate drift**: Remind the AI of the original purpose
- **Significant drift**: Regenerate the response to be more aligned
- **Severe drift**: Alert you that intervention is needed

### Can TELOS prevent all drift?

Not completely prevent, but it can detect and correct drift very effectively. The goal isn't to create perfect conversations, but to keep them productively aligned with their purpose.

## Using TELOS

### How do I set up TELOS for my use case?

Three steps:
1. Define your **purpose** - what should this accomplish?
2. Define your **scope** - what topics are relevant?
3. Define your **boundaries** - what should be avoided or redirected?

### Can I adjust TELOS after starting?

Yes! TELOS can be configured to learn from conversations (Open Mode) or use pre-established settings (Demo Mode). Settings can be adjusted based on how well governance is working.

### Does TELOS slow down conversations?

The governance overhead is typically 200-300 milliseconds - barely noticeable. The AI response time (2-5 seconds) is much longer than the governance check.

## Technical Questions (In Plain English)

### What are semantic embeddings?

A way to convert text into numbers that capture meaning. Words with similar meanings get similar numbers. This lets computers "understand" that "car" and "automobile" are related, even if the words are different.

### What is a basin of attraction?

The zone around your purpose where responses are considered acceptable. Imagine a bowl - anything inside the bowl is on track, anything rolling outside needs to be nudged back in.

### What are Lyapunov functions?

Mathematical proof that the system will naturally pull conversations back toward the purpose over time. It's like showing that a ball will always roll downhill into a valley, even if you push it slightly off course.

### What does "model-agnostic" mean?

TELOS works with any AI model - GPT, Claude, Mistral, whatever. It doesn't need to be built into the model itself. It operates as a layer on top, checking outputs and providing guidance.

## Comparisons

### How is TELOS different from prompting?

Prompts are instructions given at the start of a conversation. They fade over time as conversations get long. TELOS continuously measures and corrects throughout the entire conversation - it doesn't fade.

### How is TELOS different from fine-tuning?

Fine-tuning changes the AI model itself to behave differently. TELOS doesn't change the model - it guides the model's outputs. This means it's faster to implement and doesn't require retraining.

### How is TELOS different from RAG?

RAG (Retrieval Augmented Generation) provides relevant information to help AI answer accurately. TELOS governs whether responses stay on purpose. They're complementary - RAG provides content, TELOS provides governance.

## Use Cases

### When should I use TELOS?

Use TELOS when:
- Conversations need to stay focused on specific topics
- You need consistent AI behavior over long sessions
- Regulatory compliance requires audit trails
- Brand voice and policies must be maintained
- Educational or training scenarios need curriculum focus

### When might I not need TELOS?

You might not need TELOS if:
- Conversations are very short (1-2 turns)
- Topic flexibility is more important than consistency
- You want completely open-ended exploration
- There's no specific purpose or outcome required

## Observable Governance

### What does "observable" mean?

You can see the governance happening. Unlike a black box where you don't know why the AI said something, TELOS shows you:
- Fidelity scores every turn
- When drift is detected
- What interventions are applied
- A complete audit trail

### Why does observability matter?

For trust, debugging, and compliance:
- **Trust**: You can verify governance is working
- **Debugging**: You can see what went wrong when issues occur
- **Compliance**: You can prove to regulators that policies were enforced

### Can users see the fidelity scores?

That's up to you. TELOS can display scores to users (transparency) or keep them internal (monitoring). Different use cases have different needs.

## The Steward

### What is The Steward?

The Steward is what you get when you combine TELOS governance with a knowledge base (RAG). It's an AI expert that:
- Knows a specific domain deeply (from the knowledge base)
- Never drifts off-topic (from TELOS governance)
- Provides observable, trustworthy responses

### How is The Steward different from a chatbot?

Chatbots use keyword matching and scripts - brittle and inflexible. The Steward uses natural language understanding with governance - flexible but bounded.

### Can I create a Steward for my domain?

Yes! That's the whole point. Define your domain (museum exhibit, product, curriculum, etc.), load relevant knowledge, configure TELOS governance, and you have a Steward for your domain.

## Research and Validation

### Is TELOS proven to work?

TELOS has been tested in controlled studies showing 70% improvement in alignment over conversations without governance. However, full large-scale validation is ongoing.

### What research backs TELOS?

TELOS builds on published research showing AI alignment degrades 20-40% over long conversations. It combines control theory, dynamical systems, and information theory to address this problem.

### Is TELOS ready for production?

TELOS is operational and functional. For non-critical applications (education, museums, product demos), it's ready to use. For high-risk applications (healthcare, finance), additional validation is recommended.

## Limitations

### What can't TELOS do?

TELOS can't:
- Make the AI fundamentally smarter or more knowledgeable
- Prevent all possible mistakes or hallucinations
- Force the AI to know things it wasn't trained on
- Replace human judgment in high-stakes decisions

### What are current limitations?

- Requires computational overhead (small but measurable)
- Works best with clear, well-defined purposes
- May be too strict or too lenient until properly configured
- Doesn't eliminate the need for human oversight

## Getting Help

### Where can I learn more?

- Read the TELOS whitepaper for technical details
- Try Demo Mode to experience governance in action
- Review the architecture guide for implementation details
- Contact the TELOS team for specific use case guidance

### How do I report issues?

If you encounter problems:
1. Check the fidelity scores - are they unexpectedly low or high?
2. Review the conversation - where did things go off track?
3. Check your purpose/scope/boundaries definitions - are they clear?
4. Adjust tolerance settings if governance is too strict or loose

### Can I contribute to TELOS?

TELOS is research infrastructure with an open approach. Contributions, feedback, and validation studies are welcome. Contact the team to discuss collaboration opportunities.

---

**Quick Summary**: TELOS keeps AI conversations aligned with their purpose through continuous measurement and correction. It's observable (you can see it working), correctable (it can fix drift), and auditable (it creates records). Use it when conversations need to stay focused and consistent over time.
