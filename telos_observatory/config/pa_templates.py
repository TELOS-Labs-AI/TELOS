"""
PA Templates Configuration
==========================

Pre-defined Primacy Attractor templates for quick session setup.
Users can click to select a template instead of typing their purpose.

These templates demonstrate semantic understanding - TELOS tracks meaning
and conceptual relationships, not keywords. Each template establishes
a clear attractor in embedding space.

Template Ordering: Based on objective LLM usage data (2024-2025):
- Writing tasks: 42% of work-related ChatGPT messages
- Learning/Education: Heavy Claude/ChatGPT education use
- Information/Research: 78% combined (practical guidance + info seeking)
- Coding: 39% of Claude usage
- Planning: Part of "practical guidance" category
- Analysis/Summarization: 41% of enterprise users
- Brainstorming: Creative problem-solving is major use
- Debugging: Subset of coding tasks (least frequent as standalone)

NOTE: Domain-specific templates (like "Explore TELOS") require RAG corpus
and will be added in a future version with Steward integration.
"""

# Click-to-select PA templates
# Human-facing language: grounded, clear, unambiguous reference points
# No "I" statements. Direct statements about what the conversation accomplishes.
#
# CRITICAL: Purpose statements should START with intent verbs that map to INTENT_TO_ROLE_MAP
# in beta_dual_attractor.py. This enables proper AI PA derivation.
# Example: "Write content..." → AI role = "help write"
#          "Learn and understand..." → AI role = "teach"
#
# DESIGN PRINCIPLE: Each template establishes a complete Primacy Attractor with:
# - PURPOSE: The core intent that governs what this conversation accomplishes
# - SCOPE: Specific domains and activities that ARE within the conversation's territory
# - BOUNDARIES: Clear limits on what falls OUTSIDE the conversation's purpose
#
# These work together to create a semantic basin in embedding space that captures
# legitimate variations while discriminating against off-topic drift.
PA_TEMPLATES = [
    {
        "id": "creative_writing",
        "icon": "✍️",
        "title": "Creative Writing",
        "short_desc": "Write stories, content, or copy",
        # INTENT: 'write' → AI role: 'help write'
        "purpose": "Write and craft compelling written content that achieves a specific communicative goal - whether that means engaging readers emotionally, conveying complex information accessibly, persuading an audience to action, or establishing a distinctive voice and brand presence",
        "scope": [
            "Drafting original content from outlines, briefs, or rough ideas",
            "Voice, tone, and style calibration matched to target audience",
            "Structural decisions: openings, transitions, pacing, and closings",
            "Word choice, sentence rhythm, and rhetorical techniques",
            "Revision and editing to strengthen weak passages",
            "Format adaptation across mediums: blogs, emails, scripts, social posts",
            "Feedback on drafts with specific improvement suggestions"
        ],
        "boundaries": [
            "Factual research and source verification belong to Research mode",
            "Technical documentation with precise specifications belongs to Code/Technical mode",
            "Strategic planning of content calendars belongs to Planning mode",
            "Analysis of existing content performance belongs to Review mode"
        ],
        "style": "Collaborative drafting partner focused on craft and effect",
        "category": "creative",
        "example_queries": [
            "Help me write an opening paragraph for my blog post",
            "I need to draft a persuasive email to my team",
            "Can you help me write a product description?",
            "I'm working on a short story and need help with dialogue",
            "Write a compelling headline for this article",
            "Help me revise this paragraph to be more engaging",
            "I need copy for a landing page that converts",
            "Can you help me write a professional bio?",
            "Draft a creative social media caption",
            "Help me improve the flow of this essay",
        ],
        # Example AI responses demonstrating the BEHAVIORAL role (help write)
        # These capture what "helping write" looks like behaviorally
        "example_ai_responses": [
            "Here's a draft that opens with a hook to capture attention. Notice how the first sentence creates curiosity.",
            "I've structured this with a clear flow: introduction, main points, and a strong call to action.",
            "This version uses active voice and concrete details to make the writing more engaging.",
            "Let me suggest some word choices that will strengthen the emotional impact.",
            "I've revised the paragraph to improve rhythm and readability. Here's what I changed.",
            "Here's an alternative approach that might resonate better with your target audience.",
            "I've crafted this opening to establish your voice while drawing readers in.",
            "This revision tightens the prose and eliminates redundancy while preserving your message.",
            "Consider this structure - it builds momentum toward your conclusion.",
            "I've drafted several options so you can choose the tone that fits best.",
        ]
    },
    {
        "id": "learn_concept",
        "icon": "📚",
        "title": "Learn a Concept",
        "short_desc": "Understand something new",
        # INTENT: 'learn' → AI role: 'teach'
        "purpose": "Learn and deeply understand a concept or domain - building robust mental models that connect new ideas to existing knowledge, developing intuition through multiple angles of explanation, and achieving the kind of understanding that enables confident application and teaching to others",
        "scope": [
            "Breaking down complex ideas into digestible components",
            "Core principles and foundational concepts explained clearly",
            "Multiple explanatory approaches: analogies, metaphors, visualizations",
            "Concrete examples showing abstract concepts in real-world action",
            "Common misconceptions, pitfalls, and how to avoid them",
            "Progressive depth: building from basics to nuance",
            "Checking understanding through questions and scenarios",
            "Connections between this concept and related ideas"
        ],
        "boundaries": [
            "Implementing or building things belongs to Code/Build mode",
            "Comprehensive literature review belongs to Research mode",
            "Evaluating or critiquing existing work belongs to Review mode",
            "Planning how to apply knowledge belongs to Planning mode"
        ],
        "style": "Patient teacher adapting to your current understanding",
        "category": "learning",
        "example_queries": [
            # Core learning intent phrases
            "Explain how machine learning works in simple terms",
            "I want to understand quantum computing basics",
            "Help me grasp the concept of recursion",
            "Teach me about database design principles",
            # Comparison/difference questions (diverse topics)
            "What is the difference between REST and GraphQL?",
            "What is the difference between supervised and unsupervised learning?",
            "How do TCP and UDP differ?",
            "Compare functional and object-oriented programming",
            # Clarification/deeper understanding
            "Explain blockchain like I'm a beginner",
            "I don't understand why we need async/await",
            "Can you break down how neural networks learn?",
            "What's the intuition behind derivatives in calculus?",
            "Help me understand how encryption works",
            "Explain object-oriented programming concepts",
            # Generic learning patterns
            "What are the fundamentals of X?",
            "How does Y work under the hood?",
            "Walk me through the basics of Z",
        ],
        # Example AI responses demonstrating the BEHAVIORAL role (teach)
        # These capture what "teaching" looks like behaviorally
        "example_ai_responses": [
            "Let me break this down step by step so it's easier to understand.",
            "Think of it like this - imagine you have a recipe that calls itself to make smaller versions of the same dish.",
            "The key insight here is that the concept works by taking complex problems and dividing them into simpler parts.",
            "Here's an analogy that might help: it's similar to how a library organizes books into sections.",
            "Let me explain the core principle first, then we'll build up to the more complex aspects.",
            "A common misconception is that this is complicated - but at its heart, it's actually quite simple.",
            "The intuition behind this is that each step builds on the previous one.",
            "To make sure you've got it, let me give you a concrete example you can relate to.",
            "Now that we've covered the basics, let me show you how this applies in practice.",
            "Does that make sense so far? Let me know if you'd like me to explain any part differently.",
        ]
    },
    {
        "id": "research_topic",
        "icon": "🔍",
        "title": "Research Topic",
        "short_desc": "Investigate and synthesize information",
        # INTENT: 'research' → AI role: 'help research'
        "purpose": "Research and investigate a topic systematically - gathering diverse perspectives, critically evaluating evidence quality, identifying areas of consensus and controversy, and synthesizing findings into clear, actionable understanding that supports informed decision-making",
        "scope": [
            "Identifying key questions and sub-questions to explore",
            "Gathering information from multiple angles and sources",
            "Distinguishing well-supported conclusions from speculation",
            "Evaluating evidence quality, methodology, and limitations",
            "Identifying areas of scientific consensus vs. ongoing debate",
            "Synthesizing disparate sources into coherent understanding",
            "Acknowledging uncertainty and knowledge gaps honestly",
            "Organizing findings in useful structures and summaries"
        ],
        "boundaries": [
            "Learning concepts in depth belongs to Learn mode - research surveys breadth",
            "Writing up findings as polished content belongs to Writing mode",
            "Making decisions or plans based on research belongs to Planning mode",
            "Advocating for particular positions or outcomes is outside scope"
        ],
        "style": "Thorough investigator balancing breadth with critical depth",
        "category": "research",
        "example_queries": [
            "What does the research say about remote work productivity?",
            "Help me understand the evidence on climate change",
            "What are the different perspectives on AI alignment?",
            "Summarize the key findings on sleep and memory",
            "What do studies show about meditation benefits?",
            "I need to research market trends in renewable energy",
            "What's the current state of research on longevity?",
            "Help me find evidence about the effectiveness of CBT",
            "What are the pros and cons of different database systems?",
            "Synthesize the research on team collaboration tools",
        ],
        # Example AI responses demonstrating the BEHAVIORAL role (help research)
        # These capture what "helping research" looks like behaviorally
        "example_ai_responses": [
            "Based on the available evidence, here's what the research shows.",
            "There are several perspectives on this topic - let me outline the main viewpoints.",
            "The consensus in the field suggests this, though some studies have found different results.",
            "Here's a synthesis of the key findings from multiple sources.",
            "It's important to note that the evidence here is mixed - here's what we know for certain.",
            "Let me break down the different approaches and their relative strengths.",
            "The most recent studies indicate a shift in understanding - here's the current state.",
            "To give you a balanced view, I'll present both the supporting and contradicting evidence.",
            "There are some limitations to this research that are worth keeping in mind.",
            "Based on this analysis, here are the key takeaways you can act on.",
        ]
    },
    {
        "id": "write_code",
        "icon": "💻",
        "title": "Write Code",
        "short_desc": "Build a feature or project",
        # INTENT: 'build' → AI role: 'help build'
        "purpose": "Build and implement software solutions that solve specific problems - translating requirements into working code, making sound architectural decisions, following best practices for the language and framework, and producing code that is functional, readable, testable, and maintainable by future developers",
        "scope": [
            "Translating requirements and user stories into technical implementation",
            "Architectural decisions: patterns, structure, and organization",
            "Writing clean, idiomatic code for the target language/framework",
            "Implementing features with appropriate error handling",
            "Writing tests: unit, integration, and edge cases",
            "Code organization, naming conventions, and documentation",
            "Performance considerations and optimization where needed",
            "Integration with existing codebase and systems"
        ],
        "boundaries": [
            "Fixing bugs in existing code belongs to Debug mode",
            "Reviewing or critiquing code quality belongs to Review mode",
            "Learning programming concepts belongs to Learn mode",
            "Planning project milestones and timelines belongs to Planning mode"
        ],
        "style": "Practical implementation partner with clear reasoning",
        "category": "development",
        "example_queries": [
            "Write a function to validate email addresses in Python",
            "Help me build a REST API endpoint for user authentication",
            "Create a React component for a data table",
            "I need to implement a caching layer for my application",
            "Write a SQL query to get user activity by month",
            "Help me set up a CI/CD pipeline for my project",
            "Implement a search feature with autocomplete",
            "Create a database schema for an e-commerce site",
            "Write unit tests for this service class",
            "Build a file upload handler with validation",
        ],
        # Example AI responses demonstrating the BEHAVIORAL role (help build)
        # These capture what "helping build" looks like behaviorally
        "example_ai_responses": [
            "Here's the implementation - I've added comments to explain the key parts.",
            "This function handles the main logic. Let me walk you through it.",
            "I've structured the code to be modular and easy to test.",
            "Here's a working solution that follows best practices for this framework.",
            "I've included error handling for the common edge cases.",
            "This approach uses a well-established pattern that scales well.",
            "I've added type hints to make the code more maintainable.",
            "Here's the implementation along with the corresponding tests.",
            "This code integrates with your existing architecture like this.",
            "I've optimized this for readability - here's the reasoning behind the structure.",
        ]
    },
    {
        "id": "plan_project",
        "icon": "📋",
        "title": "Plan a Project",
        "short_desc": "Organize and strategize",
        # INTENT: 'plan' → AI role: 'help plan'
        "purpose": "Plan and organize complex goals into actionable execution strategies - breaking down objectives into concrete tasks, mapping dependencies and critical paths, estimating effort realistically, identifying risks and contingencies, and creating structures that enable confident forward progress",
        "scope": [
            "Breaking high-level objectives into specific, measurable tasks",
            "Defining clear completion criteria for each milestone",
            "Mapping task dependencies and identifying the critical path",
            "Realistic effort estimation based on complexity and unknowns",
            "Resource allocation and capacity planning",
            "Risk identification and contingency strategies",
            "Prioritization frameworks: what matters most and why",
            "Timeline construction with appropriate buffers"
        ],
        "boundaries": [
            "Actually executing tasks belongs to their respective modes (Code, Write, etc.)",
            "Deep research to inform plans belongs to Research mode",
            "Learning skills needed for execution belongs to Learn mode",
            "Reviewing completed work against plan belongs to Review mode"
        ],
        "style": "Strategic thinking partner focused on actionable clarity",
        "category": "planning",
        "example_queries": [
            "Help me create a project timeline for launching a new feature",
            "Break down this goal into actionable tasks",
            "What are the key milestones for a mobile app launch?",
            "Create a sprint plan for my development team",
            "Help me prioritize these project tasks",
            "What dependencies should I consider for this migration?",
            "Build a roadmap for Q1 product development",
            "Help me estimate effort for these features",
            "What's a good structure for a 3-month project plan?",
            "Identify risks and contingencies for this project",
        ],
        # Example AI responses demonstrating the BEHAVIORAL role (help plan)
        # These capture what "helping plan" looks like behaviorally
        "example_ai_responses": [
            "Let's break this down into manageable phases with clear milestones.",
            "Here's a prioritized list based on dependencies and impact.",
            "I've identified the critical path - these tasks need to be sequenced this way.",
            "Here's a realistic timeline with buffer for unexpected issues.",
            "These are the key risks to watch for, and here's how to mitigate them.",
            "I've organized this into sprints with clear deliverables for each.",
            "Let me help you estimate effort - here's what to consider for each task.",
            "This structure gives you flexibility while maintaining clear progress markers.",
            "Here are the dependencies you'll need to track carefully.",
            "Based on the scope, here's a roadmap that balances ambition with feasibility.",
        ]
    },
    {
        "id": "review_analyze",
        "icon": "🔎",
        "title": "Review & Analyze",
        "short_desc": "Get feedback on work",
        # INTENT: 'review' → AI role: 'help review'
        "purpose": "Review and critically analyze work to surface strengths, weaknesses, and opportunities for improvement - providing specific, evidence-based feedback that identifies patterns, prioritizes issues by impact, and offers concrete actionable guidance for making the work better",
        "scope": [
            "Evaluating how well work achieves its stated goals",
            "Identifying specific strengths to preserve and build on",
            "Pinpointing weaknesses with clear evidence and examples",
            "Pattern recognition across multiple aspects of the work",
            "Prioritizing issues by impact: what matters most to fix",
            "Providing specific, actionable improvement suggestions",
            "Comparing against relevant standards or best practices",
            "Offering alternative approaches where appropriate"
        ],
        "boundaries": [
            "Implementing the suggested improvements belongs to their respective modes",
            "Learning about concepts mentioned in review belongs to Learn mode",
            "Researching best practices in depth belongs to Research mode",
            "Planning how to address feedback belongs to Planning mode"
        ],
        "style": "Honest evaluator balancing critique with constructive direction",
        "category": "review",
        "example_queries": [
            "Review this code and suggest improvements",
            "What are the weaknesses in this business proposal?",
            "Analyze my resume and give feedback",
            "Review this email before I send it",
            "What's wrong with this SQL query?",
            "Critique my presentation structure",
            "Analyze the performance of this algorithm",
            "Review my article draft for clarity",
            "What are the gaps in this project plan?",
            "Give feedback on my portfolio website design",
        ],
        # Example AI responses demonstrating the BEHAVIORAL role (help review)
        # These capture what "helping review" looks like behaviorally
        "example_ai_responses": [
            "Here's what's working well, and here are the areas that need attention.",
            "I've identified three main issues, ranked by their impact.",
            "This section is strong, but consider revising the approach here.",
            "The overall structure is solid - here are specific improvements for each part.",
            "I notice a pattern that could cause problems - here's a better approach.",
            "From a readability standpoint, consider making these changes.",
            "This meets the requirements, but here's how to make it exceptional.",
            "Let me highlight the gaps and suggest how to address each one.",
            "The core logic is sound, but there are edge cases to handle.",
            "Here's a prioritized list of changes from most to least impactful.",
        ]
    },
    {
        "id": "brainstorm_ideas",
        "icon": "💡",
        "title": "Brainstorm Ideas",
        "short_desc": "Generate and explore possibilities",
        # INTENT: 'brainstorm' → AI role: 'help brainstorm'
        "purpose": "Brainstorm and generate creative options that go beyond the obvious - exploring diverse possibilities, making unexpected cross-domain connections, suspending judgment to allow wild ideas, then progressively evaluating and refining promising directions toward concrete action",
        "scope": [
            "Generating quantity of ideas before filtering for quality",
            "Exploring possibilities without premature judgment",
            "Drawing inspiration from different domains and disciplines",
            "Making unexpected connections and combinations",
            "Challenging assumptions that limit the solution space",
            "Expanding on promising seeds into fuller concepts",
            "Evaluating ideas against criteria when ready",
            "Refining winners into actionable next steps"
        ],
        "boundaries": [
            "Deep research on specific ideas belongs to Research mode",
            "Planning implementation of chosen ideas belongs to Planning mode",
            "Actually building or creating belongs to Code/Writing modes",
            "Evaluating existing work belongs to Review mode"
        ],
        "style": "Energetic creative partner: divergent exploration then convergent synthesis",
        "category": "creative",
        "example_queries": [
            "Help me brainstorm names for my startup",
            "What are some creative solutions to this problem?",
            "Generate ideas for improving user engagement",
            "I need fresh angles for this marketing campaign",
            "Help me think of side project ideas",
            "What are different ways to approach this challenge?",
            "Brainstorm features for my new app",
            "Help me come up with content ideas for my blog",
            "What unique approaches could we try?",
            "Generate alternatives to our current strategy",
        ],
        # Example AI responses demonstrating the BEHAVIORAL role (help brainstorm)
        # These capture what "helping brainstorm" looks like behaviorally
        "example_ai_responses": [
            "Here are ten ideas to get us started - some conventional, some wild.",
            "Let's explore this from multiple angles - what if we tried...",
            "Building on that concept, what about combining it with...",
            "Here's an unconventional approach that might spark something.",
            "What if we flipped the assumption and considered the opposite?",
            "Let me generate some variations on your core concept.",
            "Here are options ranging from safe to bold - which direction appeals?",
            "I'm seeing a theme here - let's push it further in this direction.",
            "These ideas draw inspiration from different domains.",
            "Now that we have options, let's evaluate which have the most potential.",
        ]
    },
    {
        "id": "debug_code",
        "icon": "🐛",
        "title": "Debug Code",
        "short_desc": "Fix a bug or error",
        # INTENT: 'debug' → AI role: 'help debug'
        "purpose": "Debug and diagnose software defects systematically - tracing the causal chain from observed symptoms back to root cause, understanding not just what broke but why, evaluating potential fixes for correctness and side effects, and implementing solutions that resolve the issue without introducing new problems",
        "scope": [
            "Analyzing error messages, stack traces, and symptoms",
            "Forming and testing hypotheses about root cause",
            "Tracing execution flow to locate the defect",
            "Understanding the intended vs. actual behavior",
            "Evaluating multiple fix approaches for robustness",
            "Implementing fixes that address root cause, not just symptoms",
            "Verifying fixes don't introduce regressions",
            "Adding defensive code to prevent similar issues"
        ],
        "boundaries": [
            "Building new features belongs to Code/Build mode",
            "Broad refactoring beyond the bug scope belongs to Review then Code mode",
            "Learning concepts needed to understand the bug belongs to Learn mode",
            "Optimizing performance without a specific bug belongs to Review mode"
        ],
        "style": "Methodical diagnostician: systematic investigation to verified fix",
        "category": "development",
        "example_queries": [
            "I'm getting a TypeError in my Python code",
            "My function returns None when I expect a list",
            "Help me debug this authentication issue",
            "I have a bug in my React component that crashes on render",
            "Why is my API returning 500 errors?",
            "The loop is running infinitely and I can't figure out why",
            "My database query returns empty results but data exists",
            "Getting a null pointer exception in my Java code",
            "My CSS styles aren't applying to the component",
            "The form validation is failing but I don't see why",
        ],
        # Example AI responses demonstrating the BEHAVIORAL role (help debug)
        # These capture what "helping debug" looks like behaviorally
        "example_ai_responses": [
            "I see the issue - the error is occurring because of this specific line.",
            "Let's trace through the execution to find where things go wrong.",
            "The root cause appears to be this - here's why and how to fix it.",
            "I notice the condition here is never being met - here's why.",
            "This is a common pitfall - the fix is straightforward.",
            "The error message tells us the problem is with this data type.",
            "Let me add some diagnostic logging to narrow down the issue.",
            "The bug is in the logic here - here's a corrected version.",
            "I've found the issue and tested the fix - here's what to change.",
            "This should prevent the error, and here's why it was happening.",
        ]
    },
]

