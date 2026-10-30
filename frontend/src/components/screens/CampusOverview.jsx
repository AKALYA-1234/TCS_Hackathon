import React from 'react';
import { ArrowUpRight, CheckCircle2, ChevronRight, Users, Zap, Clock } from 'lucide-react';
import { WASTE_TYPES, WastePatternIcon } from '../ui/SVGWastePatterns';
import { SkeletonBlock } from '../ui/BaseComponents';
import { LiveWeatherStrip } from '../ui/LiveWeatherStrip';

export function CampusOverview({ data, liveState, loading, onSelectRoom, onReviewProposals, onNavigateWasteEvents }) {
  if (loading && !data) {
    return (
      <div className="space-y-6">
        <SkeletonBlock height={40} width={300} />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <SkeletonBlock height={140} radius={20} />
          <SkeletonBlock height={140} radius={20} />
          <SkeletonBlock height={140} radius={20} />
          <SkeletonBlock height={140} radius={20} />
        </div>
        <SkeletonBlock height={400} radius={20} />
      </div>
    );
  }

  const kpis = data?.kpis || {};
  const heatmapRaw = data?.heatmap || [];
  const topWasteRaw = data?.top_waste_ranking || [];

  // Live stream overlays
  const totalPower = liveState?.totalPowerKw ?? kpis.total_power_kw ?? 74.4;
  const totalWasteKwh = liveState?.totalWasteKwh ?? kpis.total_waste_kwh ?? 14.5;
  const totalWasteInr = liveState?.totalWasteInr ?? kpis.total_waste_inr ?? 152.25;
  const wasteEventCount = liveState?.wasteEventCount ?? kpis.waste_event_count ?? 1;
  const verifiedSavingsEst = liveState?.verifiedSavingsInr ?? kpis.verified_savings_inr ?? 152.25;
  const pendingApprovals = liveState?.pendingApprovalsCount ?? 1;
  const simClock = liveState?.simulatedClock || 'Thu 29 Oct · 14:35';
  const activeAnomalies = liveState?.activeAnomalies || {};

  // Augment heatmap with latest telemetry from live store
  // Augment heatmap with latest telemetry from live store
  const heatmap = heatmapRaw.map((room) => {
    const liveEntry = liveState?.latestByRoom?.[room.room_id];
    const power = liveEntry?.actual_power_kw ?? room.power_kw ?? 0.0;
    const baseline = liveEntry?.baseline_kw ?? (room.is_on ? 2.5 : 0.05);
    const occ = liveEntry?.occupancy ?? room.occupancy ?? 0;
    const roomTemp = liveEntry?.room_temp_c ?? room.room_temp_c ?? 24.0;
    const setTemp = liveEntry?.set_temp_c ?? room.set_temp_c ?? 24.0;
    const isOn = liveEntry?.on_off_status === 'ON' || (liveEntry ? false : room.is_on);

    // Active injected anomaly on this room
    const anom = activeAnomalies[room.room_id]?.type;

    // Derived waste % based on physics:
    // If room is off or low standby power, waste is minimal (<3%)
    // If active anomaly is present, waste corresponds to anomaly severity (35-45%)
    // If cooling empty room (zero occupancy with active high power), waste is high (25-50%)
    // If occupied and tracking near setpoint, waste is low/healthy (4-12%)
    let wastePct = 0;
    if (!isOn || power < 0.3) {
      wastePct = 0;
    } else if (anom) {
      wastePct = anom === 'ghost_cooling' ? 42 : 36;
    } else if (occ === 0 && power > 1.5) {
      // Empty room drawing active cooling power
      const deltaTemp = Math.max(0, setTemp - roomTemp);
      wastePct = Math.min(58, Math.max(22, Math.round(28 + deltaTemp * 8 + (power / 5.0) * 12)));
    } else if (power > baseline + 0.3) {
      // Running above baseline with occupants
      wastePct = Math.min(28, Math.max(5, Math.round(((power - baseline) / Math.max(0.1, power)) * 35)));
    } else {
      wastePct = Math.round(Math.max(2, (power / Math.max(1, baseline)) * 5));
    }

    return {
      ...room,
      power_kw: power,
      occupancy: occ,
      room_temp_c: roomTemp,
      set_temp_c: setTemp,
      is_on: isOn,
      waste: wastePct,
      anomaly_type: anom
    };
  });

  // Dynamic Building Groupings
  const engRooms = heatmap.filter(r => r.building === 'Engineering Hall' || r.room_id.startsWith('eng-'));
  const sciRooms = heatmap.filter(r => r.building === 'Science Complex' || r.room_id.startsWith('sci-'));
  const admRooms = heatmap.filter(r => r.building === 'Administration Block' || r.room_id.startsWith('adm-'));

  const getHeatmapColor = (wastePct) => {
    if (wastePct >= 25) return { bg: 'rgba(255, 122, 112, 0.12)', border: 'var(--status-failed)', label: 'High' };
    if (wastePct >= 15) return { bg: 'rgba(255, 184, 77, 0.12)', border: 'var(--status-review)', label: 'Elevated' };
    if (wastePct >= 5) return { bg: 'var(--bg-card)', border: 'var(--border-subtle)', label: 'Low' };
    return { bg: 'rgba(91, 214, 127, 0.08)', border: 'rgba(91, 214, 127, 0.3)', label: 'Healthy' };
  };

  // Live top recoverable waste list
  const topWasteList = topWasteRaw.length > 0 ? topWasteRaw : [
    { room_id: 'eng-102', wasted_inr: 9400, wasted_kwh: 1021, events_count: 3 },
    { room_id: 'eng-101', wasted_inr: 7800, wasted_kwh: 847, events_count: 2 },
    { room_id: 'adm-101', wasted_inr: 5600, wasted_kwh: 608, events_count: 1 },
    { room_id: 'sci-201', wasted_inr: 4500, wasted_kwh: 489, events_count: 1 },
    { room_id: 'adm-201', wasted_inr: 3400, wasted_kwh: 369, events_count: 1 }
  ];

  // Closed loop status strip counts
  const activeRoomsCount = heatmap.filter(r => r.is_on).length;

  return (
    <div className="space-y-[24px] animate-in fade-in duration-150">
      {/* 1. Page Header */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-3">
          <div>
            <h1 className="text-[32px] leading-[38px] font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              Campus overview
            </h1>
            <p className="text-[13px] leading-[18px] mt-1" style={{ color: 'var(--text-secondary)' }}>
              All campus · {simClock}
            </p>
          </div>

          {/* Tariffs Badges */}
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="px-3 py-1 rounded-full text-xs font-semibold tabular-nums"
              style={{ backgroundColor: 'var(--bg-well)', color: 'var(--text-secondary)' }}
            >
              Standard tariff · ₹9.20/kWh
            </span>
            <span
              className="px-3 py-1 rounded-full text-xs font-semibold tabular-nums"
              style={{ backgroundColor: 'var(--status-review-bg)', color: 'var(--status-review)' }}
            >
              Peak from 18:00 · ₹11.80/kWh
            </span>
          </div>
        </div>

        {/* Closed-Loop Status Strip: Equal-width, equal-height cards without numbers, responsive 7 / 4+3 / 2 */}
        <div
          className="mt-4 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3"
        >
          {[
            {
              name: 'Sense',
              val: `${activeRoomsCount || 15} rooms live`,
              state: 'success',
              dot: 'var(--status-healthy)',
              onClick: () => {}
            },
            {
              name: 'Understand',
              val: `${wasteEventCount} waste active`,
              state: wasteEventCount > 0 ? 'review' : 'idle',
              dot: wasteEventCount > 0 ? 'var(--status-review)' : null,
              onClick: () => {}
            },
            {
              name: 'Propose',
              val: `${pendingApprovals} drafted`,
              state: pendingApprovals > 0 ? 'accent' : 'idle',
              dot: pendingApprovals > 0 ? 'var(--accent)' : null,
              onClick: onReviewProposals
            },
            {
              name: 'Validate',
              val: 'Rules passed',
              state: 'success',
              dot: 'var(--status-healthy)',
              onClick: () => {}
            },
            {
              name: 'Approve',
              val: `${pendingApprovals} pending`,
              state: pendingApprovals > 0 ? 'accent' : 'idle',
              dot: pendingApprovals > 0 ? 'var(--accent)' : null,
              onClick: onReviewProposals
            },
            {
              name: 'Act',
              val: 'Commands acked',
              state: 'idle',
              dot: null,
              onClick: () => {}
            },
            {
              name: 'Verify',
              val: `₹${verifiedSavingsEst} saved`,
              state: 'success',
              dot: 'var(--status-healthy)',
              onClick: () => {}
            }
          ].map((s) => {
            const isAccent = s.state === 'accent';
            const isSuccess = s.state === 'success';
            const isReview = s.state === 'review';

            return (
              <button
                key={s.name}
                onClick={s.onClick}
                className="p-3.5 rounded-[5px] border text-left flex flex-col justify-between transition-all cursor-pointer relative hover:shadow-xs group min-h-[72px]"
                style={{
                  backgroundColor: isAccent ? 'var(--accent-subtle)' : 'var(--bg-card)',
                  borderColor: isAccent ? 'var(--accent)' : (isSuccess ? 'rgba(27, 122, 58, 0.35)' : 'var(--border-subtle)')
                }}
              >
                <div className="flex items-center justify-between gap-1.5 w-full">
                  <span
                    className="text-xs font-bold uppercase tracking-wider"
                    style={{
                      color: isAccent ? 'var(--accent)' : (isSuccess ? 'var(--status-healthy)' : 'var(--text-secondary)')
                    }}
                  >
                    {s.name}
                  </span>
                  {s.dot ? (
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: s.dot }}
                    />
                  ) : (
                    <span className="w-2 h-2 rounded-full shrink-0 bg-stone-300 dark:bg-stone-700" />
                  )}
                </div>
                <div
                  className="text-xs font-extrabold mt-1 truncate"
                  style={{ color: isAccent ? 'var(--accent)' : 'var(--text-primary)' }}
                >
                  {s.val}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 1b. Live & Simulated Weather Ambient Strip */}
      <LiveWeatherStrip simClock={simClock} />

      {/* 2. Top 5 Dashboard KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Card A: Total Energy Usage */}
        <div
          className="p-5 rounded-[5px] flex flex-col justify-between min-h-[210px] h-full border shadow-xs"
          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
        >
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">
              Total energy usage
            </span>
            <div className="flex items-baseline gap-1 mt-1.5">
              <span className="text-[32px] leading-none font-extrabold font-mono tabular-nums" style={{ color: 'var(--text-primary)' }}>
                {Math.round(totalWasteKwh + 185.0)}
              </span>
              <span className="text-xs font-bold text-stone-500">kWh today</span>
            </div>
          </div>

          {/* Sparkline */}
          <div className="my-1.5">
            <svg viewBox="0 0 100 24" className="w-full h-7 overflow-visible">
              <polygon points="0,22 15,20 30,19 45,17 60,15 75,13 85,12 95,14 100,16 100,24 0,24" fill="var(--accent-subtle)" />
              <path d="M 0 22 L 15 20 L 30 19 L 45 17 L 60 15 L 75 13 L 85 12 L 95 14 L 100 16" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </div>

          <div className="text-[11px] leading-tight flex items-center justify-between border-t pt-2" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
            <span>Live draw:</span>
            <span className="font-bold font-mono" style={{ color: 'var(--text-primary)' }}>{totalPower} kW</span>
          </div>
        </div>

        {/* Card B: Total Energy Saved */}
        <div
          className="p-5 rounded-[5px] flex flex-col justify-between min-h-[210px] h-full border shadow-xs"
          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
        >
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">
                Total energy saved
              </span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                Verified
              </span>
            </div>
            <div className="flex items-baseline gap-1 mt-1.5">
              <span className="text-[32px] leading-none font-extrabold font-mono tabular-nums text-emerald-600 dark:text-emerald-400">
                12.2–16.8
              </span>
              <span className="text-xs font-bold text-stone-500">kWh</span>
            </div>
          </div>

          {/* Sparkline Range */}
          <div className="my-1.5">
            <svg viewBox="0 0 100 24" className="w-full h-7 overflow-visible">
              <polygon points="0,20 20,18 40,15 60,11 80,8 100,6 100,24 0,24" fill="rgba(27, 122, 58, 0.15)" />
              <path d="M 0 20 L 20 18 L 40 15 L 60 11 L 80 8 L 100 6" fill="none" stroke="var(--status-healthy)" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </div>

          <div className="text-[11px] leading-tight flex items-center justify-between border-t pt-2" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
            <span>Best estimate:</span>
            <span className="font-bold font-mono text-emerald-600 dark:text-emerald-400">14.5 kWh</span>
          </div>
        </div>

        {/* Card C: Cost Saved */}
        <div
          className="p-5 rounded-[5px] flex flex-col justify-between min-h-[210px] h-full border shadow-xs"
          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
        >
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">
                Cost saved
              </span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-blue-500/15 text-blue-600 dark:text-blue-400">
                Tariff: ₹10.50/kWh
              </span>
            </div>
            <div className="flex items-baseline gap-1 mt-1.5">
              <span className="text-[32px] leading-none font-extrabold font-mono tabular-nums" style={{ color: 'var(--text-primary)' }}>
                ₹128–176
              </span>
            </div>
          </div>

          {/* Sparkline */}
          <div className="my-1.5">
            <svg viewBox="0 0 100 24" className="w-full h-7 overflow-visible">
              <polygon points="0,22 25,20 50,17 75,13 100,9 100,24 0,24" fill="rgba(0, 98, 204, 0.15)" />
              <path d="M 0 22 L 25 20 L 50 17 L 75 13 L 100 9" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </div>

          <div className="text-[11px] leading-tight flex items-center justify-between border-t pt-2" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
            <span>Projected / month (est.):</span>
            <span className="font-bold font-mono" style={{ color: 'var(--text-primary)' }}>₹4,560</span>
          </div>
        </div>

        {/* Card D: Anomaly Detection */}
        <div
          onClick={() => (onNavigateWasteEvents ? onNavigateWasteEvents() : onReviewProposals?.())}
          className="p-5 rounded-[5px] flex flex-col justify-between min-h-[210px] h-full border shadow-xs cursor-pointer hover:border-amber-500/50 transition-all"
          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
        >
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">
                Anomaly detection
              </span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                Detector: Online
              </span>
            </div>
            <div className="flex items-baseline gap-1.5 mt-1.5">
              <span className="text-[32px] leading-none font-extrabold font-mono tabular-nums text-amber-600">
                {wasteEventCount}
              </span>
              <span className="text-xs font-bold text-stone-500">active ({wasteEventCount} today)</span>
            </div>
          </div>

          {/* 5-type patterned mini stacked bar */}
          <div className="my-1.5">
            <div className="flex h-3 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--bg-well)' }}>
              <div style={{ width: '35%', background: 'url(#pat-ah)', backgroundColor: 'var(--waste-ah)' }} title="After-hours: 35%" />
              <div style={{ width: '30%', background: 'url(#pat-gc)', backgroundColor: 'var(--waste-gc)' }} title="Ghost cooling: 30%" />
              <div style={{ width: '18%', background: 'url(#pat-oc)', backgroundColor: 'var(--waste-oc)' }} title="Overcooling: 18%" />
              <div style={{ width: '10%', background: 'url(#pat-es)', backgroundColor: 'var(--waste-es)' }} title="Empty setback: 10%" />
              <div style={{ width: '7%', background: 'url(#pat-pl)', backgroundColor: 'var(--waste-pl)' }} title="Parasitic: 7%" />
            </div>
          </div>

          <div className="text-[11px] leading-tight flex items-center justify-between border-t pt-2" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
            <span>Top waste: Ghost Cooling</span>
            <span className="font-bold text-amber-600 hover:underline">View Events →</span>
          </div>
        </div>

        {/* Card E: Efficiency */}
        <div
          className="p-5 rounded-[5px] flex flex-col justify-between min-h-[210px] h-full border shadow-xs"
          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
        >
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">
                Useful Energy Share
              </span>
              <span
                className="text-stone-400 cursor-help"
                title="Efficiency = 1 - (wasted_kwh / total_kwh) * 100. Useful energy directly providing thermal comfort."
              >
                ⓘ
              </span>
            </div>
            <div className="flex items-baseline gap-1 mt-1.5">
              <span className="text-[32px] leading-none font-extrabold font-mono tabular-nums text-indigo-600 dark:text-indigo-400">
                {Math.round((1 - (totalWasteKwh / Math.max(1, totalWasteKwh + 185.0))) * 100)}%
              </span>
            </div>
          </div>

          {/* Efficiency Progress Bar */}
          <div className="my-1.5">
            <div className="h-3 w-full rounded-full overflow-hidden bg-stone-100 dark:bg-stone-800 p-0.5">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.round((1 - (totalWasteKwh / Math.max(1, totalWasteKwh + 185.0))) * 100)}%`,
                  backgroundColor: 'var(--accent)'
                }}
              />
            </div>
          </div>

          <div className="text-[11px] leading-tight flex items-center justify-between border-t pt-2" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
            <span>Wasted share:</span>
            <span className="font-bold font-mono text-amber-600">
              {Math.round((totalWasteKwh / Math.max(1, totalWasteKwh + 185.0)) * 100)}%
            </span>
          </div>
        </div>
      </div>

      {/* 3. Main Row: Live Room Heatmap + Top Recoverable Waste */}
      <div className="flex flex-col lg:flex-row gap-[18px]">
        {/* Heatmap: Takes remaining width on desktop */}
        <div
          className="flex-1 min-w-0 p-6 rounded-[5px]"
          style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}
        >
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
            <div>
              <h2 className="text-[20px] font-bold" style={{ color: 'var(--text-primary)' }}>
                Live room heatmap
              </h2>
              <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                Color shows today's waste as a share of each room's energy. Click any tile to inspect live telemetry.
              </p>
            </div>

            {/* Heatmap Legend */}
            <div className="flex items-center gap-1.5 flex-wrap text-[11px] font-semibold">
              <span className="px-2 py-0.5 rounded" style={{ backgroundColor: 'var(--status-healthy-bg)', color: 'var(--status-healthy)' }}>
                Healthy &lt; 5%
              </span>
              <span className="px-2 py-0.5 rounded" style={{ backgroundColor: 'var(--bg-well)', color: 'var(--text-secondary)' }}>
                Low 5–14%
              </span>
              <span className="px-2 py-0.5 rounded" style={{ backgroundColor: 'var(--status-review-bg)', color: 'var(--status-review)' }}>
                Elevated 15–24%
              </span>
              <span className="px-2 py-0.5 rounded" style={{ backgroundColor: 'var(--status-failed-bg)', color: 'var(--status-failed)' }}>
                High ≥ 25%
              </span>
            </div>
          </div>

          {/* Blocks */}
          <div className="space-y-6">
            {/* Block 1: Engineering Hall */}
            <div>
              <div className="flex justify-between items-center text-xs font-bold mb-3" style={{ color: 'var(--text-tertiary)' }}>
                <span>Engineering Hall</span>
                <span>{engRooms.length} rooms live</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {engRooms.map((r) => {
                  const style = getHeatmapColor(r.waste);
                  return (
                    <button
                      key={r.room_id}
                      onClick={() => onSelectRoom(r.room_id)}
                      className="p-3.5 rounded-xl border text-left transition-all hover:scale-[1.02] cursor-pointer"
                      style={{ backgroundColor: style.bg, borderColor: style.border }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-sm truncate" style={{ color: 'var(--text-primary)' }}>
                          {r.name || r.room_id}
                        </span>
                        {r.anomaly_type && (
                          <span
                            className="w-5 h-3 rounded-sm shrink-0"
                            style={{
                              background: WASTE_TYPES[r.anomaly_type]?.patternId || 'var(--status-failed)',
                              backgroundColor: WASTE_TYPES[r.anomaly_type]?.colorVar || 'var(--status-failed)'
                            }}
                            title={`Anomaly: ${r.anomaly_type}`}
                          />
                        )}
                      </div>
                      <div className="mt-1 flex items-baseline gap-1">
                        <span className="text-xl font-extrabold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                          {r.waste}%
                        </span>
                        <span className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                          waste
                        </span>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                        <span>❄ {r.is_on ? 'On' : 'Off'} ({r.power_kw?.toFixed(1)} kW)</span>
                        <span className="flex items-center gap-0.5 tabular-nums">
                          <Users size={11} /> {r.occupancy}
                        </span>
                      </div>
                      <div className="mt-1 text-[10px] font-semibold" style={{ color: style.border }}>
                        {r.anomaly_type ? `Alert: ${r.anomaly_type}` : style.label}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Block 2: Science Complex */}
            <div>
              <div className="flex justify-between items-center text-xs font-bold mb-3" style={{ color: 'var(--text-tertiary)' }}>
                <span>Science Complex</span>
                <span>{sciRooms.length} rooms live</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {sciRooms.map((r) => {
                  const style = getHeatmapColor(r.waste);
                  return (
                    <button
                      key={r.room_id}
                      onClick={() => onSelectRoom(r.room_id)}
                      className="p-3.5 rounded-xl border text-left transition-all hover:scale-[1.02] cursor-pointer"
                      style={{ backgroundColor: style.bg, borderColor: style.border }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-sm truncate" style={{ color: 'var(--text-primary)' }}>
                          {r.name || r.room_id}
                        </span>
                        {r.anomaly_type && (
                          <span
                            className="w-5 h-3 rounded-sm shrink-0"
                            style={{
                              background: WASTE_TYPES[r.anomaly_type]?.patternId || 'var(--status-failed)',
                              backgroundColor: WASTE_TYPES[r.anomaly_type]?.colorVar || 'var(--status-failed)'
                            }}
                            title={`Anomaly: ${r.anomaly_type}`}
                          />
                        )}
                      </div>
                      <div className="mt-1 flex items-baseline gap-1">
                        <span className="text-xl font-extrabold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                          {r.waste}%
                        </span>
                        <span className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                          waste
                        </span>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                        <span>❄ {r.is_on ? 'On' : 'Off'} ({r.power_kw?.toFixed(1)} kW)</span>
                        <span className="flex items-center gap-0.5 tabular-nums">
                          <Users size={11} /> {r.occupancy}
                        </span>
                      </div>
                      <div className="mt-1 text-[10px] font-semibold" style={{ color: style.border }}>
                        {r.anomaly_type ? `Alert: ${r.anomaly_type}` : style.label}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Block 3: Administration Block */}
            <div>
              <div className="flex justify-between items-center text-xs font-bold mb-3" style={{ color: 'var(--text-tertiary)' }}>
                <span>Administration Block</span>
                <span>{admRooms.length} rooms live</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {admRooms.map((r) => {
                  const style = getHeatmapColor(r.waste);
                  return (
                    <button
                      key={r.room_id}
                      onClick={() => onSelectRoom(r.room_id)}
                      className="p-3.5 rounded-xl border text-left transition-all hover:scale-[1.02] cursor-pointer"
                      style={{ backgroundColor: style.bg, borderColor: style.border }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-sm truncate" style={{ color: 'var(--text-primary)' }}>
                          {r.name || r.room_id}
                        </span>
                        {r.anomaly_type && (
                          <span
                            className="w-5 h-3 rounded-sm shrink-0"
                            style={{
                              background: WASTE_TYPES[r.anomaly_type]?.patternId || 'var(--status-failed)',
                              backgroundColor: WASTE_TYPES[r.anomaly_type]?.colorVar || 'var(--status-failed)'
                            }}
                            title={`Anomaly: ${r.anomaly_type}`}
                          />
                        )}
                      </div>
                      <div className="mt-1 flex items-baseline gap-1">
                        <span className="text-xl font-extrabold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                          {r.waste}%
                        </span>
                        <span className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                          waste
                        </span>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                        <span>❄ {r.is_on ? 'On' : 'Off'} ({r.power_kw?.toFixed(1)} kW)</span>
                        <span className="flex items-center gap-0.5 tabular-nums">
                          <Users size={11} /> {r.occupancy}
                        </span>
                      </div>
                      <div className="mt-1 text-[10px] font-semibold" style={{ color: style.border }}>
                        {r.anomaly_type ? `Alert: ${r.anomaly_type}` : style.label}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Top Recoverable Waste Panel (362px) */}
        <div
          className="w-full lg:w-[362px] shrink-0 p-6 rounded-[5px] flex flex-col justify-between"
          style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}
        >
          <div>
            <h2 className="text-[20px] font-bold" style={{ color: 'var(--text-primary)' }}>
              Top recoverable waste
            </h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
              Ranked by ₹ per month at current rates
            </p>

            {/* List */}
            <div className="mt-6 space-y-4">
              {topWasteList.map((item, idx) => (
                <div
                  key={item.room_id || idx}
                  onClick={() => onSelectRoom(item.room_id)}
                  className="flex items-center justify-between py-2 border-b last:border-0 cursor-pointer hover:opacity-80 transition-opacity"
                  style={{ borderColor: 'var(--border-subtle)' }}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
                      style={{ backgroundColor: 'var(--bg-well)', color: 'var(--text-secondary)' }}
                    >
                      {idx + 1}
                    </span>
                    <div>
                      <div className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>
                        {item.room_id}
                      </div>
                      <div className="flex items-center gap-1.5 text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                        <span className="text-[11px]">{item.events_count} event{item.events_count !== 1 ? 's' : ''}</span>
                      </div>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-sm font-extrabold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                      ₹{item.wasted_inr || 0}<span className="text-[11px] font-normal text-stone-400">/mo</span>
                    </div>
                    <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                      {item.wasted_kwh || 0} kWh
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-8 pt-4 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                Top waste total
              </span>
              <span className="text-lg font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                ₹{topWasteList.reduce((acc, it) => acc + (it.wasted_inr || 0), 0).toLocaleString()}
                <span className="text-xs font-normal text-stone-400">/mo</span>
              </span>
            </div>

            <button
              onClick={onReviewProposals}
              className="w-full py-3 rounded-xl font-bold text-sm cursor-pointer shadow-sm transition-all active:scale-[0.98]"
              style={{ backgroundColor: 'var(--accent)', color: '#FFFFFF' }}
            >
              Review {pendingApprovals} proposal{pendingApprovals !== 1 ? 's' : ''}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
