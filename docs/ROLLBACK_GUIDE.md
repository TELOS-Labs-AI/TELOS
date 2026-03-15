# TELOS Rollback and Recovery Guide

## Overview

Three local directories and two GitHub repositories form the TELOS development and release infrastructure. This guide covers recovery from any failure scenario.

### Directory Layout

```
/Users/brunnerjf/Desktop/
├── TELOS_Master/          # Original public repo (tagged v3.0-pre-rewrite)
├── telos/                 # Private repo (full implementation)
└── telos_public_build/     # Derived public repo (derived from private repo)
```

### GitHub Repositories

| Repository | Visibility | Purpose |
|------------|-----------|---------|
| TELOS-Labs-AI/telos | Public | Public-facing TELOS Governance Observatory |
| TELOS-Labs-AI/telos | Private | Full implementation including agentic governance, TKeys, research |

---

## Scenario 1: Public Build Is Broken -- Revert GitHub to Pre-Rewrite State

If the public repository on GitHub is broken or contains leaked sensitive material and needs to be immediately reverted to its previous state:

```bash
cd /Users/brunnerjf/Desktop/TELOS_Master
git checkout v3.0-pre-rewrite
git push --force-with-lease origin HEAD:main
```

This restores the public GitHub repo to the exact state it was in before the derivation process. The `v3.0-pre-rewrite` tag is a permanent safety checkpoint.

**When to use this**: The public repo is serving broken code, has leaked sensitive content, or the new derived build has a critical defect that cannot be quickly patched.

---

## Scenario 2: Need to Re-Derive Public Build from Private Repo

If the public build directory is corrupted, lost, or needs to be regenerated from scratch:

```bash
# Remove the existing public build
rm -rf /Users/brunnerjf/Desktop/telos_public_build

# Create a fresh directory
mkdir -p /Users/brunnerjf/Desktop/telos_public_build

# Extract tracked files from private repo
cd /Users/brunnerjf/Desktop/telos
git archive HEAD | tar -x -C /Users/brunnerjf/Desktop/telos_public_build/

# Then re-run the deletion and scrubbing process
# See TELOS_PUBLIC_BUILD_PROCESS.md for the full list of files to remove and modify
```

After extraction, follow the complete deletion, scrubbing, and verification steps documented in `TELOS_PUBLIC_BUILD_PROCESS.md`:

1. Delete all files in Categories A through E
2. Scrub agentic/sensitive references from remaining files
3. Rewrite README.md and CLAUDE.md
4. Run verification (tests, Streamlit render, grep for leaks)
5. Init fresh git and push

**When to use this**: The `telos_public_build/` directory is missing, corrupted, or you need to incorporate updates from the private repo into a new public release.

---

## Scenario 3: Private Repo Is Damaged Locally

If the local `telos/` directory has been corrupted, has bad merges, or is in an inconsistent state:

```bash
cd /Users/brunnerjf/Desktop/telos
git fetch origin
git reset --hard origin/main
```

This discards all local changes and resets to the state of the remote `main` branch on GitHub.

**When to use this**: Local repo has bad commits, failed merges, or experimental changes that need to be discarded. The remote on GitHub is the authoritative copy.

**Caution**: This destroys all uncommitted and unpushed local changes. If you have work to preserve, stash or branch it first.

---

## Scenario 4: Need to Restore TELOS_Master to Pre-Rewrite State (Local Only)

If you need a local copy of the old TELOS_Master codebase without affecting GitHub:

```bash
cd /Users/brunnerjf/Desktop/TELOS_Master
git checkout v3.0-pre-rewrite -b main-restored
```

This creates a new branch `main-restored` pointing to the pre-rewrite state. The current `main` branch is not affected.

**When to use this**: You need to reference or compare against the old public codebase, or you want to selectively cherry-pick something from the pre-rewrite history.

---

## Scenario 5: Both GitHub Repos Need Recovery

In the unlikely event that both GitHub repositories are damaged or need to be restored:

### Recovering telos on GitHub

Push from the local `telos/` directory:

```bash
cd /Users/brunnerjf/Desktop/telos
git push --force-with-lease origin main
```

The local clone is the recovery source. Ensure it is up to date before pushing.

### Recovering TELOS_Master (Public) on GitHub

**Option A** -- Restore to pre-rewrite state:

```bash
cd /Users/brunnerjf/Desktop/TELOS_Master
git checkout v3.0-pre-rewrite
git push --force-with-lease origin HEAD:main
```

**Option B** -- Re-derive from private repo and push fresh:

```bash
# Follow Scenario 2 to create a fresh telos_public_build/
# Then:
cd /Users/brunnerjf/Desktop/telos_public_build
git init
git add -A
git commit -m "TELOS Governance Observatory - recovered public release"
git remote add origin https://github.com/TELOS-Labs-AI/telos.git
git push --force-with-lease origin HEAD:main
```

**When to use this**: Catastrophic failure affecting GitHub. Both local directories serve as the recovery source.

---

## Key Tags and Commits

| Reference | Value | Location |
|-----------|-------|----------|
| TELOS_Master safety tag | `v3.0-pre-rewrite` | TELOS-Labs-AI/telos |
| telos founding commit | `14858a2` | TELOS-Labs-AI/telos |
| telos latest (at time of derivation) | `f9b149e` | TELOS-Labs-AI/telos |

To verify the tag exists:

```bash
cd /Users/brunnerjf/Desktop/TELOS_Master
git tag -l "v3.0-pre-rewrite"
```

To verify the latest commit:

```bash
cd /Users/brunnerjf/Desktop/telos
git log --oneline | head -5
```

---

## GitHub Authentication

A GitHub Personal Access Token (PAT) named **"TELOS GOVERNANCE OBSERVATORY"** is configured with the following scopes:

- `repo` (full repository access)
- `workflow` (GitHub Actions workflow access)

The token has **no expiration** set.

**Do not store the token value in any committed file.** Use `git credential-store`, environment variables, or the macOS Keychain for authentication. If the token is compromised, revoke it immediately at https://github.com/settings/tokens and generate a replacement with the same scopes.

---

## Contact

For questions about this process or assistance with recovery:

**JB@telos-labs.ai**
