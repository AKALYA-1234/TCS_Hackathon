import React, { useState } from 'react';
import { ChevronRight, X, ArrowRight, Zap, Filter } from 'lucide-react';
import { WASTE_TYPES } from '../ui/SVGWastePatterns';
import { Button } from '../ui/BaseComponents';

export function WasteEvents({
  events = [],
  onSelectEvent,
  onOpenProposal,
  onNavigateRoom
}) {
  const [selectedType, setSelectedType] = useState('all');
  const [selectedRoom, setSelectedRoom] = useState('All rooms');
  const [timeRange, setTimeRange] = useState('Today');
  const [activeDrawerEvent, setActiveDrawerEvent] = useState(null);

  // Reference sample event data if events empty or loading
  const fallbackEvents = [
    { id: 'we-1', cause: 'Ghost cooling', code: 'gc', room: 'Lab 204', started: '13:05', duration: '1 h 30 m', energy: 10, cost: 100, confidence: 94, status: 'Ongoing', proposalId: 'P-1041', peak: '3.7 kW', evidenceReason: 'Camera counted 0 people since 13:05. The timetable has no class in this room until Friday 09:00. Both units are cooling at 22 °C and drawing 3.7 kW against 0–0.4 kW expected.' },
    { id: 'we-2', cause: 'Ghost cooling', code: 'gc', room: 'Lab 205', started: '12:10', duration: '1 h 10 m', energy: 7, cost: 70, confidence: 78, status: 'Closed', proposalId: null, peak: '2.4 kW', evidenceReason: 'Zero occupancy detected for >60 mins. Unit automatically switched off via scheduled timer.' },
    { id: 'we-3', cause: 'Ghost cooling', code: 'gc', room: 'A - 301', started: '11:20', duration: '1 h 30 m', energy: 11, cost: 110, confidence: 91, status: 'Closed', proposalId: null, peak: '3.2 kW', evidenceReason: 'Auditorium vacant between lectures while 3 split units operated continuously.' },
    { id: 'we-4', cause: 'Overcooling', code: 'oc', room: 'Lab 204', started: '10:40', duration: '1 h 20 m', energy: 8, cost: 85, confidence: 86, status: 'Closed', proposalId: null, peak: '3.8 kW', evidenceReason: 'Thermostat setpoint reduced to 18 °C despite 23 °C ambient outside and 24 occupants.' },
    { id: 'we-5', cause: 'Overcooling', code: 'oc', room: 'Board Room', started: '09:30', duration: '5 h 05 m', energy: 13, cost: 138, confidence: 89, status: 'Ongoing', flagged: 'Blocked', proposalId: null, peak: '2.8 kW', evidenceReason: 'VIP meeting ongoing; automation blocked by active override switch.' },
    { id: 'we-6', cause: 'Early start', code: 'es', room: 'Lab 204', started: '07:10', duration: '1 h 20 m', energy: 4, cost: 42, confidence: 88, status: 'Closed', proposalId: null, peak: '2.1 kW', evidenceReason: 'Pre-cool initiated at 07:10 for a 09:00 class (80 mins ahead instead of recommended 20 mins).' },
    { id: 'we-7', cause: 'Early start', code: 'es', room: 'Lab 102', started: '07:05', duration: '1 h 25 m', energy: 5, cost: 53, confidence: 82, status: 'Closed', proposalId: 'P-1044', peak: '2.5 kW', evidenceReason: 'AC running unattended 115 minutes prior to class start.' },
    { id: 'we-8', cause: 'Possible leakage', code: 'pl', room: 'Reception', started: '06:00', duration: '8 h 35 m', energy: 5, cost: 41, confidence: 61, status: 'Ongoing', flagged: 'Needs inspection', proposalId: null, peak: '1.2 kW', evidenceReason: 'Continuous 420W baseline draw during sealed hours indicating refrigerant leak or faulty contactor.' },
    { id: 'we-9', cause: 'After-hours', code: 'ah', room: 'A - 301', started: '01:00', duration: '5 h 00 m', energy: 12, cost: 99, confidence: 93, status: 'Closed', proposalId: null, peak: '3.0 kW', evidenceReason: 'AC ran overnight following evening guest lecture until janitorial shift.' },
    { id: 'we-10', cause: 'After-hours', code: 'ah', room: 'Accounts', started: 'Wed 23:30', duration: '6 h 40 m', energy: 10, cost: 82, confidence: 90, status: 'Closed', proposalId: null, peak: '1.9 kW', evidenceReason: 'Office unit left powered on after fiscal year-end closing.' },
    { id: 'we-11', cause: 'After-hours', code: 'ah', room: 'A - 101', started: 'Wed 22:00', duration: '8 h 10 m', energy: 17, cost: 139, confidence: 96, status: 'Closed', proposalId: 'P-1042', peak: '3.5 kW', evidenceReason: 'Classroom unit ran through night until dawn security patrol.' }
  ];

  // Map live events prop if present, else use realistic seeded fallback
  const normalizedEvents = events && events.length > 0 ? events.map(e => ({
    id: e.id,
    cause: e.event_type ? e.event_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Ghost Cooling',
    code: e.event_type === 'ghost_cooling' ? 'gc' :
          e.event_type === 'overcooling' ? 'oc' :
          e.event_type === 'early_start' ? 'es' :
          e.event_type === 'after_hours' ? 'ah' : 'pl',
    room: e.room_id || 'eng-101',
    started: e.start_time ? new Date(e.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '13:05',
    duration: '45 m',
    energy: Math.round(e.wasted_kwh || 14.5),
    cost: Math.round(e.wasted_cost_inr || 152),
    confidence: Math.round((e.confidence || 0.94) * 100),
    status: 'Ongoing',
    proposalId: 'P-1041',
    peak: '3.7 kW',
    evidenceReason: e.details?.scenario || 'Excess draw detected outside scheduled class hours.'
  })) : fallbackEvents;

  const displayList = normalizedEvents.filter((ev) => {
    if (selectedType !== 'all' && ev.code !== selectedType) return false;
    if (selectedRoom !== 'All rooms' && ev.room !== selectedRoom) return false;
    return true;
  });

  return (
    <div className="space-y-8 animate-in fade-in duration-300 relative">
      {/* 1. Header */}
      <div>
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
          Waste events
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          What Frostline found, how sure it is, and what it cost. Thursday 29 October.
        </p>

        {/* Filter Pills & Room Select */}
        <div className="mt-6 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setSelectedType('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer border transition-all`}
              style={{
                backgroundColor: selectedType === 'all' ? 'var(--accent-subtle)' : 'var(--bg-card)',
                borderColor: selectedType === 'all' ? 'var(--accent)' : 'var(--border-subtle)',
                color: selectedType === 'all' ? 'var(--accent)' : 'var(--text-secondary)'
              }}
            >
              All causes
            </button>
            {Object.entries(WASTE_TYPES).map(([code, meta]) => {
              const isSel = selectedType === code;
              return (
                <button
                  key={code}
                  onClick={() => setSelectedType(code)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer border transition-all"
                  style={{
                    backgroundColor: isSel ? 'var(--bg-well)' : 'var(--bg-card)',
                    borderColor: isSel ? meta.color : 'var(--border-subtle)',
                    color: isSel ? 'var(--text-primary)' : 'var(--text-secondary)'
                  }}
                >
                  <span
                    className="w-3.5 h-2.5 rounded-xs"
                    style={{ background: meta.pattern, backgroundColor: meta.color }}
                  />
                  <span>{meta.name}</span>
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-3">
            <div
              className="inline-flex p-1 rounded-xl"
              style={{ backgroundColor: 'var(--bg-well)', border: '1px solid var(--border-subtle)' }}
            >
              {['Today', '7 days'].map((t) => (
                <button
                  key={t}
                  onClick={() => setTimeRange(t)}
                  className="px-3 py-1 text-xs font-semibold rounded-lg cursor-pointer transition-all"
                  style={{
                    backgroundColor: timeRange === t ? 'var(--bg-card)' : 'transparent',
                    color: timeRange === t ? 'var(--text-primary)' : 'var(--text-secondary)',
                    boxShadow: timeRange === t ? 'var(--shadow-card)' : 'none'
                  }}
                >
                  {t}
                </button>
              ))}
            </div>

            <select
              value={selectedRoom}
              onChange={(e) => setSelectedRoom(e.target.value)}
              className="px-3 py-1.5 rounded-xl text-xs font-semibold border cursor-pointer"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="All rooms">All rooms</option>
              <option value="Lab 204">Lab 204</option>
              <option value="Lab 205">Lab 205</option>
              <option value="A - 301">A - 301</option>
              <option value="Board Room">Board Room</option>
              <option value="Reception">Reception</option>
            </select>
          </div>
        </div>
      </div>

      {/* 2. Waste Summary Cards (5 columns) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {[
          { code: 'ah', name: 'After-hours', kwh: 39, cost: '₹320', share: '38% of waste' },
          { code: 'gc', name: 'Ghost cooling', kwh: 28, cost: '₹280', share: '27% of waste' },
          { code: 'oc', name: 'Overcooling', kwh: 21, cost: '₹223', share: '21% of waste' },
          { code: 'es', name: 'Early start', kwh: 9, cost: '₹95', share: '9% of waste' },
          { code: 'pl', name: 'Possible leakage', kwh: 5, cost: '₹41', share: '5% of waste' }
        ].map((card) => {
          const meta = WASTE_TYPES[card.code];
          return (
            <div
              key={card.code}
              className="p-4 rounded-2xl border transition-all"
              style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
            >
              <div className="flex items-center gap-1.5 mb-2">
                <span
                  className="w-3.5 h-2.5 rounded-xs"
                  style={{ background: meta.pattern, backgroundColor: meta.color }}
                />
                <span className="text-xs font-semibold truncate" style={{ color: 'var(--text-secondary)' }}>
                  {card.name}
                </span>
              </div>
              <div className="text-2xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                {card.kwh} <span className="text-xs font-normal" style={{ color: 'var(--text-tertiary)' }}>kWh</span>
              </div>
              <div className="text-[11px] mt-1 tabular-nums" style={{ color: 'var(--text-tertiary)' }}>
                {card.cost} · {card.share}
              </div>
            </div>
          );
        })}
      </div>

      {/* 3. Waste Events Table */}
      <div
        className="rounded-2xl border overflow-hidden"
        style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}
      >
        <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>
            11 events
          </div>
          <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            Today, newest first
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
                <th className="py-3 px-4 font-medium">Cause</th>
                <th className="py-3 px-4 font-medium">Room</th>
                <th className="py-3 px-4 font-medium">Started</th>
                <th className="py-3 px-4 font-medium">Duration</th>
                <th className="py-3 px-4 font-medium">Energy</th>
                <th className="py-3 px-4 font-medium">Cost</th>
                <th className="py-3 px-4 font-medium">Confidence</th>
                <th className="py-3 px-4 font-medium">Status</th>
                <th className="py-3 px-4 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
              {displayList.map((ev) => {
                const meta = WASTE_TYPES[ev.code];
                return (
                  <tr
                    key={ev.id}
                    onClick={() => setActiveDrawerEvent(ev)}
                    className="cursor-pointer transition-colors hover:bg-slate-500/5"
                  >
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <span
                          className="w-3.5 h-2.5 rounded-xs shrink-0"
                          style={{ background: meta.pattern, backgroundColor: meta.color }}
                        />
                        <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                          {ev.cause}
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-bold" style={{ color: 'var(--text-primary)' }}>
                      {ev.room}
                    </td>
                    <td className="py-3.5 px-4 tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                      {ev.started}
                    </td>
                    <td className="py-3.5 px-4 tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                      {ev.duration}
                    </td>
                    <td className="py-3.5 px-4 font-semibold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                      {ev.energy} kWh
                    </td>
                    <td className="py-3.5 px-4 tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                      ₹{ev.cost}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 rounded-full bg-slate-200 dark:bg-white/10 overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${ev.confidence}%`,
                              backgroundColor: 'var(--accent)'
                            }}
                          />
                        </div>
                        <span className="font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                          {ev.confidence}%
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        {ev.status === 'Ongoing' ? (
                          <span
                            className="px-2 py-0.5 rounded text-[11px] font-semibold"
                            style={{ backgroundColor: 'var(--status-review-bg)', color: 'var(--status-review)' }}
                          >
                            Ongoing
                          </span>
                        ) : (
                          <span
                            className="px-2 py-0.5 rounded text-[11px] font-semibold"
                            style={{ backgroundColor: 'var(--bg-well)', color: 'var(--text-tertiary)' }}
                          >
                            Closed
                          </span>
                        )}
                        {ev.proposalId && (
                          <span className="text-[11px] font-mono font-medium" style={{ color: 'var(--accent)' }}>
                            {ev.proposalId}
                          </span>
                        )}
                        {ev.flagged && (
                          <span className="text-[11px] font-medium" style={{ color: 'var(--text-tertiary)' }}>
                            {ev.flagged}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <ChevronRight size={16} style={{ color: 'var(--text-tertiary)' }} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4. Slide-Out Evidence Drawer (Matching reference: Waste Events · Dark.png) */}
      {activeDrawerEvent && (
        <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[460px] shadow-2xl flex flex-col animate-in slide-in-from-right duration-200"
          style={{ backgroundColor: 'var(--bg-card)', borderLeft: '1px solid var(--border-separator)' }}
        >
          {/* Drawer Header */}
          <div className="p-6 border-b flex items-start justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
            <div>
              <div className="flex items-center gap-2">
                <span
                  className="w-3.5 h-2.5 rounded-xs"
                  style={{ background: WASTE_TYPES[activeDrawerEvent.code].pattern, backgroundColor: WASTE_TYPES[activeDrawerEvent.code].color }}
                />
                <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                  {activeDrawerEvent.cause}
                </span>
              </div>
              <h2 className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>
                {activeDrawerEvent.room}
              </h2>
              <div className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                {activeDrawerEvent.started} · {activeDrawerEvent.duration} · {activeDrawerEvent.status}
              </div>
            </div>

            <button
              onClick={() => setActiveDrawerEvent(null)}
              className="p-2 rounded-xl cursor-pointer hover:bg-slate-500/10"
              style={{ color: 'var(--text-secondary)' }}
            >
              <X size={20} />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Evidence Chart Box */}
            <div
              className="p-4 rounded-2xl border space-y-2"
              style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}
            >
              <div className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>
                Evidence
              </div>
              <div className="h-36 w-full">
                <svg className="w-full h-full" viewBox="0 0 380 120">
                  {/* Baseline Ribbon */}
                  <line x1="20" y1="100" x2="360" y2="100" stroke="var(--border-subtle)" strokeWidth="1" />
                  <rect x="180" y="20" width="160" height="80" fill={WASTE_TYPES[activeDrawerEvent.code].pattern} fillOpacity="0.25" stroke={WASTE_TYPES[activeDrawerEvent.code].color} strokeWidth="1" rx="4" />
                  {/* Telemetry spike */}
                  <path
                    d="M 20,95 L 175,95 L 180,25 L 340,30"
                    fill="none"
                    stroke="var(--accent)"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                  <line x1="180" y1="20" x2="180" y2="100" stroke="var(--accent)" strokeWidth="1" strokeDasharray="2 2" />
                  <text x="20" y="115" fill="var(--text-tertiary)" fontSize="9">12:00</text>
                  <text x="180" y="115" fill="var(--accent)" fontSize="9" fontWeight="bold">13:05</text>
                  <text x="340" y="115" fill="var(--text-tertiary)" fontSize="9">14:35</text>
                </svg>
              </div>
              <p className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                Grey band is the expected range. Shaded window is the event.
              </p>
            </div>

            {/* Metrics 4-cell Grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>Energy</div>
                <div className="text-xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>{activeDrawerEvent.energy} kWh</div>
              </div>
              <div className="p-3 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>Cost</div>
                <div className="text-xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>₹{activeDrawerEvent.cost}</div>
              </div>
              <div className="p-3 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>Confidence</div>
                <div className="text-xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>{activeDrawerEvent.confidence}%</div>
              </div>
              <div className="p-3 rounded-xl border" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>Peak draw</div>
                <div className="text-xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>{activeDrawerEvent.peak}</div>
              </div>
            </div>

            {/* Why Frostline thinks so */}
            <div className="space-y-2">
              <div className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>
                Why Frostline thinks so
              </div>
              <div className="text-xs space-y-2 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                <div className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ backgroundColor: 'var(--accent)' }} />
                  <span>{activeDrawerEvent.evidenceReason}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Drawer Actions */}
          <div className="p-6 border-t space-y-2" style={{ borderColor: 'var(--border-subtle)' }}>
            {activeDrawerEvent.proposalId && (
              <Button
                variant="primary"
                className="w-full justify-center"
                onClick={() => {
                  if (onOpenProposal) onOpenProposal(activeDrawerEvent.proposalId);
                  setActiveDrawerEvent(null);
                }}
              >
                Open proposal {activeDrawerEvent.proposalId}
              </Button>
            )}
            <Button
              variant="secondary"
              className="w-full justify-center"
              onClick={() => {
                if (onNavigateRoom) onNavigateRoom(activeDrawerEvent.room);
                setActiveDrawerEvent(null);
              }}
            >
              Go to {activeDrawerEvent.room}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
