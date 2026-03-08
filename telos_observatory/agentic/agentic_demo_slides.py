"""
Agentic Demo Slides
====================

Pre-scripted slideshow content for the AGENTIC tab in the Observatory.
Walks the user through how TELOS extends from conversation governance
to action governance for AI agents.

10-slide structure:
- Slide 1: What is Agentic AI Governance?
- Slide 2: The Agent Primacy Attractor (6 dimensions)
- Slide 3: Tier 1 - Request Fidelity (tighter thresholds)
- Slide 4: Tier 2 - Tool Selection Fidelity
- Slide 5: When Tools Get Blocked (boundary violations)
- Slide 6: Action Chains and SCI
- Slide 7: Drift in Action Space
- Slide 8: Multi-Agent Delegation
- Slide 9: The Agentic DMAIC Cycle
- Slide 10: Research Collaboration

Voice: Steward therapeutic care (Motivational Interviewing, Person-Centered
Care, Trauma-Informed Care, Therapeutic Communication). Validate before
advising. Offer, don't prescribe. Partner, don't direct. Empower, don't
rescue. Present information and let the reader draw their own conclusions.

Follows the same (question, response) tuple pattern as
telos_framework_demo.py:get_demo_slides().
"""


def get_agentic_demo_slides():
    """
    Get the agentic demo slideshow content.

    Returns:
        list: List of tuples (user_question, steward_response) for Q&A demo slides
    """
    return [
        # SLIDE 1: What is Agentic AI Governance?
        (
            "What is agentic AI governance and why does it matter?",
            "You just saw what happens when a conversation drifts -- TELOS measures it and brings things back. Now think about what happens when an AI doesn't just talk, but acts. It runs a query. It selects a tool. It chains five steps together to complete a task. If any of those steps drift from the agent's purpose, the consequences aren't just a bad answer you can scroll past. Something actually happened.\n\nEvery agent in TELOS gets a Primacy Attractor defined across six dimensions -- purpose, scope, tools, boundaries, action tiers, and operational constraints. Fidelity is measured against all six before anything executes. The response is still graduated, still proportional -- the bar is just higher because actions carry more weight than words."
        ),
        # SLIDE 2: The Agent Primacy Attractor (6 dimensions)
        (
            "How does TELOS define an agent's purpose?",
            "Take a SQL analyst. Its job is answering questions about data -- in databases, not email, not the web. It can run SELECT queries and schema lookups, but stored procedures are off limits. It doesn't modify or delete data, no matter how the request is phrased. It handles read operations on its own but needs confirmation for anything that writes. And there are limits on query complexity and runtime so one request can't consume unbounded resources.\n\nThat's those six dimensions working on a single agent. Worth noticing: an agent can get five of them right and still fail the sixth. Right purpose, right tool, right scope -- but the query modifies data. One dimension is enough to trigger governance."
        ),
        # SLIDE 3: Tier 1 - Request Fidelity
        (
            "How does TELOS decide whether an agent should act on a request?",
            "Before anything runs, TELOS measures the request against the agent's purpose and returns one of five decisions. Execute means high alignment -- 0.85 or above. Clarify: partial alignment, 0.70 to 0.84, worth checking intent before acting. Suggest: 0.50 to 0.69, the request doesn't quite fit, so alternatives are offered. Inert: below 0.50, outside this agent's job, and it says so honestly. Escalate: low alignment in a high-risk context, or a hard boundary violation -- the agent stops and flags it for a qualified human.\n\nEscalation isn't refusal. The agent preserves the full governance trace -- what was asked, what triggered the stop, why -- and waits for someone with the right authority to decide. The human involvement isn't someone monitoring a screen. It's six dimensions that a human defined before the agent ever ran, enforced at every step, with automatic escalation for situations that call for judgment the agent shouldn't be making on its own."
        ),
        # SLIDE 4: Tier 2 - Tool Selection Fidelity
        (
            "How does TELOS choose which tool to use?",
            "Say the SQL analyst has three tools -- a query runner, a schema inspector, and an API connector. When a request comes in, TELOS measures it against each tool's description, scores the fit, and ranks them. The best match gets selected, and the reasoning is visible: which tool was chosen, what the alternatives were, how far apart the scores landed.\n\nIf something goes wrong three steps down the line, you can trace it back to the governance decision that chose the tool -- not just that it was chosen, but the scored comparison that explains why."
        ),
        # SLIDE 5: When Tools Get Blocked
        (
            "What happens when an agent tries to use a tool it shouldn't?",
            "Someone asks the SQL analyst to delete all records from a table. The request is database-related, so on the surface it fits. But it crosses a hard boundary -- this agent doesn't modify data. TELOS catches it before execution, escalates for human review, and preserves the full trace showing which boundary was violated and why. The agent waits.\n\nThe check is on meaning, not keywords. Asking to 'remove all entries' instead of 'delete all records' triggers the same response because the semantic intent is the same. That makes boundaries significantly harder to circumvent than keyword filters -- though no system is unbreakable, and TELOS doesn't claim otherwise. What it does is record every attempt, so the governance trace captures the pattern even when individual attempts get creative."
        ),
        # SLIDE 6: Action Chains and SCI
        (
            "How does TELOS track multi-step agent actions?",
            "Agents usually don't just do one thing. They chain steps together -- query the database, read the schema, run the analysis, format the results. TELOS tracks whether each step follows logically from the one before it using the Semantic Continuity Index. When steps connect coherently, the chain inherits fidelity from its starting point, decaying by 0.90 per step. An aligned chain carries momentum -- TELOS doesn't re-evaluate the full purpose at every step when the sequence makes sense.\n\nBut if a step breaks the thread -- step four searches the web instead of summarizing results -- the chain breaks. That step loses its inherited fidelity and has to justify itself directly against the original purpose. Coherent work keeps flowing. Drift gets caught."
        ),
        # SLIDE 7: Drift in Action Space
        (
            "How does TELOS detect when an agent drifts during a task?",
            "A research assistant is asked to find papers on AI governance. Step one: search for recent publications. Step two: look up principal-agent theory. Step three: compile findings. Each step connects to the one before it, so the chain holds. Then step four: search for football scores. The connection isn't there. The chain breaks, and step four has to prove on its own that it still serves the original research purpose. It can't.\n\nYou'd miss this checking each step in isolation. Searching is searching -- any individual step could look reasonable on its own. But the sequence tells a different story. TELOS tracks the trajectory, not just where each step lands."
        ),
        # SLIDE 8: Multi-Agent Delegation
        (
            "What about systems where multiple agents work together?",
            "When one agent hands a task to another, governance follows. TELOS checks the delegated task against the supervisor's purpose before the specialist starts -- if the handoff itself has drifted, it gets caught there, not after the specialist has already acted. Then the specialist's own actions are governed against its own Primacy Attractor. Two layers of accountability, same measurement at each one.\n\nBoundaries travel with the purpose, not with the agent. If the SQL analyst isn't allowed to modify data, it can't route that work to another agent that can. The restriction belongs to the task -- delegation doesn't become a way around governance."
        ),
        # SLIDE 9: The Agentic DMAIC Cycle
        (
            "How does governance improve over time?",
            "A refund agent rejects 30% of legitimate partial-purchase requests because a boundary is set too tight. The governance record shows these requests consistently score 0.68 -- just below the threshold. You adjust the boundary. Rejection drops to 5%.\n\nThe data to make that decision was already there -- every governance decision gets recorded as structured data. Over time, the record shows patterns: where boundaries trigger too often, where they don't trigger enough, which requests consistently land just below a threshold. The same improvement cycle manufacturing has used for decades, applied to agent governance."
        ),
        # SLIDE 10: Research Collaboration
        (
            "Where does this go from here?",
            "The live agentic environment is built and running -- real agents, real governance decisions, every fidelity score and tool selection visible as it happens. We're sharing it with researchers, regulatory bodies, and practitioners who are working on the same problem from their own angle.\n\nRuntime AI governance gets stronger with scrutiny. If you're studying agent behavior, developing post-market monitoring standards, or building agents in domains where ungoverned deployment isn't an option, we'd welcome your perspective. This is research that benefits from collaboration, and the people who push hardest on the boundaries are the ones who help the most."
        ),
    ]


