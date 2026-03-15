# Security Policy

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in TELOS, please report it responsibly.

**Email:** security@telos-labs.ai

**Do NOT** open a public GitHub issue for security vulnerabilities.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Impact assessment
- Any suggested fixes

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 1 week
- **Critical fixes**: Within 7 days
- **Other fixes**: 30-90 days depending on severity

## Security Practices

### Secrets Management
- API keys are loaded from environment variables only
- `.env` files are excluded from version control via `.gitignore`
- No secrets are hardcoded in source code
- `.env.example` is provided as a template (contains NO real values)

### API Authentication
- All gateway API endpoints require Bearer token authentication
- API keys are stored as SHA-256 hashes in the agent registry
- Unauthenticated requests are rejected with 401

### CORS Policy
- Origins are explicitly whitelisted via `ALLOWED_ORIGINS` environment variable
- Wildcard origins (`*`) are never used in production

### Governance Trace Integrity
- Governance traces use SHA-256 hash chains for tamper detection
- Trace verification is available via `telos_core.trace_verifier`

### Rate Limiting
- Per-API-key rate limits prevent abuse
- Sliding window algorithm for fair resource allocation

### Input Validation
- All API inputs are validated via Pydantic models
- Structured error responses prevent information leakage

## Scope

Security concerns include:
- Vulnerabilities in the TELOS governance framework
- Issues that could compromise user data or privacy
- Bypass of fidelity detection mechanisms
- Authentication or authorization flaws

## Out of Scope

- Vulnerabilities in third-party dependencies (report to upstream)
- Social engineering attacks
- Denial of service attacks
- Issues requiring physical access

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | Yes       |
| < 1.0   | No        |

## Acknowledgments

We appreciate responsible disclosure and will acknowledge security researchers who help improve TELOS.
