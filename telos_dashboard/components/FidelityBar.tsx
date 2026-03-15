'use client';

import { DEFAULT_CONFIG } from '../lib/config';
import type { DashboardConfig } from '../lib/config';

interface FidelityBarProps {
  fidelity: number;
  config?: Pick<DashboardConfig, 'fidelityThresholds'>;
}

/**
 * Thin horizontal bar showing fidelity magnitude.
 * Color shifts at configurable thresholds (green/amber/red).
 */
export function FidelityBar({ fidelity, config }: FidelityBarProps) {
  const thresholds = config?.fidelityThresholds ?? DEFAULT_CONFIG.fidelityThresholds;
  const pct = Math.min(fidelity * 100, 100);
  const color =
    fidelity >= thresholds.green ? 'bg-green-500' :
    fidelity >= thresholds.amber ? 'bg-amber-500' :
    'bg-red-500';

  return (
    <div className="w-16 h-1.5 bg-[#1a1a2e] rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}
