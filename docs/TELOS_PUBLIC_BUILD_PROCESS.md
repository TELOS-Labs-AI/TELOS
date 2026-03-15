# TELOS Public Build Process

## Purpose

The public TELOS repository (TELOS-Labs-AI/telos on GitHub) had become architecturally outdated. Over time, the codebase accumulated structural debt that no longer reflected the current state of the framework. Meanwhile, telos was developed as a clean, security-audited implementation containing the full TELOS architecture.

This document records the process of deriving a new public repository from telos by extracting tracked files and removing all sensitive material -- agentic governance IP, TKeys/privacy components, business strategy documents, and internal research.

The result is a public codebase that accurately represents the TELOS Governance Observatory (DEMO and BETA tabs) without exposing proprietary or pre-publication work.

## Date

2026-02-09

## Source

- **Repository**: telos (github.com/TELOS-Labs-AI/telos)
- **Commit**: f9b149e
- **Local path**: Project root directory

---

## Method

### Step 1: Safety Checkpoint on TELOS_Master

Before making any changes, the existing public repository was preserved:

```bash
cd /Users/brunnerjf/Desktop/TELOS_Master
git tag v3.0-pre-rewrite
git push origin v3.0-pre-rewrite
```

This tag serves as a permanent rollback point. The entire pre-rewrite state of the public repo can be restored from this tag at any time.

### Step 2: Extract Tracked Files from telos

```bash
mkdir -p /Users/brunnerjf/Desktop/telos_public_build
cd /path/to/telos
git archive HEAD | tar -x -C /Users/brunnerjf/Desktop/telos_public_build/
```

`git archive HEAD` exports only tracked files (respecting `.gitignore`), producing a clean snapshot without `.git` history, stale artifacts, or ignored files.

### Step 3: Delete Sensitive Files

All files containing proprietary IP, private keys infrastructure, business strategy, and unpublished research were removed. See the **Files Removed** section below for the full categorized list.

### Step 4: Scrub Agentic References from Remaining Files

Files that remained in the public build but contained references to agentic governance, TKeys, or other sensitive components were edited to remove those references. This included:

- Removing import statements for agentic modules
- Removing agentic tab rendering from the Streamlit UI
- Removing agentic entries from package configuration
- Removing agentic test references from CI workflows
- Updating changelogs and documentation to omit agentic details

### Step 5: Rewrite Public-Facing Documentation

- **README.md** -- Rewritten for a public audience. Describes the TELOS Governance Observatory with DEMO and BETA functionality. No mention of agentic governance or TKeys.
- **CLAUDE.md** -- Updated to reflect the public repository structure and available commands. Removed references to private modules.

### Step 6: Initialize Fresh Git History and Push

```bash
cd /Users/brunnerjf/Desktop/telos_public_build
git init
git add -A
git commit -m "TELOS Governance Observatory v3.0 - public release (derived from Hardened)"
git remote add origin https://github.com/TELOS-Labs-AI/telos.git
git push --force-with-lease origin HEAD:main
```

The public repo receives a clean, single-commit history. The old history is preserved under the `v3.0-pre-rewrite` tag.

---

## Files Removed

### Category A: Agentic Governance IP

These files contain the proprietary agentic governance implementation -- the core differentiating IP of the TELOS framework.

- `telos_governance/agentic_*.py` -- All agentic governance modules
- `telos_governance/intelligence_layer.py` -- Governance telemetry collection (IntelligenceCollector, IntelligenceConfig)
- `telos_governance/cli.py` -- CLI entry point (contains intelligence layer commands + agentic scoring)
- `telos_observatory/agentic/` -- Entire agentic observatory directory
- Agentic UI components within the observatory
- Agentic test files and test fixtures
- Agentic validation modules and validators

### Category B: TKeys / Privacy Infrastructure

The TKeys system and all privacy-related tooling.

- `telos_privacy/` -- Entire package (all files and subdirectories)

### Category C: Business and Strategy Documents

Internal business documents not intended for public distribution.

- Strategic positioning documents
- VC and fundraising materials
- Organizational chart
- PBC (Public Benefit Corporation) governance documents

### Category D: Research Program

Unpublished and in-progress research.

- `research/` -- Entire directory (all research files, papers, notes)

### Category E: Internal Tooling and Configuration

Internal tools and configuration files specific to the private development environment.

- `telos_sql_agent/` -- Internal SQL agent tooling
- `telos_gateway_registry/` -- Internal gateway registry
- `HANDOFF.md` -- Internal handoff documentation
- `.mcp.json.example` -- MCP configuration example (contains internal paths/references)

---

## Files Modified

The following files were retained but modified to remove sensitive references:

| File | Changes Made |
|------|-------------|
| `main.py` | Removed AGENTIC tab from Streamlit UI; only DEMO and BETA tabs remain |
| `__init__.py` files | Removed imports and exports of agentic/private modules |
| `pyproject.toml` | Removed agentic dependencies and package entries |
| CI workflow files | Removed agentic test steps and validation jobs |
| `README.md` | Complete rewrite for public audience |
| `CLAUDE.md` | Updated to reflect public repo structure |
| `CHANGELOG.md` | Removed entries referencing agentic/private features |
| `CONTRIBUTING.md` | Updated contribution guidelines for public context |
| Validation README | Removed references to agentic validation |
| `.gitignore` | Cleaned up entries for removed directories |

---

## Verification

The following checks were performed to confirm the public build is clean and functional:

1. **Tests pass**: All remaining test suites execute successfully.
2. **Streamlit renders correctly**: The application loads and displays the DEMO and BETA tabs without errors. No broken imports or missing module references.
3. **Grep confirms no leaks**: A comprehensive search confirmed no remaining references to sensitive terms:
   ```bash
   grep -ri "agentic" --include="*.py" --include="*.md" --include="*.toml" --include="*.yml"
   grep -ri "tkeys" --include="*.py" --include="*.md" --include="*.toml" --include="*.yml"
   grep -ri "telos_privacy" --include="*.py" --include="*.md" --include="*.toml" --include="*.yml"
   grep -ri "telos_sql_agent" --include="*.py" --include="*.md" --include="*.toml" --include="*.yml"
   grep -ri "telos_gateway_registry" --include="*.py" --include="*.md" --include="*.toml" --include="*.yml"
   grep -ri "intelligence_layer" --include="*.py" --include="*.md" --include="*.toml" --include="*.yml"
   grep -ri "IntelligenceCollector" --include="*.py" --include="*.md" --include="*.toml" --include="*.yml"
   grep -ri "IntelligenceConfig" --include="*.py" --include="*.md" --include="*.toml" --include="*.yml"
   ```
   All searches returned zero results.

---

## Notes

- The `v3.0-pre-rewrite` tag on TELOS_Master preserves the complete prior public history. It can be restored at any time.
- telos remains the single source of truth for the full implementation. Future public releases should follow this same derivation process.
- See `ROLLBACK_GUIDE.md` for failure recovery procedures.
