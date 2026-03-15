/**
 * TELOS Governance Dashboard -- Audit API Route
 *
 * Next.js API route handler for the audit trail endpoint.
 * Reads JSONL audit file from config-driven path.
 *
 * Usage in app/api/audit/route.ts:
 *   import { createAuditHandler } from 'telos_dashboard/api/audit';
 *   import { createConfig } from 'telos_dashboard/lib';
 *   const config = createConfig({ paths: { auditJsonl: '~/.telos/audit.jsonl', ... } });
 *   export const GET = createAuditHandler(config);
 */

import { NextResponse } from 'next/server';
import { parseAuditTrail } from '../lib/audit-parser';
import type { DashboardConfig } from '../lib/config';

/**
 * Create a GET handler for the audit trail endpoint.
 * Accepts ?limit=N query param (default from config).
 */
export function createAuditHandler(config: DashboardConfig) {
  return async function GET(request: Request) {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || String(config.auditDefaultLimit));
    const summary = parseAuditTrail(config.paths.auditJsonl, limit);
    return NextResponse.json(summary);
  };
}
