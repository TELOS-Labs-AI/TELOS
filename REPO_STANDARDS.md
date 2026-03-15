# Repository Standards -- OpenClaw Autonomous Operations

> **This document governs how autonomous agents maintain this repository.**
> Violations are governance events. Repeated violations trigger escalation.

## The Principle

This codebase is a professional product, not a scratchpad. Every commit, every file, every line of code reflects the quality standard of TELOS AI Labs. Autonomous agents are held to the same standard as human engineers -- higher, because they can be more consistent.

## Commit Discipline

### Required

- Conventional Commits format on every commit (see CONTRIBUTING.md)
- One logical change per commit
- Subject under 72 characters, body at 80
- Body explains *why*, diff explains *what*

### Forbidden

- `"update files"`, `"fix stuff"`, `"wip"`, `"misc changes"` -- meaningless commit messages
- Commits that mix unrelated changes
- Commits containing secrets, tokens, or credentials
- Commits containing build artifacts or generated files
- Empty commits
- Commits that break tests

## File Discipline

### Required

- Every file has a purpose. If it exists, something references it.
- New modules get an entry in README.md
- Removed modules get their README entry removed
- Configuration files are documented (what each field does)

### Forbidden

- Orphan files (created but never imported/referenced)
- Dead code left behind after refactoring
- Duplicate files (same content, different names)
- Temporary/debug files committed to the repo
- Files over 1000 lines without documented justification

## Code Discipline

### Required

- Follow existing patterns in the file you're editing
- Maintain type hints if the module uses them
- Error handling appropriate to the context (fail-closed for security, fail-safe for UX)
- Thread safety documented for concurrent code

### Forbidden

- Silent exception swallowing (`except: pass`)
- Unused imports
- Commented-out code blocks (delete it; git has history)
- `print()` for debugging (use logging)
- Hardcoded secrets or environment-specific paths

## Documentation Discipline

### Required

- README.md stays current with module structure
- HANDOFF document updated at end of every session
- Architecture decisions documented in commit body or docs/
- Breaking changes called out explicitly in commit message

### Forbidden

- Stale documentation that contradicts the code
- Documentation that restates the code without adding insight
- Auto-generated docs committed without review

## Governance Integration

### Required

- Governance events are append-only. Never modify historical events.
- Audit trail integrity maintained (hash chains intact)
- PA compliance checked before dispatch operations
- Escalation paths tested after changes to escalation code

### Forbidden

- Modifying or deleting governance event records
- Bypassing escalation for convenience
- Committing changes to governance code without review

## Enforcement

When OpenClaw operates autonomously:

1. **Pre-commit self-check**: Before every commit, verify against this document.
2. **Session cleanup**: Before handing off, scan for orphan files, dead code, stale docs.
3. **Periodic health check**: Every 10 commits, run a full repo hygiene pass.
4. **Violation logging**: If a standard is violated (even by yourself), log it as a governance event and fix it.

## Metrics

Track these per session:

- Commits made (should be granular, not monolithic)
- Files created vs files removed (net growth should be justified)
- Test coverage delta (should not decrease)
- Documentation currency (README matches reality)
- Orphan file count (should be zero)
