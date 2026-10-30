import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  Clock, Shield, AlertTriangle, Check, RotateCcw, ChevronDown, ChevronRight,
  Minus, Plus, Info, CheckCircle2, XCircle, Search, ArrowRight, Lock, ExternalLink
} from 'lucide-react';

const WEEKDAYS = [
  { id: 0, short: 'Mon', name: 'Monday' },
  { id: 1, short: 'Tue', name: 'Tuesday' },
  { id: 2, short: 'Wed', name: 'Wednesday' },
  { id: 3, short: 'Thu', name: 'Thursday' },
  { id: 4, short: 'Fri', name: 'Friday' },
  { id: 5, short: 'Sat', name: 'Saturday' },
  { id: 6, short: 'Sun', name: 'Sunday' }
];

const START_HOUR = 7;
const END_HOUR = 20;
const HOURS_COUNT = END_HOUR - START_HOUR; // 13 hours: 07:00 to 20:00

function timeToMins(t) {
  if (!t) return 0;
  const parts = t.split(':');
  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
}

function minsToTime(m) {
  const h = Math.floor(m / 60);
  const min = m % 60;
  return `${h.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}`;
}

export function OptimizerScreen({ allRooms = [], onApplyProposal }) {
  // Room selection state
  const [selectedRoomId, setSelectedRoomId] = useState('lab-204');
  const [unitScope, setUnitScope] = useState('both'); // 'both' | 'unit_1' | 'unit_2'

  // Server data state
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Editable state
  const [editedBars, setEditedBars] = useState({});
  const [setpoint, setSetpoint] = useState(24.0);
  const [isDirty, setIsDirty] = useState(false);
  const [isRecalculating, setIsRecalculating] = useState(false);

  // Live preview results
  const [savingsData, setSavingsData] = useState(null);
  const [validationData, setValidationData] = useState(null);

  // UI state
  const [assumptionsOpen, setAssumptionsOpen] = useState(false);
  const [applyModalOpen, setApplyModalOpen] = useState(false);
  const [allRoomsDropdownOpen, setAllRoomsDropdownOpen] = useState(false);
  const [roomSearchQuery, setRoomSearchQuery] = useState('');
  const [toastMessage, setToastMessage] = useState(null);

  // Dragging interaction state
  // dragRef: { day, barIndex, handle: 'top' | 'bottom', startY, origMins, dayElRect }
  const dragRef = useRef(null);
  const [activeDragInfo, setActiveDragInfo] = useState(null);
  const gridContainerRef = useRef(null);
  const debounceTimerRef = useRef(null);

  // Fetch initial recommendation from backend
  const fetchRecommendation = useCallback(async (roomId, scope) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/optimizer/room/${encodeURIComponent(roomId)}/recommendation?unit_scope=${scope}`);
      if (!res.ok) {
        throw new Error(`Failed to load recommendation (Status ${res.status})`);
      }
      const json = await res.json();
      setData(json);
      setEditedBars(JSON.parse(JSON.stringify(json.recommended_runs_by_day || {})));
      setSetpoint(json.setpoint_c || 24.0);
      setSavingsData(json.savings);
      setValidationData(json.validation);
      setIsDirty(false);
    } catch (err) {
      setError(err.message || 'Error loading optimizer data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRecommendation(selectedRoomId, unitScope);
  }, [selectedRoomId, unitScope, fetchRecommendation]);

  // Debounced preview calculation
  const triggerPreview = useCallback((newBars, newSetpoint, newScope) => {
    setIsRecalculating(true);
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);

    debounceTimerRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`/api/optimizer/room/${encodeURIComponent(selectedRoomId)}/preview`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            bars_by_day: newBars,
            setpoint: newSetpoint,
            unit_scope: newScope
          })
        });
        if (res.ok) {
          const preview = await res.json();
          setSavingsData(preview.savings);
          setValidationData(preview.validation);
        }
      } catch (e) {
        console.error('Preview recalculation error:', e);
      } finally {
        setIsRecalculating(false);
      }
    }, 150);
  }, [selectedRoomId]);

  // Handle setpoint adjustment
  const handleSetpointChange = (delta) => {
    const minClamp = data?.min_temp_c ?? 22.0;
    const maxClamp = data?.max_temp_c ?? 26.0;
    const next = Math.max(minClamp, Math.min(maxClamp, Math.round((setpoint + delta) * 10) / 10));
    if (next !== setpoint) {
      setSetpoint(next);
      setIsDirty(true);
      triggerPreview(editedBars, next, unitScope);
    }
  };

  // Reset to recommended
  const handleResetToRecommended = () => {
    if (!data) return;
    setEditedBars(JSON.parse(JSON.stringify(data.recommended_runs_by_day || {})));
    setSetpoint(data.setpoint_c || 24.0);
    setSavingsData(data.savings);
    setValidationData(data.validation);
    setIsDirty(false);
  };

  // Drag handlers
  const handlePointerDown = (e, day, barIndex, handle) => {
    e.preventDefault();
    e.stopPropagation();

    const bar = editedBars[day]?.[barIndex];
    if (!bar) return;

    const origMins = handle === 'top' ? timeToMins(bar.start_time) : timeToMins(bar.end_time);

    dragRef.current = {
      day,
      barIndex,
      handle,
      startY: e.clientY,
      origMins,
      currentMins: origMins
    };

    setActiveDragInfo({ day, barIndex, handle });

    const onPointerMove = (ev) => {
      if (!dragRef.current) return;
      const { day: d, barIndex: bIdx, handle: h, startY, origMins } = dragRef.current;
      const deltaY = ev.clientY - startY;

      // 40px per 60 min -> 1 px = 1.5 min
      const deltaMins = Math.round((deltaY * (60 / 40)) / 5) * 5;
      let newMins = origMins + deltaMins;

      // Constraints
      newMins = Math.max(5 * 60, Math.min(23 * 60, newMins)); // 05:00 to 23:00

      setEditedBars((prev) => {
        const next = JSON.parse(JSON.stringify(prev));
        const currBar = next[d]?.[bIdx];
        if (!currBar) return prev;

        const currentStart = timeToMins(currBar.start_time);
        const currentEnd = timeToMins(currBar.end_time);

        if (h === 'top') {
          // Must end at least 30 min after start
          if (currentEnd - newMins < 30) newMins = currentEnd - 30;
          currBar.start_time = minsToTime(newMins);
        } else {
          // Must end at least 30 min after start
          if (newMins - currentStart < 30) newMins = currentStart + 30;
          currBar.end_time = minsToTime(newMins);
        }

        currBar.duration_hours = Math.round(((timeToMins(currBar.end_time) - timeToMins(currBar.start_time)) / 60) * 10) / 10;
        return next;
      });

      setIsDirty(true);
      triggerPreview(editedBars, setpoint, unitScope);
    };

    const onPointerUp = () => {
      dragRef.current = null;
      setActiveDragInfo(null);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  };

  // Keyboard navigation on drag handles (role="slider")
  const handleKeyDown = (e, day, barIndex, handle) => {
    let deltaMins = 0;
    if (e.key === 'ArrowUp') {
      deltaMins = e.shiftKey ? -15 : -5;
    } else if (e.key === 'ArrowDown') {
      deltaMins = e.shiftKey ? 15 : 5;
    } else if (e.key === 'Escape') {
      handleResetToRecommended();
      return;
    } else {
      return;
    }

    e.preventDefault();
    setEditedBars((prev) => {
      const next = JSON.parse(JSON.stringify(prev));
      const currBar = next[day]?.[barIndex];
      if (!currBar) return prev;

      const currentStart = timeToMins(currBar.start_time);
      const currentEnd = timeToMins(currBar.end_time);

      if (handle === 'top') {
        let newStart = Math.max(5 * 60, Math.min(currentEnd - 30, currentStart + deltaMins));
        currBar.start_time = minsToTime(newStart);
      } else {
        let newEnd = Math.max(currentStart + 30, Math.min(23 * 60, currentEnd + deltaMins));
        currBar.end_time = minsToTime(newEnd);
      }

      currBar.duration_hours = Math.round(((timeToMins(currBar.end_time) - timeToMins(currBar.start_time)) / 60) * 10) / 10;
      return next;
    });

    setIsDirty(true);
    triggerPreview(editedBars, setpoint, unitScope);
  };

  // Confirm and submit proposal
  const handleConfirmProposal = async () => {
    try {
      const res = await fetch('/api/proposals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'schedule_change',
          room_id: selectedRoomId,
          rules_per_weekday: editedBars,
          setpoint: setpoint,
          estimate: savingsData,
          validation: validationData,
          created_by: 'facility_admin'
        })
      });

      if (res.ok) {
        const json = await res.json();
        setApplyModalOpen(false);
        setToastMessage({
          title: 'Proposal sent for approval',
          message: `Created proposal ${json.proposal?.id || ''} for ${data?.room_name || selectedRoomId}.`
        });
        setTimeout(() => setToastMessage(null), 6000);
        if (onApplyProposal) {
          onApplyProposal({ room: data?.room_name || selectedRoomId, setpoint });
        }
      } else {
        const errJson = await res.json();
        alert(`Error submitting proposal: ${errJson.detail || 'Failed'}`);
      }
    } catch (e) {
      alert(`Network error submitting proposal: ${e.message}`);
    }
  };

  // Top 3 relevant rooms for switcher
  const relevantRooms = useMemo(() => {
    // Top 3 requested in spec: Lab 204 | A-101 | Lab 102
    return [
      { id: 'lab-204', label: 'Lab 204' },
      { id: 'eng-101', label: 'A-101' },
      { id: 'eng-102', label: 'Lab 102' }
    ];
  }, []);

  const filteredAllRooms = useMemo(() => {
    if (!roomSearchQuery.trim()) return allRooms;
    const q = roomSearchQuery.toLowerCase();
    return allRooms.filter(r => (r.name || r.id).toLowerCase().includes(q) || (r.building || '').toLowerCase().includes(q));
  }, [allRooms, roomSearchQuery]);

  // Derived display days: Mon-Sat, Sun only if present
  const displayDays = useMemo(() => {
    if (data?.has_sunday) return WEEKDAYS;
    return WEEKDAYS.slice(0, 6);
  }, [data]);

  return (
    <div
      className="p-6 md:p-8 max-w-[1600px] mx-auto min-h-screen"
      style={{
        '--hour-row-height': '40px'
      }}
    >
      {/* HEADER ROW */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              Optimizer and schedules
            </h1>
            {isDirty && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-[#0A66D6] dark:text-[#40A3FF] border border-blue-500/20 animate-in fade-in">
                Edited
              </span>
            )}
          </div>
          <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
            Recommended pre-cool start, shut-off and setpoint. Drag the ends of a blue bar, or focus a handle and use the arrow keys.
          </p>
        </div>

        {/* Room Switcher: Segmented Control + All Rooms Select */}
        <div className="flex items-center gap-2 self-start md:self-auto">
          <div
            className="flex items-center p-1 rounded-full border shadow-xs"
            style={{
              backgroundColor: 'var(--bg-well)',
              borderColor: 'var(--border-subtle)'
            }}
          >
            {relevantRooms.map((room) => {
              const isSelected = selectedRoomId === room.id;
              return (
                <button
                  key={room.id}
                  onClick={() => setSelectedRoomId(room.id)}
                  className={`px-4 py-1.5 text-xs font-semibold rounded-full transition-all duration-150 ${
                    isSelected
                      ? 'shadow-xs'
                      : 'hover:opacity-80'
                  }`}
                  style={{
                    backgroundColor: isSelected ? 'var(--bg-card)' : 'transparent',
                    color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)'
                  }}
                >
                  {room.label}
                </button>
              );
            })}
          </div>

          {/* All rooms dropdown */}
          <div className="relative">
            <button
              onClick={() => setAllRoomsDropdownOpen(!allRoomsDropdownOpen)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-secondary)'
              }}
            >
              <span>All rooms</span>
              <ChevronDown className="w-3.5 h-3.5" />
            </button>

            {allRoomsDropdownOpen && (
              <div
                className="absolute right-0 top-full mt-2 w-72 max-h-80 rounded-2xl shadow-xl border p-2 z-50 overflow-hidden flex flex-col"
                style={{
                  backgroundColor: 'var(--bg-card)',
                  borderColor: 'var(--border-subtle)'
                }}
              >
                <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl border mb-2" style={{ backgroundColor: 'var(--bg-well)', borderColor: 'var(--border-subtle)' }}>
                  <Search className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                  <input
                    type="text"
                    value={roomSearchQuery}
                    onChange={(e) => setRoomSearchQuery(e.target.value)}
                    placeholder="Search campus rooms..."
                    className="w-full text-xs bg-transparent outline-hidden"
                    style={{ color: 'var(--text-primary)' }}
                  />
                </div>

                <div className="overflow-y-auto max-h-56 divide-y divide-neutral-100 dark:divide-neutral-800">
                  {filteredAllRooms.map((r) => {
                    const isServer = (r.is_critical && (r.id.includes('server') || r.name.toLowerCase().includes('server')));
                    const isCurrent = selectedRoomId === r.id;

                    return (
                      <button
                        key={r.id}
                        disabled={isServer}
                        onClick={() => {
                          setSelectedRoomId(r.id);
                          setAllRoomsDropdownOpen(false);
                        }}
                        title={isServer ? "Protected: never switched off" : undefined}
                        className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between transition-colors ${
                          isServer ? 'opacity-50 cursor-not-allowed bg-neutral-50/50 dark:bg-neutral-900/50' : 'hover:bg-blue-500/10'
                        } ${isCurrent ? 'font-bold text-[#0A66D6]' : ''}`}
                      >
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span>{r.name || r.id}</span>
                            {isServer && <Lock className="w-3 h-3 text-amber-500 shrink-0" />}
                          </div>
                          <span className="text-[10px] text-neutral-400">{r.building}</span>
                        </div>
                        {isServer && (
                          <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">Protected</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ERROR STATE */}
      {error && (
        <div className="p-4 rounded-2xl border border-red-500/20 bg-red-500/10 text-red-600 dark:text-red-400 text-sm mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <XCircle className="w-5 h-5" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => fetchRecommendation(selectedRoomId, unitScope)}
            className="px-3 py-1 rounded-xl bg-red-600 text-white font-medium text-xs hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      )}

      {/* TWO-COLUMN GRID */}
      <div className="flex flex-col lg:flex-row items-start gap-6">
        {/* LEFT CARD: WEEKLY SCHEDULE */}
        <div
          className="flex-1 w-full min-w-0 lg:min-w-[640px] rounded-[24px] p-6 border shadow-xs transition-colors"
          style={{
            backgroundColor: 'var(--bg-card)',
            borderColor: 'var(--border-subtle)'
          }}
        >
          {/* Card Header & Dynamic Subtitle */}
          <div className="mb-4">
            <h2 className="text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              {data?.room_name || selectedRoomId}, weekly schedule
            </h2>
            <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
              {data?.subtitle || 'Loading weekly occupancy and units...'}
            </p>

            {/* Legend row */}
            <div className="flex flex-wrap items-center gap-5 mt-4 text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-3.5 rounded-[4px] border border-black/5 dark:border-white/5" style={{ backgroundColor: '#E4EAF5' }} />
                <span>Timetable</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-3.5 rounded-[4px] border-[1.5px] border-[#0A66D6] dark:border-[#40A3FF] bg-transparent" />
                <span>Recommended run</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="w-3.5 h-3.5 rounded-[4px] border border-neutral-300 dark:border-neutral-600"
                  style={{
                    backgroundImage: 'repeating-linear-gradient(45deg, #8E8E93, #8E8E93 2px, transparent 2px, transparent 6px)'
                  }}
                />
                <span>Current timer, {data?.recommendation_tile?.current_timer_label || '07:00–19:00'}</span>
              </div>
            </div>
          </div>

          {/* Schedule Grid Container with initial scroll */}
          <div
            ref={gridContainerRef}
            className="overflow-x-auto overflow-y-auto max-h-[580px] rounded-2xl border pt-3 pb-4 px-2"
            style={{
              borderColor: 'var(--border-subtle)',
              backgroundColor: 'var(--bg-page)'
            }}
          >
            <div className="min-w-[620px]">
              {/* Day Header Row */}
              <div className="grid grid-cols-[54px_repeat(6,1fr)] gap-2 mb-2 sticky top-0 z-20 pb-2 border-b" style={{ borderColor: 'var(--border-subtle)', backgroundColor: 'var(--bg-page)' }}>
                <div />
                {displayDays.map((d) => (
                  <div key={d.id} className="text-center font-semibold text-xs tracking-wide" style={{ color: 'var(--text-primary)' }}>
                    {d.short}
                  </div>
                ))}
              </div>

              {/* Grid Body: Time Axis + Day Columns */}
              <div className="grid grid-cols-[54px_repeat(6,1fr)] gap-2 relative">
                {/* Time Axis Labels */}
                <div
                  className="relative select-none"
                  style={{ height: `${HOURS_COUNT * 40}px` }}
                >
                  {Array.from({ length: HOURS_COUNT + 1 }).map((_, i) => {
                    const hour = START_HOUR + i;
                    const hourStr = `${hour.toString().padStart(2, '0')}:00`;
                    return (
                      <div
                        key={hour}
                        className="absolute w-full text-right pr-2 text-[11px] font-medium tabular-nums"
                        style={{
                          top: `${i * 40}px`,
                          transform: 'translateY(-50%)',
                          color: 'var(--text-muted)'
                        }}
                      >
                        {hourStr}
                      </div>
                    );
                  })}
                </div>

                {/* Day Columns */}
                {displayDays.map((day) => {
                  const dayTimetable = data?.timetable_by_day?.[day.id] || [];
                  const dayRuns = editedBars[day.id] || [];
                  const timer = data?.timer_by_day?.[day.id];

                  // Timer strip calculation
                  const timerStartMins = timer ? timeToMins(timer.start_time) : 7 * 60;
                  const timerEndMins = timer ? timeToMins(timer.end_time) : 19 * 60;
                  const timerTopPx = Math.max(0, (timerStartMins - START_HOUR * 60) * (40 / 60));
                  const timerHeightPx = Math.max(0, (timerEndMins - timerStartMins) * (40 / 60));

                  return (
                    <div
                      key={day.id}
                      className="relative rounded-2xl overflow-hidden transition-colors"
                      style={{
                        height: `${HOURS_COUNT * 40}px`,
                        backgroundColor: '#EDEDF1'
                      }}
                    >
                      {/* Hour divider lines */}
                      {Array.from({ length: HOURS_COUNT }).map((_, i) => (
                        <div
                          key={i}
                          className="absolute w-full border-b border-black/[0.04] dark:border-white/[0.04] pointer-events-none"
                          style={{ top: `${i * 40}px` }}
                        />
                      ))}

                      {/* Hatched Current Timer Strip on the Left Edge */}
                      {timerHeightPx > 0 && (
                        <div
                          className="absolute left-0 z-10 w-2.5 rounded-l-md pointer-events-none"
                          title={`Current timer: ${timer.start_time}–${timer.end_time}`}
                          style={{
                            top: `${timerTopPx}px`,
                            height: `${timerHeightPx}px`,
                            backgroundImage: 'repeating-linear-gradient(45deg, #8E8E93, #8E8E93 2px, transparent 2px, transparent 6px)',
                            opacity: 0.8
                          }}
                        />
                      )}

                      {/* Timetable Blocks */}
                      {dayTimetable.map((sess, idx) => {
                        const sStart = timeToMins(sess.start_time);
                        const sEnd = timeToMins(sess.end_time);
                        const topPx = (sStart - START_HOUR * 60) * (40 / 60);
                        const heightPx = (sEnd - sStart) * (40 / 60);

                        return (
                          <div
                            key={idx}
                            className="absolute left-3 right-1.5 rounded-xl p-2.5 border border-black/5 dark:border-white/5 pointer-events-none transition-all shadow-2xs"
                            style={{
                              top: `${topPx}px`,
                              height: `${heightPx}px`,
                              backgroundColor: '#E4EAF5',
                              color: '#1D1D1F'
                            }}
                          >
                            <div className="font-semibold text-xs leading-tight line-clamp-1">
                              {sess.title}
                            </div>
                            <div className="text-[11px] font-medium opacity-75 mt-0.5 tabular-nums">
                              {sess.start_time}–{sess.end_time}
                            </div>
                          </div>
                        );
                      })}

                      {/* Recommended Run Bars */}
                      {dayRuns.map((run, rIdx) => {
                        const rStart = timeToMins(run.start_time);
                        const rEnd = timeToMins(run.end_time);
                        const topPx = (rStart - START_HOUR * 60) * (40 / 60);
                        const heightPx = (rEnd - rStart) * (40 / 60);
                        const isShort = heightPx < 56;

                        return (
                          <div
                            key={rIdx}
                            className="absolute left-2 right-1 rounded-2xl group transition-all"
                            style={{
                              top: `${topPx}px`,
                              height: `${heightPx}px`,
                              border: '1.5px solid #0A66D6',
                              backgroundColor: 'rgba(10, 102, 214, 0.04)'
                            }}
                          >
                            {/* Kept-on Gaps for merged sessions (e.g. Tue/Thu) */}
                            {run.kept_on_gaps?.map((gap, gIdx) => {
                              const gStart = timeToMins(gap.start_time);
                              const gEnd = timeToMins(gap.end_time);
                              const gapTop = (gStart - rStart) * (40 / 60);
                              const gapHeight = (gEnd - gStart) * (40 / 60);
                              return (
                                <div
                                  key={gIdx}
                                  className="absolute left-0 right-0 rounded-lg pointer-events-none"
                                  title="Compressor protection: AC kept ON between sessions"
                                  style={{
                                    top: `${gapTop}px`,
                                    height: `${gapHeight}px`,
                                    backgroundColor: 'rgba(10, 102, 214, 0.12)',
                                    borderTop: '1px dashed rgba(10, 102, 214, 0.3)',
                                    borderBottom: '1px dashed rgba(10, 102, 214, 0.3)'
                                  }}
                                />
                              );
                            })}

                            {/* Top Drag Handle (Pill: 28x6px, solid blue) */}
                            <div
                              role="slider"
                              tabIndex={0}
                              aria-label="Pre-cool start handle"
                              aria-valuetext={`Start ${run.start_time}`}
                              onPointerDown={(e) => handlePointerDown(e, day.id, rIdx, 'top')}
                              onKeyDown={(e) => handleKeyDown(e, day.id, rIdx, 'top')}
                              className="absolute left-1/2 -translate-x-1/2 -top-[4px] w-7 h-2 rounded-full cursor-ns-resize z-30 transition-transform hover:scale-110 active:scale-95 focus:ring-2 focus:ring-blue-400"
                              style={{ backgroundColor: '#0A66D6' }}
                            />

                            {/* Bottom Drag Handle (Pill: 28x6px, solid blue) */}
                            <div
                              role="slider"
                              tabIndex={0}
                              aria-label="Shut-off handle"
                              aria-valuetext={`Shut-off ${run.end_time}`}
                              onPointerDown={(e) => handlePointerDown(e, day.id, rIdx, 'bottom')}
                              onKeyDown={(e) => handleKeyDown(e, day.id, rIdx, 'bottom')}
                              className="absolute left-1/2 -translate-x-1/2 -bottom-[4px] w-7 h-2 rounded-full cursor-ns-resize z-30 transition-transform hover:scale-110 active:scale-95 focus:ring-2 focus:ring-blue-400"
                              style={{ backgroundColor: '#0A66D6' }}
                            />

                            {/* White Chip with Time Range ("08:40–13:10") */}
                            <div
                              className={`absolute left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-md text-[11px] font-bold shadow-xs whitespace-nowrap z-20 pointer-events-none select-none ${
                                isShort ? 'top-full mt-1.5' : 'top-1/2 -translate-y-1/2'
                              }`}
                              style={{
                                backgroundColor: '#FFFFFF',
                                color: '#0A66D6',
                                border: '1px solid rgba(10, 102, 214, 0.15)'
                              }}
                            >
                              {run.start_time}–{run.end_time}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: RECOMMENDATION & ASSUMPTIONS */}
        <div className="w-full lg:w-[360px] flex flex-col gap-5 shrink-0">
          {/* Unit Scope Selector (only if room has > 1 unit) */}
          {(data?.units?.length > 1) && (
            <div
              className="p-1 rounded-2xl border flex items-center shadow-2xs"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-subtle)'
              }}
            >
              {[
                { id: 'both', label: 'Both units' },
                { id: 'unit_1', label: data.units[0]?.name || 'Unit 1' },
                { id: 'unit_2', label: data.units[1]?.name || 'Unit 2' }
              ].map((scope) => {
                const isSelected = unitScope === scope.id;
                return (
                  <button
                    key={scope.id}
                    onClick={() => setUnitScope(scope.id)}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                      isSelected
                        ? 'shadow-xs'
                        : 'opacity-70 hover:opacity-100'
                    }`}
                    style={{
                      backgroundColor: isSelected ? 'var(--bg-well)' : 'transparent',
                      color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)'
                    }}
                  >
                    {scope.label}
                  </button>
                );
              })}
            </div>
          )}

          {/* RECOMMENDATION CARD */}
          <div
            className="rounded-[24px] p-6 border shadow-xs"
            style={{
              backgroundColor: 'var(--bg-card)',
              borderColor: 'var(--border-subtle)'
            }}
          >
            <h3 className="text-lg font-bold tracking-tight mb-4" style={{ color: 'var(--text-primary)' }}>
              Recommendation
            </h3>

            {/* Pre-cool start and Shut-off tiles side by side */}
            <div className="grid grid-cols-2 gap-3 mb-3">
              {/* Pre-cool Tile */}
              <div
                className="p-4 rounded-2xl flex flex-col justify-between"
                style={{ backgroundColor: 'var(--bg-well)' }}
              >
                <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                  Pre-cool start
                </span>
                <span className="text-2xl font-bold tracking-tight my-1 tabular-nums" style={{ color: 'var(--text-primary)' }}>
                  {data?.recommendation_tile?.precool_start || '08:40'}
                </span>
                <span className="text-[11px] leading-tight" style={{ color: 'var(--text-secondary)' }}>
                  {data?.recommendation_tile?.precool_subtext || 'Mon to Fri, 20 min before class'}
                </span>
              </div>

              {/* Shut-off Tile */}
              <div
                className="p-4 rounded-2xl flex flex-col justify-between"
                style={{ backgroundColor: 'var(--bg-well)' }}
              >
                <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                  Shut-off
                </span>
                <span className="text-2xl font-bold tracking-tight my-1 tabular-nums" style={{ color: 'var(--text-primary)' }}>
                  {data?.recommendation_tile?.shutoff || '13:10'}
                </span>
                <span className="text-[11px] leading-tight" style={{ color: 'var(--text-secondary)' }}>
                  {data?.recommendation_tile?.shutoff_subtext || 'Tue, Thu 16:10, Sat 11:10'}
                </span>
              </div>
            </div>

            {/* Setpoint Stepper Tile */}
            <div
              className="p-4 rounded-2xl mb-4"
              style={{ backgroundColor: 'var(--bg-well)' }}
            >
              <div className="text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>
                Setpoint
              </div>
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold tracking-tight tabular-nums" style={{ color: 'var(--text-primary)' }}>
                  {setpoint.toFixed(1)} °C
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => handleSetpointChange(-0.5)}
                    disabled={setpoint <= (data?.min_temp_c ?? 22.0)}
                    className="w-8 h-8 rounded-xl flex items-center justify-center font-bold border transition-colors hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed"
                    style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
                  >
                    <Minus className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleSetpointChange(0.5)}
                    disabled={setpoint >= (data?.max_temp_c ?? 26.0)}
                    className="w-8 h-8 rounded-xl flex items-center justify-center font-bold border transition-colors hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed"
                    style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Divider */}
            <hr className="my-4" style={{ borderColor: 'var(--border-subtle)' }} />

            {/* Estimated saving per month */}
            <div className="mb-5">
              <div className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                Estimated saving per month
              </div>
              <div
                className={`text-3xl font-extrabold tracking-tight mt-1 tabular-nums transition-opacity ${
                  isRecalculating ? 'opacity-50 animate-pulse' : 'opacity-100'
                }`}
                style={{ color: 'var(--text-primary)' }}
              >
                {savingsData?.cost_saved_month?.formatted_range || '₹6.9k – ₹8.3k'}
              </div>
              <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                Against the current {data?.recommendation_tile?.current_timer_label || '07:00–19:00'} timer
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col gap-2.5">
              <button
                onClick={() => setApplyModalOpen(true)}
                disabled={validationData?.status === 'blocked'}
                className="w-full h-11 rounded-xl font-semibold text-white transition-all shadow-xs flex items-center justify-center gap-2 hover:opacity-95 active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ backgroundColor: '#0A66D6' }}
              >
                <span>Apply as proposal</span>
              </button>

              <button
                onClick={handleResetToRecommended}
                disabled={!isDirty}
                className="w-full h-11 rounded-xl font-semibold transition-all border flex items-center justify-center gap-2 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed"
                style={{
                  backgroundColor: 'var(--bg-well)',
                  borderColor: 'var(--border-subtle)',
                  color: 'var(--text-primary)'
                }}
              >
                <RotateCcw className="w-4 h-4" />
                <span>Reset to recommended</span>
              </button>
            </div>

            {/* Validation warning if blocked or warning */}
            {validationData?.status === 'blocked' && (
              <div className="mt-3 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs">
                {validationData.issues?.[0]?.message || 'Configuration blocked by safety constraints.'}
              </div>
            )}
            {validationData?.status === 'warning' && (
              <div className="mt-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{validationData.issues?.[0]?.message}</span>
              </div>
            )}

            {/* Helper Text */}
            <p className="text-xs text-center leading-relaxed mt-4" style={{ color: 'var(--text-muted)' }}>
              A proposal still goes through the rule engine and needs a human approval before any command is sent.
            </p>
          </div>

          {/* ASSUMPTIONS ACCORDION CARD */}
          <div
            className="rounded-[24px] p-5 border shadow-xs transition-colors"
            style={{
              backgroundColor: 'var(--bg-card)',
              borderColor: 'var(--border-subtle)'
            }}
          >
            <button
              onClick={() => setAssumptionsOpen(!assumptionsOpen)}
              className="w-full flex items-center justify-between text-left font-semibold text-sm transition-colors"
              style={{ color: 'var(--text-primary)' }}
            >
              <span>Assumptions</span>
              <ChevronRight
                className={`w-4 h-4 transition-transform duration-200 ${
                  assumptionsOpen ? 'rotate-90' : ''
                }`}
                style={{ color: 'var(--text-secondary)' }}
              />
            </button>

            {assumptionsOpen && (
              <div className="mt-4 pt-3 border-t text-xs space-y-3" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="flex justify-between py-1 border-b border-black/[0.04] dark:border-white/[0.04]">
                  <span style={{ color: 'var(--text-secondary)' }}>Tariff</span>
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    ₹{data?.assumptions?.tariff?.toFixed(2)}/kWh
                  </span>
                </div>

                <div className="flex justify-between py-1 border-b border-black/[0.04] dark:border-white/[0.04]">
                  <span style={{ color: 'var(--text-secondary)' }}>1R1C Thermal Model</span>
                  <span className="font-semibold text-right" style={{ color: 'var(--text-primary)' }}>
                    τ = {data?.assumptions?.tau_minutes} min (R={data?.assumptions?.R}, C={data?.assumptions?.C})
                  </span>
                </div>

                <div className="flex justify-between py-1 border-b border-black/[0.04] dark:border-white/[0.04]">
                  <span style={{ color: 'var(--text-secondary)' }}>Baseline Load</span>
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {data?.assumptions?.baseline_p_on_kw} kW [{data?.assumptions?.band_low_kw}–{data?.assumptions?.band_high_kw} kW]
                  </span>
                </div>

                <div className="flex justify-between py-1 border-b border-black/[0.04] dark:border-white/[0.04]">
                  <span style={{ color: 'var(--text-secondary)' }}>Safety Margins</span>
                  <span className="font-semibold text-right" style={{ color: 'var(--text-primary)' }}>
                    Pre-cool [{data?.assumptions?.min_lead_min}, {data?.assumptions?.max_lead_min}]m, Shutoff +{data?.assumptions?.shutoff_grace_min}m
                  </span>
                </div>

                <div className="flex justify-between py-1 border-b border-black/[0.04] dark:border-white/[0.04]">
                  <span style={{ color: 'var(--text-secondary)' }}>Compressor Gap</span>
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Min {data?.assumptions?.min_off_gap_min} min (merges sub-90m gaps)
                  </span>
                </div>

                <div className="flex justify-between py-1 border-b border-black/[0.04] dark:border-white/[0.04]">
                  <span style={{ color: 'var(--text-secondary)' }}>Setpoint Elasticity</span>
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {data?.assumptions?.elasticity_pct_per_deg}% per 1.0 °C
                  </span>
                </div>

                <div className="flex justify-between py-1 border-b border-black/[0.04] dark:border-white/[0.04]">
                  <span style={{ color: 'var(--text-secondary)' }}>Weeks per Month</span>
                  <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {data?.assumptions?.weeks_per_month}
                  </span>
                </div>

                <p className="text-[11px] italic text-right mt-2" style={{ color: 'var(--text-muted)' }}>
                  {data?.assumptions?.note || 'Estimate, synthetic data'}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* CONFIRM APPLY AS PROPOSAL MODAL */}
      {applyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in">
          <div
            className="w-full max-w-xl rounded-[24px] p-6 border shadow-2xl animate-in zoom-in-95"
            style={{
              backgroundColor: 'var(--bg-card)',
              borderColor: 'var(--border-subtle)'
            }}
          >
            <h3 className="text-xl font-bold tracking-tight mb-2" style={{ color: 'var(--text-primary)' }}>
              Confirm Schedule Proposal
            </h3>
            <p className="text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
              Submitting this proposal will validate through the safety rule engine, record an immutable audit log, and register with the Approvals Inbox for human sign-off.
            </p>

            {/* Diff Table */}
            <div className="rounded-xl border overflow-hidden mb-4" style={{ borderColor: 'var(--border-subtle)' }}>
              <table className="w-full text-xs text-left">
                <thead style={{ backgroundColor: 'var(--bg-well)' }}>
                  <tr>
                    <th className="py-2.5 px-3 font-semibold" style={{ color: 'var(--text-primary)' }}>Day</th>
                    <th className="py-2.5 px-3 font-semibold" style={{ color: 'var(--text-secondary)' }}>Current Timer</th>
                    <th className="py-2.5 px-3 font-semibold" style={{ color: 'var(--text-secondary)' }}>Proposed Run</th>
                    <th className="py-2.5 px-3 font-semibold text-right" style={{ color: 'var(--text-primary)' }}>Saved</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-black/[0.04] dark:divide-white/[0.04]">
                  {displayDays.map((d) => {
                    const timer = data?.timer_by_day?.[d.id];
                    const runs = editedBars[d.id] || [];
                    const timerStr = timer && timer.duration_hours > 0 ? `${timer.start_time}–${timer.end_time} (${timer.duration_hours}h)` : 'Off';
                    const runStr = runs.length > 0 ? runs.map(r => `${r.start_time}–${r.end_time}`).join(', ') : 'Off';
                    const savedHrs = savingsData?.saved_hours_by_day?.[d.id] ?? 0;

                    return (
                      <tr key={d.id}>
                        <td className="py-2 px-3 font-semibold" style={{ color: 'var(--text-primary)' }}>{d.name}</td>
                        <td className="py-2 px-3" style={{ color: 'var(--text-secondary)' }}>{timerStr}</td>
                        <td className="py-2 px-3 font-medium text-[#0A66D6]">{runStr}</td>
                        <td className="py-2 px-3 text-right font-bold" style={{ color: 'var(--text-primary)' }}>{savedHrs.toFixed(1)} hrs</td>
                      </tr>
                    );
                  })}
                  <tr style={{ backgroundColor: 'var(--bg-well)' }}>
                    <td colSpan={3} className="py-2 px-3 font-bold" style={{ color: 'var(--text-primary)' }}>Total Weekly Saved Hours</td>
                    <td className="py-2 px-3 text-right font-extrabold text-[#0A66D6]">{savingsData?.saved_hours_week} hrs/wk</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Savings & Setpoint summary */}
            <div className="grid grid-cols-2 gap-3 p-3 rounded-xl mb-4" style={{ backgroundColor: 'var(--bg-well)' }}>
              <div>
                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>Target Setpoint</span>
                <div className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{setpoint.toFixed(1)} °C</div>
              </div>
              <div>
                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>Monthly Savings Range</span>
                <div className="text-base font-bold text-[#0A66D6]">{savingsData?.cost_saved_month?.formatted_range}</div>
              </div>
            </div>

            {/* Modal Buttons */}
            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => setApplyModalOpen(false)}
                className="px-4 py-2.5 rounded-xl text-xs font-semibold border transition-colors hover:bg-black/5 dark:hover:bg-white/5"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmProposal}
                className="px-5 py-2.5 rounded-xl text-xs font-semibold text-white transition-opacity hover:opacity-95"
                style={{ backgroundColor: '#0A66D6' }}
              >
                Submit Proposal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Success Toast */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom duration-200">
          <div
            className="flex items-start gap-3 p-4 rounded-2xl shadow-2xl border text-xs font-medium max-w-sm"
            style={{
              backgroundColor: 'var(--bg-card)',
              borderColor: 'var(--border-subtle)',
              color: 'var(--text-primary)'
            }}
          >
            <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-bold text-sm mb-0.5">{toastMessage.title}</div>
              <p className="text-neutral-500">{toastMessage.message}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

