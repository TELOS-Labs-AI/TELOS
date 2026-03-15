'use client';

import type { GateMode } from '../lib/types';
import { DEFAULT_CONFIG } from '../lib/config';
import type { DashboardConfig } from '../lib/config';

interface GateBadgeProps {
  mode: GateMode;
  config?: Pick<DashboardConfig, 'gateBadgeStyles'>;
}

/**
 * Pill badge showing the daemon's gate mode (observe, enforce, open).
 * Includes a colored dot indicator and uppercase label.
 */
export function GateBadge({ mode, config }: GateBadgeProps) {
  const styles = config?.gateBadgeStyles ?? DEFAULT_CONFIG.gateBadgeStyles;
  const badge = styles[mode] ?? styles.unknown;

  return (
    <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full ${badge.bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`} />
      <span className={`text-[10px] font-medium ${badge.text}`}>{badge.label}</span>
    </div>
  );
}
