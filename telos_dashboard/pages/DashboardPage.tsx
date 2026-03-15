'use client';

import { useEffect, useState } from 'react';
import type { AuditSummary, Pulse, GateState } from '../lib/types';
import type { DashboardConfig } from '../lib/config';
import { DEFAULT_CONFIG } from '../lib/config';
import { VerdictBadge } from '../components/VerdictBadge';
import { FidelityBar } from '../components/FidelityBar';
import { MetricCard } from '../components/MetricCard';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DashboardPageProps {
  /** Fetch governance data (pulse + gate). */
  fetchGovernance: () => Promise<{ pulse: Pulse | null; gate: GateState | null }>;
  /** Fetch audit trail summary. */
  fetchAudit: (limit: number) => Promise<AuditSummary>;
  /** Dashboard config for styling. */
  config?: Partial<DashboardConfig>;
  /** Title override. Default: "TELOS Dashboard". */
  title?: string;
  /** Subtitle override. */
  subtitle?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Main governance dashboard page.
 * Shows 4 metric cards, live audit trail, pulse stats, and boundary triggers.
 */
export function DashboardPage({
  fetchGovernance,
  fetchAudit,
  config,
  title = 'TELOS Dashboard',
  subtitle = 'Governance Operations',
}: DashboardPageProps) {
  const [governance, setGovernance] = useState<{ pulse: Pulse | null; gate: GateState | null }>({ pulse: null, gate: null });
  const [audit, setAudit] = useState<AuditSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchGovernance(), fetchAudit(30)])
      .then(([gov, aud]) => { setGovernance(gov); setAudit(aud); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });

    const interval = setInterval(() => {
      fetchAudit(30).then(setAudit).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchGovernance, fetchAudit]);

  const verdicts = audit?.verdict_counts || {};
  const totalVerdicts = Object.values(verdicts).reduce((a, b) => a + b, 0);

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">{title}</h1>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <p className="text-red-400 text-sm">Failed to load governance data: {error}</p>
          <button onClick={() => window.location.reload()} className="text-xs text-red-300 underline mt-2">Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="text-gray-500 text-sm mt-1">{subtitle}</p>
        </div>
        {loading && <span className="text-xs text-gray-600 animate-pulse">Loading...</span>}
      </div>

      {/* Primary Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Governance Fidelity"
          value={audit ? audit.mean_fidelity.toFixed(3) : governance.pulse?.fidelity.toFixed(3) || '--'}
          sub={audit ? `${audit.total_scored} events (audit trail)` : ''}
          color={audit && audit.mean_fidelity > 0.5 ? 'green' : 'amber'}
        />
        <MetricCard
          label="ESCALATE Rate"
          value={totalVerdicts > 0 ? `${((verdicts.escalate || 0) / totalVerdicts * 100).toFixed(1)}%` : governance.pulse ? `${governance.pulse.escalate_rate}%` : '--'}
          sub={verdicts.escalate ? `${verdicts.escalate} escalations` : ''}
          color={totalVerdicts > 0 && (verdicts.escalate || 0) / totalVerdicts < 0.05 ? 'green' : 'amber'}
        />
        <MetricCard
          label="Boundary Triggers"
          value={audit?.boundary_triggers.toString() || '0'}
          sub="Active boundary detections"
          color={audit && audit.boundary_triggers > 0 ? 'amber' : 'green'}
        />
        <MetricCard
          label="Verdict Distribution"
          value={totalVerdicts > 0 ? `${((verdicts.execute || 0) / totalVerdicts * 100).toFixed(0)}% EXEC` : '--'}
          sub={totalVerdicts > 0 ? `${verdicts.clarify || 0} CLARIFY / ${verdicts.inert || 0} INERT` : ''}
          color="blue"
        />
      </div>

      {/* Two column layout */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Recent Audit Trail */}
        <div className="bg-[#111111] rounded-xl border border-[#1a1a2e] p-4">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Live Audit Trail
            <span className="ml-2 w-2 h-2 rounded-full bg-green-400 animate-pulse inline-block" />
          </h2>
          <div className="space-y-1 max-h-[400px] overflow-y-auto font-mono text-xs">
            {(audit?.recent || []).slice().reverse().map((e, i) => (
              <div key={i} className="flex items-center gap-2 py-1.5 border-b border-[#1a1a2e]/50 last:border-0">
                <VerdictBadge decision={e.decision} config={config} />
                <span className="text-gray-500 w-10 text-right">{e.sequence}</span>
                <span className="text-gray-300 flex-1 truncate">{e.tool}</span>
                <FidelityBar fidelity={e.fidelity} config={config} />
                <span className="text-gray-500 w-12 text-right">{e.fidelity.toFixed(3)}</span>
                {e.boundary_triggered && <span className="text-amber-400 text-[10px]">BOUNDARY</span>}
                {e.latency_ms > 0 && <span className="text-gray-600 w-12 text-right text-[10px]">{e.latency_ms.toFixed(0)}ms</span>}
              </div>
            ))}
            {(!audit?.recent || audit.recent.length === 0) && (
              <p className="text-gray-600 text-sm py-4 text-center">No scored tool calls yet</p>
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Governance Pulse */}
          <div className="bg-[#111111] rounded-xl border border-[#1a1a2e] p-4">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Governance Pulse <span className="text-[10px] text-gray-600 normal-case">(periodic aggregate)</span>
            </h2>
            {governance.pulse ? (
              <div className="grid grid-cols-2 gap-3">
                <PulseStat label="Fidelity" value={governance.pulse.fidelity.toFixed(3)} />
                <PulseStat label="ESCALATE Rate" value={`${governance.pulse.escalate_rate}%`} />
                <PulseStat label="False Positives" value={`${governance.pulse.false_positive_rate}%`} />
                <PulseStat label="Total Actions" value={governance.pulse.total_actions.toString()} />
                <PulseStat label="Correlation" value={`${governance.pulse.correlation}%`} />
                <PulseStat label="Gates" value={`${governance.pulse.gates_passed}/${governance.pulse.gates_total}`} />
              </div>
            ) : (
              <p className="text-gray-600 text-sm">No pulse data -- daemon may need a telemetry cycle</p>
            )}
          </div>

          {/* Boundary Triggers */}
          <div className="bg-[#111111] rounded-xl border border-[#1a1a2e] p-4">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Recent Boundary Triggers</h2>
            <div className="space-y-2">
              {(audit?.boundary_events || []).slice(-5).reverse().map((e, i) => (
                <div key={i} className="flex items-center gap-2 py-1 text-xs">
                  <span className="text-amber-400">seq {e.sequence}</span>
                  <span className="text-gray-400">{e.tool}</span>
                  <span className="text-gray-600">fid={e.fidelity.toFixed(3)}</span>
                  <VerdictBadge decision={e.decision} config={config} />
                </div>
              ))}
              {(!audit?.boundary_events || audit.boundary_events.length === 0) && (
                <p className="text-gray-600 text-sm">No boundary triggers</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal sub-components
// ---------------------------------------------------------------------------

function PulseStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] text-gray-600 uppercase">{label}</p>
      <p className="text-lg font-semibold text-gray-300">{value}</p>
    </div>
  );
}
