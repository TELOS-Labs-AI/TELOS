/**
 * TELOS Governance Dashboard
 *
 * Reusable component library and data layer for governance telemetry
 * visualization. Decoupled from any specific agent framework.
 *
 * Components (client-side React):
 *   VerdictBadge, FidelityBar, MetricCard, GateBadge, AuditTrailViewer
 *
 * Data layer (server-side Node.js):
 *   parseAuditTrail, parsePulse, parseGateState, listMarkdownFiles
 *
 * Configuration:
 *   createConfig({ paths: { auditJsonl, pulseMemory, gateState, workspace } })
 *
 * Usage in a Next.js API route:
 *   import { parseAuditTrail, createConfig } from 'telos_dashboard/lib';
 *   const config = createConfig({ paths: { auditJsonl: '/path/to/audit.jsonl', ... } });
 *   const summary = parseAuditTrail(config.paths.auditJsonl, 50);
 *
 * Usage in a React component:
 *   import { AuditTrailViewer } from 'telos_dashboard/components';
 *   <AuditTrailViewer fetchAudit={(n) => fetch(`/api/audit?limit=${n}`).then(r => r.json())} />
 */

export * from './components';
export * from './lib';
export * from './api';
export * from './pages';
