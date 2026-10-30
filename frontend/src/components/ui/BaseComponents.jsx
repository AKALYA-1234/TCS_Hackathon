import React from 'react';
import { Database, FlaskConical, Check, AlertTriangle, X, Info } from 'lucide-react';

/* Honesty Badges */
export function HonestyBadges() {
  return (
    <div className="flex items-center gap-[10px]">
      <span
        className="inline-flex items-center gap-2 px-3.5 h-[36px] rounded-full text-[13px] font-medium"
        style={{
          backgroundColor: 'var(--bg-well)',
          color: 'var(--text-primary)',
          border: '1px dashed var(--border-separator)'
        }}
      >
        <Database size={14} style={{ color: 'var(--text-secondary)' }} />
        <span>Synthetic data</span>
      </span>

      <span
        className="inline-flex items-center gap-2 px-3.5 h-[36px] rounded-full text-[13px] font-medium"
        style={{
          backgroundColor: 'var(--bg-well)',
          color: 'var(--text-primary)',
          border: '1px dashed var(--border-separator)'
        }}
        title="Model: LightGBM Regressor + Split-Conformal Band (v1)"
      >
        <FlaskConical size={14} style={{ color: 'var(--text-secondary)' }} />
        <span>LightGBM Conformal v1</span>
      </span>
    </div>
  );
}

/* Status Pill (Always icon + text label) */
export function StatusPill({ status, label, count }) {
  let bg = 'var(--bg-well)';
  let color = 'var(--text-secondary)';
  let Icon = Info;

  if (status === 'healthy' || status === 'pass') {
    bg = 'var(--status-healthy-bg)';
    color = 'var(--status-healthy)';
    Icon = Check;
  } else if (status === 'review' || status === 'warning' || status === 'elevated') {
    bg = 'var(--status-review-bg)';
    color = 'var(--status-review)';
    Icon = AlertTriangle;
  } else if (status === 'failed' || status === 'error' || status === 'high') {
    bg = 'var(--status-failed-bg)';
    color = 'var(--status-failed)';
    Icon = X;
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold tracking-wide"
      style={{ backgroundColor: bg, color: color }}
    >
      <Icon size={13} strokeWidth={2.5} />
      <span>{label}</span>
      {count !== undefined && <span className="opacity-80">({count})</span>}
    </span>
  );
}

/* Primary & Secondary Buttons */
export function Button({ children, variant = 'primary', size = 'md', className = '', ...props }) {
  const isPrimary = variant === 'primary';
  const isDestructive = variant === 'destructive';
  const isGhost = variant === 'ghost';

  let bg = isPrimary ? 'var(--accent)' : 'var(--bg-card)';
  let text = isPrimary ? '#FFFFFF' : 'var(--text-primary)';
  let border = isPrimary ? 'transparent' : 'var(--border-separator)';

  if (isDestructive) {
    bg = 'var(--status-failed-bg)';
    text = 'var(--status-failed)';
    border = '1px solid var(--status-failed)';
  } else if (isGhost) {
    bg = 'transparent';
    border = 'transparent';
  }

  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors cursor-pointer select-none active:scale-[0.98] ${
        size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm'
      } ${className}`}
      style={{
        backgroundColor: bg,
        color: text,
        border: border === 'transparent' ? 'none' : border
      }}
      {...props}
    >
      {children}
    </button>
  );
}

/* Segmented Control */
export function SegmentedControl({ options, value, onChange }) {
  return (
    <div
      className="inline-flex p-1 rounded-lg"
      style={{ backgroundColor: 'var(--bg-well)', border: '1px solid var(--border-subtle)' }}
    >
      {options.map((opt) => {
        const isSelected = (opt.value || opt) === value;
        const val = opt.value || opt;
        const label = opt.label || opt;
        return (
          <button
            key={val}
            onClick={() => onChange(val)}
            className="px-3 py-1 text-xs font-medium rounded-md transition-all cursor-pointer"
            style={{
              backgroundColor: isSelected ? 'var(--bg-card)' : 'transparent',
              color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
              boxShadow: isSelected ? 'var(--shadow-card)' : 'none'
            }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

/* Skeleton Loading State */
export function SkeletonBlock({ height = 24, width = '100%', radius = 8, className = '' }) {
  return (
    <div
      className={`skeleton-pulse ${className}`}
      style={{
        height,
        width,
        borderRadius: radius,
        backgroundColor: 'var(--bg-well)'
      }}
    />
  );
}

/* Empty State */
export function EmptyState({ title = 'Nothing waiting for you', description = 'No proposals or alerts need a decision right now.', actionText, onAction }) {
  return (
    <div
      className="flex flex-col items-center justify-center p-12 text-center rounded-2xl"
      style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}
    >
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center mb-4 text-xl"
        style={{ backgroundColor: 'var(--accent-subtle)', color: 'var(--accent)' }}
      >
        ✦
      </div>
      <h3 className="text-lg font-bold mb-1" style={{ color: 'var(--text-primary)' }}>
        {title}
      </h3>
      <p className="text-sm max-w-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
        {description}
      </p>
      {actionText && (
        <Button variant="primary" onClick={onAction}>
          {actionText}
        </Button>
      )}
    </div>
  );
}

/* Error State with Retry */
export function ErrorState({ title = "Couldn't load telemetry", description = 'The gateway timed out. Nothing was changed.', onRetry }) {
  return (
    <div
      className="flex flex-col items-center justify-center p-12 text-center rounded-2xl"
      style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--status-failed-bg)' }}
    >
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center mb-4"
        style={{ backgroundColor: 'var(--status-failed-bg)', color: 'var(--status-failed)' }}
      >
        <AlertTriangle size={24} />
      </div>
      <h3 className="text-lg font-bold mb-1" style={{ color: 'var(--text-primary)' }}>
        {title}
      </h3>
      <p className="text-sm max-w-sm mb-6" style={{ color: 'var(--text-secondary)' }}>
        {description}
      </p>
      <div className="flex items-center gap-3">
        {onRetry && (
          <Button variant="primary" onClick={onRetry}>
            Retry
          </Button>
        )}
      </div>
    </div>
  );
}
