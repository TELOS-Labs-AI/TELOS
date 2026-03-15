'use client';

import type { AuditSummary } from '../lib/types';
import type { DashboardConfig } from '../lib/config';
import { AuditTrailViewer } from '../components/AuditTrailViewer';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ActivityPageProps {
  /** Fetch audit trail summary. */
  fetchAudit: (limit: number) => Promise<AuditSummary>;
  /** Dashboard config for styling + refresh interval. */
  config?: Partial<DashboardConfig>;
  /** Number of events to display. Default: 100. */
  limit?: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Full-page activity feed wrapping AuditTrailViewer.
 * Thin wrapper that provides the page-level heading.
 */
export function ActivityPage({ fetchAudit, config, limit = 100 }: ActivityPageProps) {
  return (
    <AuditTrailViewer
      fetchAudit={fetchAudit}
      config={config}
      limit={limit}
    />
  );
}
