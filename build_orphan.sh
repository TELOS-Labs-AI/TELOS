#!/bin/bash
# build_orphan.sh — Creates the public orphan branch for TELOS
# Run from telos_hardened root. Does NOT push — Jeffrey does that manually.
set -euo pipefail

echo "=== Phase 1: Safety backup ==="
git branch "backup/pre-public-$(date +%Y%m%d)" main 2>/dev/null || echo "Backup branch already exists"

echo "=== Phase 2: Create orphan branch ==="
git checkout --orphan public-clean
git rm -rf --cached . > /dev/null 2>&1

echo "=== Phase 3: Stage PUBLIC files ==="

# --- Root files ---
git add README.md LICENSE CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md \
       CHANGELOG.md REPO_STANDARDS.md pyproject.toml requirements.txt \
       requirements.lock .env.example .mcp.json.example .gitignore

# --- CI/CD ---
git add .github/workflows/

# --- Core engine (all public) ---
git add telos_core/
git add telos_governance/
git add telos_privacy/

# --- Observatory (all) ---
git add telos_observatory/

# --- Adapters (LangGraph + Generic only, NO OpenClaw) ---
git add telos_adapters/langgraph/
git add telos_adapters/generic/

# --- Templates (NO OpenClaw) ---
git add templates/__init__.py templates/default_config.yaml \
       templates/property_intel.yaml templates/solar_site_assessor.yaml \
       templates/civic_services.yaml templates/healthcare/

# --- Demos (NO OpenClaw demos, NO raw transcript) ---
git add demos/__init__.py demos/_display_toolkit.py demos/README.md \
       demos/teloscope_demo.py demos/forensics_demo.py \
       demos/nearmap_live_demo.py demos/nearmap_live_demo_v2.py \
       demos/nearmap_live_demo_v3.py demos/nearmap_demo_transcript_clean.txt \
       demos/healthcare_launcher.py demos/healthcare_live_demo.py \
       demos/healthcare_scenarios.py

# --- Validation (all EXCEPT openclaw/) ---
git add validation/
git reset HEAD -- validation/openclaw/ 2>/dev/null || true

# --- Tests (all) ---
git add tests/

# --- Research (papers + regulatory + select experiments/benchmarks) ---
git add research/README.md
git add research/papers/
git add research/regulatory/
git add research/experiments/cross_encoder_nli_mve_phase1.md \
       research/experiments/governed_vs_ungoverned_statistical_design.md \
       research/experiments/measurement_codebook.md \
       research/experiments/osf_prereg_governed_vs_ungoverned.md \
       research/experiments/setfit_mve_data_pipeline_design.md \
       research/experiments/setfit_mve_experimental_design.md \
       research/experiments/setfit_mve_phase2_closure.md
git add research/benchmarks/agentic_benchmark_roadmap.md \
       research/benchmarks/agentic_governance_hypothesis.md \
       research/benchmarks/cascade_failure_modes.md \
       research/benchmarks/mlx_model_comparison.md
git add research/scripts/shadow_scorer.py

# --- Docs (public docs only) ---
git add docs/CLI_REFERENCE.md docs/CONFIG_REFERENCE.md docs/SETUP_GUIDE.md \
       docs/INTEGRATION_GUIDE.md docs/REPRODUCTION_GUIDE.md \
       docs/HARDWARE_REQUIREMENTS.md docs/SYSTEM_INVARIANTS.md \
       docs/DESIGN_SYSTEM.md docs/DESIGN_SYSTEM_INDEX.md \
       docs/DESIGN_SYSTEM_QUICK_REFERENCE.md docs/ROLLBACK_GUIDE.md \
       docs/TELOS_Whitepaper_v3.0.md docs/TELOS_Whitepaper_v2.5.pdf \
       docs/TELOS_Technical_Brief.pdf docs/TELOS_Technical_Brief.tex \
       docs/TELOS_Academic_Paper.md docs/TELOS_Academic_Paper.pdf \
       docs/TELOS_Academic_Paper.tex \
       docs/TELOS_Academic_Paper_Governance.md docs/TELOS_Academic_Paper_Governance.pdf \
       docs/TELOS_Academic_Paper_Governance.tex \
       docs/TELOS_Academic_Paper_Systems.md docs/TELOS_Academic_Paper_Systems.pdf \
       docs/TELOS_Academic_Paper_Systems.tex \
       docs/TELOS_ALIGNMENT_VALIDATION_SUMMARY.md \
       docs/TELOS_COMPREHENSIVE_GOVERNANCE_ASSESSMENT.md \
       docs/TELOS_NIST_600-1_CAPABILITIES_MAPPING.md \
       docs/TELOS_PBC_GOVERNANCE.md \
       docs/TELOS_Provider_Reference.pdf docs/TELOS_Provider_Reference.tex \
       docs/TELOS_PUBLIC_BUILD_PROCESS.md \
       docs/TELOS_KEY_FILES_REFERENCE.md docs/TELOS_KEY_FILES_SUMMARY.md \
       docs/BERKELEY_CLTC_MAPPING.md docs/GCP_MAPPING_ANALYSIS.md \
       docs/BENCHMARK_SCOPE_PropensityBench_AgentHarm.md
