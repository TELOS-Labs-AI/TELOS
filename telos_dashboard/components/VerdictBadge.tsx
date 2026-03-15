'use client';

import type { Verdict } from '../lib/types';
import { DEFAULT_CONFIG } from '../lib/config';
import type { DashboardConfig, VerdictStyle } from '../lib/config';

interface VerdictBadgeProps {
  decision: string;
  config?: Pick<DashboardConfig, 'verdictStyles'>;
}

/**
 * Pill badge showing a governance verdict (EXECUTE, CLARIFY, ESCALATE, INERT).
 * Color is config-driven via verdictStyles.
 */
export function VerdictBadge({ decision, config }: VerdictBadgeProps) {
  const styles = config?.verdictStyles ?? DEFAULT_CONFIG.verdictStyles;
  const fallback: VerdictStyle = { bg: 'bg-gray-500/20', text: 'text-gray-400' };
  const style = styles[decision as Verdict] ?? fallback;

  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium uppercase ${style.bg} ${style.text}`}>
      {decision}
    </span>
  );
}