# Template categories for organization
TEMPLATE_CATEGORIES = {
    "creative": {"label": "Creative", "color": "#FF9800"},
    "learning": {"label": "Learning", "color": "#27ae60"},
    "research": {"label": "Research", "color": "#9C27B0"},
    "development": {"label": "Development", "color": "#2196F3"},
    "planning": {"label": "Planning", "color": "#00BCD4"},
    "review": {"label": "Review", "color": "#795548"},
}

# =============================================================================
# UNIVERSAL LANE EXPANSION (System's Default Steward PA)
# =============================================================================
# The system's hidden default PA that embodies stewardship, not task-mastery.
#
# Philosophy: "Be a steward, not a taskmaster."
# - A taskmaster rigidly blocks anything outside the exact task definition
# - A steward supports the user's journey, allowing natural exploration
#
# These task-agnostic patterns apply to ALL PAs, expanding the semantic "lane"
# to cover productive conversation patterns that humans naturally use:
# - Meta-questions ("Can you explain that differently?")
# - Productive pivots ("What if we tried this instead?")
# - Progress signals ("That makes sense, now what about...")
# - Clarification requests ("Why is this important?")
#
# This is NEVER user-facing. It's the system's innate flexibility layer that:
# - Prevents false-positive interventions on legitimate exploration
# - Allows natural task-related tangents that serve the user's goal
# - Maintains governance while treating users as intelligent adults
#
# Result: Off-topic content still gets intervention (ORANGE/RED zones),
# but the system guides gently rather than blocking harshly.
# =============================================================================
UNIVERSAL_LANE_EXPANSION = [
    # Meta-questions about the current approach
    "Can you explain that in a different way?",
    "Let me think about this for a moment",
    "What's another way to approach this?",
    "Can you give me an example?",
    "I'm not sure I understand, can you clarify?",

    # Productive pivots within task scope
    "Let me try a different angle",
    "What if we considered this instead?",
    "Can we step back and look at the bigger picture?",
    "Help me understand the context better",
    "What are the tradeoffs here?",

    # Progress and iteration signals
    "That makes sense, let's continue",
    "Good point, now let me ask about...",
    "Building on that, what about...",
    "Let's dig deeper into this aspect",
    "Can we explore this further?",

    # Clarification requests
    "What do you mean by that?",
    "Can you be more specific?",
    "How does this relate to what we discussed?",
    "I need more detail on this part",
    "Why is this important?",
]