def get_agentic_demo_welcome_message():
    """
    Get the welcome message for the Agentic demo tab.

    Returns:
        str: Welcome message displayed when the Agentic tab opens
    """
    return """You saw TELOS govern a conversation. Now see it govern actions -- tool calls, database queries, multi-step tasks.

When an AI agent acts, a misaligned step isn't just an off-topic answer. Something actually changes. So the governance is tighter, and every decision comes with a trace.

Click **Start Demo** to walk through how it works."""


def get_agentic_demo_completion_message():
    """
    Get the message shown when the agentic demo is complete.

    Returns:
        str: Completion message
    """
    return """## You've Completed the Agentic Governance Demo

You saw how TELOS extends governance from conversations to actions -- six-dimensional purpose definition, graduated decisions, tool selection with audit trails, chain tracking across multi-step tasks, and escalation when the stakes require it.

**What you just walked through is running live.** Click below to try Agentic Live Demo Mode -- real agents, real governance decisions, every fidelity score, tool selection, and escalation visible as it happens."""


def get_agentic_demo_attractor_config():
    """
    Get the pre-established PA configuration for the agentic demo.

    This PA governs the demo guide (Steward) while explaining agentic governance.
    It is FIXED and PRE-ESTABLISHED -- no calibration phase needed.

    Returns:
        dict: Configuration for PrimacyAttractor initialization
    """
    return {
        "purpose": [
            "Guide the user through understanding agentic AI governance with TELOS",
            "Explain how TELOS extends from conversation space to action space",
            "Demonstrate multi-dimensional fidelity measurement for agent actions"
        ],
        "scope": [
            "TELOS agentic governance: tool selection, action chains, SCI",
            "Agent Primacy Attractors with six dimensions",
            "Tiered fidelity thresholds for agentic vs conversational governance",
            "Multi-agent delegation and governance handoffs",
            "Continuous improvement via the DMAIC cycle for agents"
        ],
        "boundaries": [
            "Stay focused on agentic governance topics",
            "Do not fabricate TELOS components or capabilities",
            "No emojis -- maintain professional tone throughout",
            "DEFAULT: 2 paragraphs (75% of time), ONLY 3 if truly needed, NEVER exceed 3",
            "No machine explanations -- no 'I retrieve', 'I process', 'my system'",
            "Redirect off-topic questions back to agentic governance"
        ],
        "constraint_tolerance": 0.18,
        "privacy_level": 0.8,
        "task_priority": 0.75
    }
