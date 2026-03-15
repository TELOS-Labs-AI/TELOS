'use client';

interface MetricCardProps {
  label: string;
  value: string;
  sub?: string;
  color?: 'green' | 'blue' | 'amber' | 'red' | 'white';
}

const COLOR_MAP: Record<string, string> = {
  green: 'text-green-400',
  blue: 'text-blue-400',
  amber: 'text-amber-400',
  red: 'text-red-400',
  white: 'text-white',
};

/**
 * Standard metric card with label, large value, and optional sub-text.
 * Used for governance fidelity, escalate rate, boundary triggers, etc.
 */
export function MetricCard({ label, value, sub, color = 'white' }: MetricCardProps) {
  return (
    <div className="bg-[#111111] rounded-xl border border-[#1a1a2e] p-4">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${COLOR_MAP[color] || 'text-white'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-600 mt-1">{sub}</p>}
    </div>
  );
}
