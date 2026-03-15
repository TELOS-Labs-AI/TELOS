/**
 * TELOS Governance Dashboard -- Governance API Route
 *
 * Returns pulse data, gate state, and governance moments.
 * All paths come from DashboardConfig -- no hardcoded paths.
 *
 * Usage in app/api/governance/route.ts:
 *   import { createGovernanceHandler } from 'telos_dashboard/api/governance';
 *   export const GET = createGovernanceHandler(config);
 */

import { NextResponse } from 'next/server';
import path from 'path';
import { parsePulse, parseGateState } from '../lib/pulse-parser';
import { listMarkdownFiles } from '../lib/files';
import type { DashboardConfig } from '../lib/config';

/**
 * Create a GET handler for the governance endpoint.
 * Returns { pulse, gate, moments }.
 */
export function createGovernanceHandler(config: DashboardConfig) {
  return async function GET() {
    const pulse = parsePulse(config.paths.pulseMemory);
    const gate = parseGateState(config.paths.gateState);

    const momentsDir = path.join(config.paths.workspace, 'governance_moments');
    const moments = listMarkdownFiles(momentsDir);

    return NextResponse.json({ pulse, gate, moments });
  };
}
