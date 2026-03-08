# Changelog

All notable changes to TELOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-02-09

### Added
- `telos_core` — Pure mathematical engine extracted as standalone package
- `telos_governance` — Agentic governance gates (fidelity gate, tool selection, action chains)
- Added API gateway support with auth, rate limiting, health checks (separate deployment)
- `telos_adapters` — Framework adapters (LangGraph, generic decorator)
- API key authentication on all gateway endpoints
- Rate limiting with sliding window algorithm
- Health check endpoint (`/health`)
- "Detect and Direct" terminology (replacing "Detect and Intervene")
- `@telos_governed` decorator for framework-agnostic governance
- Comprehensive test suite (unit, integration, validation)
- CI/CD with GitHub Actions (tests + linting)
- `pyproject.toml` for proper Python packaging

### Changed
- CORS: explicit origin whitelist replaces `allow_origins=["*"]`
- README: fixed `SIMILARITY_BASELINE` from 0.35 to 0.20 (matching constants.py)
- `InterventionLevel` renamed to `DirectionLevel`
- Observatory decomposed from monolithic files into focused modules
- Inline CSS (~900 lines) extracted to `styles/theme.css`
- `state_manager.py` decomposed: LLM init → `llm_service.py`, response gen → `response_service.py`
- All imports use proper package paths (no `sys.path.insert` hacks)

### Removed
- Deprecated Goldilocks constant aliases
- `sys.path.insert` import hacks
- `async_processor.py` (never production-tested)
- Inline CSS from `main.py`
- Duplicated LLM initialization (3 copies → 1)

### Fixed
- `FIDELITY_ORANGE` differentiated from `FIDELITY_RED` (both were 0.50)
- Hardcoded `threshold: 0.76` replaced with `FIDELITY_GREEN` constant
- Security: CORS wide-open vulnerability
- Security: no API authentication on gateway
- Security: `.env` with secrets committed to repo

### Security
- P0: API authentication added to all gateway endpoints
- P0: CORS restricted to explicit origin whitelist
- P0: `.env` removed from tracking, `.env.example` provided
- Rate limiting prevents API abuse
- Structured error responses (no stack traces in production)

## [3.0.0] - 2025-12-22

### Added
- **Expanded Adversarial Validation**: 1,300 attacks tested (up from 54)
  - HarmBench: 400 standard + 400 contextual behaviors
  - Med-Safety-Bench: 500 medical safety scenarios
  - Attack Success Rate: 0.0% across all benchmarks
- **Governance Observability System**: Full forensic trace logging
  - 11 event types (SessionStart, FidelityCalculated, InterventionTriggered, etc.)
  - Privacy modes: FULL, HASHED, DELTAS_ONLY
  - JSONL export for audit trails
- **Pytest Test Suite**: Unit tests for core mathematical components
- **PBC Governance Documentation**: Delaware Public Benefit Corporation framework

### Changed
- Technical Paper rewritten to v3.0
- Updated validation claims to 1,300 attacks

## [2.3.0] - 2025-12-15

### Added
- Beta testing framework with consent flows
- Session summarization with AI-powered insights
- HTML governance report generation

## [2.0.0] - 2025-12-01

### Added
- TELOSCOPE Observatory Interface
- Primacy Attractor Templates
- Proportional Controller (K=1.5)

## [1.0.0] - 2025-11-15

### Added
- Initial TELOS framework implementation
- Core fidelity mathematics
- Constitutional Filter