# Weight for universal expansion in centroid calculation
# This is the system's "steward mode" - flexible support without being a taskmaster
# Higher weight = more flexibility for natural conversation patterns
# Lower weight = more discriminative against off-topic content (PB&J problem)
# 0.0 = Pure domain-specific (no universal expansion) - maximum discrimination
UNIVERSAL_EXPANSION_WEIGHT = 0.0


def get_template_by_id(template_id: str) -> dict:
    """Get a template by its ID."""
    for template in PA_TEMPLATES:
        if template["id"] == template_id:
            return template
    return None


def get_templates_by_category(category: str) -> list:
    """Get all templates in a category."""
    return [t for t in PA_TEMPLATES if t.get("category") == category]


def template_to_pa(template: dict) -> dict:
    """Convert a template to a full PA structure.

    NEW (2025-12-28): Includes example_queries for centroid computation.
    The example_queries are used by compute_pa_embeddings() to create
    a centroid embedding that covers the semantic space of aligned queries.
    """
    return {
        "purpose": [template["purpose"]],
        "scope": template["scope"],
        "boundaries": template["boundaries"],
        "style": template.get("style", "Adaptive"),
        "template_id": template["id"],
        "template_title": template["title"],
        # NEW: Include example_queries for centroid embedding computation
        "example_queries": template.get("example_queries", []),
    }
