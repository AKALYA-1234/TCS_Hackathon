import React from 'react';

/**
 * Reusable SVG patterns for the 5 waste types:
 * AH - After-hours (diagonal stripes)
 * GC - Ghost cooling (dot grid)
 * OC - Overcooling (cross-hatch)
 * ES - Early start (horizontal bars)
 * PL - Possible leakage (vertical stripes)
 */
export function SVGWastePatterns() {
  return (
    <svg style={{ position: 'absolute', width: 0, height: 0, overflow: 'hidden' }} aria-hidden="true">
      <defs>
        {/* AH: Diagonal stripes */}
        <pattern id="pat-ah" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="8" stroke="var(--waste-ah)" strokeWidth="2.5" />
        </pattern>

        {/* GC: Dot grid */}
        <pattern id="pat-gc" width="8" height="8" patternUnits="userSpaceOnUse">
          <circle cx="4" cy="4" r="1.75" fill="var(--waste-gc)" />
        </pattern>

        {/* OC: Cross-hatch diamond */}
        <pattern id="pat-oc" width="10" height="10" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="10" stroke="var(--waste-oc)" strokeWidth="1.5" />
          <line x1="0" y1="0" x2="10" y2="0" stroke="var(--waste-oc)" strokeWidth="1.5" />
        </pattern>

        {/* ES: Horizontal bars */}
        <pattern id="pat-es" width="8" height="6" patternUnits="userSpaceOnUse">
          <line x1="0" y1="3" x2="8" y2="3" stroke="var(--waste-es)" strokeWidth="2" />
        </pattern>

        {/* PL: Vertical stripes */}
        <pattern id="pat-pl" width="6" height="8" patternUnits="userSpaceOnUse">
          <line x1="3" y1="0" x2="3" y2="8" stroke="var(--waste-pl)" strokeWidth="2" />
        </pattern>

        {/* Forecast hatched bar pattern */}
        <pattern id="pat-forecast" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="8" stroke="var(--accent)" strokeWidth="2" opacity="0.6" />
        </pattern>

        {/* Timetable non-operating hatched pattern */}
        <pattern id="pat-disabled-slot" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="8" stroke="var(--text-muted)" strokeWidth="1" opacity="0.2" />
        </pattern>
      </defs>
    </svg>
  );
}

export const WASTE_TYPES = {
  ah: { code: 'AH', name: 'After-hours', colorVar: 'var(--waste-ah)', patternId: 'url(#pat-ah)', symbol: '///' },
  gc: { code: 'GC', name: 'Ghost cooling', colorVar: 'var(--waste-gc)', patternId: 'url(#pat-gc)', symbol: ':::' },
  oc: { code: 'OC', name: 'Overcooling', colorVar: 'var(--waste-oc)', patternId: 'url(#pat-oc)', symbol: 'XXX' },
  es: { code: 'ES', name: 'Early start', colorVar: 'var(--waste-es)', patternId: 'url(#pat-es)', symbol: '===' },
  pl: { code: 'PL', name: 'Possible leakage', colorVar: 'var(--waste-pl)', patternId: 'url(#pat-pl)', symbol: '|||' }
};

export function WastePatternIcon({ type, size = 16 }) {
  const w = WASTE_TYPES[type?.toLowerCase()] || WASTE_TYPES.ah;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0 rounded-[3px] overflow-hidden">
      <rect
        x="0.75"
        y="0.75"
        width={size - 1.5}
        height={size - 1.5}
        rx="2.5"
        fill={w.patternId}
        stroke={w.colorVar}
        strokeWidth="1.5"
      />
    </svg>
  );
}

export function WasteBadge({ type, size = 'md' }) {
  const w = WASTE_TYPES[type?.toLowerCase()] || WASTE_TYPES.ah;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded font-medium ${
        size === 'sm' ? 'text-xs' : 'text-sm'
      }`}
      style={{
        backgroundColor: 'var(--bg-well)',
        border: '1px solid var(--border-subtle)',
        color: 'var(--text-primary)'
      }}
    >
      <WastePatternIcon type={type} size={14} />
      <span className="font-semibold text-xs tracking-wide" style={{ color: w.colorVar }}>
        {w.code}
      </span>
      <span>{w.name}</span>
    </span>
  );
}
