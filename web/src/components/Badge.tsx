import type { ReactNode } from 'react';

export interface BadgeProps {
  name: string;
  detail?: string | ReactNode;
  id?: string;
  className?: string;
}

const BADGE_STYLES: Record<string, { bg: string; color: string; border?: string }> = {
  'seeded request': { bg: '#fef3c7', color: '#92400e', border: '#fde68a' },
  'consent simulated': { bg: '#e0e7ff', color: '#3730a3', border: '#c7d2fe' },
  'position self-reported': { bg: '#ffedd5', color: '#9a3412', border: '#fed7aa' },
  'position not checked': { bg: '#f1f5f9', color: '#475569', border: '#cbd5e1' },
  'demo clock': { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5' },
  'replayed real job': { bg: '#e0f2fe', color: '#0369a1', border: '#bae6fd' },
  'historical imagery': { bg: '#f3e8ff', color: '#6b21a8', border: '#e9d5ff' },
  'reader: mock': { bg: '#fef9c3', color: '#854d0e', border: '#fef08a' },
  'exported by hand': { bg: '#f1f5f9', color: '#334155', border: '#cbd5e1' },
};

export default function Badge({ name, detail, id, className = '' }: BadgeProps) {
  const style = BADGE_STYLES[name] || { bg: '#f1f5f9', color: '#334155', border: '#cbd5e1' };

  return (
    <span
      id={id}
      className={`contract-badge badge-${name.toLowerCase().replace(/[^a-z0-9]/g, '-')} ${className}`}
      style={{
        backgroundColor: style.bg,
        color: style.color,
        border: `1px solid ${style.border || style.bg}`,
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 8px',
        borderRadius: '12px',
        fontSize: '0.75rem',
        fontWeight: 600,
        textTransform: 'none',
        lineHeight: 1.4,
        whiteSpace: 'nowrap',
      }}
    >
      <span className="badge-name">{name}</span>
      {detail && <span className="badge-detail font-normal text-xs">({detail})</span>}
    </span>
  );
}
