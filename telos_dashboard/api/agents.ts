/**
 * TELOS Governance Dashboard -- Agents API Route
 *
 * Returns the agent roster. Agents are defined in config (not hardcoded).
 * Optionally reads last audit timestamp and advisory cycle count from
 * filesystem if paths are provided.
 *
 * Usage in app/api/agents/route.ts:
 *   import { createAgentsHandler } from 'telos_dashboard/api/agents';
 *   export const GET = createAgentsHandler(config, agentRoster);
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import type { DashboardConfig } from '../lib/config';

// ---------------------------------------------------------------------------
// Agent roster types (richer than the lib AgentInfo for roster display)
// ---------------------------------------------------------------------------

export interface RosterAgent {
  name: string;
  role: string;
  model: string;
  location: string;
  status: string;
  emoji: string;
  description: string;
  color: string;
  lastActivity: string | null;
  cycleCount: number;
}

// ---------------------------------------------------------------------------
// Helpers (filesystem probes for live status)
// ---------------------------------------------------------------------------

function getLastAuditTimestamp(auditPath: string): number {
  try {
    const content = fs.readFileSync(auditPath, 'utf-8');
    const lines = content.trim().split('\n');
    for (let i = lines.length - 1; i >= Math.max(0, lines.length - 10); i--) {
      try {
        const entry = JSON.parse(lines[i]);
        if (entry.timestamp) return entry.timestamp;
      } catch { continue; }
    }
  } catch { /* no audit file */ }
  return 0;
}

function countAdvisoryCycles(advisoryDir: string): { count: number; latest: string | null } {
  try {
    if (!fs.existsSync(advisoryDir)) return { count: 0, latest: null };
    const dateDirs = fs.readdirSync(advisoryDir)
      .filter(d => /^\d{4}-\d{2}-\d{2}$/.test(d))
      .sort();

    let totalCycles = 0;
    let latestTime: string | null = null;

    for (const dateDir of dateDirs) {
      const fullPath = path.join(advisoryDir, dateDir);
      try {
        const timeDirs = fs.readdirSync(fullPath)
          .filter(d => /^\d{2}-\d{2}$/.test(d))
          .sort();
        totalCycles += timeDirs.length;
        if (timeDirs.length > 0) {
          latestTime = `${dateDir} ${timeDirs[timeDirs.length - 1].replace('-', ':')} UTC`;
        }
      } catch { continue; }
    }
    return { count: totalCycles, latest: latestTime };
  } catch {
    return { count: 0, latest: null };
  }
}

// ---------------------------------------------------------------------------
// Handler factory
// ---------------------------------------------------------------------------

export interface AgentsHandlerOptions {
  /** Directory containing advisory cycle data (YYYY-MM-DD/HH-MM/). Optional. */
  advisoryDir?: string;
}

/**
 * Create a GET handler for the agents endpoint.
 *
 * @param config - Dashboard config (for audit path).
 * @param roster - Static agent definitions. Caller owns the roster content.
 * @param options - Optional advisory directory for cycle counting.
 */
export function createAgentsHandler(
  config: DashboardConfig,
  roster: RosterAgent[],
  options?: AgentsHandlerOptions,
) {
  return async function GET() {
    const lastAudit = getLastAuditTimestamp(config.paths.auditJsonl);
    const cycles = options?.advisoryDir
      ? countAdvisoryCycles(options.advisoryDir)
      : { count: 0, latest: null };

    // Enrich roster with live data
    const agents = roster.map(a => ({
      ...a,
      lastActivity: a.lastActivity ?? (
        lastAudit > 0
          ? new Date(lastAudit * 1000).toISOString().slice(0, 19).replace('T', ' ') + ' UTC'
          : null
      ),
      cycleCount: a.cycleCount || cycles.count,
    }));

    return NextResponse.json({ agents });
  };
}
