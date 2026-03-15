'use client';

import { useEffect, useState } from 'react';
import type { RosterAgent } from '../api/agents';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface TeamPageProps {
  /** Fetch the agent roster. */
  fetchAgents: () => Promise<{ agents: RosterAgent[] }>;
  /** Static fallback roster (shown while loading or on fetch failure). */
  fallbackRoster?: RosterAgent[];
  /** Names of "core" agents (displayed in the top section). Others go to advisory fleet. */
  coreAgentNames?: string[];
  /** Optional principal card at the bottom. */
  principal?: { name: string; title: string; description: string };
  /** Mission statement shown at the top. */
  missionStatement?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Agent roster page showing core agents, advisory fleet, and principal.
 * All agent data comes from props/fetch -- no hardcoded names.
 */
export function TeamPage({
  fetchAgents,
  fallbackRoster = [],
  coreAgentNames = [],
  principal,
  missionStatement,
}: TeamPageProps) {
  const [agents, setAgents] = useState<RosterAgent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAgents()
      .then(d => { setAgents(d.agents || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [fetchAgents]);

  const displayAgents = agents.length > 0 ? agents : fallbackRoster;
  const coreSet = new Set(coreAgentNames);
  const core = displayAgents.filter(a => coreSet.has(a.name));
  const advisory = displayAgents.filter(a => !coreSet.has(a.name));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Agent Roster</h1>
        <p className="text-gray-500 text-sm mt-1">Live agent status & mission assignments</p>
      </div>

      {/* Mission Statement */}
      {missionStatement && (
        <div className="bg-[#111111] rounded-xl border border-[#1a1a2e] p-6">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Mission Statement</p>
          <p className="text-lg text-gray-200 leading-relaxed">{missionStatement}</p>
          <p className="text-xs text-gray-600 mt-3">-- TELOS AI Labs</p>
        </div>
      )}

      {/* Core Agents */}
      {core.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Core Agents</h2>
          <div className="grid md:grid-cols-2 gap-4">
            {core.map(a => (
              <AgentCard key={a.name} agent={a} variant="core" />
            ))}
          </div>
        </div>
      )}

      {/* Advisory Fleet */}
      {advisory.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Advisory Fleet</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {advisory.map(a => (
              <AgentCard key={a.name} agent={a} variant="advisory" />
            ))}
          </div>
        </div>
      )}

      {/* Principal */}
      {principal && (
        <div className="bg-[#111111] rounded-xl border border-[#1a1a2e] border-l-2 border-l-blue-500 p-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">&#x1F464;</span>
            <div>
              <h3 className="font-semibold text-gray-200">{principal.name}</h3>
              <p className="text-xs text-gray-500">{principal.title}</p>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-3">{principal.description}</p>
        </div>
      )}

      {loading && displayAgents.length === 0 && (
        <p className="text-gray-600 text-sm text-center py-8">Loading agent roster...</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal sub-components
// ---------------------------------------------------------------------------

function AgentCard({ agent: a, variant }: { agent: RosterAgent; variant: 'core' | 'advisory' }) {
  return (
    <div className={`bg-[#111111] rounded-xl border border-[#1a1a2e] p-4 ${variant === 'core' ? `border-l-2 ${a.color || 'border-gray-500'}` : ''}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className={variant === 'core' ? 'text-2xl' : 'text-lg'}>{a.emoji}</span>
          <div>
            <h3 className={`font-semibold ${variant === 'core' ? 'text-gray-200' : 'text-gray-300 text-sm'}`}>{a.name}</h3>
            <p className={`text-gray-${variant === 'core' ? '500' : '600'} text-${variant === 'core' ? 'xs' : '[10px]'}`}>{a.role}</p>
          </div>
        </div>
        <StatusBadge status={a.status} />
      </div>
      <p className={`text-xs text-gray-${variant === 'core' ? '400' : '500'} mt-${variant === 'core' ? '3' : '2'}`}>{a.description}</p>
      {variant === 'core' && (
        <div className="flex gap-4 mt-3 text-[10px] text-gray-600">
          <span>Model: {a.model}</span>
          <span>{a.location}</span>
        </div>
      )}
      {a.cycleCount > 0 && (
        <p className="text-[10px] text-gray-700 mt-2">{a.cycleCount} advisory cycles completed</p>
      )}
      {a.lastActivity && (
        <p className="text-[10px] text-gray-700 mt-1">Last active: {a.lastActivity}</p>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, { dot: string; text: string; label: string }> = {
    active: { dot: 'bg-green-400 animate-pulse', text: 'text-green-400', label: 'active' },
    standby: { dot: 'bg-gray-500', text: 'text-gray-400', label: 'standby' },
    commissioned: { dot: 'bg-blue-400', text: 'text-blue-400', label: 'commissioned' },
    offline: { dot: 'bg-gray-600', text: 'text-gray-500', label: 'offline' },
    error: { dot: 'bg-red-500', text: 'text-red-400', label: 'error' },
    unknown: { dot: 'bg-gray-600', text: 'text-gray-500', label: 'unknown' },
  };
  const s = styles[status] || styles.unknown;
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${s.dot}`} />
      <span className={`text-[10px] ${s.text}`}>{s.label}</span>
    </span>
  );
}
