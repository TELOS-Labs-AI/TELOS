'use client';

import { useEffect, useState, useCallback } from 'react';
import type { ScoredEvent, AuditSummary, Verdict } from '../lib/types';
import { DEFAULT_CONFIG } from '../lib/config';
import type { DashboardConfig } from '../lib/config';
import { VerdictBadge } from './VerdictBadge';
import { FidelityBar } from './FidelityBar';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AuditTrailViewerProps {
  /**
   * Data fetcher -- returns AuditSummary from your API route or data source.
   * Decouples the viewer from any specific API endpoint.
   *
   * Example: () => fetch('/api/audit?limit=100').then(r => r.json())
   */
  fetchAudit: (limit: number) => Promise<AuditSummary>;

  /** Dashboard config for styling + thresholds. */
  config?: Partial<DashboardConfig>;

  /** Number of events to fetch per refresh cycle. Default: 100. */
  limit?: number;
}

// ---------------------------------------------------------------------------
// Verdict Filter (internal)
// ---------------------------------------------------------------------------

const ALL_VERDICTS: Verdict[] = ['execute', 'clarify', 'escalate', 'inert'];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Full-page audit trail viewer with verdict filter pills and auto-refresh.
 *
 * Usage:
 *   <AuditTrailViewer
 *     fetchAudit={(limit) => fetch(`/api/audit?limit=${limit}`).then(r => r.json())}
 *   />
 */
export function AuditTrailViewer({ fetchAudit, config, limit = 100 }: AuditTrailViewerProps) {
  const [events, setEvents] = useState<ScoredEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<Verdict | 'all'>('all');

  const refreshMs = config?.auditRefreshMs ?? DEFAULT_CONFIG.auditRefreshMs;
  const verdictStyles = config?.verdictStyles ?? DEFAULT_CONFIG.verdictStyles;

  const load = useCallback(() => {
    fetchAudit(limit)
      .then((d) => {
        setEvents(d.recent || []);
        setTotal(d.total_scored || 0);
      })
      .catch(() => {});
  }, [fetchAudit, limit]);

  useEffect(() => {
    load();
    if (refreshMs > 0) {
      const iv = setInterval(load, refreshMs);
      return () => clearInterval(iv);
    }
  }, [load, refreshMs]);

  const filtered = filter === 'all' ? events : events.filter((e) => e.decision === filter);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Activity Feed</h2>
        <p className="text-gray-500 text-sm mt-1">
          Governance audit trail -- {total} scored tool calls
          {refreshMs > 0 && ` \u00B7 Auto-refreshes every ${Math.round(refreshMs / 1000)}s`}
        </p>
      </div>

      {/* Verdict filter pills */}
      <div className="flex gap-1 flex-wrap">
        <FilterPill
          label={`All (${events.length})`}
          active={filter === 'all'}
          onClick={() => setFilter('all')}
        />
        {ALL_VERDICTS.map((v) => {
          const count = events.filter((e) => e.decision === v).length;
          return (
            <FilterPill
              key={v}
              label={`${v} (${count})`}
              active={filter === v}
              onClick={() => setFilter(v)}
            />
          );
        })}
      </div>

      {/* Event list */}
      <div className="space-y-1.5">
        {filtered
          .slice()
          .reverse()
          .map((e, i) => (
            <div key={i} className="bg-[#111111] rounded-xl border border-[#1a1a2e] p-3">
              <div className="flex items-start gap-3">
                <VerdictBadge decision={e.decision} config={{ verdictStyles }} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-300 font-mono">{e.tool}</span>
                    {e.boundary_triggered && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">
                        BOUNDARY
                      </span>
                    )}
                  </div>
                  {e.action_text && (
                    <p className="text-xs text-gray-500 mt-1 truncate">{e.action_text}</p>
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-600 whitespace-nowrap">
                  <FidelityBar fidelity={e.fidelity} config={config} />
                  <span>fid {e.fidelity.toFixed(3)}</span>
                  {e.latency_ms > 0 && <span>{e.latency_ms.toFixed(0)}ms</span>}
                  <span className="text-gray-700">seq {e.sequence}</span>
                </div>
              </div>
            </div>
          ))}
        {filtered.length === 0 && (
          <p className="text-gray-600 text-sm text-center py-8">No governance events recorded yet</p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal sub-components
// ---------------------------------------------------------------------------

function FilterPill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 rounded-lg text-xs uppercase ${
        active ? 'bg-[#1a1a2e] text-white' : 'text-gray-500'
      }`}
    >
      {label}
    </button>
  );
}
