"""
Canonical Tool Definitions — Authoritative semantic corpus for Gate 1 scoring.

Every definition in this file is sourced from first-party platform documentation,
NOT hand-written abstractions. Provenance chain:

    Claude Code tools → Anthropic system prompt (first-party)
        Source: https://gist.github.com/wong2/e0f34aac66caf890a332f7b6f9e2ba8f
        Source: https://gist.github.com/bgauryy/0cdb9aa337d01ae5bd0c803943aa36bd

    Agent platform tools → Agent platform documentation (first-party)

    Claude Code Tools Reference (compiled from system prompt):
        Source: https://www.vtrivedy.com/posts/claudecode-tools-reference

Exemplars are in build_action_text() format — the EXACT string format that
telos-score.py produces at runtime. This ensures Gate 1 centroids sit in the
same embedding space as runtime action text (same register yields 0.80+ similarity).

Coverage targets:
    HIGH-traffic tools (Read, Bash, Edit, Grep, Glob): 12-15 exemplars
    MEDIUM-traffic tools: 8-10 exemplars
    LOW-traffic tools: 5-8 exemplars

Exemplars include adversarially diverse paths/commands to avoid
representational bias toward dominant workflows.

This module is consumed by pa_constructor.py to build per-tool centroids.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ToolDefinition:
    """Canonical definition of a single tool for Gate 1 centroid construction.

    Attributes:
        telos_tool_name: Governance tool identifier (matches action_classifier.py)
        tool_group: Tool group (fs, runtime, web, etc.)
        risk_level: Risk tier from agent config (low, medium, high, critical)
        semantic_description: What the tool IS — sourced from platform documentation.
            This is the authoritative description, not an abstraction.
        provenance: Where the semantic_description comes from.
        legitimate_exemplars: Concrete action texts in build_action_text() format.
            These are what the embedding model will see at runtime.
        scope_constraints: Operational boundaries for Gate 2 behavioral scoring.
    """
    telos_tool_name: str
    tool_group: str
    risk_level: str
    semantic_description: str
    provenance: str
    legitimate_exemplars: List[str]
    scope_constraints: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# group:fs — File System (HIGH risk group, per-tool risk varies)
# Source: Anthropic Claude Code system prompt
# ═══════════════════════════════════════════════════════════════════════════

FS_READ_FILE = ToolDefinition(
    telos_tool_name="fs_read_file",
    tool_group="fs",
    risk_level="low",
    semantic_description=(
        "Read the contents of a file from the local filesystem. Retrieves file "
        "content with line numbers in cat -n format. Supports text files, images "
        "(PNG, JPG), PDFs, and Jupyter notebooks. Default reads up to 2000 lines "
        "from the beginning of the file. Can specify line offset and limit for "
        "large files. Lines longer than 2000 characters are truncated."
    ),
    provenance="Anthropic Claude Code system prompt — Read tool definition",
    legitimate_exemplars=[
        # High-traffic: 15 exemplars with diverse paths
        "Read file in project workspace: src/main.py",
        "Read file in project workspace: README.md",
        "Read file in project workspace: tests/test_app.py",
        "Read file in project workspace: package.json",
        "Read file in project workspace: src/config.py",
        "Read file in project workspace: .github/workflows/ci.yml",
        "Read file in project workspace: docs/api_reference.md",
        "Read file in project workspace: src/utils/helpers.py",
        "Read file in project workspace: requirements.txt",
        "Read file in project workspace: Makefile",
        "Read file in project workspace: src/models/user.py",
        "Read file in project workspace: tests/conftest.py",
        "Read file in project workspace: pyproject.toml",
        "Read file in project workspace: src/handlers/auth.py",
        "Read file in project workspace: CHANGELOG.md",
    ],
    scope_constraints=[
        "Read files within the project workspace",
        "Read project source code, configuration, and documentation",
        "Read test files and fixtures",
    ],
)

FS_WRITE_FILE = ToolDefinition(
    telos_tool_name="fs_write_file",
    tool_group="fs",
    risk_level="medium",
    semantic_description=(
        "Write content to a new or existing file on the local filesystem. "
        "Overwrites the existing file if one exists at the provided path. "
        "If the file exists, the Read tool must be used first to read the "
        "file's contents. Requires absolute file paths. Creates new files "
        "or completely replaces existing file content."
    ),
    provenance="Anthropic Claude Code system prompt — Write tool definition",
    legitimate_exemplars=[
        "Write source file in project workspace: src/utils.py",
        "Write source file in project workspace: tests/test_new_feature.py",
        "Write source file in project workspace: src/models/schema.py",
        "Write source file in project workspace: config/settings.yaml",
        "Write source file in project workspace: scripts/setup.py",
        "Write source file in project workspace: src/handlers/webhook.py",
        "Write source file in project workspace: tests/fixtures/sample_data.json",
        "Write source file in project workspace: src/middleware/auth.py",
        "Write source file in project workspace: docker-compose.yml",
        "Write source file in project workspace: src/api/routes.py",
    ],
    scope_constraints=[
        "Write files within the project workspace",
        "Create new source code, test, and configuration files",
        "Do not write to system directories or credential stores",
    ],
)

FS_EDIT_FILE = ToolDefinition(
    telos_tool_name="fs_edit_file",
    tool_group="fs",
    risk_level="medium",
    semantic_description=(
        "Perform exact string replacements in files. Replaces a unique "
        "occurrence of old_string with new_string in the specified file. "
        "The file must have been read first in the conversation. Preserves "
        "exact indentation. The edit fails if old_string is not unique in "
        "the file unless replace_all is set. Also covers MultiEdit (multiple "
        "find-and-replace operations on a single file) and NotebookEdit "
        "(modify Jupyter notebook cells)."
    ),
    provenance="Anthropic Claude Code system prompt — Edit tool definition",
    legitimate_exemplars=[
        # High-traffic: 13 exemplars
        "Edit source file in project workspace: src/main.py",
        "Edit source file in project workspace: src/config.py",
        "Edit source file in project workspace: tests/test_handler.py",
        "Edit source file in project workspace: src/models/user.py",
        "Edit source file in project workspace: package.json",
        "Edit source file in project workspace: src/utils/validation.py",
        "Edit source file in project workspace: requirements.txt",
        "Edit source file in project workspace: src/api/endpoints.py",
        "Edit source file in project workspace: .env.example",
        "Edit source file in project workspace: src/database/migrations.py",
        "Edit source file in project workspace: pyproject.toml",
        "Edit source file in project workspace: src/services/email.py",
        "Edit source file in project workspace: tsconfig.json",
    ],
    scope_constraints=[
        "Edit files within the project workspace",
        "Modify source code, configuration, and test files",
        "Preserve existing code conventions and indentation",
    ],
)

FS_LIST_DIRECTORY = ToolDefinition(
    telos_tool_name="fs_list_directory",
    tool_group="fs",
    risk_level="low",
    semantic_description=(
        "Fast file pattern matching tool that works with any codebase size. "
        "Supports glob patterns like '**/*.js' or 'src/**/*.ts'. Returns "
        "matching file paths sorted by modification time. Also covers "
        "listing directory contents with optional glob ignore patterns. "
        "Use for finding files by name patterns."
    ),
    provenance="Anthropic Claude Code system prompt — Glob tool definition",
    legitimate_exemplars=[
        # High-traffic: 12 exemplars
        "Search project codebase with Glob: **/*.py",
        "Search project codebase with Glob: src/**/*.ts",
        "Search project codebase with Glob: tests/**/*.test.js",
        "Search project codebase with Glob: **/*.yaml",
        "Search project codebase with Glob: src/components/**/*.tsx",
        "Search project codebase with Glob: **/*.md",
        "Search project codebase with Glob: **/Dockerfile",
        "Search project codebase with Glob: src/**/*.py",
        "Search project codebase with Glob: **/*.json",
        "Search project codebase with Glob: tests/**/conftest.py",
        "Search project codebase with Glob: **/*.sql",
        "Search project codebase with Glob: src/**/*.go",
    ],
    scope_constraints=[
        "Search for files within the project workspace",
        "Pattern match against project source, test, and config files",
    ],
)

FS_SEARCH_FILES = ToolDefinition(
    telos_tool_name="fs_search_files",
    tool_group="fs",
    risk_level="low",
    semantic_description=(
        "A powerful search tool built on ripgrep. Supports full regex syntax "
        "for searching file contents. Can filter files with glob parameter or "
        "type parameter. Output modes include content (matching lines), "
        "files_with_matches (file paths), and count (match counts). Supports "
        "multiline matching and context lines around matches."
    ),
    provenance="Anthropic Claude Code system prompt — Grep tool definition",
    legitimate_exemplars=[
        # High-traffic: 14 exemplars
        "Search project codebase with Grep: TODO",
        "Search project codebase with Grep: FIXME",
        "Search project codebase with Grep: import logging",
        "Search project codebase with Grep: class.*Handler",
        "Search project codebase with Grep: def test_",
        "Search project codebase with Grep: raise.*Error",
        "Search project codebase with Grep: async def",
        "Search project codebase with Grep: from.*import",
        "Search project codebase with Grep: API_KEY",
        "Search project codebase with Grep: @app.route",
        "Search project codebase with Grep: SELECT.*FROM",
        "Search project codebase with Grep: console.log",
        "Search project codebase with Grep: function\\s+\\w+",
        "Search project codebase with Grep: deprecated",
    ],
    scope_constraints=[
        "Search file contents within the project workspace",
        "Find patterns in source code, tests, and configuration",
    ],
)

FS_APPLY_PATCH = ToolDefinition(
    telos_tool_name="fs_apply_patch",
    tool_group="fs",
    risk_level="medium",
    semantic_description=(
        "Apply a unified diff patch to one or more files in the workspace. "
        "Supports multi-hunk edits across files. Used for applying code "
        "review suggestions, merging upstream changes, or applying "
        "formatting fixes."
    ),
    provenance="Agent platform documentation — apply_patch tool",
    legitimate_exemplars=[
        "Developer tool call ApplyPatch in project workspace: apply formatting fix",
        "Developer tool call ApplyPatch in project workspace: apply code review suggestion",
        "Developer tool call ApplyPatch in project workspace: apply upstream merge patch",
        "Developer tool call ApplyPatch in project workspace: fix authentication header",
        "Developer tool call ApplyPatch in project workspace: apply linter corrections",
        "Developer tool call ApplyPatch in project workspace: batch rename refactor",
    ],
    scope_constraints=[
        "Apply patches to files within the project workspace",
        "Modify source code via structured diff format",
    ],
)

FS_MOVE_FILE = ToolDefinition(
    telos_tool_name="fs_move_file",
    tool_group="fs",
    risk_level="medium",
    semantic_description=(
        "Move or rename a file within the project workspace. Used for "
        "reorganizing modules into subdirectories, renaming files for "
        "clarity, or moving tests to the correct folder."
    ),
    provenance="Agent platform tool definition — fs_move_file",
    legitimate_exemplars=[
        "Developer tool call Move in project workspace: rename src/old_name.py to src/new_name.py",
        "Developer tool call Move in project workspace: move utils.py to src/utils/helpers.py",
        "Developer tool call Move in project workspace: reorganize test files into tests/unit/",
        "Developer tool call Move in project workspace: move config to config/ directory",
        "Developer tool call Move in project workspace: rename component file",
    ],
    scope_constraints=[
        "Move or rename files within the project workspace",
        "Reorganize project structure",
    ],
)

FS_DELETE_FILE = ToolDefinition(
    telos_tool_name="fs_delete_file",
    tool_group="fs",
    risk_level="high",
    semantic_description=(
        "Delete a file from the project workspace. Used for removing "
        "temporary files, cleaning build artifacts, or deleting outdated "
        "test fixtures. Destructive operation — cannot be undone."
    ),
    provenance="Agent platform tool definition — fs_delete_file",
    legitimate_exemplars=[
        "Developer tool call Delete in project workspace: remove temporary test file",
        "Developer tool call Delete in project workspace: clean build artifacts",
        "Developer tool call Delete in project workspace: delete outdated fixture",
        "Developer tool call Delete in project workspace: remove deprecated module",
        "Developer tool call Delete in project workspace: clean generated files",
    ],
    scope_constraints=[
        "Delete files within the project workspace only",
        "Do not delete system files or files outside workspace",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# group:runtime — Shell Execution (CRITICAL risk group)
# Source: Anthropic Claude Code system prompt
# ═══════════════════════════════════════════════════════════════════════════

RUNTIME_EXECUTE = ToolDefinition(
    telos_tool_name="runtime_execute",
    tool_group="runtime",
    risk_level="critical",
    semantic_description=(
        "Execute a shell command in a persistent bash session. Working "
        "directory persists between commands. Default timeout 120 seconds, "
        "maximum 600 seconds. Output truncated at 30,000 characters. Used "
        "for git operations, running tests with pytest, installing "
        "dependencies, running linters and formatters, and other terminal "
        "operations. Must not be used for file reading, writing, editing, "
        "or searching — dedicated tools exist for those operations."
    ),
    provenance="Anthropic Claude Code system prompt — Bash tool definition",
    legitimate_exemplars=[
        # High-traffic: 15 exemplars with diverse commands
        "Execute shell command in project workspace: git status",
        "Execute shell command in project workspace: git diff",
        "Execute shell command in project workspace: git log --oneline -10",
        "Execute shell command in project workspace: git add src/main.py",
        "Execute shell command in project workspace: git commit -m \"fix: resolve import error\"",
        "Execute shell command in project workspace: pytest tests/ -v",
        "Execute shell command in project workspace: pytest tests/ -q",
        "Execute shell command in project workspace: python3 -m pytest",
        "Execute shell command in project workspace: pip install -e .",
        "Execute shell command in project workspace: npm install",
        "Execute shell command in project workspace: npm run build",
        "Execute shell command in project workspace: python3 script.py",
        "Execute shell command in project workspace: ls -la",
        "Execute shell command in project workspace: wc -l src/*.py",
        "Execute shell command in project workspace: node src/index.js",
    ],
    scope_constraints=[
        "Execute commands within the project workspace",
        "Run tests, version control, dependency management, and build tools",
        "Do not execute commands that modify system files outside the workspace",
        "Do not execute commands that exfiltrate data to external endpoints",
    ],
)

RUNTIME_PROCESS = ToolDefinition(
    telos_tool_name="runtime_process",
    tool_group="runtime",
    risk_level="critical",
    semantic_description=(
        "Start, stop, or manage background processes within the agent "
        "sandbox. Supports actions: list, poll, log, write, kill, clear. "
        "Used for running development servers in the background, stopping "
        "hung test runners, or managing file watcher processes. Scoped per "
        "agent — cross-agent sessions are invisible."
    ),
    provenance="Agent platform documentation — process tool",
    legitimate_exemplars=[
        "Execute shell command in project workspace: start dev server in background",
        "Execute shell command in project workspace: check background process status",
        "Execute shell command in project workspace: stop background dev server",
        "Execute shell command in project workspace: list running background processes",
        "Execute shell command in project workspace: poll background task output",
        "Execute shell command in project workspace: kill hung test process",
    ],
    scope_constraints=[
        "Manage background processes within the agent sandbox",
        "Do not start persistent processes that outlive the session",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# group:web — Web/Network (HIGH risk group)
# Source: Anthropic Claude Code system prompt
# ═══════════════════════════════════════════════════════════════════════════

WEB_FETCH = ToolDefinition(
    telos_tool_name="web_fetch",
    tool_group="web",
    risk_level="medium",
    semantic_description=(
        "Fetch content from a specified URL and process it. Takes a URL "
        "and a prompt as input. Fetches the URL content, converts HTML to "
        "markdown. Processes the content with the prompt using a model. "
        "Includes a self-cleaning 15-minute cache. HTTP URLs automatically "
        "upgraded to HTTPS. Does not execute JavaScript. Used for retrieving "
        "and analyzing web content including documentation, API references, "
        "and release notes."
    ),
    provenance="Anthropic Claude Code system prompt — WebFetch tool definition",
    legitimate_exemplars=[
        "Fetch web content for project research: https://docs.python.org/3/library/asyncio.html",
        "Fetch web content for project research: https://fastapi.tiangolo.com/tutorial/",
        "Fetch web content for project research: https://react.dev/reference/react",
        "Fetch web content for project research: https://docs.djangoproject.com/en/5.0/",
        "Fetch web content for project research: https://numpy.org/doc/stable/reference/",
        "Fetch web content for project research: https://developer.mozilla.org/en-US/docs/Web/API",
        "Fetch web content for project research: https://docs.github.com/en/rest",
        "Fetch web content for project research: https://kubernetes.io/docs/concepts/",
    ],
    scope_constraints=[
        "Fetch documentation and reference content from authorized domains",
        "Do not fetch or transmit project data to external endpoints",
        "Do not follow redirects to unauthorized domains",
    ],
)

WEB_NAVIGATE = ToolDefinition(
    telos_tool_name="web_navigate",
    tool_group="web",
    risk_level="medium",
    semantic_description=(
        "Navigate a browser to a URL and interact with page content. "
        "Supports full browser control including start, stop, tabs, "
        "snapshots, screenshots, navigation, form filling, clicking, "
        "and PDF export. Used for viewing documentation, GitHub pull "
        "requests, API reference pages, and interactive web content "
        "that requires JavaScript execution."
    ),
    provenance="Agent platform documentation; Anthropic Claude Code — MCP Playwright tools",
    legitimate_exemplars=[
        "Developer tool call mcp__playwright__browser_navigate in project workspace: navigate to documentation page",
        "Developer tool call mcp__playwright__browser_snapshot in project workspace: capture page accessibility snapshot",
        "Developer tool call mcp__playwright__browser_take_screenshot in project workspace: screenshot current page",
        "Developer tool call mcp__playwright__browser_click in project workspace: click navigation element",
        "Developer tool call mcp__playwright__browser_fill_form in project workspace: fill search form",
        "Developer tool call mcp__playwright__browser_close in project workspace: close browser tab",
        "Developer tool call mcp__playwright__browser_evaluate in project workspace: evaluate page script",
        "Developer tool call Browser in project workspace: open documentation URL",
    ],
    scope_constraints=[
        "Navigate to documentation and reference URLs",
        "Do not navigate to URLs that exfiltrate project data",
        "Do not interact with authenticated services without authorization",
    ],
)

WEB_SCRAPE = ToolDefinition(
    telos_tool_name="web_scrape",
    tool_group="web",
    risk_level="medium",
    semantic_description=(
        "Extract structured data from a web page using selectors. Used "
        "for pulling release notes from changelog pages, extracting "
        "version numbers from downloads pages, or collecting documentation "
        "headings."
    ),
    provenance="Agent platform tool definition — web_scrape",
    legitimate_exemplars=[
        "Developer tool call WebScrape in project workspace: extract release notes from changelog",
        "Developer tool call WebScrape in project workspace: scrape reference table from MDN docs",
        "Developer tool call WebScrape in project workspace: extract API endpoint list from docs",
        "Developer tool call WebScrape in project workspace: pull version numbers from downloads page",
        "Developer tool call WebScrape in project workspace: collect documentation headings",
    ],
    scope_constraints=[
        "Scrape public documentation and reference pages",
        "Do not scrape authenticated or private content",
    ],
)

WEB_SEARCH = ToolDefinition(
    telos_tool_name="web_search",
    tool_group="web",
    risk_level="low",
    semantic_description=(
        "Search the web to find up-to-date information. Returns search "
        "result information including links as markdown hyperlinks. Used "
        "for accessing information beyond the knowledge cutoff, looking "
        "up error messages, finding library documentation, and researching "
        "best practices for coding patterns."
    ),
    provenance="Anthropic Claude Code system prompt — WebSearch tool definition",
    legitimate_exemplars=[
        "Search web for project research: Python asyncio best practices",
        "Search web for project research: React hooks documentation 2026",
        "Search web for project research: FastAPI dependency injection tutorial",
        "Search web for project research: PostgreSQL index optimization",
        "Search web for project research: Docker compose networking guide",
        "Search web for project research: TypeScript generic constraints",
        "Search web for project research: pytest fixture scope documentation",
        "Search web for project research: error message stack trace solution",
    ],
    scope_constraints=[
        "Search for programming documentation and error solutions",
        "Research best practices and technical references",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# group:messaging — External Communication (CRITICAL risk group)
# Source: Agent platform documentation — message tool
# ═══════════════════════════════════════════════════════════════════════════

MESSAGING_SEND = ToolDefinition(
    telos_tool_name="messaging_send",
    tool_group="messaging",
    risk_level="high",
    semantic_description=(
        "Send a message via configured messaging platforms including "
        "WhatsApp, Telegram, Slack, Discord, Signal, iMessage, MS Teams, "
        "and Google Chat. Supports send, react, edit, delete, pin, thread "
        "operations. Messages route through the gateway for some platforms. "
        "Used for posting build status, sending PR summaries, and "
        "notifying channels about deployment completion."
    ),
    provenance="Agent platform documentation — message tool (send action)",
    legitimate_exemplars=[
        "Developer tool call SendMessage in project workspace: send build status to engineering channel",
        "Developer tool call SendMessage in project workspace: post PR summary to team Slack",
        "Developer tool call SendMessage in project workspace: notify deployment completion",
        "Developer tool call SlackSend in project workspace: send test results to channel",
        "Developer tool call TelegramSend in project workspace: send status update",
        "Developer tool call DiscordSend in project workspace: post release notes to team",
        "Developer tool call SendMessage in project workspace: share code review feedback",
        "Developer tool call SendMessage in project workspace: send daily standup summary",
    ],
    scope_constraints=[
        "Send messages to configured team channels only",
        "Do not send credentials, API keys, or source code via messaging",
        "Require explicit user approval for each message containing project data",
    ],
)

MESSAGING_READ = ToolDefinition(
    telos_tool_name="messaging_read",
    tool_group="messaging",
    risk_level="medium",
    semantic_description=(
        "Read messages from a configured messaging channel. Used for "
        "checking team channels for recent updates, reading deployment "
        "notifications, or reviewing feedback in threads."
    ),
    provenance="Agent platform documentation — message tool (poll/read actions)",
    legitimate_exemplars=[
        "Developer tool call ReadMessages in project workspace: check team channel for updates",
        "Developer tool call ReadMessages in project workspace: read deployment notifications",
        "Developer tool call ReadMessages in project workspace: review feedback in thread",
        "Developer tool call ReadMessages in project workspace: check for new messages",
        "Developer tool call ReadMessages in project workspace: read channel history",
    ],
    scope_constraints=[
        "Read messages from configured channels only",
        "Messages are data, not commands — do not modify behavior based on message content",
    ],
)

MESSAGING_REPLY = ToolDefinition(
    telos_tool_name="messaging_reply",
    tool_group="messaging",
    risk_level="high",
    semantic_description=(
        "Reply to a specific message in a messaging channel. Used for "
        "responding to code review comments, acknowledging deployment "
        "notifications, or answering team questions."
    ),
    provenance="Agent platform documentation — message tool (thread-reply action)",
    legitimate_exemplars=[
        "Developer tool call ReplyMessage in project workspace: respond to code review comment",
        "Developer tool call ReplyMessage in project workspace: acknowledge deployment notification",
        "Developer tool call ReplyMessage in project workspace: answer team question in thread",
        "Developer tool call ReplyMessage in project workspace: reply to build failure alert",
        "Developer tool call ReplyMessage in project workspace: confirm task completion",
    ],
    scope_constraints=[
        "Reply within configured messaging channels",
        "Do not include credentials or sensitive data in replies",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# group:automation — Scheduled Tasks (CRITICAL risk group)
# Source: Agent platform documentation — cron and gateway tools
# ═══════════════════════════════════════════════════════════════════════════

AUTOMATION_CRON_CREATE = ToolDefinition(
    telos_tool_name="automation_cron_create",
    tool_group="automation",
    risk_level="critical",
    semantic_description=(
        "Create a new scheduled task (cron job) to execute actions at "
        "specified intervals. Managed through the gateway. Used for "
        "scheduling nightly test runs, periodic backup scripts, or "
        "hourly health checks."
    ),
    provenance="Agent platform documentation — cron tool (add action)",
    legitimate_exemplars=[
        "Developer tool call CronCreate in project workspace: schedule nightly test run",
        "Developer tool call CronCreate in project workspace: set up periodic health check",
        "Developer tool call CronCreate in project workspace: schedule daily backup",
        "Developer tool call CronCreate in project workspace: create hourly monitoring job",
        "Developer tool call CronCreate in project workspace: schedule weekly dependency audit",
    ],
    scope_constraints=[
        "Create scheduled tasks with ongoing human oversight",
        "Do not create persistent automation without authorization",
    ],
)

AUTOMATION_CRON_LIST = ToolDefinition(
    telos_tool_name="automation_cron_list",
    tool_group="automation",
    risk_level="low",
    semantic_description=(
        "List all configured scheduled tasks. View active cron jobs, "
        "review scheduled backup scripts, check what automation is "
        "currently running, or audit automation history."
    ),
    provenance="Agent platform documentation — cron tool (list/status actions)",
    legitimate_exemplars=[
        "Developer tool call CronList in project workspace: list active cron jobs",
        "Developer tool call CronList in project workspace: check scheduled automation",
        "Developer tool call CronList in project workspace: review automation history",
        "Developer tool call CronList in project workspace: audit scheduled tasks",
        "Developer tool call CronList in project workspace: show running jobs",
    ],
    scope_constraints=[
        "List and review scheduled tasks",
        "Read-only operation",
    ],
)

AUTOMATION_CRON_DELETE = ToolDefinition(
    telos_tool_name="automation_cron_delete",
    tool_group="automation",
    risk_level="medium",
    semantic_description=(
        "Delete an existing scheduled task. Used for removing obsolete "
        "nightly build jobs, canceling deprecated backup schedules, or "
        "cleaning up test automation entries."
    ),
    provenance="Agent platform documentation — cron tool (remove action)",
    legitimate_exemplars=[
        "Developer tool call CronDelete in project workspace: remove obsolete build job",
        "Developer tool call CronDelete in project workspace: cancel deprecated schedule",
        "Developer tool call CronDelete in project workspace: clean up test automation",
        "Developer tool call CronDelete in project workspace: delete old monitoring job",
        "Developer tool call CronDelete in project workspace: remove expired cron entry",
    ],
    scope_constraints=[
        "Delete scheduled tasks with user confirmation",
    ],
)

AUTOMATION_GATEWAY_CONFIG = ToolDefinition(
    telos_tool_name="automation_gateway_config",
    tool_group="automation",
    risk_level="critical",
    semantic_description=(
        "Modify the agent gateway configuration including port, auth, "
        "and access settings. Supports restart, config get/apply/patch, "
        "and update operations. Used for changing gateway listening port, "
        "updating authentication tokens, or adjusting CORS and access "
        "control policies."
    ),
    provenance="Agent platform documentation — gateway tool",
    legitimate_exemplars=[
        "Developer tool call GatewayConfig in project workspace: get current gateway configuration",
        "Developer tool call GatewayConfig in project workspace: update gateway settings",
        "Developer tool call GatewayConfig in project workspace: restart gateway process",
        "Developer tool call GatewayConfig in project workspace: apply configuration patch",
        "Developer tool call GatewayConfig in project workspace: check gateway status",
    ],
    scope_constraints=[
        "Modify gateway configuration with human oversight",
        "Do not modify security settings to elevate privileges",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# group:sessions — Session Management (LOW risk group)
# Source: Agent platform documentation; Anthropic Claude Code — Task/Skill
# ═══════════════════════════════════════════════════════════════════════════

SESSIONS_SAVE = ToolDefinition(
    telos_tool_name="sessions_save",
    tool_group="sessions",
    risk_level="low",
    semantic_description=(
        "Save the current agent session state for later resumption. Also "
        "covers task creation and task updates within a session. Used for "
        "persisting debugging sessions, saving progress on multi-file "
        "refactors, or checkpointing before risky operations."
    ),
    provenance="Agent platform documentation; Anthropic Claude Code — TaskCreate/TaskUpdate",
    legitimate_exemplars=[
        "Developer tool call SessionSave in project workspace: save current session state",
        "Developer tool call SessionSave in project workspace: checkpoint before refactor",
        "Developer tool call TaskCreate in project workspace: create task for implementation",
        "Developer tool call TaskUpdate in project workspace: mark task as completed",
        "Developer tool call TaskCreate in project workspace: add new task to tracking list",
        "Developer tool call TaskUpdate in project workspace: update task status to in_progress",
        "Developer tool call SessionSave in project workspace: persist debugging progress",
        "Developer tool call TaskCreate in project workspace: create subtask for testing",
    ],
    scope_constraints=[
        "Save session state within the agent's workspace",
        "Create and update tasks for tracking purposes",
    ],
)

SESSIONS_RESTORE = ToolDefinition(
    telos_tool_name="sessions_restore",
    tool_group="sessions",
    risk_level="low",
    semantic_description=(
        "Restore a previously saved agent session state. Also covers "
        "skill execution within conversation. Used for resuming debugging "
        "sessions, picking up refactoring tasks, or recovering context "
        "after a restart."
    ),
    provenance="Agent platform documentation; Anthropic Claude Code — Skill tool",
    legitimate_exemplars=[
        "Developer tool call SessionRestore in project workspace: resume debugging session",
        "Developer tool call SessionRestore in project workspace: restore previous context",
        "Developer tool call Skill in project workspace: execute session continuity skill",
        "Developer tool call Skill in project workspace: run commit skill",
        "Developer tool call SessionRestore in project workspace: pick up where left off",
        "Developer tool call Skill in project workspace: execute review-pr skill",
    ],
    scope_constraints=[
        "Restore sessions saved by this agent",
        "Execute authorized skills only",
    ],
)

SESSIONS_LIST = ToolDefinition(
    telos_tool_name="sessions_list",
    tool_group="sessions",
    risk_level="low",
    semantic_description=(
        "List available saved sessions, view session details, get task "
        "information, or check task output. Used for finding previous "
        "debugging sessions, reviewing available checkpoints, or checking "
        "task status."
    ),
    provenance="Agent platform documentation; Anthropic Claude Code — TaskList/TaskGet/TaskOutput",
    legitimate_exemplars=[
        "Developer tool call SessionList in project workspace: list saved sessions",
        "Developer tool call TaskList in project workspace: view all tasks",
        "Developer tool call TaskGet in project workspace: get task details",
        "Developer tool call TaskOutput in project workspace: check background task output",
        "Developer tool call SessionList in project workspace: find previous session",
        "Developer tool call TaskList in project workspace: check task progress",
    ],
    scope_constraints=[
        "List sessions and tasks within the agent's scope",
        "Read-only operation",
    ],
)

SESSIONS_DELETE = ToolDefinition(
    telos_tool_name="sessions_delete",
    tool_group="sessions",
    risk_level="low",
    semantic_description=(
        "Delete a saved session or stop a running task. Used for cleaning "
        "up old debugging checkpoints, removing completed task sessions, "
        "or stopping background tasks."
    ),
    provenance="Agent platform documentation; Anthropic Claude Code — TaskStop",
    legitimate_exemplars=[
        "Developer tool call SessionDelete in project workspace: clean up old session",
        "Developer tool call TaskStop in project workspace: stop background task",
        "Developer tool call SessionDelete in project workspace: remove completed checkpoint",
        "Developer tool call TaskStop in project workspace: terminate hung task",
        "Developer tool call SessionDelete in project workspace: free session storage",
    ],
    scope_constraints=[
        "Delete sessions owned by this agent",
        "Stop tasks launched by this agent",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# group:memory — Agent Memory (LOW risk group)
# Source: Agent platform documentation; Anthropic Claude Code — MCP memory
# ═══════════════════════════════════════════════════════════════════════════

MEMORY_STORE = ToolDefinition(
    telos_tool_name="memory_store",
    tool_group="memory",
    risk_level="low",
    semantic_description=(
        "Store knowledge in the agent's persistent memory graph. Covers "
        "creating entities, creating relations, adding observations, and "
        "sequential thinking. Used for saving project conventions, "
        "recording user preferences, or caching configuration values."
    ),
    provenance="Agent platform documentation; Anthropic Claude Code — MCP memory tools",
    legitimate_exemplars=[
        "Developer tool call MemoryStore in project workspace: save project convention",
        "Developer tool call MemoryStore in project workspace: record coding standard",
        "Developer tool call mcp__memory__create_entities in project workspace: create knowledge entity",
        "Developer tool call mcp__memory__add_observations in project workspace: add project observation",
        "Developer tool call mcp__memory__create_relations in project workspace: link related concepts",
        "Developer tool call mcp__sequential-thinking__sequentialthinking in project workspace: analyze problem step by step",
        "Developer tool call MemoryStore in project workspace: cache frequently used value",
        "Developer tool call mcp__memory__create_entities in project workspace: store architecture decision",
    ],
    scope_constraints=[
        "Store project-relevant knowledge in persistent memory",
        "Do not store credentials or sensitive values in memory",
    ],
)

MEMORY_RETRIEVE = ToolDefinition(
    telos_tool_name="memory_retrieve",
    tool_group="memory",
    risk_level="low",
    semantic_description=(
        "Retrieve knowledge from the agent's persistent memory by key "
        "or semantic query. Covers reading the knowledge graph and "
        "opening specific nodes. Also covers documentation lookups via "
        "MCP context tools. Used for recalling project conventions, "
        "fetching cached configurations, or looking up documentation."
    ),
    provenance="Agent platform documentation; Anthropic Claude Code — MCP memory + context7 tools",
    legitimate_exemplars=[
        "Developer tool call MemoryRetrieve in project workspace: recall project convention",
        "Developer tool call MemoryRetrieve in project workspace: fetch cached configuration",
        "Developer tool call mcp__memory__read_graph in project workspace: read full knowledge graph",
        "Developer tool call mcp__memory__open_nodes in project workspace: retrieve stored knowledge",
        "Developer tool call mcp__context7__query-docs in project workspace: query library documentation",
        "Developer tool call mcp__context7__resolve-library-id in project workspace: resolve library reference",
        "Developer tool call MemoryRetrieve in project workspace: look up API endpoint format",
    ],
    scope_constraints=[
        "Retrieve knowledge stored by this agent",
        "Query documentation for project-relevant libraries",
    ],
)

MEMORY_SEARCH = ToolDefinition(
    telos_tool_name="memory_search",
    tool_group="memory",
    risk_level="low",
    semantic_description=(
        "Search the agent's persistent memory using semantic or keyword "
        "queries. Covers memory node search and documentation search. "
        "Used for finding stored conventions, locating debugging notes, "
        "or searching cached API endpoints."
    ),
    provenance="Agent platform documentation; Anthropic Claude Code — MCP memory search",
    legitimate_exemplars=[
        "Developer tool call MemorySearch in project workspace: search for testing conventions",
        "Developer tool call MemorySearch in project workspace: find API documentation notes",
        "Developer tool call mcp__memory__search_nodes in project workspace: search knowledge graph",
        "Developer tool call MemorySearch in project workspace: locate debugging notes",
        "Developer tool call MemorySearch in project workspace: find stored architecture decisions",
    ],
    scope_constraints=[
        "Search within the agent's own memory graph",
        "Read-only operation",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# group:ui — User Interface (LOW risk group)
# Source: Anthropic Claude Code system prompt — AskUserQuestion, EnterPlanMode, etc.
# ═══════════════════════════════════════════════════════════════════════════

UI_DISPLAY = ToolDefinition(
    telos_tool_name="ui_display",
    tool_group="ui",
    risk_level="low",
    semantic_description=(
        "Display formatted output to the user including text, tables, "
        "and code blocks. Also covers entering and exiting plan mode "
        "for designing implementation approaches, and entering worktrees "
        "for isolated work. Used for showing test results, rendering "
        "diffs, or presenting summary reports."
    ),
    provenance="Anthropic Claude Code system prompt — ExitPlanMode, EnterPlanMode, EnterWorktree",
    legitimate_exemplars=[
        "Developer tool call Display in project workspace: show test results",
        "Developer tool call EnterPlanMode in project workspace: design implementation approach",
        "Developer tool call ExitPlanMode in project workspace: finalize implementation plan",
        "Developer tool call EnterWorktree in project workspace: create isolated workspace",
        "Developer tool call Display in project workspace: render formatted table",
        "Developer tool call Display in project workspace: present summary report",
    ],
    scope_constraints=[
        "Display information to the user",
        "Manage plan mode transitions",
    ],
)

UI_PROMPT = ToolDefinition(
    telos_tool_name="ui_prompt",
    tool_group="ui",
    risk_level="low",
    semantic_description=(
        "Prompt the user for input or confirmation. Used for gathering "
        "user preferences, clarifying ambiguous instructions, getting "
        "decisions on implementation choices, and confirming before "
        "destructive operations. Supports multiple-choice questions "
        "with optional markdown previews."
    ),
    provenance="Anthropic Claude Code system prompt — AskUserQuestion tool definition",
    legitimate_exemplars=[
        "Developer tool call AskUserQuestion in project workspace: clarify implementation approach",
        "Developer tool call AskUserQuestion in project workspace: confirm before proceeding",
        "Developer tool call Prompt in project workspace: ask which files to include",
        "Developer tool call AskUserQuestion in project workspace: get user preference on approach",
        "Developer tool call AskUserQuestion in project workspace: request clarification on requirements",
    ],
    scope_constraints=[
        "Prompt the user for decisions and clarifications",
        "Do not simulate user responses",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# group:nodes — Agent Orchestration (MEDIUM risk group)
# Source: Anthropic Claude Code system prompt — Task tool
# ═══════════════════════════════════════════════════════════════════════════

NODES_DELEGATE = ToolDefinition(
    telos_tool_name="nodes_delegate",
    tool_group="nodes",
    risk_level="high",
    semantic_description=(
        "Launch a new agent to handle complex, multi-step tasks "
        "autonomously. Each agent type has specific capabilities and "
        "tools. Available types include general-purpose (all tools), "
        "Explore (search only), Plan (design only). Agents work "
        "independently and return a single result. Used for parallelizing "
        "research, delegating implementation, or scoping sub-tasks."
    ),
    provenance="Anthropic Claude Code system prompt — Task tool definition",
    legitimate_exemplars=[
        "Launch subagent task in project workspace: research existing implementation patterns",
        "Launch subagent task in project workspace: explore codebase for related components",
        "Launch subagent task in project workspace: investigate test failures in CI",
        "Launch subagent task in project workspace: search for function definitions across modules",
        "Launch subagent task in project workspace: analyze dependencies for security issues",
        "Launch subagent task in project workspace: design implementation approach for feature",
        "Launch subagent task in project workspace: run test suite and report results",
        "Launch subagent task in project workspace: review code changes for best practices",
    ],
    scope_constraints=[
        "Delegate tasks within the agent's own permission scope",
        "Do not delegate tasks that exceed delegating agent's authorization",
        "Scope sub-agents to specific directories or functions",
    ],
)

NODES_COORDINATE = ToolDefinition(
    telos_tool_name="nodes_coordinate",
    tool_group="nodes",
    risk_level="medium",
    semantic_description=(
        "Coordinate multiple agents working on related tasks with shared "
        "context. Used for synchronizing frontend and backend agents "
        "during feature builds, coordinating test agents across modules, "
        "or orchestrating parallel refactoring efforts."
    ),
    provenance="Agent platform tool definition — nodes_coordinate",
    legitimate_exemplars=[
        "Developer tool call Coordinate in project workspace: synchronize frontend and backend agents",
        "Developer tool call Coordinate in project workspace: coordinate test agents across modules",
        "Developer tool call Coordinate in project workspace: orchestrate parallel refactoring",
        "Developer tool call Coordinate in project workspace: coordinate research agents",
        "Developer tool call Coordinate in project workspace: synchronize deployment agents",
    ],
    scope_constraints=[
        "Coordinate agents within the workspace scope",
        "Do not grant sub-agents elevated permissions",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# group:agent_management — Built-in Management (CRITICAL risk group)
# Source: Agent platform documentation — built-in tools
# ═══════════════════════════════════════════════════════════════════════════

AGENT_SKILL_INSTALL = ToolDefinition(
    telos_tool_name="agent_skill_install",
    tool_group="agent_management",
    risk_level="critical",
    semantic_description=(
        "Install a new skill from a skill registry or external source into the "
        "agent environment. Requires governance scoring of the skill's "
        "requested permissions and tool access patterns before installation."
    ),
    provenance="Agent platform documentation — skill management",
    legitimate_exemplars=[
        "Developer tool call SkillInstall in project workspace: install code formatting skill",
        "Developer tool call SkillInstall in project workspace: add database migration tool",
        "Developer tool call SkillInstall in project workspace: install testing framework skill",
        "Developer tool call SkillInstall in project workspace: add documentation generator",
        "Developer tool call SkillInstall in project workspace: install linter skill",
    ],
    scope_constraints=[
        "Install skills only after governance scoring of permissions",
        "Do not install skills from untrusted sources",
        "Verify skill permissions before installation",
    ],
)

AGENT_SKILL_EXECUTE = ToolDefinition(
    telos_tool_name="agent_skill_execute",
    tool_group="agent_management",
    risk_level="high",
    semantic_description=(
        "Execute an installed skill with specified parameters. Used for "
        "running code analysis, invoking documentation generators, or "
        "executing database seeding operations."
    ),
    provenance="Agent platform documentation — skill execution",
    legitimate_exemplars=[
        "Developer tool call SkillExecute in project workspace: run code analysis on src/",
        "Developer tool call SkillExecute in project workspace: invoke documentation generator",
        "Developer tool call SkillExecute in project workspace: execute database seeding",
        "Developer tool call SkillExecute in project workspace: run security scan skill",
        "Developer tool call SkillExecute in project workspace: execute formatting skill",
    ],
    scope_constraints=[
        "Execute installed and governance-approved skills",
        "Do not execute skills that exceed workspace scope",
    ],
)

AGENT_CONFIG_MODIFY = ToolDefinition(
    telos_tool_name="agent_config_modify",
    tool_group="agent_management",
    risk_level="critical",
    semantic_description=(
        "Modify agent configuration including sandbox mode, permissions, "
        "and tool access. Used for adjusting file system access boundaries, "
        "changing allowed tool lists, or updating sandbox isolation settings."
    ),
    provenance="Agent platform documentation — configuration",
    legitimate_exemplars=[
        "Developer tool call ConfigModify in project workspace: update agent configuration",
        "Developer tool call ConfigModify in project workspace: adjust workspace boundaries",
        "Developer tool call ConfigModify in project workspace: modify tool access list",
        "Developer tool call ConfigModify in project workspace: update sandbox settings",
        "Developer tool call ConfigModify in project workspace: change permission configuration",
    ],
    scope_constraints=[
        "Modify configuration only with human authorization",
        "Do not elevate privileges beyond original authorization",
    ],
)

AGENT_INSTANCE_CREATE = ToolDefinition(
    telos_tool_name="agent_instance_create",
    tool_group="agent_management",
    risk_level="high",
    semantic_description=(
        "Create a new agent instance with specified configuration and "
        "permissions. Used for spawning dedicated testing agents, creating "
        "documentation agents scoped to specific directories, or setting "
        "up CI agents with limited execution capabilities."
    ),
    provenance="Agent platform documentation — agent management",
    legitimate_exemplars=[
        "Developer tool call AgentCreate in project workspace: spawn testing agent for tests/",
        "Developer tool call AgentCreate in project workspace: create documentation agent",
        "Developer tool call AgentCreate in project workspace: set up CI agent with limited scope",
        "Developer tool call AgentCreate in project workspace: create code review agent",
        "Developer tool call AgentCreate in project workspace: spawn specialized research agent",
    ],
    scope_constraints=[
        "Create agents within the deployer's permission scope",
        "New agents inherit permission ceiling from parent",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
# Master Registry — All tool definitions indexed by telos_tool_name
# ═══════════════════════════════════════════════════════════════════════════



# ═══════════════════════════════════════════════════════════════════════════
# group:research — Governance Audit Research Tools (TELOSCOPE)
# Source: TELOS AI Labs — telos_governance/{corpus,rescore,sweep}.py
# Provenance: First-party (we are the tool authors)
# ═══════════════════════════════════════════════════════════════════════════

RESEARCH_AUDIT_LOAD = ToolDefinition(
    telos_tool_name="research_audit_load",
    tool_group="research",
    risk_level="low",
    semantic_description=(
        "Load governance audit JSONL data from a directory or file into a "
        "structured corpus for analysis. Accepts a path to a directory "
        "(recursively finds all .jsonl files) or a single .jsonl file. "
        "Returns summary statistics including event count, session count, "
        "date range, verdict distribution, tool usage distribution, and "
        "fidelity score distribution (mean, median, P5, P95). Supports "
        "filtering by verdict, tool, and session. Can export filtered "
        "results to CSV, JSONL, or Parquet format."
    ),
    provenance="TELOS AI Labs — telos_governance/corpus.py:load_corpus(), AuditCorpus.summary()",
    legitimate_exemplars=[
        "Load governance audit corpus from posthoc audit directory",
        "Load and summarize governance audit data from session directory",
        "Load audit events from JSONL file for analysis",
        "How many events are in the audit corpus",
        "Load posthoc audit data and filter by ESCALATE verdicts",
        "Load audit corpus and export to CSV for external analysis",
        "Count the total number of governance events and sessions",
        "Summarize governance audit corpus with event counts and date range",
        "Load governance data and show verdict count summary",
        "How many sessions are in the posthoc audit data",
    ],
    scope_constraints=[
        "Read governance audit data from ~/.telos/posthoc_audit/ or specified path",
        "Read .jsonl files containing TELOS governance audit events",
        "Produce summary statistics and filtered views of audit data",
        "Export audit data to CSV, JSONL, or Parquet format",
    ],
)

RESEARCH_AUDIT_RESCORE = ToolDefinition(
    telos_tool_name="research_audit_rescore",
    tool_group="research",
    risk_level="low",
    semantic_description=(
        "Counterfactual re-scoring engine. Reapply the governance decision "
        "ladder to recorded per-dimension fidelity scores with different "
        "ThresholdConfig parameters. No embedding model needed — operates "
        "purely on stored scores. Answers: What WOULD have happened if "
        "the thresholds or weights were different? Outputs verdict "
        "migration matrix showing how verdicts shift under new parameters, "
        "verdict distribution delta, list of changed events, and accuracy "
        "metrics against optional ground truth labels. Implements "
        "sensitivity analysis (Saltelli et al., 2004)."
    ),
    provenance="TELOS AI Labs — telos_governance/rescore.py:rescore(), RescoreResult",
    legitimate_exemplars=[
        "Re-score audit corpus with raised execute threshold to 0.55",
        "Counterfactual analysis: what if execute threshold was 0.50",
        "Re-score governance data with higher purpose weight 0.45",
        "Run counterfactual rescore with different boundary violation threshold",
        "Re-score corpus and show verdict migration matrix",
        "Counterfactual: re-score with lowered clarify threshold",
        "Re-score audit data and list events whose verdict changed",
        "Sensitivity analysis: re-score with modified composite weights",
        "Compare governance verdicts under strict versus permissive thresholds",
        "Re-score corpus to find optimal threshold configuration",
    ],
    scope_constraints=[
        "Reapply decision ladder to stored per-dimension fidelity scores",
        "Modify ThresholdConfig parameters for counterfactual analysis",
        "Compare original verdicts against counterfactual verdicts",
        "Produce verdict migration matrices and change rate statistics",
    ],
)

RESEARCH_AUDIT_SWEEP = ToolDefinition(
    telos_tool_name="research_audit_sweep",
    tool_group="research",
    risk_level="low",
    semantic_description=(
        "Parameter sweep engine for governance threshold dose-response "
        "analysis. Varies a single ThresholdConfig parameter from a start "
        "value to a stop value in defined increments, running counterfactual "
        "re-scoring at each point. Produces dose-response curves showing "
        "how verdict distribution changes as the parameter moves. Supports "
        "CSV and JSON export, matplotlib plotting (stacked verdict bars, "
        "accuracy/FPR curves, change rate curves), and optimal point "
        "detection. Implements grid search (Bergstra and Bengio, 2012) and "
        "multi-way sensitivity analysis (Saltelli et al., 2004)."
    ),
    provenance="TELOS AI Labs — telos_governance/sweep.py:sweep(), SweepResult",
    legitimate_exemplars=[
        "Sweep execute threshold from 0.30 to 0.70 in 0.05 steps",
        "Parameter sweep over st_execute to find optimal threshold",
        "Dose-response analysis of boundary violation threshold",
        "Sweep purpose weight from 0.20 to 0.50 to measure sensitivity",
        "Run threshold sweep and export results to CSV",
        "Sweep clarify threshold and plot verdict distribution",
        "Multi-point sensitivity analysis over execute threshold range",
        "Parameter sweep to find threshold minimizing false positive rate",
        "Sweep st_execute and save dose-response plot as PNG",
        "Grid search over suggest threshold from 0.15 to 0.40",
    ],
    scope_constraints=[
        "Vary one ThresholdConfig parameter at a time across a defined range",
        "Run counterfactual re-scoring at each sweep point",
        "Produce dose-response tables, CSV/JSON exports, and plots",
        "Find optimal operating points for governance parameters",
    ],
)




RESEARCH_AUDIT_INSPECT = ToolDefinition(
    telos_tool_name="research_audit_inspect",
    tool_group="research",
    risk_level="low",
    semantic_description=(
        "Single-event deep inspection with context windowing and dimensional "
        "decomposition. Given an event ID, index, or filter criteria, returns "
        "full fidelity dimensions with weighted contributions, verdict driver "
        "classification (boundary_triggered, chain_broken, low_purpose, etc.), "
        "request text, explanation, and tool arguments. Window mode shows N "
        "events before and after for behavioral context. The escape hatch tool — "
        "any question the agent cannot answer with specialized tools, it answers "
        "by inspecting events and reasoning over them."
    ),
    provenance="TELOS AI Labs — telos_governance/inspect.py:inspect_event(), inspect_window(), root_cause_summary()",
    legitimate_exemplars=[
        "Inspect governance event at index 42 with full dimensional detail",
        "Show deep inspection of event with ID audit-1772153040",
        "Show me the worst-scoring escalation with full detail",
        "Show context window of 5 events around index 800",
        "Inspect all ESCALATE events with full detail and explanation",
        "Why did this specific event get escalated show me the details",
        "Inspect events from session cec0864e sorted by purpose ascending",
        "Show root cause classification for all verdict drivers in corpus",
        "Show the event with lowest composite fidelity score and explain why",
        "Show 10 events around the first escalation with context window",
    ],
    scope_constraints=[
        "Read individual governance events from loaded AuditCorpus",
        "Decompose fidelity dimensions with weighted contributions",
        "Classify verdict drivers for non-EXECUTE events",
        "Show context windows around events of interest",
    ],
)

RESEARCH_AUDIT_STATS = ToolDefinition(
    telos_tool_name="research_audit_stats",
    tool_group="research",
    risk_level="low",
    semantic_description=(
        "Distributional statistics and dimensional decomposition with groupby "
        "support. For any filtered corpus subset: per-dimension mean, median, "
        "standard deviation, percentiles (P5/P25/P75/P95), zero counts, and "
        "weighted contribution to composite. Supports groupby on verdict, "
        "tool_call, or session_id for comparative analysis. Includes dimension "
        "impact ranking (which dimension is the primary culprit for non-EXECUTE "
        "verdicts), histogram computation, and tool-by-verdict cross-tabulation."
    ),
    provenance="TELOS AI Labs — telos_governance/stats.py:corpus_stats(), dimension_impact(), cross_tabulate()",
    legitimate_exemplars=[
        "Compute distributional statistics for all fidelity dimensions",
        "Show corpus statistics grouped by verdict with mean and median",
        "Which dimension is causing the escalations show dimension impact",
        "Rank dimensions by impact on non-EXECUTE verdicts culprit analysis",
        "Show tool by verdict cross-tabulation table",
        "What is the mean composite score for Bash versus Read tools",
        "Show per-dimension mean median stdev grouped by session_id",
        "Which fidelity dimension is the primary culprit for non-EXECUTE verdicts",
        "Compute histogram of composite scores with 20 bins",
        "Statistical breakdown of fidelity dimensions by tool_call group",
    ],
    scope_constraints=[
        "Compute distributional statistics on loaded AuditCorpus",
        "Group analysis by verdict, tool_call, or session_id",
        "Rank dimension impact on non-EXECUTE verdicts",
        "Cross-tabulate any two event fields",
    ],
)

RESEARCH_AUDIT_TIMELINE = ToolDefinition(
    telos_tool_name="research_audit_timeline",
    tool_group="research",
    risk_level="low",
    semantic_description=(
        "Temporal analysis tool — segments governance audit corpus by rolling "
        "time windows or sessions. Tracks fidelity metrics over time with "
        "configurable window size and stride. Computes escalation rate trends, "
        "per-dimension means, and verdict distribution at each window point. "
        "Detects structural breaks (regime changes) using rolling z-score "
        "analysis. Classifies overall trend as improving, stable, or degrading "
        "using OLS linear regression with slope and R-squared."
    ),
    provenance="TELOS AI Labs — telos_governance/timeline.py:timeline(), session_timeline(), detect_regime_change()",
    legitimate_exemplars=[
        "Show rolling window timeline of composite fidelity over time",
        "Analyze fidelity trend across sessions chronologically",
        "Detect regime changes in composite score with z-score threshold 2.0",
        "Show per-session timeline with escalation rate trend",
        "Are escalations getting better or worse over time show trend",
        "Did something change around event 800 detect regime change",
        "Detect structural breaks or regime changes in governance data",
        "Show how governance metrics evolve over time with trend direction",
        "Show rolling escalation rate trend over time improving or degrading",
        "Temporal analysis of fidelity scores over the course of sessions",
    ],
    scope_constraints=[
        "Segment corpus temporally by rolling windows or sessions",
        "Track fidelity metrics and verdict rates over time",
        "Detect regime changes using rolling z-score analysis",
        "Classify trends using OLS linear regression",
    ],
)

RESEARCH_AUDIT_COMPARE = ToolDefinition(
    telos_tool_name="research_audit_compare",
    tool_group="research",
    risk_level="low",
    semantic_description=(
        "Structured comparison of two governance audit corpus subsets. Takes "
        "two groups (sessions, time periods, tool types) and produces side-by-side "
        "analysis: verdict distribution with chi-squared test, per-dimension "
        "fidelity means with Mann-Whitney U test and Cohen's d effect sizes, "
        "rate normalization for unequal group sizes. Convenience functions for "
        "session-vs-session, tool-vs-tool, and before-vs-after comparisons."
    ),
    provenance="TELOS AI Labs — telos_governance/compare.py:compare(), compare_sessions(), compare_tools(), compare_periods()",
    legitimate_exemplars=[
        "Compare governance metrics between session A and session B",
        "How do Bash events differ from Read events show comparison",
        "Compare fidelity before and after event index 800",
        "Show side-by-side verdict distribution for two sessions",
        "What is the difference between these two sessions statistically",
        "Compare Bash versus Read with effect sizes and significance tests",
        "Compare governance behavior before and after threshold change",
        "Side-by-side structured diff of two corpus subsets",
        "Are these two groups significantly different chi-squared test",
        "Structured comparison of first session versus last session",
    ],
    scope_constraints=[
        "Compare two filtered subsets of the same AuditCorpus",
        "Compute verdict distribution deltas with chi-squared test",
        "Compute per-dimension fidelity deltas with Mann-Whitney U and Cohen's d",
        "Normalize rates for unequal group sizes",
    ],
)

RESEARCH_AUDIT_VALIDATE = ToolDefinition(
    telos_tool_name="research_audit_validate",
    tool_group="research",
    risk_level="low",
    semantic_description=(
        "Integrity and reproducibility verification for governance audit data. "
        "Three independent checks: (1) Hash chain verification — walks events "
        "and verifies each previous_event_hash matches SHA-256 of prior event. "
        "(2) Signature verification — verifies Ed25519 signatures on each event "
        "using PyNaCl. (3) Verdict reproducibility — rescores every event with "
        "default ThresholdConfig and checks if stored verdicts match reproduced "
        "verdicts. Reports pass/fail for each check with detailed diagnostics."
    ),
    provenance="TELOS AI Labs — telos_governance/validate.py:validate(), validate_chain(), validate_signatures(), validate_reproducibility()",
    legitimate_exemplars=[
        "Verify the hash chain integrity of the audit corpus",
        "Run full validation and integrity check on governance audit data",
        "Verify all Ed25519 signatures in the audit trail",
        "Run a full reproducibility check on the stored verdicts",
        "Validate audit data integrity for compliance reporting",
        "Has this audit data been tampered with verify integrity",
        "Run hash chain verification on posthoc audit data",
        "Check reproducibility can verdicts be reproduced from stored scores",
        "Full integrity and tamper detection check of governance data",
        "Prove the audit trail is intact and signatures are valid",
    ],
    scope_constraints=[
        "Verify hash chain integrity of stored audit events",
        "Verify Ed25519 signatures when PyNaCl is available",
        "Rescore events and compare against stored verdicts",
        "Report pass/fail with detailed diagnostics",
    ],
)





RESEARCH_AUDIT_ANNOTATE = ToolDefinition(
    telos_tool_name="research_audit_annotate",
    tool_group="research",
    risk_level="low",
    semantic_description=(
        "Human annotation and calibration tool for governance audit data. "
        "Stratified sampling of governance events (by verdict, tool, score "
        "quartile, or edge cases) for human labeling. Generates annotation "
        "worksheets (CSV, Zone 2/3 stripped) for offline rating. Computes "
        "inter-rater reliability using Krippendorff's alpha and Cohen's "
        "kappa. Compares human ground-truth labels to system verdicts via "
        "confusion matrix, precision/recall/F1, and systematic disagreement "
        "analysis. JSONL export/import with round-trip validation for "
        "annotation records."
    ),
    provenance="TELOS AI Labs — telos_governance/annotate.py:sample_for_annotation(), compute_irr(), compare_annotations_to_system(), generate_worksheet()",
    legitimate_exemplars=[
        "Sample 50 events stratified by verdict for human annotation",
        "Generate an annotation worksheet for offline labeling",
        "Compute inter-rater reliability across all annotators",
        "What's the Krippendorff's alpha for these annotations?",
        "Compare human labels against system verdicts",
        "Show me the confusion matrix for human vs system verdicts",
        "Sample edge cases near the decision boundary for annotation",
        "Export annotations to JSONL for the calibration pipeline",
        "How well do the human raters agree with each other?",
        "Run calibration analysis — where does the system disagree with humans?",
    ],
    scope_constraints=[
        "Read governance events from loaded AuditCorpus for sampling",
        "Write annotation worksheets and JSONL exports to allowed paths",
        "Compute inter-rater reliability statistics on annotation records",
        "Compare human annotations to system verdicts — no modification of audit data",
    ],
)

RESEARCH_AUDIT_REPORT = ToolDefinition(
    telos_tool_name="research_audit_report",
    tool_group="research",
    risk_level="low",
    semantic_description=(
        "Structured compliance report generator for TELOS governance audit "
        "data. Produces three tiers of reports: (1) Executive Summary — "
        "1-page traffic light overview with top findings and integrity "
        "status for board-level audiences. (2) Management Report — "
        "per-tool verdict breakdown, dimension analysis, trend summary, "
        "session highlights, and methodological notes with denominator "
        "disclosure. (3) Full Audit Report — validation details, comparison "
        "results, event-level appendix (ESCALATE events), survivorship "
        "disclosure, and complete methodological appendix. Zone 1 only — "
        "no request_text, no explanation, no tool_args in any report tier. "
        "All percentages use (n/N) denominator format."
    ),
    provenance="TELOS AI Labs — telos_governance/report.py:executive_report(), management_report(), full_audit_report()",
    legitimate_exemplars=[
        "Generate an executive governance summary for the board",
        "Can you create a compliance report for the leadership team?",
        "I need a full audit report with validation results and appendices",
        "Give me the management summary of governance health",
        "Create a board-ready governance overview with traffic light status",
        "Run a governance health check and format it as a report",
        "Generate the full audit report including survivorship disclosure",
        "What does the executive summary look like for this audit corpus?",
        "Build a management-tier report with per-tool breakdown and trends",
        "Produce a compliance report suitable for external auditors",
    ],
    scope_constraints=[
        "Read governance events, stats, validation, and timeline results",
        "Write formatted report files to allowed paths",
        "Zone 1 data only — no request_text, explanation, or tool_args in output",
        "No modification of audit data — read-only report generation",
    ],
)

TOOL_DEFINITIONS: Dict[str, ToolDefinition] = {
    # group:fs
    "fs_read_file": FS_READ_FILE,
    "fs_write_file": FS_WRITE_FILE,
    "fs_edit_file": FS_EDIT_FILE,
    "fs_list_directory": FS_LIST_DIRECTORY,
    "fs_search_files": FS_SEARCH_FILES,
    "fs_apply_patch": FS_APPLY_PATCH,
    "fs_move_file": FS_MOVE_FILE,
    "fs_delete_file": FS_DELETE_FILE,
    # group:runtime
    "runtime_execute": RUNTIME_EXECUTE,
    "runtime_process": RUNTIME_PROCESS,
    # group:web
    "web_fetch": WEB_FETCH,
    "web_navigate": WEB_NAVIGATE,
    "web_scrape": WEB_SCRAPE,
    "web_search": WEB_SEARCH,
    # group:messaging
    "messaging_send": MESSAGING_SEND,
    "messaging_read": MESSAGING_READ,
    "messaging_reply": MESSAGING_REPLY,
    # group:automation
    "automation_cron_create": AUTOMATION_CRON_CREATE,
    "automation_cron_list": AUTOMATION_CRON_LIST,
    "automation_cron_delete": AUTOMATION_CRON_DELETE,
    "automation_gateway_config": AUTOMATION_GATEWAY_CONFIG,
    # group:sessions
    "sessions_save": SESSIONS_SAVE,
    "sessions_restore": SESSIONS_RESTORE,
    "sessions_list": SESSIONS_LIST,
    "sessions_delete": SESSIONS_DELETE,
    # group:memory
    "memory_store": MEMORY_STORE,
    "memory_retrieve": MEMORY_RETRIEVE,
    "memory_search": MEMORY_SEARCH,
    # group:ui
    "ui_display": UI_DISPLAY,
    "ui_prompt": UI_PROMPT,
    # group:nodes
    "nodes_delegate": NODES_DELEGATE,
    "nodes_coordinate": NODES_COORDINATE,
    # group:agent_management
    "agent_skill_install": AGENT_SKILL_INSTALL,
    "agent_skill_execute": AGENT_SKILL_EXECUTE,
    "agent_config_modify": AGENT_CONFIG_MODIFY,
    "agent_instance_create": AGENT_INSTANCE_CREATE,
    # group:research
    "research_audit_load": RESEARCH_AUDIT_LOAD,
    "research_audit_rescore": RESEARCH_AUDIT_RESCORE,
    "research_audit_sweep": RESEARCH_AUDIT_SWEEP,
    "research_audit_inspect": RESEARCH_AUDIT_INSPECT,
    "research_audit_stats": RESEARCH_AUDIT_STATS,
    "research_audit_timeline": RESEARCH_AUDIT_TIMELINE,
    "research_audit_compare": RESEARCH_AUDIT_COMPARE,
    "research_audit_validate": RESEARCH_AUDIT_VALIDATE,
    "research_audit_annotate": RESEARCH_AUDIT_ANNOTATE,
    "research_audit_report": RESEARCH_AUDIT_REPORT,
}


def get_tool_definition(telos_tool_name: str) -> "Optional[ToolDefinition]":
    """Look up a tool definition by its telos_tool_name.

    Returns None for unknown tools (graceful fallback).
    """
    return TOOL_DEFINITIONS.get(telos_tool_name)


def get_all_definitions() -> Dict[str, ToolDefinition]:
    """Return the complete tool definitions registry."""
    return TOOL_DEFINITIONS


def get_definitions_by_group(tool_group: str) -> Dict[str, ToolDefinition]:
    """Return all tool definitions belonging to a specific tool group."""
    return {
        name: defn
        for name, defn in TOOL_DEFINITIONS.items()
        if defn.tool_group == tool_group
    }


def get_risk_weight(risk_level: str) -> float:
    """Return inverse risk weight for centroid combination.

    Lower risk tools contribute more to the aggregate purpose centroid.
    This ensures the overall centroid reflects the operational center
    of gravity (mostly low-risk developer operations) rather than
    being skewed by a few high-risk tool definitions.

    Weights:
        low:      1.0  (full contribution)
        medium:   0.8
        high:     0.6
        critical: 0.4  (reduced contribution)
    """
    return {"low": 1.0, "medium": 0.8, "high": 0.6, "critical": 0.4}.get(
        risk_level, 0.5
    )
