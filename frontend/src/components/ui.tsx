// Shared small components: panels, chips, meters, state pills.

import type { ReactNode } from 'react';

export function Panel(
  { title, right, children, className = '', scroll = false }: {
    title?: string;
    right?: ReactNode;
    children: ReactNode;
    className?: string;
    scroll?: boolean;
  }) {
  return (
    <section className={`bg-cc-panel border border-cc-line rounded-lg shadow-sm flex flex-col min-h-0 ${className}`}>
      {title && (
        <header className="flex items-center justify-between px-3 py-1.5 border-b border-cc-line shrink-0">
          <h2 className="text-[11px] font-semibold tracking-wider text-cc-dim uppercase">{title}</h2>
          {right}
        </header>
      )}
      <div className={`flex-1 min-h-0 ${scroll ? 'overflow-y-auto' : ''}`}>{children}</div>
    </section>
  );
}

export function SevChip({ severity }: { severity: string }) {
  return (
    <span className={`sev-${severity} text-[10px] px-1.5 py-0.5 border rounded-sm font-mono uppercase tracking-wide`}>
      {severity}
    </span>
  );
}

export function StatusDot({ ok, warn, title }: { ok: boolean; warn?: boolean; title: string }) {
  const cls = ok ? 'bg-cc-accent'
    : warn ? 'bg-cc-amber animate-pulse'
    : 'bg-cc-red animate-pulse';
  return <span title={title} className={`inline-block w-2 h-2 rounded-full shrink-0 ${cls}`} />;
}

export function Metric({ label, value, unit = '', warn = false, dim = false }: {
  label: string; value: string | number; unit?: string; warn?: boolean; dim?: boolean;
}) {
  return (
    <div className="bg-cc-panel2 border border-cc-line rounded-lg px-2.5 py-1.5 min-w-0">
      <div className="text-[9px] uppercase tracking-wider text-cc-dim truncate">{label}</div>
      <div className={`font-mono text-lg leading-tight truncate ${
        warn ? 'text-cc-red' : dim ? 'text-cc-dim' : 'text-cc-text'}`}>
        {value}<span className="text-xs text-cc-dim ml-0.5">{unit}</span>
      </div>
    </div>
  );
}

export function Pill({ tone = 'dim', title, children }: {
  tone?: 'dim' | 'green' | 'amber' | 'red' | 'blue';
  title?: string;
  children: ReactNode;
}) {
  const tones = {
    dim: 'text-cc-dim border-cc-line',
    green: 'text-cc-accent border-cc-accent/40',
    amber: 'text-cc-amber border-cc-amber/40',
    red: 'text-cc-red border-cc-red/40',
    blue: 'text-cc-blue border-cc-blue/40',
  };
  return (
    <span title={title} className={`text-[10px] px-1.5 py-0.5 border rounded-sm font-mono uppercase tracking-wide whitespace-nowrap ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="h-full min-h-24 flex items-center justify-center text-cc-dim text-xs font-mono text-center px-4">
      {children}
    </div>
  );
}

export function ComingSoon({ label }: { label: string }) {
  return (
    <span
      title={`${label} — not implemented in this build`}
      className="inline-flex items-center gap-1 text-[9px] font-mono uppercase tracking-wider
        text-cc-dim/80 border border-dashed border-cc-line rounded px-1.5 py-0.5 cursor-not-allowed
        bg-cc-panel2/50 select-none"
    >
      {label}
      <span className="text-cc-dim/70">— COMING SOON</span>
    </span>
  );
}

export function eventTypeLabel(type: string): string {
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

export function eventTone(type: string): 'red' | 'green' | 'amber' | 'blue' | 'dim' {
  if (type === 'ZONE_ENTRY' || type === 'ANPR_READ') return 'green';
  if (type === 'ZONE_EXIT' || type === 'SOURCE_LOST' || type === 'OCR_UNCERTAIN') return 'amber';
  if (type === 'SOURCE_CONNECTED' || type === 'SOURCE_RECONNECTED'
    || type === 'SESSION_COMPLETED') return 'green';
  if (type === 'PERSON_DETECTED' || type === 'VEHICLE_DETECTED' || type === 'ANPR_PLATE_DETECTED' || type === 'FACE_DETECTED') return 'blue';
  return 'dim';
}