git add docs/diagrams/ docs/zenodo/

# --- Analysis tools ---
git add analysis/

# --- Public tools (NOT generate_labs_key, pull_form_responses) ---
git add tools/__init__.py tools/governance_comparison.py \
       tools/governance_optimizer.py tools/run_backtest.py \
       tools/sign_manifest.py tools/add_disclosures.py

# --- References (NIST only) ---
git add references/NIST.AI.600-1.pdf references/NIST.SP.1301.pdf \
       references/NIST.SP.1302.pdf

# --- Branding ---
git add branding/logo/

echo "=== Phase 4: Remove specific exclusions ==="

# Remove proprietary OpenClaw corpus (pulled in via telos_governance/)
git reset HEAD -- telos_governance/corpus/boundary_corpus_openclaw.py 2>/dev/null || true

# Remove Observatory binary cache
git reset HEAD -- telos_observatory/config/pa_template_embeddings.npz 2>/dev/null || true

# Remove OpenClaw-specific tests
git reset HEAD -- tests/unit/test_openclaw_adapter.py 2>/dev/null || true
git reset HEAD -- tests/unit/test_openclaw_cli.py 2>/dev/null || true
git reset HEAD -- tests/unit/test_stewart_integration.py 2>/dev/null || true
git reset HEAD -- tests/unit/test_notification_service.py 2>/dev/null || true
git reset HEAD -- tests/unit/test_permission_controller.py 2>/dev/null || true
git reset HEAD -- tests/integration/test_openclaw_governance.py 2>/dev/null || true
git reset HEAD -- tests/validation/test_openclaw_benchmark.py 2>/dev/null || true

# Remove OpenClaw regulatory mapping
git reset HEAD -- research/regulatory/openclaw_regulatory_mapping.md 2>/dev/null || true

# Remove validation result reports (regenerable)
git reset HEAD -- validation/nearmap/reports/ 2>/dev/null || true

echo "=== Phase 5: Verification ==="

echo ""
echo "--- STAGED FILE COUNT ---"
STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
echo "$STAGED files staged"

echo ""
echo "--- EXCLUSION CHECKS (all should show 0) ---"

check_exclusion() {
    local label="$1"
    local pattern="$2"
    local count
    count=$(git diff --cached --name-only | grep -c "$pattern" 2>/dev/null || echo "0")
    if [ "$count" -eq 0 ]; then
        echo "  OK: $label = 0"
    else
        echo "  FAIL: $label = $count <--- FIX THIS"
        git diff --cached --name-only | grep "$pattern"
    fi
}

check_exclusion "OpenClaw adapter" "telos_adapters/openclaw"
check_exclusion "Gateway" "telos_gateway"
check_exclusion "OpenClaw validation" "validation/openclaw"
check_exclusion "OpenClaw tests" "test_openclaw\|test_stewart\|test_notification_service\|test_permission_controller"
check_exclusion "HANDOFF files" "[Hh][Aa][Nn][Dd][Oo][Ff][Ff]"
check_exclusion "LinkedIn docs" "[Ll][Ii][Nn][Kk][Ee][Dd][Ii][Nn]"
check_exclusion "Grant files" "grants/"
check_exclusion "Archive files" "archive/"
check_exclusion "Models dir" "^models/"
check_exclusion "OpenClaw templates" "templates/openclaw"
check_exclusion "Internal tools" "generate_labs_key\|pull_form_responses"
check_exclusion "Codex audit" "codex_audit\|A39"
check_exclusion ".claude dir" "^\.claude/"
check_exclusion "CLAUDE.md" "^CLAUDE.md$"
check_exclusion "Cost of Ungoverned" "[Cc]ost.*[Uu]ngoverned"
check_exclusion "Customer setup" "CUSTOMER_SETUP"
check_exclusion "SetFit retraining" "setfit_retraining_pipeline"
check_exclusion "Internal planning" "research/planning/"
check_exclusion "Internal architecture" "research/architecture/"
check_exclusion "Binary npz" "\.npz"
check_exclusion "OpenClaw corpus" "boundary_corpus_openclaw"
check_exclusion "Supabase dir" "supabase/"
check_exclusion "telos-openclaw pkg" "telos-openclaw/"
check_exclusion "telos_sql_agent" "telos_sql_agent/"
check_exclusion "ops dir" "^ops/"
check_exclusion "Prompt files" "t_prompt_"
check_exclusion "Backup files" "\.bak$"
check_exclusion "Demo output" "demos/output/"

echo ""
echo "=== DONE ==="
echo "Review staged files: git diff --cached --name-only | sort"
echo "Script complete. Do NOT commit yet — run scanners first."
